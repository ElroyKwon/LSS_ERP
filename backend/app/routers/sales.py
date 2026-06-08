from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func as sqlfunc
from typing import Optional, List
from decimal import Decimal
from datetime import date
from ..database import get_db
from ..models.sales import Estimate, EstimateItem, Contract, ContractChange, ProgressBilling, Collection, DesignRequest
from ..models.accounting import AccountsReceivable, JournalEntry, JournalLine
from ..models.master import AccountCode
from ..utils.auth import get_current_user
from ..utils import to_kst, to_kst_date
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["영업·수주"])


# ── 견적 ──────────────────────────────────────────
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
class ContractCreate(BaseModel):
    contract_no: str
    site_id: Optional[int] = None
    estimate_id: Optional[int] = None
    client_id: Optional[int] = None
    contract_name: str
    contract_type: str
    revenue_type: str = "general"
    original_amount: Decimal = Decimal(0)
    current_amount: Decimal = Decimal(0)
    original_cost: Decimal = Decimal(0)
    current_cost: Decimal = Decimal(0)
    contract_date: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = "active"
    notes: Optional[str] = None


@router.get("/contracts")
def list_contracts(status: Optional[str] = None, site_id: Optional[int] = None,
                   search: Optional[str] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Contract)
    if status:
        q = q.filter(Contract.status == status)
    if site_id:
        q = q.filter(Contract.site_id == site_id)
    if search:
        q = q.filter(or_(Contract.contract_name.ilike(f"%{search}%"), Contract.contract_no.ilike(f"%{search}%")))
    return q.order_by(Contract.created_at.desc()).all()


@router.get("/contracts/{cid}")
def get_contract(cid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    c = db.query(Contract).filter(Contract.id == cid).first()
    if not c:
        raise HTTPException(status_code=404, detail="계약을 찾을 수 없습니다.")
    return c


@router.post("/contracts")
def create_contract(data: ContractCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    c = Contract(**data.dict(), sales_manager_id=current.id, created_by=current.id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/contracts/{cid}")
def update_contract(cid: int, data: ContractCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    c = db.query(Contract).filter(Contract.id == cid).first()
    if not c:
        raise HTTPException(status_code=404, detail="계약을 찾을 수 없습니다.")
    for field, val in data.dict(exclude_none=True).items():
        setattr(c, field, val)
    db.commit()
    return c


# ── 계약 변경 (설계변경) ──────────────────────────────────────────
class ContractChangeCreate(BaseModel):
    contract_id: int
    change_no: int
    change_date: date
    amount_change: Decimal = Decimal(0)
    cost_change: Decimal = Decimal(0)
    end_date_after: Optional[date] = None
    reason: Optional[str] = None


@router.get("/contract-changes")
def list_contract_changes(contract_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(ContractChange).filter(ContractChange.contract_id == contract_id).order_by(ContractChange.change_no).all()


@router.post("/contract-changes")
def create_contract_change(data: ContractChangeCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    contract = db.query(Contract).filter(Contract.id == data.contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="계약을 찾을 수 없습니다.")
    change = ContractChange(
        contract_id=data.contract_id,
        change_no=data.change_no,
        change_date=data.change_date,
        amount_before=contract.current_amount,
        amount_change=data.amount_change,
        amount_after=contract.current_amount + data.amount_change,
        cost_before=contract.current_cost,
        cost_change=data.cost_change,
        cost_after=contract.current_cost + data.cost_change,
        end_date_before=contract.end_date,
        end_date_after=data.end_date_after or contract.end_date,
        reason=data.reason,
        created_by=current.id,
    )
    contract.current_amount += data.amount_change
    contract.current_cost += data.cost_change
    if data.end_date_after:
        contract.end_date = data.end_date_after
    db.add(change)
    db.commit()
    db.refresh(change)
    return change


# ── 기성 ──────────────────────────────────────────
class ProgressBillingCreate(BaseModel):
    billing_no: str
    contract_id: int
    site_id: Optional[int] = None
    billing_seq: int
    billing_date: date
    progress_rate: Decimal = Decimal(0)
    billing_amount: Decimal = Decimal(0)
    vat_amount: Decimal = Decimal(0)
    total_amount: Decimal = Decimal(0)
    due_date: Optional[date] = None
    notes: Optional[str] = None


@router.get("/progress-billings")
def list_progress_billings(contract_id: Optional[int] = None, site_id: Optional[int] = None,
                            status: Optional[str] = None, db: Session = Depends(get_db),
                            _=Depends(get_current_user)):
    q = db.query(ProgressBilling)
    if contract_id:
        q = q.filter(ProgressBilling.contract_id == contract_id)
    if site_id:
        q = q.filter(ProgressBilling.site_id == site_id)
    if status:
        q = q.filter(ProgressBilling.status == status)
    return q.order_by(ProgressBilling.billing_date.desc()).all()


@router.get("/progress-billings/{bid}")
def get_billing(bid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    b = db.query(ProgressBilling).filter(ProgressBilling.id == bid).first()
    if not b:
        raise HTTPException(status_code=404, detail="기성을 찾을 수 없습니다.")
    return b


@router.post("/progress-billings")
def create_billing(data: ProgressBillingCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    b = ProgressBilling(**data.dict(), created_by=current.id)
    db.add(b)
    db.flush()
    # 누계 계산
    prev = db.query(sqlfunc.coalesce(sqlfunc.sum(ProgressBilling.billing_amount), 0)).filter(
        ProgressBilling.contract_id == data.contract_id,
        ProgressBilling.id != b.id,
        ProgressBilling.status != "cancelled",
    ).scalar()
    b.cumulative_amount = float(prev) + float(data.billing_amount)
    db.commit()
    db.refresh(b)
    return b


@router.patch("/progress-billings/{bid}/approve")
def approve_billing(bid: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    from datetime import datetime
    b = db.query(ProgressBilling).filter(ProgressBilling.id == bid).first()
    if not b:
        raise HTTPException(status_code=404, detail="기성을 찾을 수 없습니다.")
    b.status = "approved"
    b.approved_by = current.id
    b.approved_at = datetime.utcnow()
    # 자동 전표 및 매출채권 생성
    ar = AccountsReceivable(
        billing_id=b.id, site_id=b.site_id, client_id=b.contract.client_id if b.contract else None,
        issue_date=b.billing_date, due_date=b.due_date,
        billing_amount=b.total_amount, outstanding_amount=b.total_amount,
    )
    db.add(ar)
    db.commit()
    return {"message": "승인되었습니다.", "id": bid}


# ── 수금 ──────────────────────────────────────────
class CollectionCreate(BaseModel):
    collection_no: str
    billing_id: Optional[int] = None
    contract_id: Optional[int] = None
    site_id: Optional[int] = None
    client_id: Optional[int] = None
    collected_date: date
    collected_amount: Decimal
    bank_name: Optional[str] = None
    notes: Optional[str] = None


@router.get("/collections")
def list_collections(site_id: Optional[int] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Collection)
    if site_id:
        q = q.filter(Collection.site_id == site_id)
    return q.order_by(Collection.collected_date.desc()).all()


@router.post("/collections")
def create_collection(data: CollectionCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    c = Collection(**data.dict(), created_by=current.id)
    db.add(c)
    if data.billing_id:
        ar = db.query(AccountsReceivable).filter(AccountsReceivable.billing_id == data.billing_id).first()
        if ar:
            ar.collected_amount = float(ar.collected_amount) + float(data.collected_amount)
            ar.outstanding_amount = float(ar.billing_amount) - float(ar.collected_amount)
            ar.status = "collected" if ar.outstanding_amount <= 0 else "partial"
    db.commit()
    db.refresh(c)
    return c


# ── 설계 의뢰 ──────────────────────────────────────────
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
