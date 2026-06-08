from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from typing import Optional
from decimal import Decimal
from datetime import date
from ..database import get_db
from ..models.forecast import RevenueForecast, SalesPipeline, FundPlan
from ..models.sales import Contract, ProgressBilling, Collection
from ..models.purchase import CostInput
from ..models.accounting import AccountsReceivable
from ..models.master import Site
from ..utils.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["경영예측"])


# ── 대시보드 KPI ──────────────────────────────────────────
@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _=Depends(get_current_user)):
    # 수주잔고 (진행중 계약 잔여금액)
    active_contracts = db.query(sqlfunc.sum(Contract.current_amount)).filter(Contract.status == "active").scalar() or 0

    # 당월 매출 (기성 승인)
    from datetime import datetime
    now = datetime.now()
    monthly_billing = db.query(sqlfunc.sum(ProgressBilling.billing_amount)).filter(
        ProgressBilling.status == "approved",
        sqlfunc.extract("year", ProgressBilling.billing_date) == now.year,
        sqlfunc.extract("month", ProgressBilling.billing_date) == now.month,
    ).scalar() or 0

    # 미수금
    outstanding_ar = db.query(sqlfunc.sum(AccountsReceivable.outstanding_amount)).filter(
        AccountsReceivable.status.in_(["outstanding", "partial"])
    ).scalar() or 0

    # 원가 투입 (당월)
    monthly_cost = db.query(sqlfunc.sum(CostInput.amount)).filter(
        sqlfunc.extract("year", CostInput.input_date) == now.year,
        sqlfunc.extract("month", CostInput.input_date) == now.month,
    ).scalar() or 0

    # 진행중 현장 수
    active_sites = db.query(sqlfunc.count(Site.id)).filter(Site.status == "active").scalar() or 0

    # 수주 파이프라인
    pipeline_total = db.query(sqlfunc.sum(SalesPipeline.expected_amount)).filter(
        SalesPipeline.status == "active"
    ).scalar() or 0
    pipeline_weighted = db.query(sqlfunc.sum(SalesPipeline.weighted_amount)).filter(
        SalesPipeline.status == "active"
    ).scalar() or 0

    # 최근 기성 현황 (최근 5건)
    recent_billings = db.query(ProgressBilling).filter(
        ProgressBilling.status == "approved"
    ).order_by(ProgressBilling.billing_date.desc()).limit(5).all()

    # 현장별 원가율
    site_cost_rates = db.query(
        Site.site_name,
        sqlfunc.sum(ProgressBilling.billing_amount).label("revenue"),
        sqlfunc.sum(CostInput.amount).label("cost"),
    ).outerjoin(ProgressBilling, ProgressBilling.site_id == Site.id)\
     .outerjoin(CostInput, CostInput.site_id == Site.id)\
     .filter(Site.status == "active")\
     .group_by(Site.id, Site.site_name)\
     .limit(10).all()

    # ── 누계 (1월~당월) ──
    ytd_revenue = db.query(sqlfunc.sum(ProgressBilling.billing_amount)).filter(
        ProgressBilling.status == "approved",
        sqlfunc.extract("year", ProgressBilling.billing_date) == now.year,
    ).scalar() or 0

    ytd_orders = db.query(sqlfunc.sum(Contract.current_amount)).filter(
        sqlfunc.extract("year", Contract.contract_date) == now.year,
    ).scalar() or 0

    ytd_cost = db.query(sqlfunc.sum(CostInput.amount)).filter(
        sqlfunc.extract("year", CostInput.input_date) == now.year,
    ).scalar() or 0

    # ── 월별 추이 (최근 12개월) ──
    monthly_trend = []
    for i in range(11, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        rev = db.query(sqlfunc.sum(ProgressBilling.billing_amount)).filter(
            ProgressBilling.status == "approved",
            sqlfunc.extract("year",  ProgressBilling.billing_date) == y,
            sqlfunc.extract("month", ProgressBilling.billing_date) == m,
        ).scalar() or 0
        ord_ = db.query(sqlfunc.sum(Contract.current_amount)).filter(
            sqlfunc.extract("year",  Contract.contract_date) == y,
            sqlfunc.extract("month", Contract.contract_date) == m,
        ).scalar() or 0
        cost = db.query(sqlfunc.sum(CostInput.amount)).filter(
            sqlfunc.extract("year",  CostInput.input_date) == y,
            sqlfunc.extract("month", CostInput.input_date) == m,
        ).scalar() or 0
        monthly_trend.append({
            "label": f"{y}-{m:02d}",
            "short": f"{m}월",
            "revenue": float(rev),
            "orders":  float(ord_),
            "cost":    float(cost),
        })

    # ── 손익 요약 ──
    gross_profit = float(ytd_revenue) - float(ytd_cost)
    gross_margin = round(gross_profit / float(ytd_revenue) * 100, 1) if ytd_revenue else 0
    # 판관비: 별도 집계 없으면 0 (추후 연동)
    sga = 0
    operating_income = gross_profit - sga
    operating_margin = round(operating_income / float(ytd_revenue) * 100, 1) if ytd_revenue else 0

    # 당월 손익
    monthly_gross = float(monthly_billing) - float(monthly_cost)
    monthly_margin = round(monthly_gross / float(monthly_billing) * 100, 1) if monthly_billing else 0

    return {
        "kpi": {
            "order_backlog":    float(active_contracts),
            "monthly_billing":  float(monthly_billing),
            "outstanding_ar":   float(outstanding_ar),
            "monthly_cost":     float(monthly_cost),
            "active_sites":     int(active_sites),
            "pipeline_total":   float(pipeline_total),
            "pipeline_weighted":float(pipeline_weighted),
            "ytd_revenue":      float(ytd_revenue),
            "ytd_orders":       float(ytd_orders),
            "ytd_cost":         float(ytd_cost),
            "gross_margin":     gross_margin,
            "operating_margin": operating_margin,
            "monthly_margin":   monthly_margin,
        },
        "monthly_trend": monthly_trend,
        "pl_summary": {
            "revenue":          float(ytd_revenue),
            "cost":             float(ytd_cost),
            "gross_profit":     gross_profit,
            "gross_margin":     gross_margin,
            "sga":              sga,
            "operating_income": operating_income,
            "operating_margin": operating_margin,
            "monthly_revenue":  float(monthly_billing),
            "monthly_cost":     float(monthly_cost),
            "monthly_gross":    monthly_gross,
            "monthly_margin":   monthly_margin,
        },
        "recent_billings": [
            {
                "billing_no":    b.billing_no,
                "site_id":       b.site_id,
                "billing_date":  str(b.billing_date),
                "billing_amount":float(b.billing_amount),
            } for b in recent_billings
        ],
        "site_cost_rates": [
            {
                "site_name": r.site_name,
                "revenue":   float(r.revenue or 0),
                "cost":      float(r.cost or 0),
                "cost_rate": round(float(r.cost or 0) / float(r.revenue) * 100, 1) if r.revenue else 0,
            } for r in site_cost_rates
        ],
    }


# ── 매출 예측 ──────────────────────────────────────────
class RevenueForecastCreate(BaseModel):
    site_id: int
    forecast_year: int
    forecast_month: int
    forecast_amount: Decimal = Decimal(0)
    notes: Optional[str] = None


@router.get("/revenue-forecasts")
def list_revenue_forecasts(forecast_year: Optional[int] = None, site_id: Optional[int] = None,
                            db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(RevenueForecast)
    if forecast_year:
        q = q.filter(RevenueForecast.forecast_year == forecast_year)
    if site_id:
        q = q.filter(RevenueForecast.site_id == site_id)
    return q.order_by(RevenueForecast.forecast_year, RevenueForecast.forecast_month).all()


@router.post("/revenue-forecasts")
def upsert_revenue_forecast(data: RevenueForecastCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    existing = db.query(RevenueForecast).filter(
        RevenueForecast.site_id == data.site_id,
        RevenueForecast.forecast_year == data.forecast_year,
        RevenueForecast.forecast_month == data.forecast_month,
    ).first()
    if existing:
        existing.forecast_amount = data.forecast_amount
        existing.notes = data.notes
    else:
        f = RevenueForecast(**data.dict(), created_by=current.id)
        db.add(f)
    db.commit()
    return {"message": "저장되었습니다."}


# ── 수주 파이프라인 ──────────────────────────────────────────
class SalesPipelineCreate(BaseModel):
    pipeline_name: str
    client_id: Optional[int] = None
    expected_amount: Decimal = Decimal(0)
    probability: int = 50
    expected_date: Optional[date] = None
    notes: Optional[str] = None


@router.get("/sales-pipelines")
def list_sales_pipelines(status: Optional[str] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(SalesPipeline)
    if status:
        q = q.filter(SalesPipeline.status == status)
    return q.order_by(SalesPipeline.expected_date).all()


@router.post("/sales-pipelines")
def create_sales_pipeline(data: SalesPipelineCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    weighted = float(data.expected_amount) * data.probability / 100
    p = SalesPipeline(
        **data.dict(),
        weighted_amount=Decimal(str(weighted)),
        sales_manager_id=current.id, created_by=current.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put("/sales-pipelines/{pid}")
def update_sales_pipeline(pid: int, data: SalesPipelineCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    p = db.query(SalesPipeline).filter(SalesPipeline.id == pid).first()
    if not p:
        raise HTTPException(status_code=404, detail="파이프라인을 찾을 수 없습니다.")
    for field, val in data.dict(exclude_none=True).items():
        setattr(p, field, val)
    p.weighted_amount = float(p.expected_amount) * p.probability / 100
    db.commit()
    return p


@router.patch("/sales-pipelines/{pid}/status")
def update_pipeline_status(pid: int, status: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    p = db.query(SalesPipeline).filter(SalesPipeline.id == pid).first()
    if not p:
        raise HTTPException(status_code=404, detail="파이프라인을 찾을 수 없습니다.")
    p.status = status
    db.commit()
    return {"message": "상태가 변경되었습니다."}


# ── 자금 계획 ──────────────────────────────────────────
class FundPlanCreate(BaseModel):
    plan_year: int
    plan_month: int
    planned_income: Decimal = Decimal(0)
    planned_expense: Decimal = Decimal(0)
    notes: Optional[str] = None


@router.get("/fund-plans")
def list_fund_plans(plan_year: Optional[int] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(FundPlan)
    if plan_year:
        q = q.filter(FundPlan.plan_year == plan_year)
    return q.order_by(FundPlan.plan_year, FundPlan.plan_month).all()


@router.post("/fund-plans")
def upsert_fund_plan(data: FundPlanCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    existing = db.query(FundPlan).filter(
        FundPlan.plan_year == data.plan_year,
        FundPlan.plan_month == data.plan_month,
    ).first()
    planned_balance = float(data.planned_income) - float(data.planned_expense)
    if existing:
        existing.planned_income = data.planned_income
        existing.planned_expense = data.planned_expense
        existing.planned_balance = planned_balance
        existing.notes = data.notes
    else:
        f = FundPlan(**data.dict(), planned_balance=planned_balance, created_by=current.id)
        db.add(f)
    db.commit()
    return {"message": "저장되었습니다."}


# ── 손익 분석 리포트 ──────────────────────────────────────────
@router.get("/reports/profit-loss")
def profit_loss_report(site_id: Optional[int] = None, year: Optional[int] = None,
                        db: Session = Depends(get_db), _=Depends(get_current_user)):
    from datetime import datetime
    target_year = year or datetime.now().year

    q_billing = db.query(
        ProgressBilling.site_id,
        sqlfunc.sum(ProgressBilling.billing_amount).label("revenue"),
    ).filter(
        ProgressBilling.status == "approved",
        sqlfunc.extract("year", ProgressBilling.billing_date) == target_year,
    )
    if site_id:
        q_billing = q_billing.filter(ProgressBilling.site_id == site_id)
    billing_data = {r.site_id: float(r.revenue or 0) for r in q_billing.group_by(ProgressBilling.site_id).all()}

    q_cost = db.query(
        CostInput.site_id,
        sqlfunc.sum(CostInput.amount).label("cost"),
    ).filter(
        sqlfunc.extract("year", CostInput.input_date) == target_year,
    )
    if site_id:
        q_cost = q_cost.filter(CostInput.site_id == site_id)
    cost_data = {r.site_id: float(r.cost or 0) for r in q_cost.group_by(CostInput.site_id).all()}

    sites_q = db.query(Site).filter(Site.status.in_(["active", "completed"]))
    if site_id:
        sites_q = sites_q.filter(Site.id == site_id)

    result = []
    for site in sites_q.all():
        revenue = billing_data.get(site.id, 0)
        cost = cost_data.get(site.id, 0)
        profit = revenue - cost
        cost_rate = round(cost / revenue * 100, 1) if revenue > 0 else 0
        result.append({
            "site_id": site.id,
            "site_name": site.site_name,
            "site_code": site.site_code,
            "revenue": revenue,
            "cost": cost,
            "profit": profit,
            "cost_rate": cost_rate,
        })
    return result
