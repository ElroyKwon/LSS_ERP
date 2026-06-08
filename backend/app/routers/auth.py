from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from ..models.common import User, UserRegistration
from ..utils.auth import verify_password, create_access_token, get_current_user, hash_password
from ..utils import to_kst
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["인증"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username, User.is_active == True).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    user.last_login = datetime.utcnow()
    db.commit()

    token = create_access_token({"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "role": user.role,
            "email": user.email,
        },
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "name": current_user.name,
        "role": current_user.role,
        "email": current_user.email,
        "position": current_user.position,
    }


@router.post("/change-password")
def change_password(req: PasswordChangeRequest, current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")
    current_user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"message": "비밀번호가 변경되었습니다."}


# ── 회원가입 신청 ──────────────────────────────────────────
class RegistrationCreate(BaseModel):
    username: str
    password: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    reason: Optional[str] = None


class RejectRequest(BaseModel):
    rejection_reason: Optional[str] = None


def _reg_dict(r):
    return {
        "id": r.id,
        "username": r.username,
        "name": r.name,
        "email": r.email,
        "phone": r.phone,
        "department": r.department,
        "position": r.position,
        "reason": r.reason,
        "status": r.status,
        "rejection_reason": r.rejection_reason,
        "reviewed_by": r.reviewed_by,
        "reviewed_at": to_kst(r.reviewed_at),
        "created_at":  to_kst(r.created_at),
    }


@router.post("/register")
def register(data: RegistrationCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="이미 사용 중인 아이디입니다.")
    if db.query(UserRegistration).filter(
        UserRegistration.username == data.username,
        UserRegistration.status == "pending"
    ).first():
        raise HTTPException(status_code=400, detail="이미 가입 신청이 접수된 아이디입니다.")
    reg = UserRegistration(
        username=data.username,
        password_hash=hash_password(data.password),
        name=data.name,
        email=data.email,
        phone=data.phone,
        department=data.department,
        position=data.position,
        reason=data.reason,
    )
    db.add(reg)
    db.commit()
    return {"message": "가입 신청이 완료되었습니다. 관리자 승인 후 로그인이 가능합니다."}


@router.get("/check-username/{username}")
def check_username(username: str, db: Session = Depends(get_db)):
    in_use = (
        db.query(User).filter(User.username == username).first() is not None or
        db.query(UserRegistration).filter(
            UserRegistration.username == username,
            UserRegistration.status == "pending"
        ).first() is not None
    )
    return {"available": not in_use}


@router.get("/registrations/pending-count")
def pending_count(db: Session = Depends(get_db), current=Depends(get_current_user)):
    if current.role != "admin":
        return {"count": 0}
    count = db.query(UserRegistration).filter(UserRegistration.status == "pending").count()
    return {"count": count}


@router.get("/registrations")
def list_registrations(status: Optional[str] = None, db: Session = Depends(get_db),
                       current=Depends(get_current_user)):
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    q = db.query(UserRegistration)
    if status:
        q = q.filter(UserRegistration.status == status)
    return [_reg_dict(r) for r in q.order_by(UserRegistration.created_at.desc()).all()]


@router.patch("/registrations/{rid}/approve")
def approve_registration(rid: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    reg = db.query(UserRegistration).filter(UserRegistration.id == rid).first()
    if not reg:
        raise HTTPException(status_code=404, detail="신청을 찾을 수 없습니다.")
    if reg.status != "pending":
        raise HTTPException(status_code=400, detail="이미 처리된 신청입니다.")
    if db.query(User).filter(User.username == reg.username).first():
        raise HTTPException(status_code=400, detail="이미 동일한 아이디의 사용자가 존재합니다.")
    user = User(
        username=reg.username,
        password_hash=reg.password_hash,
        name=reg.name,
        email=reg.email,
        phone=reg.phone,
        position=reg.position,
        role="user",
        is_active=True,
    )
    db.add(user)
    reg.status = "approved"
    reg.reviewed_by = current.id
    reg.reviewed_at = datetime.utcnow()
    db.commit()
    return {"message": f"{reg.name} 님의 가입이 승인되었습니다."}


@router.delete("/registrations/{rid}")
def delete_registration(rid: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    reg = db.query(UserRegistration).filter(UserRegistration.id == rid).first()
    if not reg:
        raise HTTPException(status_code=404, detail="신청을 찾을 수 없습니다.")
    db.delete(reg)
    db.commit()
    return {"message": "삭제되었습니다."}


@router.patch("/registrations/{rid}/reject")
def reject_registration(rid: int, data: RejectRequest, db: Session = Depends(get_db),
                        current=Depends(get_current_user)):
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    reg = db.query(UserRegistration).filter(UserRegistration.id == rid).first()
    if not reg:
        raise HTTPException(status_code=404, detail="신청을 찾을 수 없습니다.")
    if reg.status != "pending":
        raise HTTPException(status_code=400, detail="이미 처리된 신청입니다.")
    reg.status = "rejected"
    reg.rejection_reason = data.rejection_reason
    reg.reviewed_by = current.id
    reg.reviewed_at = datetime.utcnow()
    db.commit()
    return {"message": "거절 처리되었습니다."}
