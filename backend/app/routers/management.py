from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, date, timedelta
import json
from ..database import get_db
from ..models.management import DeptBudget, ManagementSalesBusinessPlanRow
from ..models.accounting import AccountsReceivable, AccountsPayable
from ..models.sales import SalesManagementWeeklyRow
from ..models.purchase import CostInput
from ..models.execution import Project, ProjectPlanWeeklySnapshot, ProjectSalesPlanRow, SalesBill
from ..utils.auth import get_current_user
from ..utils import to_kst, to_kst_date
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["경영"])
APPROVED_SALES_BILL_STATUS = "승인"

CATEGORIES = ["매출목표", "재료비", "노무비", "외주비", "경비", "판관비", "기타"]


# ══════════════════════════════════════════════════════
# 예산 관리
# ══════════════════════════════════════════════════════
class DeptBudgetUpsert(BaseModel):
    budget_year: int
    department:  str
    category:    str
    q1:     Decimal = Decimal(0)
    q2:     Decimal = Decimal(0)
    q3:     Decimal = Decimal(0)
    q4:     Decimal = Decimal(0)
    status: str = "작성중"
    notes:  Optional[str] = None


class ReceivableUpsert(BaseModel):
    receivable_type: Optional[str] = "외상매출금"
    business_division: Optional[str] = None
    job_no: Optional[str] = None
    department: Optional[str] = None
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    sales_manager: Optional[str] = None
    construction_manager: Optional[str] = None
    collection_terms: Optional[str] = None
    due_date: Optional[date] = None
    sales_date: Optional[date] = None
    amount: Decimal = Decimal(0)
    customer_class: Optional[str] = "일반"
    collection_date: Optional[date] = None
    note_maturity_date: Optional[date] = None
    note_issuer: Optional[str] = None
    notes: Optional[str] = None


class PayableUpsert(BaseModel):
    job_no: Optional[str] = None
    contract_name: Optional[str] = None
    vendor_name: Optional[str] = None
    debt_date: Optional[date] = None
    debt_amount: Decimal = Decimal(0)
    contract_amount_ex_vat: Decimal = Decimal(0)
    contract_amount: Decimal = Decimal(0)
    purchase_type: Optional[str] = None
    subcontract_type: Optional[str] = None
    payment_terms: Optional[str] = None
    collection_terms: Optional[str] = None
    related_revenue_no: Optional[str] = None
    related_revenue: Decimal = Decimal(0)
    related_revenue_collection_date: Optional[date] = None
    related_revenue_collection_method: Optional[str] = None
    payment_due_date: Optional[date] = None
    actual_payment_date: Optional[date] = None
    payment_type: Optional[str] = None
    cash_paid_amount: Decimal = Decimal(0)
    note_issued_amount: Decimal = Decimal(0)
    note_maturity_date: Optional[date] = None
    payment_amount: Decimal = Decimal(0)
    notes: Optional[str] = None


class ManagementSalesBusinessPlanBulk(BaseModel):
    plan_year: int
    rows: List[dict] = Field(default_factory=list)


def _bdict(r):
    total = float((r.q1 or 0) + (r.q2 or 0) + (r.q3 or 0) + (r.q4 or 0))
    return {
        "id": r.id, "budget_year": r.budget_year,
        "department": r.department, "category": r.category,
        "q1": float(r.q1 or 0), "q2": float(r.q2 or 0),
        "q3": float(r.q3 or 0), "q4": float(r.q4 or 0),
        "total": total, "status": r.status, "notes": r.notes,
        "created_at": to_kst(r.created_at),
    }


@router.get("/dept-budgets")
def list_dept_budgets(budget_year: int, department: Optional[str] = None,
                      db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(DeptBudget).filter(DeptBudget.budget_year == budget_year)
    if department:
        q = q.filter(DeptBudget.department == department)
    return [_bdict(r) for r in q.order_by(DeptBudget.department, DeptBudget.category).all()]


@router.post("/dept-budgets")
def upsert_dept_budget(data: DeptBudgetUpsert, db: Session = Depends(get_db),
                       current=Depends(get_current_user)):
    row = db.query(DeptBudget).filter(
        DeptBudget.budget_year == data.budget_year,
        DeptBudget.department  == data.department,
        DeptBudget.category    == data.category,
    ).first()
    if row:
        for f, v in data.dict().items(): setattr(row, f, v)
    else:
        row = DeptBudget(**data.dict(), created_by=current.id)
        db.add(row)
    db.commit(); db.refresh(row)
    return _bdict(row)


@router.delete("/dept-budgets/{bid}")
def delete_dept_budget(bid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.query(DeptBudget).filter(DeptBudget.id == bid).first()
    if not row: raise HTTPException(404, "예산 항목을 찾을 수 없습니다.")
    db.delete(row); db.commit()
    return {"message": "삭제되었습니다."}


@router.get("/dept-budgets/departments")
def list_departments(budget_year: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.query(DeptBudget.department).filter(DeptBudget.budget_year == budget_year)\
             .distinct().order_by(DeptBudget.department).all()
    return [r[0] for r in rows]


# ══════════════════════════════════════════════════════
# 경영 분석
# ══════════════════════════════════════════════════════
@router.get("/management/analysis/sales-plan")
def management_sales_plan_analysis(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    now = datetime.now()
    target_year = year or now.year
    target_month = month or now.month
    week1_start = _month_week_start(target_year, target_month, 1)
    week4_start = _month_week_start(target_year, target_month, 4)

    week1_rows = _analysis_source_map(db, week1_start)
    week4_rows = _analysis_source_map(db, week4_start)
    plan_rows = _business_plan_map(db, target_year)
    row_keys = sorted(set(plan_rows.keys()) | set(week1_rows.keys()) | set(week4_rows.keys()))

    result_rows = []
    for row_key in row_keys:
        source = week4_rows.get(row_key) or week1_rows.get(row_key) or plan_rows.get(row_key) or {}
        plan = plan_rows.get(row_key, {})
        plan_months = plan.get("business_plan_months") or {}
        result_rows.append({
            "row_key": row_key,
            "business_division": source.get("business_division") or plan.get("business_division") or "",
            "sales_team": source.get("sales_team") or plan.get("sales_team") or "",
            "business_category": source.get("business_category") or plan.get("business_category") or "",
            "sales_no": source.get("sales_no") or plan.get("sales_no") or "",
            "project_name": source.get("project_name") or plan.get("project_name") or "",
            "probability": source.get("probability") or plan.get("probability") or "",
            "sales_status": source.get("sales_status") or plan.get("sales_status") or "",
            "domestic_overseas": source.get("domestic_overseas") or plan.get("domestic_overseas") or "",
            "special_relation": source.get("special_relation") or plan.get("special_relation") or "",
            "business_plan": {
                "total": float(plan.get("business_plan_total") or 0),
                "months": {
                    str(month_no): float(plan_months.get(str(month_no)) or 0)
                    for month_no in range(1, 13)
                },
            },
            "current_week1": _month_values(week1_rows.get(row_key, {}), "order_current"),
            "current_week4": _month_values(week4_rows.get(row_key, {}), "order_current"),
            "next_week1": _month_values(week1_rows.get(row_key, {}), "order_next"),
            "next_week4": _month_values(week4_rows.get(row_key, {}), "order_next"),
        })

    return {
        "year": target_year,
        "month": target_month,
        "week1_start": to_kst_date(week1_start),
        "week4_start": to_kst_date(week4_start),
        "rows": result_rows,
    }


@router.post("/management/analysis/sales-plan")
def save_management_sales_business_plan(
    data: ManagementSalesBusinessPlanBulk,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    incoming = []
    for item in data.rows:
        row_data = dict(item)
        row_key = str(row_data.get("row_key") or _sales_analysis_row_key(row_data))
        if not row_key:
            continue
        row_data["row_key"] = row_key
        incoming.append((row_key, row_data))

    existing = {
        row.row_key: row
        for row in db.query(ManagementSalesBusinessPlanRow).filter(
            ManagementSalesBusinessPlanRow.plan_year == data.plan_year
        ).all()
    }
    for row_key, row_data in incoming:
        row = existing.get(row_key)
        if not row:
            row = ManagementSalesBusinessPlanRow(
                plan_year=data.plan_year,
                row_key=row_key,
                created_by=current.id,
                data_json="{}",
            )
            db.add(row)
        row.data_json = json.dumps(row_data, ensure_ascii=False)
    db.commit()
    return {"ok": True, "count": len(incoming)}


@router.get("/management/analysis/revenue-plan")
def management_revenue_plan_analysis(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    now = datetime.now()
    target_year = year or now.year
    target_month = month or now.month
    next_year = target_year + 1
    week1_start = _month_week_start(target_year, target_month, 1)
    week4_start = _month_week_start(target_year, target_month, 4)

    plan_rows = _business_plan_map(db, target_year)
    sales_week1 = _analysis_source_map(db, week1_start)
    sales_week4 = _analysis_source_map(db, week4_start)
    order_week1 = _project_revenue_source_map(db, target_year, week1_start)
    order_week4 = _project_revenue_source_map(db, target_year, week4_start)
    row_keys = sorted(set(sales_week1.keys()) | set(sales_week4.keys()) | set(order_week1.keys()) | set(order_week4.keys()))

    result_rows = []
    for row_key in row_keys:
        source = order_week4.get(row_key) or order_week1.get(row_key) or sales_week4.get(row_key) or sales_week1.get(row_key) or {}
        plan = _find_business_plan(plan_rows, source)
        plan_months = plan.get("business_plan_months") or {}
        is_order = row_key.startswith("order:")
        result_rows.append({
            "row_key": row_key,
            "source_type": "수주" if is_order else "영업",
            "business_division": source.get("business_division") or plan.get("business_division") or "",
            "sales_team": source.get("sales_team") or source.get("team_name") or plan.get("sales_team") or "",
            "business_category": source.get("business_category") or plan.get("business_category") or "",
            "sales_no": source.get("sales_no") or plan.get("sales_no") or "",
            "job_no": source.get("job_no") or source.get("project_no") or "",
            "project_name": source.get("project_name") or plan.get("project_name") or "",
            "contract_company": source.get("contract_company") or source.get("client_name") or "",
            "domestic_overseas": source.get("domestic_overseas") or plan.get("domestic_overseas") or "",
            "special_relation": source.get("special_relation") or plan.get("special_relation") or "",
            "business_plan": {
                "total": float(plan.get("business_plan_total") or 0),
                "months": {
                    str(month_no): float(plan_months.get(str(month_no)) or 0)
                    for month_no in range(1, 13)
                },
            },
            "current_week1": _revenue_values(order_week1 if is_order else sales_week1, row_key, target_year, "revenue_current"),
            "current_week4": _revenue_values(order_week4 if is_order else sales_week4, row_key, target_year, "revenue_current"),
            "next_week1": _revenue_values(order_week1 if is_order else sales_week1, row_key, next_year, "revenue_next"),
            "next_week4": _revenue_values(order_week4 if is_order else sales_week4, row_key, next_year, "revenue_next"),
        })

    return {
        "year": target_year,
        "month": target_month,
        "week1_start": to_kst_date(week1_start),
        "week4_start": to_kst_date(week4_start),
        "rows": result_rows,
    }


@router.get("/management/analysis")
def management_analysis(year: Optional[int] = None,
                        db: Session = Depends(get_db), _=Depends(get_current_user)):
    now = datetime.now()
    target_year = year or now.year

    # 월별 수주·매출 (12개월)
    monthly = []
    for m in range(1, 13):
        rev = db.query(sqlfunc.sum(SalesBill.bill_amount)).filter(
            SalesBill.status == APPROVED_SALES_BILL_STATUS,
            sqlfunc.extract("year",  SalesBill.bill_date) == target_year,
            sqlfunc.extract("month", SalesBill.bill_date) == m,
        ).scalar() or 0
        orders = db.query(sqlfunc.sum(Project.contract_amount)).filter(
            sqlfunc.extract("year",  Project.contract_start) == target_year,
            sqlfunc.extract("month", Project.contract_start) == m,
        ).scalar() or 0
        cost = db.query(sqlfunc.sum(CostInput.amount)).filter(
            sqlfunc.extract("year",  CostInput.input_date) == target_year,
            sqlfunc.extract("month", CostInput.input_date) == m,
        ).scalar() or 0
        monthly.append({"month": m, "revenue": float(rev), "orders": float(orders), "cost": float(cost)})

    # 프로젝트별 수익성
    projects = db.query(Project).filter(Project.status == "진행중").all()
    proj_pl = []
    for p in projects:
        rev = float(db.query(sqlfunc.sum(SalesBill.bill_amount)).filter(
            SalesBill.status == APPROVED_SALES_BILL_STATUS,
        ).scalar() or 0)
        cost = float(db.query(sqlfunc.sum(CostInput.amount)).scalar() or 0)
        proj_pl.append({
            "id": p.id, "project_no": p.project_no, "project_name": p.project_name,
            "client_name": p.client_name, "contract_amount": float(p.contract_amount or 0),
            "status": p.status, "pm_name": p.pm_name,
        })

    # YTD 요약
    ytd_rev = sum(m["revenue"] for m in monthly[:now.month])
    ytd_ord = sum(m["orders"]  for m in monthly[:now.month])
    ytd_cost = sum(m["cost"]   for m in monthly[:now.month])

    return {
        "year": target_year,
        "monthly": monthly,
        "projects": proj_pl,
        "summary": {
            "ytd_revenue": ytd_rev,
            "ytd_orders":  ytd_ord,
            "ytd_cost":    ytd_cost,
            "gross_profit": ytd_rev - ytd_cost,
            "gross_margin": round((ytd_rev - ytd_cost) / ytd_rev * 100, 1) if ytd_rev else 0,
        },
    }


# ══════════════════════════════════════════════════════
# 채권 관리 — AR Aging Analysis
# ══════════════════════════════════════════════════════
def _customer_class(value):
    return value if value in ["특수관계자", "대리점", "일반"] else "일반"


def _ar_dict(r, today=None):
    today = today or date.today()
    amount = float(r.billing_amount or 0)
    due_days = (today - r.due_date).days if r.due_date else 0
    customer_class = _customer_class(r.customer_class)
    bad_debt_rate = 0 if customer_class in ["특수관계자", "대리점"] else 0.01
    return {
        "id": r.id,
        "sales_bill_id": r.sales_bill_id,
        "project_id": r.project_id,
        "receivable_type": r.receivable_type or "외상매출금",
        "business_division": r.business_division,
        "job_no": r.job_no,
        "department": r.department,
        "client_name": r.client_name or (r.client.company_name if r.client else None),
        "project_name": r.project_name,
        "sales_manager": r.sales_manager,
        "construction_manager": r.construction_manager,
        "collection_terms": r.collection_terms,
        "due_date": to_kst_date(r.due_date),
        "sales_date": to_kst_date(r.issue_date),
        "issue_date": to_kst_date(r.issue_date),
        "amount": amount,
        "billing_amount": amount,
        "collected_amount": float(r.collected_amount or 0),
        "outstanding_amount": float(r.outstanding_amount or 0),
        "age_months": int(due_days // 30) if r.due_date else 0,
        "overdue_days": due_days,
        "bad_debt_rate": bad_debt_rate,
        "bad_debt_allowance": round(amount * bad_debt_rate),
        "customer_class": customer_class,
        "collection_date": to_kst_date(r.collection_date),
        "note_maturity_date": to_kst_date(r.note_maturity_date),
        "note_issuer": r.note_issuer,
        "status": r.status,
        "notes": r.notes,
    }


def _start_of_week(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _month_week_start(year: int, month: int, week_index: int) -> date:
    return _start_of_week(date(year, month, 1)) + timedelta(days=(week_index - 1) * 7)


def _decode_json_dict(value: str) -> dict:
    try:
        data = json.loads(value or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def _sales_analysis_row_key(row: dict) -> str:
    if row.get("sales_no"):
        return str(row.get("sales_no"))
    if row.get("id"):
        return str(row.get("id"))
    return f"{row.get('project_name') or ''}:{row.get('client_name') or ''}"


def _sales_management_rows_for_week(db: Session, week_start: date) -> List[dict]:
    rows = db.query(SalesManagementWeeklyRow).filter(
        SalesManagementWeeklyRow.week_start == week_start
    ).order_by(SalesManagementWeeklyRow.id.asc()).all()
    return [_decode_json_dict(row.data_json) for row in rows]


def _month_values(row: dict, prefix: str) -> dict:
    values = {}
    total = 0.0
    for month in range(1, 13):
        key = f"{prefix}_{month}월"
        value = float(row.get(key) or 0)
        values[str(month)] = value
        total += value
    return {"total": total, "months": values}


def _plan_row_dict(row: ManagementSalesBusinessPlanRow) -> dict:
    data = _decode_json_dict(row.data_json)
    data["row_key"] = row.row_key
    data["plan_year"] = row.plan_year
    return data


def _business_plan_map(db: Session, plan_year: int) -> dict:
    rows = db.query(ManagementSalesBusinessPlanRow).filter(
        ManagementSalesBusinessPlanRow.plan_year == plan_year
    ).all()
    return {row.row_key: _plan_row_dict(row) for row in rows}


def _analysis_source_map(db: Session, week_start: date) -> dict:
    result = {}
    for row in _sales_management_rows_for_week(db, week_start):
        if row.get("probability") not in ["A", "B", "C"]:
            continue
        result[_sales_analysis_row_key(row)] = row
    return result


def _project_sales_plan_by_project(db: Session, plan_year: int) -> dict:
    result = {}
    rows = db.query(ProjectSalesPlanRow).filter(
        ProjectSalesPlanRow.plan_year == plan_year
    ).all()
    for row in rows:
        data = _decode_json_dict(row.data_json)
        if row.project_id:
            result[row.project_id] = data
    return result


def _project_revenue_source_map(db: Session, plan_year: int, week_start: date) -> dict:
    sales_plan_by_project = _project_sales_plan_by_project(db, plan_year)
    snapshots = db.query(ProjectPlanWeeklySnapshot).filter(
        ProjectPlanWeeklySnapshot.plan_year == plan_year,
        ProjectPlanWeeklySnapshot.week_start == week_start,
    ).order_by(ProjectPlanWeeklySnapshot.id.asc()).all()
    result = {}
    for snapshot in snapshots:
        payload = _decode_json_dict(snapshot.data_json)
        project = snapshot.project
        sales_plan = sales_plan_by_project.get(snapshot.project_id, {})
        key = f"order:{snapshot.project_id}"
        result[key] = {
            "row_key": key,
            "project_id": snapshot.project_id,
            "job_no": sales_plan.get("job_no") or getattr(project, "project_no", "") or "",
            "project_name": sales_plan.get("project_name") or getattr(project, "project_name", "") or "",
            "contract_company": sales_plan.get("contract_company") or getattr(project, "client_name", "") or "",
            "client_name": sales_plan.get("contract_company") or getattr(project, "client_name", "") or "",
            "business_division": sales_plan.get("business_division") or getattr(project, "business_division", "") or "",
            "sales_team": sales_plan.get("team_name") or getattr(project, "team_name", "") or "",
            "team_name": sales_plan.get("team_name") or getattr(project, "team_name", "") or "",
            "business_category": sales_plan.get("business_category") or getattr(project, "business_category", "") or "",
            "domestic_overseas": sales_plan.get("domestic_overseas") or ("해외" if getattr(project, "contract_type", "") == "국외" else "내수"),
            "special_relation": sales_plan.get("special_relation") or getattr(project, "special_relation", "") or "",
            "planData": payload.get("planData") if isinstance(payload.get("planData"), dict) else {},
        }
    return result


def _find_business_plan(plan_rows: dict, source: dict) -> dict:
    candidates = [
        source.get("row_key"),
        source.get("sales_no"),
        source.get("id"),
        f"{source.get('project_name') or ''}:{source.get('client_name') or source.get('contract_company') or ''}",
    ]
    for key in candidates:
        if key and str(key) in plan_rows:
            return plan_rows[str(key)]
    project_name = str(source.get("project_name") or "").strip()
    if project_name:
        for plan in plan_rows.values():
            if str(plan.get("project_name") or "").strip() == project_name:
                return plan
    return {}


def _plan_data_month_values(row: dict, year: int) -> dict:
    values = {}
    total = 0.0
    year_data = (row.get("planData") or {}).get(str(year)) or (row.get("planData") or {}).get(year) or {}
    for month in range(1, 13):
        month_data = year_data.get(str(month)) or year_data.get(month) or {}
        value = float(month_data.get("revenue_plan") or 0)
        values[str(month)] = value
        total += value
    return {"total": total, "months": values}


def _revenue_values(source_map: dict, row_key: str, year: int, sales_prefix: str) -> dict:
    row = source_map.get(row_key, {})
    if row_key.startswith("order:"):
        return _plan_data_month_values(row, year)
    return _month_values(row, sales_prefix)


def _apply_receivable(row, data: ReceivableUpsert):
    amount = data.amount or Decimal(0)
    row.receivable_type = data.receivable_type or "외상매출금"
    row.business_division = data.business_division
    row.job_no = data.job_no
    row.department = data.department
    row.client_name = data.client_name
    row.project_name = data.project_name
    row.sales_manager = data.sales_manager
    row.construction_manager = data.construction_manager
    row.collection_terms = data.collection_terms
    row.due_date = data.due_date
    row.issue_date = data.sales_date or row.issue_date or date.today()
    row.billing_amount = amount
    row.customer_class = _customer_class(data.customer_class)
    row.collection_date = data.collection_date
    row.note_maturity_date = data.note_maturity_date
    row.note_issuer = data.note_issuer
    row.notes = data.notes
    row.collected_amount = amount if data.collection_date else Decimal(0)
    row.outstanding_amount = Decimal(0) if data.collection_date else amount
    row.status = "collected" if data.collection_date else "outstanding"


@router.get("/management/receivables")
def management_receivables(db: Session = Depends(get_db), _=Depends(get_current_user)):
    today = date.today()
    rows = db.query(AccountsReceivable).order_by(
        AccountsReceivable.issue_date.desc(),
        AccountsReceivable.id.desc(),
    ).all()

    aging_buckets = {"current": 0, "d30": 0, "d60": 0, "d90": 0, "over90": 0}
    items = []
    for r in rows:
        days = (today - r.due_date).days if r.due_date else 0
        if days <= 0:      bucket = "current"
        elif days <= 30:   bucket = "d30"
        elif days <= 60:   bucket = "d60"
        elif days <= 90:   bucket = "d90"
        else:              bucket = "over90"
        aging_buckets[bucket] += float(r.outstanding_amount or 0)
        items.append(_ar_dict(r, today))

    total_outstanding = sum(i["outstanding_amount"] for i in items)
    return {"items": items, "aging": aging_buckets, "total_outstanding": total_outstanding}


@router.post("/management/receivables")
def create_receivable(data: ReceivableUpsert, db: Session = Depends(get_db),
                      _=Depends(get_current_user)):
    row = AccountsReceivable(issue_date=data.sales_date or date.today())
    _apply_receivable(row, data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _ar_dict(row)


@router.put("/management/receivables/{rid}")
def update_receivable(rid: int, data: ReceivableUpsert, db: Session = Depends(get_db),
                      _=Depends(get_current_user)):
    row = db.query(AccountsReceivable).filter(AccountsReceivable.id == rid).first()
    if not row:
        raise HTTPException(404, "채권 정보를 찾을 수 없습니다.")
    _apply_receivable(row, data)
    db.commit()
    db.refresh(row)
    return _ar_dict(row)


# ══════════════════════════════════════════════════════
# 채무 관리 — Payment Schedule
# ══════════════════════════════════════════════════════
def _payable_vendor_name(row: AccountsPayable):
    if row.vendor_name:
        return row.vendor_name
    vendor = getattr(row, "vendor", None)
    if not vendor:
        return None
    return (
        getattr(vendor, "company_name", None)
        or getattr(vendor, "name", None)
        or getattr(vendor, "short_name", None)
    )


def _payable_amount(value):
    return float(value or 0)


def _payable_dict(row: AccountsPayable, today: Optional[date] = None):
    today = today or date.today()
    days_left = (row.due_date - today).days if row.due_date else None
    debt_amount = _payable_amount(row.total_amount)
    payment_amount = _payable_amount(row.paid_amount)
    balance = _payable_amount(row.outstanding_amount)
    if not balance and debt_amount:
        balance = max(debt_amount - payment_amount, 0)
    return {
        "id": row.id,
        "job_no": row.job_no,
        "contract_name": row.contract_name,
        "vendor_name": _payable_vendor_name(row),
        "debt_date": to_kst_date(row.issue_date),
        "debt_amount": debt_amount,
        "contract_amount_ex_vat": _payable_amount(row.contract_amount_ex_vat),
        "contract_amount": _payable_amount(row.contract_amount),
        "purchase_type": row.purchase_type,
        "subcontract_type": row.subcontract_type,
        "payment_terms": row.payment_terms,
        "collection_terms": row.collection_terms,
        "related_revenue_no": row.related_revenue_no,
        "related_revenue": _payable_amount(row.related_revenue),
        "related_revenue_collection_date": to_kst_date(row.related_revenue_collection_date),
        "related_revenue_collection_method": row.related_revenue_collection_method,
        "payment_due_date": to_kst_date(row.due_date),
        "actual_payment_date": to_kst_date(row.actual_payment_date),
        "payment_type": row.payment_type,
        "cash_paid_amount": _payable_amount(row.cash_paid_amount),
        "note_issued_amount": _payable_amount(row.note_issued_amount),
        "note_maturity_date": to_kst_date(row.note_maturity_date),
        "payment_amount": payment_amount,
        "payable_balance": balance,
        "status": row.status,
        "notes": row.notes,
        "days_left": days_left,
        "overdue": days_left is not None and days_left < 0 and balance > 0,
    }


def _apply_payable(row: AccountsPayable, data: PayableUpsert):
    debt_amount = Decimal(data.debt_amount or 0)
    cash_paid = Decimal(data.cash_paid_amount or 0)
    note_issued = Decimal(data.note_issued_amount or 0)
    if data.actual_payment_date and data.payment_type == "현금":
        cash_paid = debt_amount
        note_issued = Decimal(0)
    elif data.actual_payment_date and data.payment_type == "어음":
        cash_paid = Decimal(0)
        note_issued = debt_amount
    payment_amount = cash_paid + note_issued
    row.job_no = data.job_no
    row.contract_name = data.contract_name
    row.vendor_name = data.vendor_name
    row.issue_date = data.debt_date or date.today()
    row.total_amount = debt_amount
    row.contract_amount_ex_vat = data.contract_amount_ex_vat or Decimal(0)
    row.contract_amount = data.contract_amount or Decimal(0)
    row.purchase_type = data.purchase_type
    row.subcontract_type = data.subcontract_type
    row.payment_terms = data.payment_terms
    row.collection_terms = data.collection_terms
    row.related_revenue_no = data.related_revenue_no
    row.related_revenue = data.related_revenue or Decimal(0)
    row.related_revenue_collection_date = data.related_revenue_collection_date
    row.related_revenue_collection_method = data.related_revenue_collection_method
    row.due_date = data.payment_due_date
    row.actual_payment_date = data.actual_payment_date
    row.payment_type = data.payment_type
    row.cash_paid_amount = cash_paid
    row.note_issued_amount = note_issued
    row.note_maturity_date = data.note_maturity_date
    row.paid_amount = payment_amount
    row.outstanding_amount = max(debt_amount - payment_amount, Decimal(0))
    row.status = "paid" if row.outstanding_amount <= 0 and debt_amount > 0 else "outstanding"
    row.notes = data.notes


@router.get("/management/payables")
def management_payables(db: Session = Depends(get_db), _=Depends(get_current_user)):
    today = date.today()
    rows = db.query(AccountsPayable).order_by(
        AccountsPayable.due_date.asc(),
        AccountsPayable.id.desc(),
    ).all()

    items = [_payable_dict(row, today) for row in rows]
    total_outstanding = sum(i["payable_balance"] for i in items)
    overdue_amount = sum(i["payable_balance"] for i in items if i["overdue"])
    due_30 = sum(
        i["payable_balance"] for i in items
        if not i["overdue"] and i["days_left"] is not None and i["days_left"] <= 30
    )

    return {
        "items": items,
        "summary": {
            "total_outstanding": total_outstanding,
            "overdue_amount": overdue_amount,
            "due_30": due_30,
        },
    }


@router.post("/management/payables")
def create_payable(data: PayableUpsert, db: Session = Depends(get_db),
                   _=Depends(get_current_user)):
    row = AccountsPayable(issue_date=data.debt_date or date.today())
    _apply_payable(row, data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _payable_dict(row)


@router.put("/management/payables/{pid}")
def update_payable(pid: int, data: PayableUpsert, db: Session = Depends(get_db),
                   _=Depends(get_current_user)):
    row = db.query(AccountsPayable).filter(AccountsPayable.id == pid).first()
    if not row:
        raise HTTPException(404, "채무 정보를 찾을 수 없습니다.")
    _apply_payable(row, data)
    db.commit()
    db.refresh(row)
    return _payable_dict(row)


# ══════════════════════════════════════════════════════
# 손익계산서
# ══════════════════════════════════════════════════════
@router.get("/reports/profit-loss")
def profit_loss_report(year: Optional[int] = None, month: Optional[int] = None,
                       db: Session = Depends(get_db), _=Depends(get_current_user)):
    now = datetime.now()
    target_year  = year  or now.year
    target_month = month or now.month

    def get_revenue(y, m=None):
        q = db.query(sqlfunc.sum(SalesBill.bill_amount)).filter(
            SalesBill.status == APPROVED_SALES_BILL_STATUS,
            sqlfunc.extract("year", SalesBill.bill_date) == y,
        )
        if m: q = q.filter(sqlfunc.extract("month", SalesBill.bill_date) == m)
        return float(q.scalar() or 0)

    def get_cost(y, m=None):
        q = db.query(sqlfunc.sum(CostInput.amount)).filter(
            sqlfunc.extract("year", CostInput.input_date) == y,
        )
        if m: q = q.filter(sqlfunc.extract("month", CostInput.input_date) == m)
        return float(q.scalar() or 0)

    # 당월
    rev_m  = get_revenue(target_year, target_month)
    cost_m = get_cost(target_year,    target_month)
    gp_m   = rev_m - cost_m

    # 누계 (1월~당월)
    rev_ytd  = get_revenue(target_year)
    cost_ytd = get_cost(target_year)
    gp_ytd   = rev_ytd - cost_ytd

    # 전년 동월
    rev_py   = get_revenue(target_year - 1, target_month)
    cost_py  = get_cost(target_year - 1,    target_month)
    gp_py    = rev_py - cost_py

    # 월별 트렌드
    monthly = []
    for m in range(1, 13):
        rv = get_revenue(target_year, m)
        cs = get_cost(target_year, m)
        monthly.append({"month": m, "revenue": rv, "cost": cs, "gross_profit": rv - cs})

    def pct(a, b): return round(a / b * 100, 1) if b else 0
    def yoy(curr, prev): return round((curr - prev) / prev * 100, 1) if prev else None

    return {
        "year": target_year, "month": target_month,
        "current": {
            "revenue": rev_m, "cost": cost_m, "gross_profit": gp_m,
            "sga": 0, "operating_income": gp_m,
            "gross_margin": pct(gp_m, rev_m),
            "op_margin":    pct(gp_m, rev_m),
        },
        "ytd": {
            "revenue": rev_ytd, "cost": cost_ytd, "gross_profit": gp_ytd,
            "sga": 0, "operating_income": gp_ytd,
            "gross_margin": pct(gp_ytd, rev_ytd),
            "op_margin":    pct(gp_ytd, rev_ytd),
        },
        "prior_year": {
            "revenue": rev_py, "cost": cost_py, "gross_profit": gp_py,
            "gross_margin": pct(gp_py, rev_py),
        },
        "yoy_revenue": yoy(rev_m, rev_py),
        "monthly": monthly,
    }
