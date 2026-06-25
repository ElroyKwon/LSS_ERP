from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from decimal import Decimal
from datetime import date
import json
from ..database import get_db
from ..models.execution import (
    Project, ProjectPlan, ProjectSalesPlanRow, ProjectPurchasePlanRow, ProjectBusinessCategory, ProjectPlanMeta, ProjectPlanWeeklySnapshot,
    PurchaseContract, ReleaseRequest, SalesBill, APBill,
)
from ..models.accounting import AccountsReceivable
from ..models.master import Company, Material
from ..utils.auth import get_current_user
from ..utils import to_kst_date, to_kst
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["실행"])

CONTRACT_FORMS = ["원도급", "하도급", "공동도급", "위탁", "기타"]
CONTRACT_TYPES = ["국내", "국외"]
STATUSES       = ["미진행", "진행중", "완료"]
PROJECT_REQ_MARKER = "\n---프로젝트리스트요구사항---\n"
DEFAULT_BUSINESS_CATEGORIES = ["빌딩", "DC", "BAS", "E&M", "O&M", "DR", "FEMS리스", "SE", "솔루션", "CS", "스테콤", "SCADA"]


def _json_meta(notes: Optional[str], marker: str) -> dict:
    raw = notes or ""
    idx = raw.find(marker)
    if idx < 0:
        return {}
    try:
        parsed = json.loads(raw[idx + len(marker):])
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _valid_customer_class(value: Optional[str]) -> str:
    return value if value in ["특수관계자", "대리점", "일반"] else "일반"


class ProjectCreate(BaseModel):
    project_no:      Optional[str]     = None
    project_name:    str
    client_id:       Optional[int]     = None
    client_name:     Optional[str]     = None
    contract_form:   str               = "원도급"
    contract_type:   str               = "국내"
    status:          str               = "미진행"
    contract_amount: Decimal           = Decimal(0)
    contract_rate:   Decimal           = Decimal(0)
    contract_start:  Optional[date]    = None
    contract_end:    Optional[date]    = None
    construct_start: Optional[date]    = None
    construct_end:   Optional[date]    = None
    pm_name:         Optional[str]     = None
    pm_dept:         Optional[str]     = None
    region:          Optional[str]     = None
    notes:           Optional[str]     = None


def _proj_dict(p: Project) -> dict:
    return {
        "id":             p.id,
        "project_no":     p.project_no,
        "project_name":   p.project_name,
        "client_id":      p.client_id,
        "client_name":    p.client_name or (p.client.company_name if p.client else None),
        "contract_form":  p.contract_form,
        "contract_type":  p.contract_type,
        "status":         p.status,
        "contract_amount": float(p.contract_amount or 0),
        "contract_rate":  float(p.contract_rate or 0),
        "contract_start": to_kst_date(p.contract_start),
        "contract_end":   to_kst_date(p.contract_end),
        "construct_start": to_kst_date(p.construct_start),
        "construct_end":  to_kst_date(p.construct_end),
        "pm_name":        p.pm_name,
        "pm_dept":        p.pm_dept,
        "region":         p.region,
        "notes":          p.notes,
        "created_at":     to_kst(p.created_at),
    }


@router.get("/projects")
def list_projects(
    status:         Optional[str] = None,
    contract_form:  Optional[str] = None,
    contract_type:  Optional[str] = None,
    search:         Optional[str] = None,
    client_name:    Optional[str] = None,
    construct_from: Optional[date] = None,
    construct_to:   Optional[date] = None,
    contract_from:  Optional[date] = None,
    contract_to:    Optional[date] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Project)
    if status:
        q = q.filter(Project.status == status)
    if contract_form:
        q = q.filter(Project.contract_form == contract_form)
    if contract_type:
        q = q.filter(Project.contract_type == contract_type)
    if search:
        q = q.filter(or_(
            Project.project_name.ilike(f"%{search}%"),
            Project.project_no.ilike(f"%{search}%"),
        ))
    if client_name:
        q = q.join(Company, Project.client_id == Company.id)\
             .filter(Company.company_name.ilike(f"%{client_name}%"))
    if construct_from:
        q = q.filter(Project.construct_start >= construct_from)
    if construct_to:
        q = q.filter(Project.construct_end <= construct_to)
    if contract_from:
        q = q.filter(Project.contract_start >= contract_from)
    if contract_to:
        q = q.filter(Project.contract_end <= contract_to)

    projects = q.order_by(Project.created_at.desc()).all()
    return [_proj_dict(p) for p in projects]


@router.post("/projects")
def create_project(data: ProjectCreate, db: Session = Depends(get_db),
                   current=Depends(get_current_user)):
    p = Project(**data.dict(), created_by=current.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _proj_dict(p)


@router.put("/projects/{pid}")
def update_project(pid: int, data: ProjectCreate, db: Session = Depends(get_db),
                   _=Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == pid).first()
    if not p:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    for field, val in data.dict().items():
        setattr(p, field, val)
    db.commit()
    db.refresh(p)
    return _proj_dict(p)


@router.delete("/projects/{pid}")
def delete_project(pid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == pid).first()
    if not p:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    db.delete(p)
    db.commit()
    return {"message": "삭제되었습니다."}


# ── 공통 헬퍼 ──────────────────────────────────────────
def _proj_name(project_id, db):
    if not project_id:
        return None
    p = db.query(Project).filter(Project.id == project_id).first()
    return p.project_name if p else None


# ══════════════════════════════════════════════════════
# 매출/투입 계획
# ══════════════════════════════════════════════════════
class ProjectPlanUpsert(BaseModel):
    project_id:       int
    plan_year:        int
    plan_month:       int
    invoice_plan:     Decimal = Decimal(0)
    revenue_plan:     Decimal = Decimal(0)
    material_plan:    Decimal = Decimal(0)
    labor_plan:       Decimal = Decimal(0)
    subcontract_plan: Decimal = Decimal(0)
    expense_plan:     Decimal = Decimal(0)
    notes:            Optional[str] = None


class ProjectPlanMetaSave(BaseModel):
    project_id: int
    plan_year: int
    version: Optional[int] = None
    contractDate: Optional[str] = None
    orderDate: Optional[str] = None
    orderAmount: Optional[float] = 0
    orderCompanyName: Optional[str] = None
    orderLaborCost: Optional[float] = 0
    orderExpenseCost: Optional[float] = 0
    changeColumnGroups: dict = {}
    materialVendorRows: List[dict] = []
    laborDetailRows: List[dict] = []


class ProjectPlanWeeklySnapshotSave(BaseModel):
    project_id: int
    plan_year: int
    week_start: date
    planData: dict = {}
    meta: dict = {}


class ProjectBusinessCategoriesSave(BaseModel):
    categories: List[str] = []


def _seed_business_categories(db: Session, current=None):
    if db.query(ProjectBusinessCategory).count() > 0:
        return
    for index, name in enumerate(DEFAULT_BUSINESS_CATEGORIES):
        db.add(ProjectBusinessCategory(
            name=name,
            sort_order=index,
            created_by=getattr(current, "id", None),
        ))
    db.commit()


@router.get("/project-plans")
def list_plans(project_id: int, plan_year: int,
               db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.query(ProjectPlan).filter(
        ProjectPlan.project_id == project_id,
        ProjectPlan.plan_year  == plan_year,
    ).order_by(ProjectPlan.plan_month).all()
    return [{
        "id": r.id, "project_id": r.project_id,
        "plan_year": r.plan_year, "plan_month": r.plan_month,
        "invoice_plan":     float(getattr(r, "invoice_plan", 0) or 0),
        "revenue_plan":     float(r.revenue_plan or 0),
        "material_plan":    float(r.material_plan or 0),
        "labor_plan":       float(r.labor_plan or 0),
        "subcontract_plan": float(r.subcontract_plan or 0),
        "expense_plan":     float(r.expense_plan or 0),
        "notes": r.notes,
    } for r in rows]


@router.post("/project-plans")
def upsert_plan(data: ProjectPlanUpsert, db: Session = Depends(get_db),
                current=Depends(get_current_user)):
    row = db.query(ProjectPlan).filter(
        ProjectPlan.project_id  == data.project_id,
        ProjectPlan.plan_year   == data.plan_year,
        ProjectPlan.plan_month  == data.plan_month,
    ).first()
    if row:
        for f, v in data.dict().items():
            setattr(row, f, v)
    else:
        row = ProjectPlan(**data.dict(), created_by=current.id)
        db.add(row)
    db.commit()
    db.refresh(row)
    return {"message": "저장되었습니다.", "id": row.id}


@router.get("/project-plan-meta")
def get_project_plan_meta(
    project_id: int,
    plan_year: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    row = db.query(ProjectPlanMeta).filter(
        ProjectPlanMeta.project_id == project_id,
        ProjectPlanMeta.plan_year == plan_year,
    ).first()
    if not row:
        return {"exists": False}
    try:
        data = json.loads(row.data_json or "{}")
        if not isinstance(data, dict):
            data = {}
    except (TypeError, ValueError):
        data = {}
    data["exists"] = True
    data["id"] = row.id
    data["project_id"] = row.project_id
    data["plan_year"] = row.plan_year
    return data


@router.post("/project-plan-meta")
def save_project_plan_meta(
    data: ProjectPlanMetaSave,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    if not db.query(Project).filter(Project.id == data.project_id).first():
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    payload = data.dict()
    row = db.query(ProjectPlanMeta).filter(
        ProjectPlanMeta.project_id == data.project_id,
        ProjectPlanMeta.plan_year == data.plan_year,
    ).first()
    if not row:
        row = ProjectPlanMeta(
            project_id=data.project_id,
            plan_year=data.plan_year,
            created_by=current.id,
            data_json="{}",
        )
        db.add(row)
    row.data_json = json.dumps(payload, ensure_ascii=False)
    db.commit()
    db.refresh(row)
    return {**payload, "exists": True, "id": row.id}


def _weekly_snapshot_dict(row: ProjectPlanWeeklySnapshot) -> dict:
    try:
        payload = json.loads(row.data_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except (TypeError, ValueError):
        payload = {}
    payload["exists"] = True
    payload["id"] = row.id
    payload["project_id"] = row.project_id
    payload["plan_year"] = row.plan_year
    payload["week_start"] = to_kst_date(row.week_start)
    return payload


@router.get("/project-plan-weekly")
def get_project_plan_weekly(
    project_id: int,
    plan_year: int,
    week_start: date,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    row = db.query(ProjectPlanWeeklySnapshot).filter(
        ProjectPlanWeeklySnapshot.project_id == project_id,
        ProjectPlanWeeklySnapshot.plan_year == plan_year,
        ProjectPlanWeeklySnapshot.week_start == week_start,
    ).first()
    if not row:
        return {"exists": False}
    return _weekly_snapshot_dict(row)


@router.get("/project-plan-weekly/latest-before")
def get_latest_project_plan_weekly_before(
    project_id: int,
    plan_year: int,
    week_start: date,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    row = db.query(ProjectPlanWeeklySnapshot).filter(
        ProjectPlanWeeklySnapshot.project_id == project_id,
        ProjectPlanWeeklySnapshot.plan_year == plan_year,
        ProjectPlanWeeklySnapshot.week_start < week_start,
    ).order_by(ProjectPlanWeeklySnapshot.week_start.desc()).first()
    if not row:
        return {"week_start": None, "exists": False}
    return _weekly_snapshot_dict(row)


@router.post("/project-plan-weekly")
def save_project_plan_weekly(
    data: ProjectPlanWeeklySnapshotSave,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    if not db.query(Project).filter(Project.id == data.project_id).first():
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    payload = data.dict()
    row = db.query(ProjectPlanWeeklySnapshot).filter(
        ProjectPlanWeeklySnapshot.project_id == data.project_id,
        ProjectPlanWeeklySnapshot.plan_year == data.plan_year,
        ProjectPlanWeeklySnapshot.week_start == data.week_start,
    ).first()
    if not row:
        row = ProjectPlanWeeklySnapshot(
            project_id=data.project_id,
            plan_year=data.plan_year,
            week_start=data.week_start,
            created_by=current.id,
            data_json="{}",
        )
        db.add(row)
    row.data_json = json.dumps(payload, ensure_ascii=False, default=str)
    db.commit()
    db.refresh(row)
    return _weekly_snapshot_dict(row)


@router.get("/project-business-categories")
def list_project_business_categories(
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    _seed_business_categories(db, current)
    rows = db.query(ProjectBusinessCategory).filter(
        ProjectBusinessCategory.is_active == True
    ).order_by(ProjectBusinessCategory.sort_order.asc(), ProjectBusinessCategory.id.asc()).all()
    return [row.name for row in rows]


@router.post("/project-business-categories")
def save_project_business_categories(
    data: ProjectBusinessCategoriesSave,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    values = []
    seen = set()
    for item in data.categories:
        value = str(item or "").strip()
        if value and value not in seen:
            seen.add(value)
            values.append(value)

    existing = {row.name: row for row in db.query(ProjectBusinessCategory).all()}
    for index, value in enumerate(values):
        row = existing.get(value)
        if not row:
            row = ProjectBusinessCategory(name=value, created_by=current.id)
            db.add(row)
        row.sort_order = index
        row.is_active = True

    for name, row in existing.items():
        if name not in seen:
            row.is_active = False

    db.commit()
    return values


class ProjectSalesPlanBulk(BaseModel):
    plan_year: int
    rows: List[dict] = []


class ProjectPurchasePlanBulk(BaseModel):
    plan_year: int
    rows: List[dict] = []


def _sales_plan_row_key(row: dict) -> str:
    if row.get("project_id"):
        return f"project:{row.get('project_id')}"
    if row.get("id"):
        return str(row.get("id"))
    if row.get("job_no"):
        return f"job:{row.get('job_no')}"
    return f"manual:{len(json.dumps(row, ensure_ascii=False, sort_keys=True))}"


def _sales_plan_dict(row: ProjectSalesPlanRow) -> dict:
    try:
        data = json.loads(row.data_json or "{}")
        if not isinstance(data, dict):
            data = {}
    except (TypeError, ValueError):
        data = {}
    data["db_id"] = row.id
    data["id"] = data.get("id") or row.row_key
    data["plan_year"] = row.plan_year
    data["project_id"] = data.get("project_id") or row.project_id
    return data


def _purchase_plan_dict(row: ProjectPurchasePlanRow) -> dict:
    try:
        data = json.loads(row.data_json or "{}")
        if not isinstance(data, dict):
            data = {}
    except (TypeError, ValueError):
        data = {}
    data["db_id"] = row.id
    data["id"] = data.get("id") or row.row_key
    data["plan_year"] = row.plan_year
    data["project_id"] = data.get("project_id") or row.project_id
    return data


@router.get("/project-sales-plans")
def list_project_sales_plans(
    plan_year: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    rows = db.query(ProjectSalesPlanRow).filter(
        ProjectSalesPlanRow.plan_year == plan_year
    ).order_by(ProjectSalesPlanRow.id.asc()).all()
    return [_sales_plan_dict(row) for row in rows]


@router.post("/project-sales-plans/bulk")
def save_project_sales_plans(
    data: ProjectSalesPlanBulk,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    incoming = []
    seen = set()
    for item in data.rows:
        row_data = dict(item)
        row_key = _sales_plan_row_key(row_data)
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
        for row in db.query(ProjectSalesPlanRow).filter(
            ProjectSalesPlanRow.plan_year == data.plan_year
        ).all()
    }

    keep_keys = set()
    for row_key, row_data in incoming:
        keep_keys.add(row_key)
        row = existing.get(row_key)
        if not row:
            row = ProjectSalesPlanRow(
                plan_year=data.plan_year,
                row_key=row_key,
                created_by=current.id,
            )
            db.add(row)
        row.project_id = row_data.get("project_id")
        row.data_json = json.dumps(row_data, ensure_ascii=False)

    for row_key, row in existing.items():
        if row_key not in keep_keys:
            db.delete(row)

    db.commit()
    rows = db.query(ProjectSalesPlanRow).filter(
        ProjectSalesPlanRow.plan_year == data.plan_year
    ).order_by(ProjectSalesPlanRow.id.asc()).all()
    return [_sales_plan_dict(row) for row in rows]


@router.get("/project-purchase-plans")
def list_project_purchase_plans(
    plan_year: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    rows = db.query(ProjectPurchasePlanRow).filter(
        ProjectPurchasePlanRow.plan_year == plan_year
    ).order_by(ProjectPurchasePlanRow.id.asc()).all()
    return [_purchase_plan_dict(row) for row in rows]


@router.post("/project-purchase-plans/bulk")
def save_project_purchase_plans(
    data: ProjectPurchasePlanBulk,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    incoming = []
    seen = set()
    for item in data.rows:
        row_data = dict(item)
        row_key = _sales_plan_row_key(row_data)
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
        for row in db.query(ProjectPurchasePlanRow).filter(
            ProjectPurchasePlanRow.plan_year == data.plan_year
        ).all()
    }

    keep_keys = set()
    for row_key, row_data in incoming:
        keep_keys.add(row_key)
        row = existing.get(row_key)
        if not row:
            row = ProjectPurchasePlanRow(
                plan_year=data.plan_year,
                row_key=row_key,
                created_by=current.id,
            )
            db.add(row)
        row.project_id = row_data.get("project_id")
        row.data_json = json.dumps(row_data, ensure_ascii=False)

    for row_key, row in existing.items():
        if row_key not in keep_keys:
            db.delete(row)

    db.commit()
    rows = db.query(ProjectPurchasePlanRow).filter(
        ProjectPurchasePlanRow.plan_year == data.plan_year
    ).order_by(ProjectPurchasePlanRow.id.asc()).all()
    return [_purchase_plan_dict(row) for row in rows]


# ══════════════════════════════════════════════════════
# 구매/계약
# ══════════════════════════════════════════════════════
class PurchaseContractCreate(BaseModel):
    contract_no:     Optional[str]  = None
    project_id:      Optional[int]  = None
    vendor_name:     str
    vendor_id:       Optional[int]  = None
    contract_name:   str
    contract_type:   str            = "자재"
    contract_amount: Decimal        = Decimal(0)
    start_date:      Optional[date] = None
    end_date:        Optional[date] = None
    status:          str            = "진행"
    notes:           Optional[str]  = None


def _pc_dict(r, db):
    return {
        "id": r.id, "contract_no": r.contract_no,
        "project_id": r.project_id, "project_name": _proj_name(r.project_id, db),
        "vendor_name": r.vendor_name, "vendor_id": r.vendor_id,
        "contract_name": r.contract_name, "contract_type": r.contract_type,
        "contract_amount": float(r.contract_amount or 0),
        "start_date": to_kst_date(r.start_date), "end_date": to_kst_date(r.end_date),
        "status": r.status, "notes": r.notes, "created_at": to_kst(r.created_at),
    }


@router.get("/purchase-contracts")
def list_purchase_contracts(project_id: Optional[int] = None, status: Optional[str] = None,
                             db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(PurchaseContract)
    if project_id: q = q.filter(PurchaseContract.project_id == project_id)
    if status:     q = q.filter(PurchaseContract.status == status)
    return [_pc_dict(r, db) for r in q.order_by(PurchaseContract.created_at.desc()).all()]


@router.post("/purchase-contracts")
def create_purchase_contract(data: PurchaseContractCreate,
                              db: Session = Depends(get_db), current=Depends(get_current_user)):
    r = PurchaseContract(**data.dict(), created_by=current.id)
    db.add(r); db.commit(); db.refresh(r)
    return _pc_dict(r, db)


@router.put("/purchase-contracts/{rid}")
def update_purchase_contract(rid: int, data: PurchaseContractCreate,
                              db: Session = Depends(get_db), _=Depends(get_current_user)):
    r = db.query(PurchaseContract).filter(PurchaseContract.id == rid).first()
    if not r: raise HTTPException(404, "구매계약을 찾을 수 없습니다.")
    for f, v in data.dict().items(): setattr(r, f, v)
    db.commit(); db.refresh(r)
    return _pc_dict(r, db)


@router.delete("/purchase-contracts/{rid}")
def delete_purchase_contract(rid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    r = db.query(PurchaseContract).filter(PurchaseContract.id == rid).first()
    if not r: raise HTTPException(404, "구매계약을 찾을 수 없습니다.")
    db.delete(r); db.commit()
    return {"message": "삭제되었습니다."}


# ══════════════════════════════════════════════════════
# 출고 요청
# ══════════════════════════════════════════════════════
class ReleaseRequestCreate(BaseModel):
    request_no:    Optional[str]   = None
    project_id:    Optional[int]   = None
    material_name: str
    material_id:   Optional[int]   = None
    quantity:      Decimal         = Decimal(0)
    unit:          Optional[str]   = None
    request_date:  Optional[date]  = None
    needed_date:   Optional[date]  = None
    status:        str             = "요청"
    notes:         Optional[str]   = None


def _rr_dict(r, db):
    return {
        "id": r.id, "request_no": r.request_no,
        "project_id": r.project_id, "project_name": _proj_name(r.project_id, db),
        "material_name": r.material_name, "material_id": r.material_id,
        "quantity": float(r.quantity or 0), "unit": r.unit,
        "request_date": to_kst_date(r.request_date), "needed_date": to_kst_date(r.needed_date),
        "status": r.status, "notes": r.notes, "created_at": to_kst(r.created_at),
    }


@router.get("/release-requests")
def list_release_requests(project_id: Optional[int] = None, status: Optional[str] = None,
                           db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(ReleaseRequest)
    if project_id: q = q.filter(ReleaseRequest.project_id == project_id)
    if status:     q = q.filter(ReleaseRequest.status == status)
    return [_rr_dict(r, db) for r in q.order_by(ReleaseRequest.created_at.desc()).all()]


@router.post("/release-requests")
def create_release_request(data: ReleaseRequestCreate,
                            db: Session = Depends(get_db), current=Depends(get_current_user)):
    r = ReleaseRequest(**data.dict(), created_by=current.id)
    db.add(r); db.commit(); db.refresh(r)
    return _rr_dict(r, db)


@router.put("/release-requests/{rid}")
def update_release_request(rid: int, data: ReleaseRequestCreate,
                            db: Session = Depends(get_db), _=Depends(get_current_user)):
    r = db.query(ReleaseRequest).filter(ReleaseRequest.id == rid).first()
    if not r: raise HTTPException(404, "출고요청을 찾을 수 없습니다.")
    for f, v in data.dict().items(): setattr(r, f, v)
    db.commit(); db.refresh(r)
    return _rr_dict(r, db)


@router.delete("/release-requests/{rid}")
def delete_release_request(rid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    r = db.query(ReleaseRequest).filter(ReleaseRequest.id == rid).first()
    if not r: raise HTTPException(404, "출고요청을 찾을 수 없습니다.")
    db.delete(r); db.commit()
    return {"message": "삭제되었습니다."}


# ══════════════════════════════════════════════════════
# 매출 청구 (세금계산서 발행 요청)
# ══════════════════════════════════════════════════════
class SalesBillCreate(BaseModel):
    bill_no:      Optional[str]  = None
    project_id:   Optional[int]  = None
    client_name:  Optional[str]  = None
    bill_amount:  Decimal        = Decimal(0)
    vat_amount:   Decimal        = Decimal(0)
    total_amount: Decimal        = Decimal(0)
    bill_date:    Optional[date] = None
    due_date:     Optional[date] = None
    invoice_no:   Optional[str]  = None
    invoice_date: Optional[date] = None
    status:       str            = "발행요청"
    notes:        Optional[str]  = None


def _sb_dict(r, db):
    return {
        "id": r.id, "bill_no": r.bill_no,
        "project_id": r.project_id, "project_name": _proj_name(r.project_id, db),
        "client_name": r.client_name,
        "bill_amount": float(r.bill_amount or 0),
        "vat_amount":  float(r.vat_amount  or 0),
        "total_amount": float(r.total_amount or 0),
        "bill_date": to_kst_date(r.bill_date), "due_date": to_kst_date(r.due_date),
        "invoice_no": r.invoice_no, "invoice_date": to_kst_date(r.invoice_date),
        "status": r.status, "notes": r.notes, "created_at": to_kst(r.created_at),
    }


@router.get("/sales-bills")
def list_sales_bills(project_id: Optional[int] = None, status: Optional[str] = None,
                     db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(SalesBill)
    if project_id: q = q.filter(SalesBill.project_id == project_id)
    if status:     q = q.filter(SalesBill.status == status)
    return [_sb_dict(r, db) for r in q.order_by(SalesBill.created_at.desc()).all()]


@router.post("/sales-bills")
def create_sales_bill(data: SalesBillCreate,
                      db: Session = Depends(get_db), current=Depends(get_current_user)):
    r = SalesBill(**data.dict(), created_by=current.id)
    db.add(r); db.commit(); db.refresh(r)
    return _sb_dict(r, db)


@router.put("/sales-bills/{rid}")
def update_sales_bill(rid: int, data: SalesBillCreate,
                      db: Session = Depends(get_db), _=Depends(get_current_user)):
    r = db.query(SalesBill).filter(SalesBill.id == rid).first()
    if not r: raise HTTPException(404, "매출청구를 찾을 수 없습니다.")
    for f, v in data.dict().items(): setattr(r, f, v)
    db.commit(); db.refresh(r)
    return _sb_dict(r, db)


@router.delete("/sales-bills/{rid}")
def delete_sales_bill(rid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    r = db.query(SalesBill).filter(SalesBill.id == rid).first()
    if not r: raise HTTPException(404, "매출청구를 찾을 수 없습니다.")
    db.delete(r); db.commit()
    return {"message": "삭제되었습니다."}


@router.patch("/sales-bills/{rid}/approve")
def approve_sales_bill(rid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    bill = db.query(SalesBill).filter(SalesBill.id == rid).first()
    if not bill:
        raise HTTPException(404, "매출청구를 찾을 수 없습니다.")

    project = db.query(Project).filter(Project.id == bill.project_id).first() if bill.project_id else None
    req = _json_meta(project.notes if project else None, PROJECT_REQ_MARKER)
    client = None
    if project and project.client_id:
        client = db.query(Company).filter(Company.id == project.client_id).first()
    if not client and bill.client_name:
        client = db.query(Company).filter(Company.company_name == bill.client_name).first()

    amount = bill.bill_amount or Decimal(0)
    customer_class = _valid_customer_class(client.company_category_name if client else None)
    receivable = db.query(AccountsReceivable).filter(
        AccountsReceivable.sales_bill_id == bill.id
    ).first()
    if not receivable:
        receivable = AccountsReceivable(
            sales_bill_id=bill.id,
            issue_date=bill.bill_date or date.today(),
            collected_amount=Decimal(0),
            status="outstanding",
        )
        db.add(receivable)

    receivable.project_id = project.id if project else bill.project_id
    receivable.client_id = client.id if client else (project.client_id if project else None)
    receivable.due_date = bill.due_date
    receivable.billing_amount = amount
    receivable.outstanding_amount = amount
    receivable.receivable_type = "외상매출금"
    receivable.business_division = req.get("business_division")
    receivable.job_no = project.project_no if project else None
    receivable.department = req.get("team_name") or (project.pm_dept if project else None)
    receivable.client_name = bill.client_name or (project.client_name if project else None)
    receivable.project_name = project.project_name if project else _proj_name(bill.project_id, db)
    receivable.sales_manager = req.get("sales_manager")
    receivable.construction_manager = req.get("execution_manager") or (project.pm_name if project else None)
    receivable.collection_terms = req.get("collection_terms")
    receivable.customer_class = customer_class

    bill.status = "승인"
    db.commit()
    db.refresh(bill)
    return _sb_dict(bill, db)


# ══════════════════════════════════════════════════════
# 매입 청구 (하도급 지급 요청)
# ══════════════════════════════════════════════════════
class APBillCreate(BaseModel):
    bill_no:      Optional[str]  = None
    project_id:   Optional[int]  = None
    vendor_name:  str
    vendor_id:    Optional[int]  = None
    bill_amount:  Decimal        = Decimal(0)
    vat_amount:   Decimal        = Decimal(0)
    total_amount: Decimal        = Decimal(0)
    bill_date:    Optional[date] = None
    due_date:     Optional[date] = None
    status:       str            = "지급요청"
    notes:        Optional[str]  = None


def _ap_dict(r, db):
    return {
        "id": r.id, "bill_no": r.bill_no,
        "project_id": r.project_id, "project_name": _proj_name(r.project_id, db),
        "vendor_name": r.vendor_name, "vendor_id": r.vendor_id,
        "bill_amount":  float(r.bill_amount  or 0),
        "vat_amount":   float(r.vat_amount   or 0),
        "total_amount": float(r.total_amount or 0),
        "bill_date": to_kst_date(r.bill_date), "due_date": to_kst_date(r.due_date),
        "status": r.status, "notes": r.notes, "created_at": to_kst(r.created_at),
    }


@router.get("/ap-bills")
def list_ap_bills(project_id: Optional[int] = None, status: Optional[str] = None,
                  db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(APBill)
    if project_id: q = q.filter(APBill.project_id == project_id)
    if status:     q = q.filter(APBill.status == status)
    return [_ap_dict(r, db) for r in q.order_by(APBill.created_at.desc()).all()]


@router.post("/ap-bills")
def create_ap_bill(data: APBillCreate,
                   db: Session = Depends(get_db), current=Depends(get_current_user)):
    r = APBill(**data.dict(), created_by=current.id)
    db.add(r); db.commit(); db.refresh(r)
    return _ap_dict(r, db)


@router.put("/ap-bills/{rid}")
def update_ap_bill(rid: int, data: APBillCreate,
                   db: Session = Depends(get_db), _=Depends(get_current_user)):
    r = db.query(APBill).filter(APBill.id == rid).first()
    if not r: raise HTTPException(404, "매입청구를 찾을 수 없습니다.")
    for f, v in data.dict().items(): setattr(r, f, v)
    db.commit(); db.refresh(r)
    return _ap_dict(r, db)


@router.delete("/ap-bills/{rid}")
def delete_ap_bill(rid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    r = db.query(APBill).filter(APBill.id == rid).first()
    if not r: raise HTTPException(404, "매입청구를 찾을 수 없습니다.")
    db.delete(r); db.commit()
    return {"message": "삭제되었습니다."}
