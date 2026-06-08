from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from typing import Optional, List
from decimal import Decimal
from ..database import get_db
from ..models.budget import Budget, BudgetItem
from ..models.purchase import CostInput
from ..utils.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["예산·원가"])


class BudgetItemIn(BaseModel):
    cost_code_id: Optional[int] = None
    cost_type: Optional[str] = None
    item_name: Optional[str] = None
    budgeted_amount: Decimal = Decimal(0)
    execution_amount: Decimal = Decimal(0)
    notes: Optional[str] = None


class BudgetCreate(BaseModel):
    contract_id: Optional[int] = None
    site_id: Optional[int] = None
    version: int = 1
    budget_name: Optional[str] = None
    total_amount: Decimal = Decimal(0)
    notes: Optional[str] = None
    items: List[BudgetItemIn] = []


@router.get("/budgets")
def list_budgets(site_id: Optional[int] = None, contract_id: Optional[int] = None,
                 db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Budget)
    if site_id:
        q = q.filter(Budget.site_id == site_id)
    if contract_id:
        q = q.filter(Budget.contract_id == contract_id)
    return q.order_by(Budget.version.desc()).all()


@router.get("/budgets/{bid}")
def get_budget(bid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    b = db.query(Budget).filter(Budget.id == bid).first()
    if not b:
        raise HTTPException(status_code=404, detail="예산을 찾을 수 없습니다.")
    return b


@router.post("/budgets")
def create_budget(data: BudgetCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    items = data.items
    b = Budget(**data.dict(exclude={"items"}), created_by=current.id)
    db.add(b)
    db.flush()
    for item in items:
        bi = BudgetItem(**item.dict(), budget_id=b.id)
        db.add(bi)
    db.commit()
    db.refresh(b)
    return b


@router.put("/budgets/{bid}")
def update_budget(bid: int, data: BudgetCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    b = db.query(Budget).filter(Budget.id == bid).first()
    if not b:
        raise HTTPException(status_code=404, detail="예산을 찾을 수 없습니다.")
    items = data.items
    for field, val in data.dict(exclude={"items"}, exclude_none=True).items():
        setattr(b, field, val)
    db.query(BudgetItem).filter(BudgetItem.budget_id == bid).delete()
    for item in items:
        bi = BudgetItem(**item.dict(), budget_id=b.id)
        db.add(bi)
    db.commit()
    return b


@router.get("/cost-analysis")
def cost_analysis(site_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    budget = db.query(Budget).filter(Budget.site_id == site_id, Budget.status == "active").first()

    actual_by_type = db.query(
        CostInput.cost_type,
        sqlfunc.sum(CostInput.amount).label("actual"),
    ).filter(CostInput.site_id == site_id).group_by(CostInput.cost_type).all()
    actual_dict = {r.cost_type: float(r.actual) for r in actual_by_type}

    result = []
    if budget:
        for item in budget.items:
            actual = actual_dict.get(item.cost_type, 0)
            budget_amt = float(item.budgeted_amount)
            exec_amt = float(item.execution_amount)
            result.append({
                "cost_type": item.cost_type,
                "item_name": item.item_name,
                "budgeted": budget_amt,
                "execution": exec_amt,
                "actual": actual,
                "remaining": budget_amt - actual,
                "rate": round(actual / budget_amt * 100, 1) if budget_amt > 0 else 0,
            })
    return {
        "site_id": site_id,
        "budget_id": budget.id if budget else None,
        "items": result,
        "total_actual": sum(v for v in actual_dict.values()),
    }
