from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime
from ..database import get_db
from ..models.purchase import (PurchaseRequest, PurchaseRequestItem, PurchaseOrder, PurchaseOrderItem,
                                Receipt, ReceiptItem, Inventory, InventoryTransaction,
                                Subcontract, SubcontractBilling, LaborInput, Expense, CostInput)
from ..utils.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["구매·투입"])


# ── 구매요청 ──────────────────────────────────────────
class RequestItemIn(BaseModel):
    material_id: Optional[int] = None
    item_name: str
    spec: Optional[str] = None
    unit: Optional[str] = None
    quantity: Decimal = Decimal(0)
    unit_price: Decimal = Decimal(0)
    amount: Decimal = Decimal(0)
    cost_code_id: Optional[int] = None
    notes: Optional[str] = None


class PurchaseRequestCreate(BaseModel):
    request_no: str
    site_id: Optional[int] = None
    request_type: str
    request_date: date
    required_date: Optional[date] = None
    total_amount: Decimal = Decimal(0)
    notes: Optional[str] = None
    items: List[RequestItemIn] = []


@router.get("/purchase-requests")
def list_purchase_requests(site_id: Optional[int] = None, status: Optional[str] = None,
                            db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(PurchaseRequest)
    if site_id:
        q = q.filter(PurchaseRequest.site_id == site_id)
    if status:
        q = q.filter(PurchaseRequest.status == status)
    return q.order_by(PurchaseRequest.request_date.desc()).all()


@router.post("/purchase-requests")
def create_purchase_request(data: PurchaseRequestCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    items = data.items
    r = PurchaseRequest(**data.dict(exclude={"items"}), requested_by=current.id)
    db.add(r)
    db.flush()
    for item in items:
        db.add(PurchaseRequestItem(**item.dict(), request_id=r.id))
    db.commit()
    db.refresh(r)
    return r


# ── 발주 ──────────────────────────────────────────
class OrderItemIn(BaseModel):
    material_id: Optional[int] = None
    item_name: str
    spec: Optional[str] = None
    unit: Optional[str] = None
    ordered_qty: Decimal = Decimal(0)
    unit_price: Decimal = Decimal(0)
    amount: Decimal = Decimal(0)
    cost_code_id: Optional[int] = None
    notes: Optional[str] = None


class PurchaseOrderCreate(BaseModel):
    order_no: str
    site_id: Optional[int] = None
    vendor_id: Optional[int] = None
    request_id: Optional[int] = None
    order_type: str
    order_date: date
    delivery_date: Optional[date] = None
    total_amount: Decimal = Decimal(0)
    vat_amount: Decimal = Decimal(0)
    notes: Optional[str] = None
    items: List[OrderItemIn] = []


@router.get("/purchase-orders")
def list_purchase_orders(site_id: Optional[int] = None, status: Optional[str] = None,
                          vendor_id: Optional[int] = None, db: Session = Depends(get_db),
                          _=Depends(get_current_user)):
    q = db.query(PurchaseOrder)
    if site_id:
        q = q.filter(PurchaseOrder.site_id == site_id)
    if status:
        q = q.filter(PurchaseOrder.status == status)
    if vendor_id:
        q = q.filter(PurchaseOrder.vendor_id == vendor_id)
    return q.order_by(PurchaseOrder.order_date.desc()).all()


@router.get("/purchase-orders/{oid}")
def get_purchase_order(oid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    o = db.query(PurchaseOrder).filter(PurchaseOrder.id == oid).first()
    if not o:
        raise HTTPException(status_code=404, detail="발주를 찾을 수 없습니다.")
    return o


@router.post("/purchase-orders")
def create_purchase_order(data: PurchaseOrderCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    items = data.items
    o = PurchaseOrder(**data.dict(exclude={"items"}), created_by=current.id)
    db.add(o)
    db.flush()
    for item in items:
        db.add(PurchaseOrderItem(**item.dict(), order_id=o.id))
    db.commit()
    db.refresh(o)
    return o


# ── 입고 ──────────────────────────────────────────
class ReceiptItemIn(BaseModel):
    order_item_id: Optional[int] = None
    material_id: Optional[int] = None
    item_name: str
    unit: Optional[str] = None
    received_qty: Decimal = Decimal(0)
    returned_qty: Decimal = Decimal(0)
    unit_price: Decimal = Decimal(0)
    amount: Decimal = Decimal(0)
    cost_code_id: Optional[int] = None


class ReceiptCreate(BaseModel):
    receipt_no: str
    order_id: Optional[int] = None
    site_id: Optional[int] = None
    vendor_id: Optional[int] = None
    receipt_date: date
    invoice_no: Optional[str] = None
    total_amount: Decimal = Decimal(0)
    vat_amount: Decimal = Decimal(0)
    notes: Optional[str] = None
    items: List[ReceiptItemIn] = []


@router.get("/receipts")
def list_receipts(site_id: Optional[int] = None, status: Optional[str] = None,
                  db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Receipt)
    if site_id:
        q = q.filter(Receipt.site_id == site_id)
    if status:
        q = q.filter(Receipt.status == status)
    return q.order_by(Receipt.receipt_date.desc()).all()


@router.post("/receipts")
def create_receipt(data: ReceiptCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    items = data.items
    r = Receipt(**data.dict(exclude={"items"}), created_by=current.id)
    db.add(r)
    db.flush()
    for item in items:
        ri = ReceiptItem(**item.dict(), receipt_id=r.id)
        db.add(ri)
    db.commit()
    db.refresh(r)
    return r


@router.patch("/receipts/{rid}/approve")
def approve_receipt(rid: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    r = db.query(Receipt).filter(Receipt.id == rid).first()
    if not r:
        raise HTTPException(status_code=404, detail="입고를 찾을 수 없습니다.")
    r.status = "approved"
    r.inspector_id = current.id
    r.inspected_at = datetime.utcnow()
    # 재고 업데이트
    for item in r.items:
        if item.material_id and r.site_id:
            inv = db.query(Inventory).filter(
                Inventory.site_id == r.site_id, Inventory.material_id == item.material_id
            ).first()
            if not inv:
                inv = Inventory(site_id=r.site_id, material_id=item.material_id)
                db.add(inv)
                db.flush()
            net_qty = float(item.received_qty) - float(item.returned_qty)
            inv.current_qty = float(inv.current_qty) + net_qty
            inv.available_qty = float(inv.current_qty) - float(inv.reserved_qty)
            # 이동평균 단가
            if net_qty > 0:
                total_val = float(inv.avg_unit_price) * (float(inv.current_qty) - net_qty) + float(item.unit_price) * net_qty
                inv.avg_unit_price = total_val / float(inv.current_qty) if float(inv.current_qty) > 0 else 0
            tx = InventoryTransaction(
                site_id=r.site_id, material_id=item.material_id,
                transaction_type="in", quantity=net_qty,
                unit_price=item.unit_price, amount=item.amount,
                ref_type="receipt", ref_id=r.id,
                transaction_date=r.receipt_date, created_by=current.id,
            )
            db.add(tx)
    db.commit()
    return {"message": "입고 승인되었습니다."}


# ── 재고 ──────────────────────────────────────────
@router.get("/inventory")
def list_inventory(site_id: Optional[int] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Inventory)
    if site_id:
        q = q.filter(Inventory.site_id == site_id)
    return q.all()


# ── 하도급 ──────────────────────────────────────────
class SubcontractCreate(BaseModel):
    subcontract_no: str
    site_id: Optional[int] = None
    vendor_id: Optional[int] = None
    contract_name: str
    cost_code_id: Optional[int] = None
    contract_amount: Decimal = Decimal(0)
    advance_payment: Decimal = Decimal(0)
    retention_rate: Decimal = Decimal(0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None


@router.get("/subcontracts")
def list_subcontracts(site_id: Optional[int] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Subcontract)
    if site_id:
        q = q.filter(Subcontract.site_id == site_id)
    return q.order_by(Subcontract.created_at.desc()).all()


@router.post("/subcontracts")
def create_subcontract(data: SubcontractCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    s = Subcontract(**data.dict(), created_by=current.id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.put("/subcontracts/{sid}")
def update_subcontract(sid: int, data: SubcontractCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    s = db.query(Subcontract).filter(Subcontract.id == sid).first()
    if not s:
        raise HTTPException(status_code=404, detail="하도급 계약을 찾을 수 없습니다.")
    for field, val in data.dict(exclude_none=True).items():
        setattr(s, field, val)
    db.commit()
    return s


# ── 하도급 기성 ──────────────────────────────────────────
class SubcontractBillingCreate(BaseModel):
    billing_no: str
    subcontract_id: int
    site_id: Optional[int] = None
    billing_seq: int
    billing_date: date
    progress_rate: Decimal = Decimal(0)
    billing_amount: Decimal = Decimal(0)
    vat_amount: Decimal = Decimal(0)
    total_amount: Decimal = Decimal(0)
    notes: Optional[str] = None


@router.get("/subcontract-billings")
def list_subcontract_billings(subcontract_id: Optional[int] = None, site_id: Optional[int] = None,
                               db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(SubcontractBilling)
    if subcontract_id:
        q = q.filter(SubcontractBilling.subcontract_id == subcontract_id)
    if site_id:
        q = q.filter(SubcontractBilling.site_id == site_id)
    return q.order_by(SubcontractBilling.billing_date.desc()).all()


@router.post("/subcontract-billings")
def create_subcontract_billing(data: SubcontractBillingCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    b = SubcontractBilling(**data.dict(), created_by=current.id)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@router.patch("/subcontract-billings/{bid}/approve")
def approve_subcontract_billing(bid: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    b = db.query(SubcontractBilling).filter(SubcontractBilling.id == bid).first()
    if not b:
        raise HTTPException(status_code=404, detail="하도급 기성을 찾을 수 없습니다.")
    b.status = "approved"
    b.approved_by = current.id
    b.approved_at = datetime.utcnow()
    ci = CostInput(
        site_id=b.site_id, cost_type="subcontract",
        input_date=b.billing_date, amount=b.billing_amount,
        ref_type="subcontract_billing", ref_id=b.id,
    )
    db.add(ci)
    db.commit()
    return {"message": "승인되었습니다."}


# ── 노무비 투입 ──────────────────────────────────────────
class LaborInputCreate(BaseModel):
    site_id: Optional[int] = None
    employee_id: Optional[int] = None
    cost_code_id: Optional[int] = None
    work_date: date
    work_days: Decimal = Decimal(1)
    daily_wage: Decimal = Decimal(0)
    amount: Decimal = Decimal(0)
    insurance_amount: Decimal = Decimal(0)
    net_amount: Decimal = Decimal(0)
    notes: Optional[str] = None


@router.get("/labor-inputs")
def list_labor_inputs(site_id: Optional[int] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(LaborInput)
    if site_id:
        q = q.filter(LaborInput.site_id == site_id)
    return q.order_by(LaborInput.work_date.desc()).all()


@router.post("/labor-inputs")
def create_labor_input(data: LaborInputCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    l = LaborInput(**data.dict(), created_by=current.id)
    db.add(l)
    db.flush()
    ci = CostInput(
        site_id=data.site_id, cost_code_id=data.cost_code_id,
        cost_type="labor", input_date=data.work_date, amount=data.amount,
        ref_type="labor_input", ref_id=l.id,
    )
    db.add(ci)
    db.commit()
    db.refresh(l)
    return l


# ── 경비 ──────────────────────────────────────────
class ExpenseCreate(BaseModel):
    expense_no: str
    site_id: Optional[int] = None
    cost_code_id: Optional[int] = None
    expense_date: date
    expense_type: Optional[str] = None
    description: Optional[str] = None
    amount: Decimal = Decimal(0)
    vat_amount: Decimal = Decimal(0)
    vendor_id: Optional[int] = None
    receipt_no: Optional[str] = None
    notes: Optional[str] = None


@router.get("/expenses")
def list_expenses(site_id: Optional[int] = None, status: Optional[str] = None,
                  db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Expense)
    if site_id:
        q = q.filter(Expense.site_id == site_id)
    if status:
        q = q.filter(Expense.status == status)
    return q.order_by(Expense.expense_date.desc()).all()


@router.post("/expenses")
def create_expense(data: ExpenseCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    e = Expense(**data.dict(), requested_by=current.id)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e
