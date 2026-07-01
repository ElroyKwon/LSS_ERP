from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True, index=True)
    entry_no = Column(String(30), unique=True, nullable=False)
    entry_date = Column(Date, nullable=False)
    entry_type = Column(String(20), default="general")
    description = Column(Text)
    total_debit = Column(Numeric(18, 2), default=0)
    total_credit = Column(Numeric(18, 2), default=0)
    site_id = Column(Integer, ForeignKey("sites.id"))
    status = Column(String(20), default="draft")
    ref_type = Column(String(50))
    ref_id = Column(Integer)
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    site = relationship("Site")
    lines = relationship("JournalLine", back_populates="entry", cascade="all, delete-orphan")


class JournalLine(Base):
    __tablename__ = "journal_lines"
    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"))
    line_no = Column(Integer, nullable=False)
    account_id = Column(Integer, ForeignKey("account_codes.id"))
    debit_amount = Column(Numeric(18, 2), default=0)
    credit_amount = Column(Numeric(18, 2), default=0)
    site_id = Column(Integer, ForeignKey("sites.id"))
    cost_code_id = Column(Integer, ForeignKey("cost_codes.id"))
    vendor_id = Column(Integer, ForeignKey("companies.id"))
    description = Column(String(300))
    tax_invoice_no = Column(String(50))

    entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("AccountCode")


class AccountsReceivable(Base):
    __tablename__ = "accounts_receivable"
    id = Column(Integer, primary_key=True, index=True)
    sales_bill_id = Column(Integer, ForeignKey("sales_bills.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    site_id = Column(Integer, ForeignKey("sites.id"))
    client_id = Column(Integer, ForeignKey("companies.id"))
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date)
    billing_amount = Column(Numeric(18, 2), default=0)
    collected_amount = Column(Numeric(18, 2), default=0)
    outstanding_amount = Column(Numeric(18, 2), default=0)
    receivable_type = Column(String(20), default="외상매출금")
    business_division = Column(String(100))
    job_no = Column(String(30))
    department = Column(String(100))
    client_name = Column(String(200))
    project_name = Column(String(300))
    sales_manager = Column(String(100))
    construction_manager = Column(String(100))
    collection_terms = Column(String(200))
    customer_class = Column(String(30), default="일반")
    collection_date = Column(Date)
    note_maturity_date = Column(Date)
    note_issuer = Column(String(200))
    status = Column(String(20), default="outstanding")
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    sales_bill = relationship("SalesBill")
    project = relationship("Project")
    site = relationship("Site")
    client = relationship("Company")


class AccountsPayable(Base):
    __tablename__ = "accounts_payable"
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"))
    vendor_id = Column(Integer, ForeignKey("companies.id"))
    ref_type = Column(String(50))
    ref_id = Column(Integer)
    job_no = Column(String(30))
    contract_name = Column(String(300))
    vendor_name = Column(String(200))
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date)
    invoice_no = Column(String(50))
    total_amount = Column(Numeric(18, 2), default=0)
    contract_amount_ex_vat = Column(Numeric(18, 2), default=0)
    contract_amount = Column(Numeric(18, 2), default=0)
    purchase_type = Column(String(30))
    subcontract_type = Column(String(30))
    payment_terms = Column(String(200))
    collection_terms = Column(String(200))
    related_revenue_no = Column(String(50))
    related_revenue = Column(Numeric(18, 2), default=0)
    related_revenue_collection_date = Column(Date)
    related_revenue_collection_method = Column(String(50))
    actual_payment_date = Column(Date)
    payment_type = Column(String(30))
    cash_paid_amount = Column(Numeric(18, 2), default=0)
    note_issued_amount = Column(Numeric(18, 2), default=0)
    note_maturity_date = Column(Date)
    paid_amount = Column(Numeric(18, 2), default=0)
    outstanding_amount = Column(Numeric(18, 2), default=0)
    status = Column(String(20), default="outstanding")
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    site = relationship("Site")
    vendor = relationship("Company")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    payment_no = Column(String(30), unique=True, nullable=False)
    vendor_id = Column(Integer, ForeignKey("companies.id"))
    site_id = Column(Integer, ForeignKey("sites.id"))
    payment_date = Column(Date, nullable=False)
    payment_amount = Column(Numeric(18, 2), nullable=False)
    payment_method = Column(String(20), default="transfer")
    bank_name = Column(String(50))
    notes = Column(Text)
    status = Column(String(20), default="draft")
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    vendor = relationship("Company")
    site = relationship("Site")
    items = relationship("PaymentItem", back_populates="payment", cascade="all, delete-orphan")


class PaymentItem(Base):
    __tablename__ = "payment_items"
    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="CASCADE"))
    payable_id = Column(Integer, ForeignKey("accounts_payable.id"))
    applied_amount = Column(Numeric(18, 2), default=0)

    payment = relationship("Payment", back_populates="items")
    payable = relationship("AccountsPayable")


class PeriodClosing(Base):
    __tablename__ = "period_closings"
    id = Column(Integer, primary_key=True, index=True)
    close_year = Column(Integer, nullable=False)
    close_month = Column(Integer, nullable=False)
    status = Column(String(20), default="open")
    closed_by = Column(Integer, ForeignKey("users.id"))
    closed_at = Column(DateTime)
    notes = Column(Text)
