from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Estimate(Base):
    __tablename__ = "estimates"
    id = Column(Integer, primary_key=True, index=True)
    estimate_no = Column(String(30), unique=True, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"))
    client_id = Column(Integer, ForeignKey("companies.id"))
    title = Column(String(300), nullable=False)
    estimate_type = Column(String(20), default="bas")
    total_amount = Column(Numeric(18, 2), default=0)
    labor_amount = Column(Numeric(18, 2), default=0)
    material_amount = Column(Numeric(18, 2), default=0)
    subcontract_amount = Column(Numeric(18, 2), default=0)
    expense_amount = Column(Numeric(18, 2), default=0)
    overhead_amount = Column(Numeric(18, 2), default=0)
    profit_amount = Column(Numeric(18, 2), default=0)
    status = Column(String(20), default="draft")
    estimated_by = Column(Integer, ForeignKey("users.id"))
    estimate_date = Column(Date)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    site = relationship("Site")
    client = relationship("Company")
    items = relationship("EstimateItem", back_populates="estimate", cascade="all, delete-orphan")


class EstimateItem(Base):
    __tablename__ = "estimate_items"
    id = Column(Integer, primary_key=True, index=True)
    estimate_id = Column(Integer, ForeignKey("estimates.id", ondelete="CASCADE"))
    cost_code_id = Column(Integer, ForeignKey("cost_codes.id"))
    item_name = Column(String(200), nullable=False)
    spec = Column(String(200))
    unit = Column(String(20))
    quantity = Column(Numeric(14, 4), default=0)
    unit_price = Column(Numeric(18, 2), default=0)
    amount = Column(Numeric(18, 2), default=0)
    sort_order = Column(Integer, default=0)
    notes = Column(Text)

    estimate = relationship("Estimate", back_populates="items")
    cost_code = relationship("CostCode")


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(Integer, primary_key=True, index=True)
    contract_no = Column(String(30), unique=True, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"))
    estimate_id = Column(Integer, ForeignKey("estimates.id"))
    client_id = Column(Integer, ForeignKey("companies.id"))
    contract_name = Column(String(300), nullable=False)
    contract_type = Column(String(20), nullable=False)
    revenue_type = Column(String(20), default="general")
    original_amount = Column(Numeric(18, 2), default=0)
    current_amount = Column(Numeric(18, 2), default=0)
    original_cost = Column(Numeric(18, 2), default=0)
    current_cost = Column(Numeric(18, 2), default=0)
    contract_date = Column(Date)
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String(20), default="active")
    sales_manager_id = Column(Integer, ForeignKey("users.id"))
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    site = relationship("Site")
    client = relationship("Company")
    changes = relationship("ContractChange", back_populates="contract")
    billings = relationship("ProgressBilling", back_populates="contract")


class ContractChange(Base):
    __tablename__ = "contract_changes"
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"))
    change_no = Column(Integer, nullable=False)
    change_date = Column(Date, nullable=False)
    amount_before = Column(Numeric(18, 2))
    amount_change = Column(Numeric(18, 2), default=0)
    amount_after = Column(Numeric(18, 2))
    cost_before = Column(Numeric(18, 2))
    cost_change = Column(Numeric(18, 2), default=0)
    cost_after = Column(Numeric(18, 2))
    end_date_before = Column(Date)
    end_date_after = Column(Date)
    reason = Column(Text)
    status = Column(String(20), default="draft")
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    contract = relationship("Contract", back_populates="changes")


class ProgressBilling(Base):
    __tablename__ = "progress_billings"
    id = Column(Integer, primary_key=True, index=True)
    billing_no = Column(String(30), unique=True, nullable=False)
    contract_id = Column(Integer, ForeignKey("contracts.id"))
    site_id = Column(Integer, ForeignKey("sites.id"))
    billing_seq = Column(Integer, nullable=False)
    billing_date = Column(Date, nullable=False)
    progress_rate = Column(Numeric(6, 2), default=0)
    billing_amount = Column(Numeric(18, 2), default=0)
    vat_amount = Column(Numeric(18, 2), default=0)
    total_amount = Column(Numeric(18, 2), default=0)
    cumulative_amount = Column(Numeric(18, 2), default=0)
    status = Column(String(20), default="draft")
    invoice_no = Column(String(50))
    invoice_date = Column(Date)
    due_date = Column(Date)
    notes = Column(Text)
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    contract = relationship("Contract", back_populates="billings")
    site = relationship("Site")


class Collection(Base):
    __tablename__ = "collections"
    id = Column(Integer, primary_key=True, index=True)
    collection_no = Column(String(30), unique=True, nullable=False)
    billing_id = Column(Integer, ForeignKey("progress_billings.id"))
    contract_id = Column(Integer, ForeignKey("contracts.id"))
    site_id = Column(Integer, ForeignKey("sites.id"))
    client_id = Column(Integer, ForeignKey("companies.id"))
    collected_date = Column(Date, nullable=False)
    collected_amount = Column(Numeric(18, 2), nullable=False)
    bank_name = Column(String(50))
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    billing = relationship("ProgressBilling")
    site = relationship("Site")
    client = relationship("Company")


class DesignRequest(Base):
    __tablename__ = "design_requests"
    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(300), nullable=False)
    department = Column(String(100))
    requester_name = Column(String(100))
    order_company_id = Column(Integer, ForeignKey("companies.id"))       # 발주처
    construction_company_id = Column(Integer, ForeignKey("companies.id"))  # 건설사
    partner_company_id = Column(Integer, ForeignKey("companies.id"))     # 거래처
    request_date = Column(Date)
    due_date = Column(Date)
    status = Column(String(20), default="received")
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    order_company = relationship("Company", foreign_keys=[order_company_id])
    construction_company = relationship("Company", foreign_keys=[construction_company_id])
    partner_company = relationship("Company", foreign_keys=[partner_company_id])
