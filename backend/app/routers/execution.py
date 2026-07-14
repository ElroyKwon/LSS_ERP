from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
from decimal import Decimal
from datetime import date
from io import BytesIO
from urllib.parse import quote
import json
from ..database import get_db
from ..models.execution import (
    Project, ProjectPlan, ProjectSalesPlanRow, ProjectPurchasePlanRow, ProjectBusinessCategory, ProjectPlanMeta, ProjectPlanWeeklySnapshot,
    PurchaseContract, ReleaseRequest, SalesBill, APBill,
)
from ..models.accounting import AccountsReceivable, AccountsPayable
from ..models.master import Company, Employee, Material
from ..utils.auth import get_current_user
from ..utils import to_kst_date, to_kst
from ..utils.excel_import import (
    PROJECT_HEADERS,
    make_source_header_template_response,
    make_template_response,
    read_upload_rows,
    read_upload_rows_with_raw_headers,
    to_date_value,
    to_decimal_value,
)
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["실행"])

CONTRACT_FORMS = ["원도급", "하도급", "공동도급", "위탁", "기타"]
CONTRACT_TYPES = ["국내", "국외"]
STATUSES       = ["미진행", "진행중", "완료"]
STATUS_ALIASES = {
    "진행": "진행중",
    "진행 중": "진행중",
    "종료": "완료",
    "종료됨": "완료",
    "완료됨": "완료",
}
PROJECT_REQ_MARKER = "\n---프로젝트리스트요구사항---\n"
AP_BILL_REQ_MARKER = "\n---매입청구요구사항---\n"
PURCHASE_CONTRACT_REQ_MARKER = "\n---구매계약요구사항---\n"
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


def _json_tail_meta(notes: Optional[str]) -> dict:
    raw = notes or ""
    marker_start = raw.rfind("\n---")
    marker_end = raw.find("---\n", marker_start + 4) if marker_start >= 0 else -1
    if marker_start < 0 or marker_end < 0:
        return {}
    try:
        parsed = json.loads(raw[marker_end + 4:])
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _project_req(project: Optional[Project]) -> dict:
    return _json_meta(project.notes if project else None, PROJECT_REQ_MARKER)


def _purchase_contract_meta(contract: Optional[PurchaseContract]) -> dict:
    if not contract:
        return {}
    return _json_meta(contract.notes, PURCHASE_CONTRACT_REQ_MARKER) or _json_tail_meta(contract.notes)


def _ap_bill_meta(bill: Optional[APBill]) -> dict:
    if not bill:
        return {}
    return _json_meta(bill.notes, AP_BILL_REQ_MARKER) or _json_tail_meta(bill.notes)


def _valid_customer_class(value: Optional[str]) -> str:
    return value if value in ["특수관계자", "대리점", "일반"] else "일반"


def _normalize_project_status(value: Optional[str]) -> str:
    status = str(value or "").strip()
    status = STATUS_ALIASES.get(status, status)
    return status if status in STATUSES else STATUSES[0]


def _project_status_filter_values(value: Optional[str]) -> list[str]:
    status = _normalize_project_status(value)
    values = [status]
    values.extend(alias for alias, normalized in STATUS_ALIASES.items() if normalized == status)
    return values


def _employee_by_code(db: Session, employee_code: Optional[str]) -> Optional[Employee]:
    code = str(employee_code or "").strip()
    if not code:
        return None
    return db.query(Employee).filter(Employee.emp_code == code).first()


def _employee_code_for_name(db: Session, name: Optional[str]) -> Optional[str]:
    value = str(name or "").strip()
    if not value:
        return None
    matches = db.query(Employee).filter(Employee.name == value).all()
    return matches[0].emp_code if len(matches) == 1 else None


def _resolve_project_pm(db: Session, payload: dict) -> None:
    employee = _employee_by_code(db, payload.get("pm_employee_code"))
    if employee:
        payload["pm_employee_code"] = employee.emp_code
        if not payload.get("pm_name"):
            payload["pm_name"] = employee.name
        if not payload.get("pm_dept"):
            payload["pm_dept"] = employee.department_name
        return

    payload["pm_employee_code"] = _employee_code_for_name(db, payload.get("pm_name"))


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
    contract_material_cost: Decimal    = Decimal(0)
    contract_labor_cost: Decimal       = Decimal(0)
    sales_domestic_material_cost: Decimal = Decimal(0)
    sales_overseas_material_cost: Decimal = Decimal(0)
    sales_outsourcing_cost: Decimal    = Decimal(0)
    sales_labor_cost: Decimal          = Decimal(0)
    sales_expense_cost: Decimal        = Decimal(0)
    sales_indirect_cost: Decimal       = Decimal(0)
    contract_start:  Optional[date]    = None
    contract_end:    Optional[date]    = None
    construct_start: Optional[date]    = None
    construct_end:   Optional[date]    = None
    pm_name:         Optional[str]     = None
    pm_employee_code: Optional[str]    = None
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
        "status":         _normalize_project_status(p.status),
        "contract_amount": float(p.contract_amount or 0),
        "contract_rate":  float(p.contract_rate or 0),
        "contract_material_cost": float(p.contract_material_cost or 0),
        "contract_labor_cost": float(p.contract_labor_cost or 0),
        "sales_domestic_material_cost": float(p.sales_domestic_material_cost or 0),
        "sales_overseas_material_cost": float(p.sales_overseas_material_cost or 0),
        "sales_outsourcing_cost": float(p.sales_outsourcing_cost or 0),
        "sales_labor_cost": float(p.sales_labor_cost or 0),
        "sales_expense_cost": float(p.sales_expense_cost or 0),
        "sales_indirect_cost": float(p.sales_indirect_cost or 0),
        "contract_start": to_kst_date(p.contract_start),
        "contract_end":   to_kst_date(p.contract_end),
        "construct_start": to_kst_date(p.construct_start),
        "construct_end":  to_kst_date(p.construct_end),
        "pm_name":        p.pm_name,
        "pm_employee_code": p.pm_employee_code,
        "pm_dept":        p.pm_dept,
        "region":         p.region,
        "notes":          p.notes,
        "created_at":     to_kst(p.created_at),
    }


def _excel_response(content: bytes, filename: str):
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


MONTH_LABELS = [f"{month}월" for month in range(1, 13)]


def _numbered_month_from_key(key: str, prefix: str) -> int | None:
    if not key.startswith(f"{prefix}_"):
        return None
    rest = key[len(prefix) + 1:]
    digits = ""
    for char in rest:
        if char.isdigit():
            digits += char
        else:
            break
    if not digits:
        return None
    month = int(digits)
    return month if 1 <= month <= 12 else None


def _month_amount(row: dict, prefix: str, month: int) -> float:
    for key, value in row.items():
        if _numbered_month_from_key(str(key), prefix) == month:
            return float(to_decimal_value(value, Decimal(0)) or 0)
    return 0.0


def _month_fields(row: dict, source_prefix: str, target_prefix: str) -> dict:
    return {
        f"{target_prefix}_{month_label}": _month_amount(row, source_prefix, month)
        for month, month_label in enumerate(MONTH_LABELS, start=1)
    }


def _plan_row_key(project: Project, fallback: dict) -> str:
    if project.id:
        return f"project:{project.id}"
    if project.project_no:
        return f"job:{project.project_no}"
    return _sales_plan_row_key(fallback)


def _upsert_sales_plan_from_project(db: Session, project: Project, row: dict, plan_year: int, current) -> None:
    contract_material = float(to_decimal_value(row.get("sales_material_cost_total"), Decimal(0)) or 0)
    contract_labor = float(to_decimal_value(row.get("sales_labor_cost"), Decimal(0)) or 0)
    order_months = _month_fields(row, "order_current", "order")
    revenue_months = _month_fields(row, "revenue_current", "revenue_progress")
    tax_invoice_months = _month_fields(row, "revenue_current", "tax_invoice_revenue")
    row_data = {
        "project_id": project.id,
        "job_no": project.project_no or "",
        "project_name": project.project_name or "",
        "contract_company": row.get("client_name") or "",
        "domestic_overseas": "해외" if project.contract_type == "국외" else "내수",
        "special_relation": "특수관계" if row.get("special_relation") == "특수관계" else "x",
        "progress_status": "종료" if project.status == "완료" else "진행",
        "contract_date": to_kst_date(project.contract_start),
        "completion_date": to_kst_date(project.construct_end or project.contract_end),
        "months": str(row.get("months") or ""),
        "contract_material_cost": contract_material or float(project.contract_amount or 0),
        "contract_labor_cost": contract_labor,
        "current_order_amount": sum(order_months.values()),
        **order_months,
        **revenue_months,
        **tax_invoice_months,
    }
    row_key = _plan_row_key(project, row_data)
    existing = db.query(ProjectSalesPlanRow).filter(
        ProjectSalesPlanRow.plan_year == plan_year,
        ProjectSalesPlanRow.row_key == row_key,
    ).first()
    if not existing:
        existing = ProjectSalesPlanRow(plan_year=plan_year, row_key=row_key, created_by=current.id)
        db.add(existing)
    existing.project_id = project.id
    existing.data_json = json.dumps({"id": row_key, **row_data}, ensure_ascii=False, default=str)


def _upsert_purchase_plan_from_project(db: Session, project: Project, row: dict, plan_year: int, current) -> None:
    contract_material = float(to_decimal_value(row.get("sales_material_cost_total"), Decimal(0)) or 0)
    contract_labor = float(to_decimal_value(row.get("sales_labor_cost"), Decimal(0)) or 0)
    input_months = _month_fields(row, "input_current", "input_amount")
    material_input_months = _month_fields(row, "input_current", "material_input")
    row_data = {
        "project_id": project.id,
        "job_no": project.project_no or "",
        "project_name": project.project_name or "",
        "contract_company": row.get("client_name") or "",
        "domestic_overseas": "해외" if project.contract_type == "국외" else "내수",
        "special_relation": "특수관계" if row.get("special_relation") == "특수관계" else "x",
        "progress_status": "종료" if project.status == "완료" else "진행",
        "contract_date": to_kst_date(project.contract_start),
        "completion_date": to_kst_date(project.construct_end or project.contract_end),
        "months": str(row.get("months") or ""),
        "contract_material_cost": contract_material or float(project.contract_amount or 0),
        "contract_labor_cost": contract_labor,
        **input_months,
        **material_input_months,
    }
    row_key = _plan_row_key(project, row_data)
    existing = db.query(ProjectPurchasePlanRow).filter(
        ProjectPurchasePlanRow.plan_year == plan_year,
        ProjectPurchasePlanRow.row_key == row_key,
    ).first()
    if not existing:
        existing = ProjectPurchasePlanRow(plan_year=plan_year, row_key=row_key, created_by=current.id)
        db.add(existing)
    existing.project_id = project.id
    existing.data_json = json.dumps({"id": row_key, **row_data}, ensure_ascii=False, default=str)


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
        q = q.filter(Project.status.in_(_project_status_filter_values(status)))
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
    payload = data.dict()
    payload["status"] = _normalize_project_status(payload.get("status"))
    _resolve_project_pm(db, payload)
    p = Project(**payload, created_by=current.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _proj_dict(p)


@router.get("/projects/template")
def download_project_template(_=Depends(get_current_user)):
    filename = "프로젝트리스트_수주_양식.xlsx"
    content, filename = make_source_header_template_response(
        "프로젝트리스트.xlsx",
        filename,
        2,
        make_template_response("프로젝트리스트(수주)", PROJECT_HEADERS, filename),
    )
    return _excel_response(content, filename)


@router.post("/projects/import-excel")
def import_projects_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    fields = [field for _, field in PROJECT_HEADERS]
    rows = read_upload_rows_with_raw_headers(file, fields)
    imported = 0
    updated = 0
    skipped = 0
    errors = []
    for index, row_packet in enumerate(rows, start=1):
        try:
            row = row_packet["mapped"]
            raw_excel = row_packet["raw"]
            project_name = row.get("project_name")
            if not project_name:
                skipped += 1
                errors.append({"row": index, "detail": "프로젝트명이 없습니다."})
                continue

            project_no = str(row.get("project_no") or "").strip() or None
            client_name = row.get("order_company")
            client = None
            if client_name:
                client = db.query(Company).filter(Company.company_name == str(client_name)).first()
            payload = {
                "project_no": project_no,
                "project_name": project_name,
                "client_id": client.id if client else None,
                "client_name": client_name,
                "contract_form": row.get("contract_form") or CONTRACT_FORMS[0],
                "contract_type": row.get("contract_type") or CONTRACT_TYPES[0],
                "status": _normalize_project_status(row.get("status")),
                "contract_amount": to_decimal_value(row.get("contract_amount"), Decimal(0)) or Decimal(0),
                "contract_material_cost": to_decimal_value(row.get("sales_material_cost_total"), Decimal(0)) or Decimal(0),
                "contract_labor_cost": to_decimal_value(row.get("sales_labor_cost"), Decimal(0)) or Decimal(0),
                "sales_domestic_material_cost": to_decimal_value(row.get("sales_material_cost_total"), Decimal(0)) or Decimal(0),
                "sales_overseas_material_cost": Decimal(0),
                "sales_outsourcing_cost": Decimal(0),
                "sales_labor_cost": to_decimal_value(row.get("sales_labor_cost"), Decimal(0)) or Decimal(0),
                "sales_expense_cost": Decimal(0),
                "sales_indirect_cost": Decimal(0),
                "contract_start": to_date_value(row.get("contract_start")),
                "construct_end": to_date_value(row.get("construct_end")),
                "pm_name": row.get("execution_manager") or row.get("sales_manager"),
                "pm_dept": row.get("team_name") or row.get("business_division"),
                "region": row.get("site_address"),
                "excel_data_json": json.dumps(raw_excel, ensure_ascii=False, default=str),
            }
            _resolve_project_pm(db, payload)
            req = {
                "business_division": row.get("business_division"),
                "team_name": row.get("team_name"),
                "contract_company_name": row.get("client_name"),
                "business_category": row.get("business_category"),
                "sales_manager": row.get("sales_manager"),
                "execution_manager": row.get("execution_manager"),
                "collection_manager": row.get("collection_manager"),
                "revenue_type": row.get("revenue_type"),
                "work_type": row.get("work_type"),
                "collection_terms": row.get("collection_terms"),
                "warranty_period": row.get("warranty_period"),
                "special_relation": row.get("special_relation"),
                "_excel_raw": raw_excel,
            }
            payload["notes"] = PROJECT_REQ_MARKER + json.dumps(req, ensure_ascii=False, default=str)

            project = None
            if project_no:
                project = db.query(Project).filter(Project.project_no == project_no).first()
            if not project:
                project = db.query(Project).filter(
                    Project.project_name == str(project_name),
                    Project.client_name == str(client_name) if client_name else Project.client_name.is_(None),
                ).first()
            if project:
                for field, value in payload.items():
                    setattr(project, field, value)
                updated += 1
            else:
                project = Project(**payload, created_by=current.id)
                db.add(project)
                imported += 1
            db.flush()
            plan_year = date.today().year
            _upsert_sales_plan_from_project(db, project, row, plan_year, current)
            _upsert_purchase_plan_from_project(db, project, row, plan_year, current)
        except Exception as exc:
            skipped += 1
            errors.append({"row": index, "detail": str(exc)})
    db.commit()
    return {"imported": imported, "updated": updated, "skipped": skipped, "errors": errors[:20]}


@router.put("/projects/{pid}")
def update_project(pid: int, data: ProjectCreate, db: Session = Depends(get_db),
                   _=Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == pid).first()
    if not p:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    payload = data.dict()
    payload["status"] = _normalize_project_status(payload.get("status"))
    _resolve_project_pm(db, payload)
    for field, val in payload.items():
        setattr(p, field, val)
    db.commit()
    db.refresh(p)
    return _proj_dict(p)


@router.delete("/projects/{pid}")
def delete_project(pid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == pid).first()
    if not p:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    try:
        for model in (
            ProjectPlanWeeklySnapshot,
            ProjectPlanMeta,
            ProjectPlan,
            ProjectSalesPlanRow,
            ProjectPurchasePlanRow,
        ):
            db.query(model).filter(model.project_id == pid).delete(synchronize_session=False)

        for model in (PurchaseContract, ReleaseRequest, SalesBill, APBill, AccountsReceivable):
            db.query(model).filter(model.project_id == pid).update(
                {model.project_id: None},
                synchronize_session=False,
            )

        for table_name in ("sales_management_weekly_rows", "timesheet_entries", "vehicle_logs"):
            db.execute(text(f"UPDATE {table_name} SET project_id = NULL WHERE project_id = :pid"), {"pid": pid})

        db.delete(p)
        db.commit()
        return {"message": "삭제되었습니다."}
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="프로젝트를 참조하는 데이터가 있어 삭제할 수 없습니다. 연결된 자료를 먼저 확인해 주세요.",
        ) from exc


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


@router.patch("/ap-bills/{rid}/approve")
def approve_ap_bill(rid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    bill = db.query(APBill).filter(APBill.id == rid).first()
    if not bill:
        raise HTTPException(404, "매입청구를 찾을 수 없습니다.")

    project = db.query(Project).filter(Project.id == bill.project_id).first() if bill.project_id else None
    project_req = _project_req(project)
    bill_req = _ap_bill_meta(bill)

    purchase_contract = None
    purchase_contract_id = bill_req.get("purchase_contract_id")
    if purchase_contract_id:
        purchase_contract = db.query(PurchaseContract).filter(PurchaseContract.id == purchase_contract_id).first()
    if not purchase_contract and bill.project_id:
        purchase_contract = db.query(PurchaseContract).filter(
            PurchaseContract.project_id == bill.project_id,
            PurchaseContract.vendor_name == bill.vendor_name,
        ).order_by(PurchaseContract.id.desc()).first()
    if not purchase_contract and bill.vendor_id:
        purchase_contract = db.query(PurchaseContract).filter(
            PurchaseContract.vendor_id == bill.vendor_id,
        ).order_by(PurchaseContract.id.desc()).first()

    contract_req = _purchase_contract_meta(purchase_contract)
    related_bill_no = (bill_req.get("related_sales_bill") or "").strip()
    sales_bill = None
    if related_bill_no:
        sales_bill = db.query(SalesBill).filter(SalesBill.bill_no == related_bill_no).first()
    if not sales_bill and bill.project_id:
        sales_bill = db.query(SalesBill).filter(SalesBill.project_id == bill.project_id).order_by(
            SalesBill.bill_date.desc(),
            SalesBill.id.desc(),
        ).first()
    related_bill_no = related_bill_no or (sales_bill.bill_no if sales_bill else None)

    receivable = None
    if sales_bill:
        receivable = db.query(AccountsReceivable).filter(
            AccountsReceivable.sales_bill_id == sales_bill.id
        ).order_by(AccountsReceivable.id.desc()).first()
    if not receivable and bill.project_id:
        receivable = db.query(AccountsReceivable).filter(
            AccountsReceivable.project_id == bill.project_id
        ).order_by(AccountsReceivable.issue_date.desc(), AccountsReceivable.id.desc()).first()

    payable = db.query(AccountsPayable).filter(
        AccountsPayable.ref_type == "ap_bill",
        AccountsPayable.ref_id == bill.id,
    ).first()
    if not payable:
        payable = AccountsPayable(ref_type="ap_bill", ref_id=bill.id, issue_date=bill.bill_date or date.today())
        db.add(payable)

    contract_amount_ex_vat = purchase_contract.contract_amount if purchase_contract else Decimal(0)
    debt_amount = bill.total_amount or bill.bill_amount or Decimal(0)
    payable.vendor_id = bill.vendor_id or (purchase_contract.vendor_id if purchase_contract else None)
    payable.job_no = project.project_no if project else None
    payable.contract_name = project.project_name if project else _proj_name(bill.project_id, db)
    payable.vendor_name = bill.vendor_name or (purchase_contract.vendor_name if purchase_contract else None)
    payable.issue_date = bill.bill_date or date.today()
    payable.due_date = bill.due_date
    payable.total_amount = debt_amount
    payable.contract_amount_ex_vat = contract_amount_ex_vat
    payable.contract_amount = contract_amount_ex_vat * Decimal("1.1")
    payable.purchase_type = purchase_contract.contract_type if purchase_contract else None
    payable.subcontract_type = contract_req.get("subcontract_flag")
    payable.payment_terms = contract_req.get("payment_terms")
    payable.collection_terms = project_req.get("collection_terms")
    payable.related_revenue_no = related_bill_no
    payable.related_revenue = sales_bill.bill_amount if sales_bill else Decimal(0)
    payable.related_revenue_collection_date = receivable.collection_date if receivable else None
    payable.related_revenue_collection_method = receivable.collection_terms if receivable else None
    payable.paid_amount = (payable.cash_paid_amount or Decimal(0)) + (payable.note_issued_amount or Decimal(0))
    payable.outstanding_amount = max(debt_amount - (payable.paid_amount or Decimal(0)), Decimal(0))
    payable.status = "paid" if payable.outstanding_amount <= 0 and debt_amount > 0 else "outstanding"

    bill.status = "승인"
    db.commit()
    db.refresh(bill)
    return _ap_dict(bill, db)


@router.delete("/ap-bills/{rid}")
def delete_ap_bill(rid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    r = db.query(APBill).filter(APBill.id == rid).first()
    if not r: raise HTTPException(404, "매입청구를 찾을 수 없습니다.")
    db.delete(r); db.commit()
    return {"message": "삭제되었습니다."}
