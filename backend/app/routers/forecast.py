from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
import json

from fastapi import APIRouter, Depends
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.accounting import AccountsPayable, AccountsReceivable
from ..models.execution import APBill, Project, ProjectPurchasePlanRow, ProjectSalesPlanRow, SalesBill
from ..models.sales import SalesManagementWeeklyRow
from ..utils.auth import get_current_user

router = APIRouter(prefix="/api", tags=["dashboard"])

MONTH_KEYS = [f"{month}월" for month in range(1, 13)]
APPROVED_STATUSES = {"승인", "발행완료", "지급완료", "approved"}
ORDER_PROBABILITY_WEIGHT = {"A": 1.0, "B": 0.8, "C": 0.5, "D": 0.2, "E": 0.0}


def _num(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _decode_json(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _project_meta(project: Project | None) -> dict:
    if not project:
        return {}
    raw = project.notes or ""
    marker_start = raw.rfind("\n---")
    marker_end = raw.find("---\n", marker_start + 4) if marker_start >= 0 else -1
    if marker_start < 0 or marker_end < 0:
        return {}
    return _decode_json(raw[marker_end + 4:])


def _project_business_division(project: Project | None) -> str:
    meta = _project_meta(project)
    return meta.get("business_division") or getattr(project, "pm_dept", None) or "미지정"


def _project_business_category(project: Project | None) -> str:
    meta = _project_meta(project)
    return meta.get("business_category") or "미지정"


def _sales_bill_amount(row: SalesBill) -> float:
    return _num(row.bill_amount or row.total_amount)


def _ap_bill_amount(row: APBill) -> float:
    return _num(row.total_amount or row.bill_amount)


def _empty_months() -> dict[int, float]:
    return {month: 0.0 for month in range(1, 13)}


def _add_month_value(bucket: dict[int, float], when: date | None, amount: float, year: int) -> None:
    if when and when.year == year:
        bucket[when.month] += amount


def _ytd(monthly: dict[int, float], month: int) -> float:
    return sum(monthly.get(idx, 0.0) for idx in range(1, month + 1))


def _row_total(data: dict, candidates: list[str]) -> float:
    for key in candidates:
        value = _num(data.get(key))
        if value:
            return value
    return 0.0


def _sum_project_sales_plan_months(db: Session, year: int) -> dict[int, float]:
    monthly = _empty_months()
    rows = db.query(ProjectSalesPlanRow).filter(ProjectSalesPlanRow.plan_year == year).all()
    for row in rows:
        data = _decode_json(row.data_json)
        for month_key in MONTH_KEYS:
            month = int(month_key[:-1])
            amount = _row_total(
                data,
                [
                    f"revenue_progress_{month_key}",
                    f"tax_invoice_revenue_{month_key}",
                    f"revenue_{month_key}",
                    f"{month_key}매출",
                ],
            )
            monthly[month] += amount
    return monthly


def _sum_project_purchase_plan_months(db: Session, year: int) -> dict[int, float]:
    monthly = _empty_months()
    rows = db.query(ProjectPurchasePlanRow).filter(ProjectPurchasePlanRow.plan_year == year).all()
    for row in rows:
        data = _decode_json(row.data_json)
        for month_key in MONTH_KEYS:
            month = int(month_key[:-1])
            amount = (
                _num(data.get(f"input_amount_{month_key}"))
                or _num(data.get(f"material_input_{month_key}")) + _num(data.get(f"subcontract_input_{month_key}"))
            )
            monthly[month] += amount
    return monthly


def _actual_sales_months(db: Session, year: int) -> dict[int, float]:
    monthly = _empty_months()
    rows = db.query(SalesBill).filter(SalesBill.bill_date.isnot(None), SalesBill.status.in_(APPROVED_STATUSES)).all()
    for row in rows:
        _add_month_value(monthly, row.bill_date, _sales_bill_amount(row), year)
    return monthly


def _actual_purchase_months(db: Session, year: int) -> dict[int, float]:
    monthly = _empty_months()
    rows = db.query(APBill).filter(APBill.bill_date.isnot(None), APBill.status.in_(APPROVED_STATUSES)).all()
    for row in rows:
        _add_month_value(monthly, row.bill_date, _ap_bill_amount(row), year)
    return monthly


def _order_months(db: Session, year: int) -> dict[int, float]:
    monthly = _empty_months()
    rows = db.query(Project).filter(Project.contract_start.isnot(None)).all()
    for row in rows:
        _add_month_value(monthly, row.contract_start, _num(row.contract_amount), year)
    return monthly


def _latest_sales_management_rows(db: Session) -> list[dict]:
    latest_week = db.query(sqlfunc.max(SalesManagementWeeklyRow.week_start)).scalar()
    if not latest_week:
        return []
    rows = db.query(SalesManagementWeeklyRow).filter(SalesManagementWeeklyRow.week_start == latest_week).all()
    return [_decode_json(row.data_json) for row in rows]


def _sales_pipeline_summary(db: Session) -> dict:
    rows = _latest_sales_management_rows(db)
    by_probability = defaultdict(float)
    count_by_probability = defaultdict(int)
    by_status = defaultdict(float)
    total = 0.0
    weighted = 0.0

    for data in rows:
        probability = data.get("probability") or data.get("수주확도") or "미지정"
        status = data.get("sales_status") or data.get("영업상태") or "미지정"
        amount = _num(data.get("expected_order_amount") or data.get("발주예상금액"))
        total += amount
        weighted += amount * ORDER_PROBABILITY_WEIGHT.get(str(probability).upper(), 0.0)
        by_probability[str(probability)] += amount
        count_by_probability[str(probability)] += 1
        by_status[str(status)] += amount

    return {
        "total": total,
        "weighted": weighted,
        "by_probability": [
            {"name": key, "value": value, "count": count_by_probability[key]}
            for key, value in sorted(by_probability.items())
        ],
        "by_status": [{"name": key, "value": value} for key, value in sorted(by_status.items())],
    }


def _risk_summary(db: Session, today: date) -> dict:
    ar_rows = db.query(AccountsReceivable).all()
    ap_rows = db.query(AccountsPayable).all()

    ar_total = sum(_num(row.outstanding_amount) for row in ar_rows)
    ar_overdue = sum(_num(row.outstanding_amount) for row in ar_rows if row.due_date and row.due_date < today)
    ap_total = sum(_num(row.outstanding_amount) for row in ap_rows)
    ap_overdue = sum(_num(row.outstanding_amount) for row in ap_rows if row.due_date and row.due_date < today)
    ap_due_30 = sum(
        _num(row.outstanding_amount)
        for row in ap_rows
        if row.due_date and 0 <= (row.due_date - today).days <= 30
    )

    ar_buckets = {"정상": 0.0, "30일 이하": 0.0, "31~60일": 0.0, "61일 이상": 0.0}
    for row in ar_rows:
        amount = _num(row.outstanding_amount)
        if not row.due_date or row.due_date >= today:
            ar_buckets["정상"] += amount
            continue
        overdue_days = (today - row.due_date).days
        if overdue_days <= 30:
            ar_buckets["30일 이하"] += amount
        elif overdue_days <= 60:
            ar_buckets["31~60일"] += amount
        else:
            ar_buckets["61일 이상"] += amount

    return {
        "ar_total": ar_total,
        "ar_overdue": ar_overdue,
        "ar_buckets": [{"name": key, "value": value} for key, value in ar_buckets.items()],
        "ap_total": ap_total,
        "ap_overdue": ap_overdue,
        "ap_due_30": ap_due_30,
    }


def _summary_rows(db: Session, year: int, group_by: str) -> list[dict]:
    rows: dict[str, dict] = {}

    def ensure(name: str) -> dict:
        if name not in rows:
            rows[name] = {
                "name": name,
                "orders": 0.0,
                "revenue": 0.0,
                "purchase": 0.0,
                "profit": 0.0,
                "profit_rate": 0.0,
                "receivable": 0.0,
                "payable": 0.0,
            }
        return rows[name]

    project_map = {project.id: project for project in db.query(Project).all()}
    for project in project_map.values():
        key = _project_business_division(project) if group_by == "division" else _project_business_category(project)
        if project.contract_start and project.contract_start.year == year:
            ensure(key)["orders"] += _num(project.contract_amount)

    for bill in db.query(SalesBill).filter(SalesBill.status.in_(APPROVED_STATUSES)).all():
        project = project_map.get(bill.project_id)
        key = _project_business_division(project) if group_by == "division" else _project_business_category(project)
        if bill.bill_date and bill.bill_date.year == year:
            ensure(key)["revenue"] += _sales_bill_amount(bill)

    for bill in db.query(APBill).filter(APBill.status.in_(APPROVED_STATUSES)).all():
        project = project_map.get(bill.project_id)
        key = _project_business_division(project) if group_by == "division" else _project_business_category(project)
        if bill.bill_date and bill.bill_date.year == year:
            ensure(key)["purchase"] += _ap_bill_amount(bill)

    for ar in db.query(AccountsReceivable).all():
        project = project_map.get(ar.project_id)
        key = _project_business_division(project) if group_by == "division" else _project_business_category(project)
        ensure(key)["receivable"] += _num(ar.outstanding_amount)

    for ap in db.query(AccountsPayable).all():
        project = None
        if ap.ref_type == "ap_bill" and ap.ref_id:
            bill = db.query(APBill).filter(APBill.id == ap.ref_id).first()
            project = project_map.get(bill.project_id) if bill else None
        key = _project_business_division(project) if group_by == "division" else _project_business_category(project)
        ensure(key)["payable"] += _num(ap.outstanding_amount)

    for row in rows.values():
        row["profit"] = row["revenue"] - row["purchase"]
        row["profit_rate"] = (row["profit"] / row["revenue"] * 100) if row["revenue"] else 0.0

    result = sorted(rows.values(), key=lambda item: item["revenue"], reverse=True)
    total = {
        "name": "합계(전사)",
        "orders": sum(row["orders"] for row in result),
        "revenue": sum(row["revenue"] for row in result),
        "purchase": sum(row["purchase"] for row in result),
        "receivable": sum(row["receivable"] for row in result),
        "payable": sum(row["payable"] for row in result),
    }
    total["profit"] = total["revenue"] - total["purchase"]
    total["profit_rate"] = (total["profit"] / total["revenue"] * 100) if total["revenue"] else 0.0
    return [total, *result] if result else [total]


@router.get("/dashboard")
def get_dashboard(
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    today = date.today()
    target_year = year or today.year
    target_month = max(1, min(month or today.month, 12))

    planned_revenue = _sum_project_sales_plan_months(db, target_year)
    planned_purchase = _sum_project_purchase_plan_months(db, target_year)
    actual_revenue = _actual_sales_months(db, target_year)
    actual_purchase = _actual_purchase_months(db, target_year)
    orders = _order_months(db, target_year)

    monthly = []
    for idx in range(1, 13):
        plan = planned_revenue[idx]
        actual = actual_revenue[idx]
        purchase = actual_purchase[idx]
        monthly.append(
            {
                "month": idx,
                "label": f"{idx}월",
                "planned_revenue": plan,
                "actual_revenue": actual,
                "planned_purchase": planned_purchase[idx],
                "actual_purchase": purchase,
                "orders": orders[idx],
                "profit": actual - purchase,
                "cumulative_plan": _ytd(planned_revenue, idx),
                "cumulative_actual": _ytd(actual_revenue, idx),
                "achievement_rate": (actual / plan * 100) if plan else 0.0,
            }
        )

    ytd_orders = _ytd(orders, target_month)
    ytd_plan_revenue = _ytd(planned_revenue, target_month)
    ytd_actual_revenue = _ytd(actual_revenue, target_month)
    ytd_purchase = _ytd(actual_purchase, target_month)
    ytd_profit = ytd_actual_revenue - ytd_purchase
    pipeline = _sales_pipeline_summary(db)
    risk = _risk_summary(db, today)

    return {
        "period": {"year": target_year, "month": target_month, "today": today.isoformat()},
        "kpi": {
            "ytd_orders": ytd_orders,
            "pipeline_total": pipeline["total"],
            "pipeline_weighted": pipeline["weighted"],
            "order_backlog": max(0.0, ytd_orders - ytd_actual_revenue),
            "ytd_plan_revenue": ytd_plan_revenue,
            "ytd_actual_revenue": ytd_actual_revenue,
            "achievement_rate": (ytd_actual_revenue / ytd_plan_revenue * 100) if ytd_plan_revenue else 0.0,
            "ytd_purchase": ytd_purchase,
            "ytd_profit": ytd_profit,
            "ytd_profit_rate": (ytd_profit / ytd_actual_revenue * 100) if ytd_actual_revenue else 0.0,
            "ar_total": risk["ar_total"],
            "ar_overdue": risk["ar_overdue"],
            "ap_total": risk["ap_total"],
            "ap_due_30": risk["ap_due_30"],
        },
        "monthly": monthly,
        "pipeline": pipeline,
        "risk": risk,
        "summary": {
            "division": _summary_rows(db, target_year, "division"),
            "business_group": _summary_rows(db, target_year, "business_group"),
        },
    }
