from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func as sqlfunc
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime
from ..database import get_db
from ..models.accounting import (JournalEntry, JournalLine, AccountsReceivable, AccountsPayable,
                                   Payment, PaymentItem, PeriodClosing)
from ..utils.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["회계"])


# ── 전표 ──────────────────────────────────────────
class JournalLineIn(BaseModel):
    line_no: int
    account_id: Optional[int] = None
    debit_amount: Decimal = Decimal(0)
    credit_amount: Decimal = Decimal(0)
    site_id: Optional[int] = None
    cost_code_id: Optional[int] = None
    vendor_id: Optional[int] = None
    description: Optional[str] = None
    tax_invoice_no: Optional[str] = None


class JournalEntryCreate(BaseModel):
    entry_no: str
    entry_date: date
    entry_type: str = "general"
    description: Optional[str] = None
    site_id: Optional[int] = None
    notes: Optional[str] = None
    lines: List[JournalLineIn] = []


@router.get("/journal-entries")
def list_journal_entries(site_id: Optional[int] = None, status: Optional[str] = None,
                          date_from: Optional[date] = None, date_to: Optional[date] = None,
                          db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(JournalEntry)
    if site_id:
        q = q.filter(JournalEntry.site_id == site_id)
    if status:
        q = q.filter(JournalEntry.status == status)
    if date_from:
        q = q.filter(JournalEntry.entry_date >= date_from)
    if date_to:
        q = q.filter(JournalEntry.entry_date <= date_to)
    return q.order_by(JournalEntry.entry_date.desc()).all()


@router.get("/journal-entries/{eid}")
def get_journal_entry(eid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    e = db.query(JournalEntry).filter(JournalEntry.id == eid).first()
    if not e:
        raise HTTPException(status_code=404, detail="전표를 찾을 수 없습니다.")
    return e


@router.post("/journal-entries")
def create_journal_entry(data: JournalEntryCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    lines = data.lines
    total_debit = sum(float(l.debit_amount) for l in lines)
    total_credit = sum(float(l.credit_amount) for l in lines)
    e = JournalEntry(**data.dict(exclude={"lines"}),
                     total_debit=total_debit, total_credit=total_credit, created_by=current.id)
    db.add(e)
    db.flush()
    for line in lines:
        jl = JournalLine(**line.dict(), entry_id=e.id)
        db.add(jl)
    db.commit()
    db.refresh(e)
    return e


@router.patch("/journal-entries/{eid}/approve")
def approve_journal_entry(eid: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    e = db.query(JournalEntry).filter(JournalEntry.id == eid).first()
    if not e:
        raise HTTPException(status_code=404, detail="전표를 찾을 수 없습니다.")
    if e.status == "approved":
        raise HTTPException(status_code=400, detail="이미 승인된 전표입니다.")
    e.status = "approved"
    e.approved_by = current.id
    e.approved_at = datetime.utcnow()
    db.commit()
    return {"message": "전표가 승인되었습니다."}


@router.patch("/journal-entries/{eid}/cancel")
def cancel_journal_entry(eid: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    e = db.query(JournalEntry).filter(JournalEntry.id == eid).first()
    if not e:
        raise HTTPException(status_code=404, detail="전표를 찾을 수 없습니다.")
    e.status = "cancelled"
    e.cancelled_at = datetime.utcnow()
    db.commit()
    return {"message": "전표가 취소되었습니다."}


# ── 매출채권 ──────────────────────────────────────────
@router.get("/accounts-receivable")
def list_ar(site_id: Optional[int] = None, status: Optional[str] = None,
            client_id: Optional[int] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(AccountsReceivable)
    if site_id:
        q = q.filter(AccountsReceivable.site_id == site_id)
    if status:
        q = q.filter(AccountsReceivable.status == status)
    if client_id:
        q = q.filter(AccountsReceivable.client_id == client_id)
    return q.order_by(AccountsReceivable.issue_date.desc()).all()


@router.get("/accounts-receivable/summary")
def ar_summary(db: Session = Depends(get_db), _=Depends(get_current_user)):
    result = db.query(
        sqlfunc.sum(AccountsReceivable.billing_amount).label("total_billing"),
        sqlfunc.sum(AccountsReceivable.collected_amount).label("total_collected"),
        sqlfunc.sum(AccountsReceivable.outstanding_amount).label("total_outstanding"),
    ).first()
    return {
        "total_billing": float(result.total_billing or 0),
        "total_collected": float(result.total_collected or 0),
        "total_outstanding": float(result.total_outstanding or 0),
    }


# ── 매입채무 ──────────────────────────────────────────
@router.get("/accounts-payable")
def list_ap(site_id: Optional[int] = None, status: Optional[str] = None,
            vendor_id: Optional[int] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(AccountsPayable)
    if site_id:
        q = q.filter(AccountsPayable.site_id == site_id)
    if status:
        q = q.filter(AccountsPayable.status == status)
    if vendor_id:
        q = q.filter(AccountsPayable.vendor_id == vendor_id)
    return q.order_by(AccountsPayable.issue_date.desc()).all()


# ── 지급 ──────────────────────────────────────────
class PaymentItemIn(BaseModel):
    payable_id: Optional[int] = None
    applied_amount: Decimal = Decimal(0)


class PaymentCreate(BaseModel):
    payment_no: str
    vendor_id: Optional[int] = None
    site_id: Optional[int] = None
    payment_date: date
    payment_amount: Decimal
    payment_method: str = "transfer"
    bank_name: Optional[str] = None
    notes: Optional[str] = None
    items: List[PaymentItemIn] = []


@router.get("/payments")
def list_payments(vendor_id: Optional[int] = None, site_id: Optional[int] = None,
                  db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Payment)
    if vendor_id:
        q = q.filter(Payment.vendor_id == vendor_id)
    if site_id:
        q = q.filter(Payment.site_id == site_id)
    return q.order_by(Payment.payment_date.desc()).all()


@router.post("/payments")
def create_payment(data: PaymentCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    items = data.items
    p = Payment(**data.dict(exclude={"items"}), created_by=current.id)
    db.add(p)
    db.flush()
    for item in items:
        pi = PaymentItem(**item.dict(), payment_id=p.id)
        db.add(pi)
        if item.payable_id:
            ap = db.query(AccountsPayable).filter(AccountsPayable.id == item.payable_id).first()
            if ap:
                ap.paid_amount = float(ap.paid_amount) + float(item.applied_amount)
                ap.outstanding_amount = float(ap.total_amount) - float(ap.paid_amount)
                ap.status = "paid" if ap.outstanding_amount <= 0 else "partial"
    db.commit()
    db.refresh(p)
    return p


# ── 기간 마감 ──────────────────────────────────────────
class PeriodClosingCreate(BaseModel):
    close_year: int
    close_month: int
    notes: Optional[str] = None


@router.get("/period-closings")
def list_period_closings(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(PeriodClosing).order_by(PeriodClosing.close_year.desc(), PeriodClosing.close_month.desc()).all()


@router.post("/period-closings")
def close_period(data: PeriodClosingCreate, db: Session = Depends(get_db), current=Depends(get_current_user)):
    existing = db.query(PeriodClosing).filter(
        PeriodClosing.close_year == data.close_year,
        PeriodClosing.close_month == data.close_month,
    ).first()
    if existing and existing.status == "closed":
        raise HTTPException(status_code=400, detail="이미 마감된 기간입니다.")
    if not existing:
        pc = PeriodClosing(**data.dict(), status="closed", closed_by=current.id, closed_at=datetime.utcnow())
        db.add(pc)
    else:
        existing.status = "closed"
        existing.closed_by = current.id
        existing.closed_at = datetime.utcnow()
    db.commit()
    return {"message": f"{data.close_year}년 {data.close_month}월 마감 완료"}


# ── 총계정원장 ──────────────────────────────────────────
@router.get("/ledger")
def get_ledger(account_id: Optional[int] = None, site_id: Optional[int] = None,
               date_from: Optional[date] = None, date_to: Optional[date] = None,
               db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(JournalLine).join(JournalEntry).filter(JournalEntry.status == "approved")
    if account_id:
        q = q.filter(JournalLine.account_id == account_id)
    if site_id:
        q = q.filter(JournalLine.site_id == site_id)
    if date_from:
        q = q.filter(JournalEntry.entry_date >= date_from)
    if date_to:
        q = q.filter(JournalEntry.entry_date <= date_to)
    lines = q.order_by(JournalEntry.entry_date).all()
    result = []
    balance = 0
    for line in lines:
        balance += float(line.debit_amount) - float(line.credit_amount)
        result.append({
            "entry_id": line.entry_id,
            "entry_date": line.entry.entry_date,
            "description": line.description or line.entry.description,
            "debit": float(line.debit_amount),
            "credit": float(line.credit_amount),
            "balance": balance,
        })
    return result
