from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func as sqlfunc
from typing import Optional, List
from decimal import Decimal
from datetime import date
import json
import os
import shutil
import uuid
from ..database import get_db
from ..models.sales import Estimate, EstimateItem, EstimateAttachment, DesignRequest, SalesManagementWeeklyRow
from ..utils.auth import get_current_user
from ..utils import to_kst, to_kst_date
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["영업·수주"])
UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "estimates")


# ── 견적 ──────────────────────────────────────────
class SalesManagementBulk(BaseModel):
    week_start: date
    rows: List[dict] = Field(default_factory=list)


def _sales_management_row_key(row: dict) -> str:
    if row.get("sales_no"):
        return str(row.get("sales_no"))
    if row.get("id"):
        return str(row.get("id"))
    if row.get("project_name"):
        return f"name:{row.get('project_name')}"
    return f"manual:{len(json.dumps(row, ensure_ascii=False, sort_keys=True))}"


def _sales_management_dict(row: SalesManagementWeeklyRow) -> dict:
    try:
        data = json.loads(row.data_json or "{}")
        if not isinstance(data, dict):
            data = {}
    except (TypeError, ValueError):
        data = {}
    data["db_id"] = row.id
    data["id"] = data.get("id") or row.row_key
    data["week_start"] = to_kst_date(row.week_start)
    return data


def _next_sales_management_no(db: Session, year: int, reserved: set[str]) -> str:
    prefix = f"B{year % 100:02d}"
    max_seq = 0
    rows = db.query(SalesManagementWeeklyRow.data_json).all()
    for (data_json,) in rows:
        try:
            data = json.loads(data_json or "{}")
        except (TypeError, ValueError):
            continue
        sales_no = str(data.get("sales_no") or "")
        if not sales_no.startswith(prefix):
            continue
        suffix = sales_no[len(prefix):]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))

    next_seq = max_seq + 1
    while True:
        candidate = f"{prefix}{next_seq:03d}"
        if candidate not in reserved:
            reserved.add(candidate)
            return candidate
        next_seq += 1


@router.get("/sales-management")
def list_sales_management_rows(
    week_start: date,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    rows = db.query(SalesManagementWeeklyRow).filter(
        SalesManagementWeeklyRow.week_start == week_start
    ).order_by(SalesManagementWeeklyRow.id.asc()).all()
    return [_sales_management_dict(row) for row in rows]


@router.get("/sales-management/latest-before")
def latest_sales_management_rows_before(
    week_start: date,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    latest_week = db.query(sqlfunc.max(SalesManagementWeeklyRow.week_start)).filter(
        SalesManagementWeeklyRow.week_start < week_start
    ).scalar()
    if not latest_week:
        return {"week_start": None, "rows": []}
    rows = db.query(SalesManagementWeeklyRow).filter(
        SalesManagementWeeklyRow.week_start == latest_week
    ).order_by(SalesManagementWeeklyRow.id.asc()).all()
    return {"week_start": to_kst_date(latest_week), "rows": [_sales_management_dict(row) for row in rows]}


@router.post("/sales-management/bulk")
def save_sales_management_rows(
    data: SalesManagementBulk,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    year = data.week_start.year
    reserved_sales_numbers = {
        str(item.get("sales_no"))
        for item in data.rows
        if item.get("sales_no")
    }
    incoming = []
    seen = set()
    for item in data.rows:
        row_data = dict(item)
        if not row_data.get("sales_no"):
            row_data["sales_no"] = _next_sales_management_no(db, year, reserved_sales_numbers)
        row_key = _sales_management_row_key(row_data)
        unique_key = row_key
        suffix = 1
        while unique_key in seen:
            suffix += 1
            unique_key = f"{row_key}:{suffix}"
        seen.add(unique_key)
        row_data["id"] = row_data.get("id") or unique_key
        incoming.append((unique_key, row_data))

    existing = {
        row.row_key: row
        for row in db.query(SalesManagementWeeklyRow).filter(
            SalesManagementWeeklyRow.week_start == data.week_start
        ).all()
    }

    keep_keys = set()
    for row_key, row_data in incoming:
        keep_keys.add(row_key)
        row = existing.get(row_key)
        if not row:
            row = SalesManagementWeeklyRow(
                week_start=data.week_start,
                row_key=row_key,
                created_by=current.id,
            )
            db.add(row)
        row.data_json = json.dumps(row_data, ensure_ascii=False)

    for row_key, row in existing.items():
        if row_key not in keep_keys:
            db.delete(row)

    db.commit()
    rows = db.query(SalesManagementWeeklyRow).filter(
        SalesManagementWeeklyRow.week_start == data.week_start
    ).order_by(SalesManagementWeeklyRow.id.asc()).all()
    return [_sales_management_dict(row) for row in rows]


class EstimateItemIn(BaseModel):
    cost_code_id: Optional[int] = None
    item_name: str
    spec: Optional[str] = None
    unit: Optional[str] = None
    quantity: Decimal = Decimal(0)
    unit_price: Decimal = Decimal(0)
    amount: Decimal = Decimal(0)
    sort_order: int = 0
    notes: Optional[str] = None


class EstimateCreate(BaseModel):
    estimate_no: str
    site_id: Optional[int] = None
    client_id: Optional[int] = None
    title: str
    estimate_type: str = "bas"
    total_amount: Decimal = Decimal(0)
    labor_amount: Decimal = Decimal(0)
    material_amount: Decimal = Decimal(0)
    subcontract_amount: Decimal = Decimal(0)
    expense_amount: Decimal = Decimal(0)
    overhead_amount: Decimal = Decimal(0)
    profit_amount: Decimal = Decimal(0)
    status: str = "draft"
    estimate_date: Optional[date] = None
    notes: Optional[str] = None
    items: List[EstimateItemIn] = []


@router.get("/estimates")
def list_estimates(status: Optional[str] = None, search: Optional[str] = None,
                   db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Estimate)
    if status:
        q = q.filter(Estimate.status == status)
    if search:
        q = q.filter(or_(Estimate.title.ilike(f"%{search}%"), Estimate.estimate_no.ilike(f"%{search}%")))
    return q.order_by(Estimate.created_at.desc()).all()


@router.get("/estimates/{eid}")
def get_estimate(eid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    e = db.query(Estimate).filter(Estimate.id == eid).first()
    if not e:
        raise HTTPException(status_code=404, detail="견적을 찾을 수 없습니다.")
    return e


@router.post("/estimates")
def create_estimate(data: EstimateCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    items = data.items
    est_data = data.dict(exclude={"items"})
    e = Estimate(**est_data, created_by=current.id, estimated_by=current.id)
    db.add(e)
    db.flush()
    for item in items:
        ei = EstimateItem(**item.dict(), estimate_id=e.id)
        db.add(ei)
    db.commit()
    db.refresh(e)
    return e


@router.put("/estimates/{eid}")
def update_estimate(eid: int, data: EstimateCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    e = db.query(Estimate).filter(Estimate.id == eid).first()
    if not e:
        raise HTTPException(status_code=404, detail="견적을 찾을 수 없습니다.")
    items = data.items
    for field, val in data.dict(exclude={"items"}, exclude_none=True).items():
        setattr(e, field, val)
    db.query(EstimateItem).filter(EstimateItem.estimate_id == eid).delete()
    for item in items:
        ei = EstimateItem(**item.dict(), estimate_id=e.id)
        db.add(ei)
    db.commit()
    return e


# ── 계약 ──────────────────────────────────────────
def _estimate_attachment_dict(row: EstimateAttachment) -> dict:
    return {
        "id": row.id,
        "estimate_id": row.estimate_id,
        "original_name": row.original_name,
        "content_type": row.content_type,
        "file_size": row.file_size,
        "created_at": to_kst(row.created_at),
    }


@router.get("/estimates/{eid}/attachments")
def list_estimate_attachments(eid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    estimate = db.query(Estimate).filter(Estimate.id == eid).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="견적을 찾을 수 없습니다.")
    rows = db.query(EstimateAttachment).filter(
        EstimateAttachment.estimate_id == eid
    ).order_by(EstimateAttachment.created_at.desc()).all()
    return [_estimate_attachment_dict(row) for row in rows]


@router.post("/estimates/{eid}/attachments")
def upload_estimate_attachment(
    eid: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == eid).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="견적을 찾을 수 없습니다.")
    original_name = os.path.basename(file.filename or "attachment")
    ext = os.path.splitext(original_name)[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    directory = os.path.join(UPLOAD_ROOT, str(eid))
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, stored_name)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size = os.path.getsize(file_path)
    finally:
        file.file.close()
    row = EstimateAttachment(
        estimate_id=eid,
        original_name=original_name,
        stored_name=stored_name,
        content_type=file.content_type,
        file_size=file_size,
        file_path=file_path,
        created_by=current.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _estimate_attachment_dict(row)


@router.get("/estimate-attachments/{attachment_id}/download")
def download_estimate_attachment(attachment_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.query(EstimateAttachment).filter(EstimateAttachment.id == attachment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="첨부파일을 찾을 수 없습니다.")
    if not os.path.isfile(row.file_path):
        raise HTTPException(status_code=404, detail="파일이 서버에 존재하지 않습니다.")
    return FileResponse(row.file_path, filename=row.original_name, media_type=row.content_type or "application/octet-stream")


@router.delete("/estimate-attachments/{attachment_id}")
def delete_estimate_attachment(attachment_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.query(EstimateAttachment).filter(EstimateAttachment.id == attachment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="첨부파일을 찾을 수 없습니다.")
    file_path = row.file_path
    db.delete(row)
    db.commit()
    if file_path and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass
    return {"ok": True}



class DesignRequestCreate(BaseModel):
    project_name: str
    department: Optional[str] = None
    requester_name: Optional[str] = None
    order_company_id: Optional[int] = None
    construction_company_id: Optional[int] = None
    partner_company_id: Optional[int] = None
    request_date: Optional[date] = None
    due_date: Optional[date] = None
    status: str = "received"
    notes: Optional[str] = None


def _dr_dict(dr):
    return {
        "id": dr.id,
        "project_name": dr.project_name,
        "department": dr.department,
        "requester_name": dr.requester_name,
        "order_company_id": dr.order_company_id,
        "order_company_name": dr.order_company.company_name if dr.order_company else None,
        "construction_company_id": dr.construction_company_id,
        "construction_company_name": dr.construction_company.company_name if dr.construction_company else None,
        "partner_company_id": dr.partner_company_id,
        "partner_company_name": dr.partner_company.company_name if dr.partner_company else None,
        "request_date": to_kst_date(dr.request_date),
        "due_date":     to_kst_date(dr.due_date),
        "status":       dr.status,
        "notes":        dr.notes,
        "created_at":   to_kst(dr.created_at),
    }


@router.get("/design-requests")
def list_design_requests(status: Optional[str] = None, search: Optional[str] = None,
                         db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(DesignRequest)
    if status:
        q = q.filter(DesignRequest.status == status)
    if search:
        q = q.filter(DesignRequest.project_name.ilike(f"%{search}%"))
    return [_dr_dict(dr) for dr in q.order_by(DesignRequest.created_at.desc()).all()]


@router.post("/design-requests")
def create_design_request(data: DesignRequestCreate, db: Session = Depends(get_db),
                          current=Depends(get_current_user)):
    dr = DesignRequest(**data.dict(), created_by=current.id)
    db.add(dr)
    db.commit()
    db.refresh(dr)
    return _dr_dict(dr)


@router.put("/design-requests/{did}")
def update_design_request(did: int, data: DesignRequestCreate, db: Session = Depends(get_db),
                          _=Depends(get_current_user)):
    dr = db.query(DesignRequest).filter(DesignRequest.id == did).first()
    if not dr:
        raise HTTPException(status_code=404, detail="설계의뢰를 찾을 수 없습니다.")
    for field, val in data.dict(exclude_none=False).items():
        setattr(dr, field, val)
    db.commit()
    db.refresh(dr)
    return _dr_dict(dr)


@router.delete("/design-requests/{did}")
def delete_design_request(did: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    dr = db.query(DesignRequest).filter(DesignRequest.id == did).first()
    if not dr:
        raise HTTPException(status_code=404, detail="설계의뢰를 찾을 수 없습니다.")
    db.delete(dr)
    db.commit()
    return {"message": "삭제되었습니다."}
