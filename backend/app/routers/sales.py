from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func as sqlfunc
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime
from io import BytesIO
from urllib.parse import quote
import json
import os
import shutil
import uuid
from ..database import get_db
from ..models.sales import Estimate, EstimateItem, EstimateAttachment, DesignRequest, SalesManagementWeeklyRow
from ..utils.auth import get_current_user
from ..utils import to_kst, to_kst_date
from ..utils.excel_import import (
    SALES_HEADERS,
    make_source_header_template_response,
    make_template_response,
    read_upload_rows,
    read_upload_rows_with_raw_headers,
    to_date_value,
    to_decimal_value,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["영업·수주"])
UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "estimates")


def _excel_response(content: bytes, filename: str):
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


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


def _sales_management_entry_round(week_start: date) -> str:
    first_day = week_start.replace(day=1)
    monday_offset = first_day.weekday()
    week_no = ((week_start.day + monday_offset - 1) // 7) + 1
    return f"{week_start.year % 100:02d}-{week_start.month:02d}-{week_no}"


def _json_safe(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _sales_management_json(row_data: dict) -> str:
    return json.dumps(_json_safe(row_data), ensure_ascii=False)


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
    data["entry_round"] = data.get("entry_round") or _sales_management_entry_round(row.week_start)
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
        row_data["entry_round"] = _sales_management_entry_round(data.week_start)
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
        row_json = _sales_management_json(row_data)
        row = existing.get(row_key)
        if not row:
            row = SalesManagementWeeklyRow(
                week_start=data.week_start,
                row_key=row_key,
                data_json=row_json,
                created_by=current.id,
            )
            db.add(row)
        row.data_json = row_json

    for row_key, row in existing.items():
        if row_key not in keep_keys:
            db.delete(row)

    db.commit()
    rows = db.query(SalesManagementWeeklyRow).filter(
        SalesManagementWeeklyRow.week_start == data.week_start
    ).order_by(SalesManagementWeeklyRow.id.asc()).all()
    return [_sales_management_dict(row) for row in rows]


@router.get("/sales-management/template")
def download_sales_management_template(_=Depends(get_current_user)):
    filename = "\uc601\uc5c5\uad00\ub9ac_\uc591\uc2dd.xlsx"
    headers = SALES_HEADERS + [
        (f"{month}\uc6d4", f"order_current_{month}\uc6d4") for month in range(1, 13)
    ] + [
        (f"{month}\uc6d4", f"order_next_{month}\uc6d4") for month in range(1, 13)
    ] + [
        (f"{month}\uc6d4\ub9e4\ucd9c", f"revenue_current_{month}\uc6d4") for month in range(1, 13)
    ] + [
        (f"{month}\uc6d4\ub9e4\ucd9c", f"revenue_next_{month}\uc6d4") for month in range(1, 13)
    ]
    content, filename = make_source_header_template_response(
        "\uc601\uc5c5\uad00\ub9ac.xlsx",
        filename,
        1,
        make_template_response("\uc601\uc5c5\uad00\ub9ac", headers, filename),
    )
    return _excel_response(content, filename)


@router.post("/sales-management/import-excel")
def import_sales_management_excel(
    week_start: date,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    fields = [field for _, field in SALES_HEADERS]
    rows = read_upload_rows_with_raw_headers(file, fields)
    imported = 0
    updated = 0
    skipped = 0
    errors = []
    month_keys = []
    for prefix in ["order_current", "order_next", "revenue_current", "revenue_next"]:
        month_keys.extend([f"{prefix}_{month}\uc6d4" for month in range(1, 13)])

    existing = {
        row.row_key: row
        for row in db.query(SalesManagementWeeklyRow).filter(
            SalesManagementWeeklyRow.week_start == week_start
        ).all()
    }
    keep_keys = set()
    reserved_sales_numbers = set()
    for index, row_packet in enumerate(rows, start=1):
        try:
            item = row_packet["mapped"]
            raw_excel = row_packet["raw"]
            if not item.get("project_name"):
                skipped += 1
                errors.append({"row": index, "detail": "프로젝트명이 없습니다."})
                continue
            row_data = {
                "id": item.get("id"),
                "entry_round": _sales_management_entry_round(week_start),
                "sales_no": item.get("sales_no"),
                "project_name": item.get("project_name"),
                "client_name": item.get("client_name"),
                "probability": item.get("probability") or "C",
                "sales_status": item.get("sales_status") or "\uc0ac\uc5c5\ubc1c\uad74",
                "project_no": item.get("project_no"),
                "business_division": item.get("business_division"),
                "sales_team": item.get("sales_team"),
                "business_category": item.get("business_category"),
                "manager": item.get("manager"),
                "revenue_type": item.get("revenue_type"),
                "contract_expected_date": to_kst_date(to_date_value(item.get("contract_expected_date"))),
                "completion_expected_date": to_kst_date(to_date_value(item.get("completion_expected_date"))),
                "domestic_overseas": item.get("domestic_overseas"),
                "special_relation": item.get("special_relation"),
                "material_ratio": float(to_decimal_value(item.get("material_ratio"), Decimal(0)) or 0),
                "expected_order_amount": float(to_decimal_value(item.get("expected_order_amount"), Decimal(0)) or 0),
                "_excel_raw": raw_excel,
            }
            for key in month_keys:
                if key in item:
                    row_data[key] = float(to_decimal_value(item.get(key), Decimal(0)) or 0)
            if not row_data.get("sales_no"):
                row_data["sales_no"] = _next_sales_management_no(db, week_start.year, reserved_sales_numbers)
            row_key = _sales_management_row_key(row_data)
            unique_key = row_key
            suffix = 1
            while unique_key in keep_keys:
                suffix += 1
                unique_key = f"{row_key}:{suffix}"
            keep_keys.add(unique_key)
            row_data["id"] = row_data.get("id") or unique_key
            row_json = _sales_management_json(row_data)
            row = existing.get(unique_key)
            if row:
                updated += 1
            else:
                row = SalesManagementWeeklyRow(
                    week_start=week_start,
                    row_key=unique_key,
                    data_json=row_json,
                    created_by=current.id,
                )
                db.add(row)
                imported += 1
            row.data_json = row_json
        except Exception as exc:
            skipped += 1
            errors.append({"row": index, "detail": str(exc)})
    db.commit()
    saved = db.query(SalesManagementWeeklyRow).filter(
        SalesManagementWeeklyRow.week_start == week_start
    ).order_by(SalesManagementWeeklyRow.id.asc()).all()
    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],
        "rows": [_sales_management_dict(row) for row in saved],
    }


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
    return FileResponse(
        row.file_path,
        media_type=row.content_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.original_name)}"},
    )


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
