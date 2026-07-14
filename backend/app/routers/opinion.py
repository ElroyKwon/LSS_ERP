from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.common import OpinionAttachment, OpinionNotificationSetting, OpinionPost, User
from ..services.email_service import EmailNotConfiguredError, send_email
from ..utils import to_kst
from ..utils.auth import get_current_user
from ..utils.permissions import is_system_admin, normalize_role

router = APIRouter(prefix="/api", tags=["의견 청취"])

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "opinions"


class OpinionCreate(BaseModel):
    title: str
    content: str


class OpinionAnswer(BaseModel):
    answer: str


class OpinionNotificationSettingIn(BaseModel):
    notify_on_new_post: Optional[bool] = None
    notify_on_registration: Optional[bool] = None


def _attachment_dict(row: OpinionAttachment) -> dict:
    return {
        "id": row.id,
        "opinion_id": row.opinion_id,
        "original_name": row.original_name,
        "content_type": row.content_type,
        "file_size": row.file_size,
        "created_by": row.created_by,
        "creator_name": row.creator.name if row.creator else None,
        "created_at": to_kst(row.created_at),
    }


def _opinion_dict(row: OpinionPost) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "content": row.content,
        "answer": row.answer,
        "answered_by": row.answered_by,
        "answerer_name": row.answerer.name if row.answerer else None,
        "answered_at": to_kst(row.answered_at),
        "created_by": row.created_by,
        "creator_name": row.creator.name if row.creator else None,
        "creator_email": row.creator.email if row.creator else None,
        "created_at": to_kst(row.created_at),
        "updated_at": to_kst(row.updated_at),
        "status": "answered" if row.answer else "waiting",
        "attachments": [_attachment_dict(item) for item in row.attachments],
    }


def _admin_notification_recipients(db: Session) -> list[str]:
    try:
        admins = db.query(User).filter(
            User.is_active == True,
            User.email.isnot(None),
        ).all()
        settings_by_user = {
            item.user_id: item.notify_on_new_post
            for item in db.query(OpinionNotificationSetting).all()
        }
    except SQLAlchemyError:
        db.rollback()
        return []
    recipients = []
    for user in admins:
        if not is_system_admin(user.role):
            continue
        if settings_by_user.get(user.id, True):
            recipients.append(user.email)
    return recipients


def _send_mail_safely(recipients: list[str], subject: str, body: str) -> bool:
    try:
        return send_email(recipients, subject, body)
    except EmailNotConfiguredError:
        return False
    except Exception:
        return False


def _require_admin(current: User) -> None:
    if not is_system_admin(current.role):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")


def _require_owner(row: OpinionPost, current: User) -> None:
    if row.created_by != current.id:
        raise HTTPException(status_code=403, detail="등록한 사용자만 수정할 수 있습니다.")


def _require_owner_or_admin(row: OpinionPost, current: User) -> None:
    if row.created_by != current.id and not is_system_admin(current.role):
        raise HTTPException(status_code=403, detail="등록한 사용자 또는 관리자만 삭제할 수 있습니다.")


@router.get("/opinions")
def list_opinions(
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(OpinionPost)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(OpinionPost.title.ilike(like), OpinionPost.content.ilike(like)))
    if status == "waiting":
        q = q.filter(OpinionPost.answer.is_(None))
    elif status == "answered":
        q = q.filter(OpinionPost.answer.isnot(None))
    rows = q.order_by(OpinionPost.created_at.desc(), OpinionPost.id.desc()).all()
    return [_opinion_dict(row) for row in rows]


@router.get("/opinions/{opinion_id}")
def get_opinion(opinion_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.query(OpinionPost).filter(OpinionPost.id == opinion_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="의견 청취 글을 찾을 수 없습니다.")
    return _opinion_dict(row)


@router.post("/opinions")
def create_opinion(data: OpinionCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    if not data.title.strip():
        raise HTTPException(status_code=422, detail="제목을 입력하세요.")
    if not data.content.strip():
        raise HTTPException(status_code=422, detail="내용을 입력하세요.")
    row = OpinionPost(title=data.title.strip(), content=data.content.strip(), created_by=current.id)
    db.add(row)
    db.commit()
    db.refresh(row)

    recipients = _admin_notification_recipients(db)
    _send_mail_safely(
        recipients,
        "[LSS ERP] 의견 청취 글이 등록되었습니다.",
        f"등록자: {current.name}\n제목: {row.title}\n등록일: {to_kst(row.created_at)}\n\n{row.content}",
    )
    return _opinion_dict(row)


@router.put("/opinions/{opinion_id}")
def update_opinion(
    opinion_id: int,
    data: OpinionCreate,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    row = db.query(OpinionPost).filter(OpinionPost.id == opinion_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="의견 청취 글을 찾을 수 없습니다.")
    _require_owner(row, current)
    if not data.title.strip():
        raise HTTPException(status_code=422, detail="제목을 입력하세요.")
    if not data.content.strip():
        raise HTTPException(status_code=422, detail="내용을 입력하세요.")
    row.title = data.title.strip()
    row.content = data.content.strip()
    db.commit()
    db.refresh(row)
    return _opinion_dict(row)


@router.delete("/opinions/{opinion_id}")
def delete_opinion(opinion_id: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    row = db.query(OpinionPost).filter(OpinionPost.id == opinion_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="의견 청취 글을 찾을 수 없습니다.")
    _require_owner_or_admin(row, current)
    file_paths = [attachment.file_path for attachment in row.attachments]
    db.delete(row)
    db.commit()
    for file_path in file_paths:
        if file_path and os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
    return {"ok": True}


@router.put("/opinions/{opinion_id}/answer")
def answer_opinion(
    opinion_id: int,
    data: OpinionAnswer,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    _require_admin(current)
    row = db.query(OpinionPost).filter(OpinionPost.id == opinion_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="의견 청취 글을 찾을 수 없습니다.")
    if not data.answer.strip():
        raise HTTPException(status_code=422, detail="답변을 입력하세요.")
    row.answer = data.answer.strip()
    row.answered_by = current.id
    row.answered_at = datetime.now()
    db.commit()
    db.refresh(row)

    if row.creator and row.creator.email:
        _send_mail_safely(
            [row.creator.email],
            "[LSS ERP] 의견 청취 답변이 등록되었습니다.",
            f"제목: {row.title}\n답변자: {current.name}\n답변일: {to_kst(row.answered_at)}\n\n{row.answer}",
        )
    return _opinion_dict(row)


@router.delete("/opinions/{opinion_id}/answer")
def delete_opinion_answer(
    opinion_id: int,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    _require_admin(current)
    row = db.query(OpinionPost).filter(OpinionPost.id == opinion_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="의견 청취 글을 찾을 수 없습니다.")
    row.answer = None
    row.answered_by = None
    row.answered_at = None
    db.commit()
    db.refresh(row)
    return _opinion_dict(row)


@router.post("/opinions/{opinion_id}/attachments")
def upload_opinion_attachment(
    opinion_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    row = db.query(OpinionPost).filter(OpinionPost.id == opinion_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="의견 청취 글을 찾을 수 없습니다.")
    _require_owner(row, current)
    original_name = os.path.basename(file.filename or "attachment")
    ext = os.path.splitext(original_name)[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    directory = UPLOAD_ROOT / str(opinion_id)
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / stored_name
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size = file_path.stat().st_size
    finally:
        file.file.close()
    attachment = OpinionAttachment(
        opinion_id=opinion_id,
        original_name=original_name,
        stored_name=stored_name,
        content_type=file.content_type,
        file_size=file_size,
        file_path=str(file_path),
        created_by=current.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return _attachment_dict(attachment)


@router.get("/opinion-attachments/{attachment_id}/download")
def download_opinion_attachment(attachment_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.query(OpinionAttachment).filter(OpinionAttachment.id == attachment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="첨부파일을 찾을 수 없습니다.")
    if not os.path.isfile(row.file_path):
        raise HTTPException(status_code=404, detail="파일이 서버에 존재하지 않습니다.")
    return FileResponse(
        row.file_path,
        media_type=row.content_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.original_name, safe='')}"},
    )


@router.delete("/opinion-attachments/{attachment_id}")
def delete_opinion_attachment(attachment_id: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    row = db.query(OpinionAttachment).filter(OpinionAttachment.id == attachment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="첨부파일을 찾을 수 없습니다.")
    opinion = db.query(OpinionPost).filter(OpinionPost.id == row.opinion_id).first()
    if not opinion:
        raise HTTPException(status_code=404, detail="의견 청취 글을 찾을 수 없습니다.")
    _require_owner_or_admin(opinion, current)
    file_path = row.file_path
    db.delete(row)
    db.commit()
    if file_path and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass
    return {"ok": True}


@router.get("/opinion-notification-settings")
def list_opinion_notification_settings(db: Session = Depends(get_db), current=Depends(get_current_user)):
    _require_admin(current)
    settings_by_user = {
        item.user_id: item
        for item in db.query(OpinionNotificationSetting).all()
    }
    admins = db.query(User).filter(User.is_active == True).order_by(User.name.asc(), User.id.asc()).all()
    return [
        {
            "user_id": user.id,
            "username": user.username,
            "name": user.name,
            "email": user.email,
            "role": normalize_role(user.role),
            "notify_on_new_post": settings_by_user.get(user.id).notify_on_new_post
            if user.id in settings_by_user
            else True,
            "notify_on_registration": settings_by_user.get(user.id).notify_on_registration
            if user.id in settings_by_user
            else True,
        }
        for user in admins
        if is_system_admin(user.role)
    ]


@router.put("/opinion-notification-settings/{user_id}")
def update_opinion_notification_setting(
    user_id: int,
    data: OpinionNotificationSettingIn,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    _require_admin(current)
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user or not is_system_admin(user.role):
        raise HTTPException(status_code=404, detail="관리자 사용자를 찾을 수 없습니다.")
    row = db.query(OpinionNotificationSetting).filter(
        OpinionNotificationSetting.user_id == user_id
    ).first()
    if not row:
        row = OpinionNotificationSetting(user_id=user_id)
        db.add(row)
    if data.notify_on_new_post is not None:
        row.notify_on_new_post = data.notify_on_new_post
    if data.notify_on_registration is not None:
        row.notify_on_registration = data.notify_on_registration
    db.commit()
    return {"ok": True}
