from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, ForeignKey, Text, UniqueConstraint
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


class EstimateAttachment(Base):
    __tablename__ = "estimate_attachments"
    id = Column(Integer, primary_key=True, index=True)
    estimate_id = Column(Integer, ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False)
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    content_type = Column(String(120))
    file_size = Column(Integer, default=0)
    file_path = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    estimate = relationship("Estimate")


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


class SalesManagementWeeklyRow(Base):
    """Weekly sales management project list row snapshot."""
    __tablename__ = "sales_management_weekly_rows"
    __table_args__ = (UniqueConstraint("week_start", "row_key"),)
    id         = Column(Integer, primary_key=True, index=True)
    week_start = Column(Date, nullable=False, index=True)
    row_key    = Column(String(80), nullable=False)
    data_json  = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
