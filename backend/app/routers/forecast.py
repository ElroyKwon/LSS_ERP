from datetime import datetime
import json

from fastapi import APIRouter, Depends
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.accounting import AccountsReceivable
from ..models.execution import Project, SalesBill
from ..models.purchase import CostInput
from ..models.sales import SalesManagementWeeklyRow
from ..utils.auth import get_current_user

router = APIRouter(prefix="/api", tags=["dashboard"])


APPROVED_SALES_BILL_STATUS = "승인"


def _sum_sales_bills(db: Session, year: int, month: int | None = None) -> float:
    q = db.query(sqlfunc.sum(SalesBill.bill_amount)).filter(
        SalesBill.status == APPROVED_SALES_BILL_STATUS,
        sqlfunc.extract("year", SalesBill.bill_date) == year,
    )
    if month:
        q = q.filter(sqlfunc.extract("month", SalesBill.bill_date) == month)
    return float(q.scalar() or 0)


def _sum_project_orders(db: Session, year: int, month: int | None = None) -> float:
    q = db.query(sqlfunc.sum(Project.contract_amount)).filter(
        sqlfunc.extract("year", Project.contract_start) == year,
    )
    if month:
        q = q.filter(sqlfunc.extract("month", Project.contract_start) == month)
    return float(q.scalar() or 0)


def _sum_cost_inputs(db: Session, year: int, month: int | None = None) -> float:
    q = db.query(sqlfunc.sum(CostInput.amount)).filter(
        sqlfunc.extract("year", CostInput.input_date) == year,
    )
    if month:
        q = q.filter(sqlfunc.extract("month", CostInput.input_date) == month)
    return float(q.scalar() or 0)


def _latest_sales_pipeline_total(db: Session) -> tuple[float, float]:
    latest_week = db.query(sqlfunc.max(SalesManagementWeeklyRow.week_start)).scalar()
    if not latest_week:
        return 0, 0

    total = 0.0
    weighted = 0.0
    rows = db.query(SalesManagementWeeklyRow.data_json).filter(
        SalesManagementWeeklyRow.week_start == latest_week
    ).all()
    probability_map = {"A": 1.0, "B": 0.8, "C": 0.5, "D": 0.2, "E": 0.0}
    for (data_json,) in rows:
        try:
            data = json.loads(data_json or "{}")
        except (TypeError, ValueError):
            continue
        amount = float(
            data.get("current_year_order_total")
            or data.get("order_current_total")
            or data.get("expected_order_amount")
            or data.get("order_amount")
            or 0
        )
        probability = probability_map.get(str(data.get("probability") or data.get("order_probability") or "").upper(), 0)
        total += amount
        weighted += amount * probability
    return total, weighted


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _=Depends(get_current_user)):
    now = datetime.now()

    monthly_billing = _sum_sales_bills(db, now.year, now.month)
    ytd_revenue = _sum_sales_bills(db, now.year)
    ytd_orders = _sum_project_orders(db, now.year)
    monthly_cost = _sum_cost_inputs(db, now.year, now.month)
    ytd_cost = _sum_cost_inputs(db, now.year)
    pipeline_total, pipeline_weighted = _latest_sales_pipeline_total(db)

    outstanding_ar = db.query(sqlfunc.sum(AccountsReceivable.outstanding_amount)).filter(
        AccountsReceivable.status.in_(["outstanding", "partial"])
    ).scalar() or 0
    active_projects = db.query(sqlfunc.count(Project.id)).scalar() or 0
    order_backlog = max(0, float(ytd_orders) - float(ytd_revenue))

    monthly_trend = []
    for i in range(11, -1, -1):
        month = now.month - i
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        monthly_trend.append({
            "label": f"{year}-{month:02d}",
            "short": f"{month}월",
            "revenue": _sum_sales_bills(db, year, month),
            "orders": _sum_project_orders(db, year, month),
            "cost": _sum_cost_inputs(db, year, month),
        })

    gross_profit = ytd_revenue - ytd_cost
    gross_margin = round(gross_profit / ytd_revenue * 100, 1) if ytd_revenue else 0
    operating_income = gross_profit
    operating_margin = gross_margin
    monthly_gross = monthly_billing - monthly_cost
    monthly_margin = round(monthly_gross / monthly_billing * 100, 1) if monthly_billing else 0

    project_rows = []
    projects = db.query(Project).order_by(Project.created_at.desc()).limit(10).all()
    for project in projects:
        revenue = float(db.query(sqlfunc.sum(SalesBill.bill_amount)).filter(
            SalesBill.project_id == project.id,
            SalesBill.status == APPROVED_SALES_BILL_STATUS,
        ).scalar() or 0)
        cost = 0.0
        project_rows.append({
            "site_name": project.project_name,
            "revenue": revenue,
            "cost": cost,
            "cost_rate": round(cost / revenue * 100, 1) if revenue else 0,
        })

    return {
        "kpi": {
            "order_backlog": order_backlog,
            "monthly_billing": monthly_billing,
            "outstanding_ar": float(outstanding_ar),
            "monthly_cost": monthly_cost,
            "active_sites": int(active_projects),
            "pipeline_total": pipeline_total,
            "pipeline_weighted": pipeline_weighted,
            "ytd_revenue": ytd_revenue,
            "ytd_orders": ytd_orders,
            "ytd_cost": ytd_cost,
            "gross_margin": gross_margin,
            "operating_margin": operating_margin,
            "monthly_margin": monthly_margin,
        },
        "monthly_trend": monthly_trend,
        "pl_summary": {
            "revenue": ytd_revenue,
            "cost": ytd_cost,
            "gross_profit": gross_profit,
            "gross_margin": gross_margin,
            "sga": 0,
            "operating_income": operating_income,
            "operating_margin": operating_margin,
            "monthly_revenue": monthly_billing,
            "monthly_cost": monthly_cost,
            "monthly_gross": monthly_gross,
            "monthly_margin": monthly_margin,
        },
        "recent_billings": [],
        "site_cost_rates": project_rows,
    }
