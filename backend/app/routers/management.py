from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from typing import Optional
from decimal import Decimal
from datetime import datetime, date, timedelta
from ..database import get_db
from ..models.management import DeptBudget
from ..models.accounting import AccountsReceivable, AccountsPayable
from ..models.sales import ProgressBilling, Collection, Contract
from ..models.purchase import CostInput, SubcontractBilling
from ..models.execution import Project
from ..utils.auth import get_current_user
from ..utils import to_kst, to_kst_date
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["경영"])

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
@router.get("/management/analysis")
def management_analysis(year: Optional[int] = None,
                        db: Session = Depends(get_db), _=Depends(get_current_user)):
    now = datetime.now()
    target_year = year or now.year

    # 월별 수주·매출 (12개월)
    monthly = []
    for m in range(1, 13):
        rev = db.query(sqlfunc.sum(ProgressBilling.billing_amount)).filter(
            ProgressBilling.status == "approved",
            sqlfunc.extract("year",  ProgressBilling.billing_date) == target_year,
            sqlfunc.extract("month", ProgressBilling.billing_date) == m,
        ).scalar() or 0
        orders = db.query(sqlfunc.sum(Contract.current_amount)).filter(
            sqlfunc.extract("year",  Contract.contract_date) == target_year,
            sqlfunc.extract("month", Contract.contract_date) == m,
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
        rev = float(db.query(sqlfunc.sum(ProgressBilling.billing_amount)).filter(
            ProgressBilling.status == "approved",
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
@router.get("/management/receivables")
def management_receivables(db: Session = Depends(get_db), _=Depends(get_current_user)):
    today = date.today()
    rows = db.query(AccountsReceivable).filter(
        AccountsReceivable.status.in_(["outstanding", "partial"])
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
        items.append({
            "id": r.id, "billing_id": r.billing_id,
            "issue_date": to_kst_date(r.issue_date), "due_date": to_kst_date(r.due_date),
            "billing_amount":    float(r.billing_amount or 0),
            "collected_amount":  float(r.collected_amount or 0),
            "outstanding_amount": float(r.outstanding_amount or 0),
            "status": r.status, "overdue_days": max(0, days),
        })
    items.sort(key=lambda x: x["overdue_days"], reverse=True)

    total_outstanding = sum(i["outstanding_amount"] for i in items)
    return {"items": items, "aging": aging_buckets, "total_outstanding": total_outstanding}


# ══════════════════════════════════════════════════════
# 채무 관리 — Payment Schedule
# ══════════════════════════════════════════════════════
@router.get("/management/payables")
def management_payables(db: Session = Depends(get_db), _=Depends(get_current_user)):
    today = date.today()
    rows = db.query(AccountsPayable).filter(
        AccountsPayable.status.in_(["outstanding", "partial"])
    ).all()

    items = []
    for r in rows:
        days_left = (r.due_date - today).days if r.due_date else None
        items.append({
            "id": r.id,
            "issue_date": to_kst_date(r.issue_date), "due_date": to_kst_date(r.due_date),
            "total_amount":      float(r.total_amount or 0),
            "paid_amount":       float(r.paid_amount or 0),
            "outstanding_amount": float(r.outstanding_amount or 0),
            "status": r.status, "days_left": days_left,
            "overdue": days_left is not None and days_left < 0,
        })
    items.sort(key=lambda x: (x.get("due_date") or "9999"))

    total_outstanding = sum(i["outstanding_amount"] for i in items)
    overdue_amount    = sum(i["outstanding_amount"] for i in items if i["overdue"])
    due_30 = sum(i["outstanding_amount"] for i in items
                 if not i["overdue"] and i["days_left"] is not None and i["days_left"] <= 30)

    return {
        "items": items,
        "summary": {
            "total_outstanding": total_outstanding,
            "overdue_amount":    overdue_amount,
            "due_30":            due_30,
        },
    }


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
        q = db.query(sqlfunc.sum(ProgressBilling.billing_amount)).filter(
            ProgressBilling.status == "approved",
            sqlfunc.extract("year", ProgressBilling.billing_date) == y,
        )
        if m: q = q.filter(sqlfunc.extract("month", ProgressBilling.billing_date) == m)
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
