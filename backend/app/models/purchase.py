from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"
    id = Column(Integer, primary_key=True, index=True)
    request_no = Column(String(30), unique=True, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"))
    request_type = Column(String(20), nullable=False)
    request_date = Column(Date, nullable=False)
    required_date = Column(Date)
    total_amount = Column(Numeric(18, 2), default=0)
    status = Column(String(20), default="draft")
    notes = Column(Text)
    requested_by = Column(Integer, ForeignKey("users.id"))
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

    site = relationship("Site")
    items = relationship("PurchaseRequestItem", back_populates="request", cascade="all, delete-orphan")


class PurchaseRequestItem(Base):
    __tablename__ = "purchase_request_items"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("purchase_requests.id", ondelete="CASCADE"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    item_name = Column(String(200), nullable=False)
    spec = Column(String(200))
    unit = Column(String(20))
    quantity = Column(Numeric(14, 4), default=0)
    unit_price = Column(Numeric(18, 2), default=0)
    amount = Column(Numeric(18, 2), default=0)
    cost_code_id = Column(Integer, ForeignKey("cost_codes.id"))
    notes = Column(Text)

    request = relationship("PurchaseRequest", back_populates="items")
    material = relationship("Material")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(30), unique=True, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"))
    vendor_id = Column(Integer, ForeignKey("companies.id"))
    request_id = Column(Integer, ForeignKey("purchase_requests.id"))
    order_type = Column(String(20), nullable=False)
    order_date = Column(Date, nullable=False)
    delivery_date = Column(Date)
    total_amount = Column(Numeric(18, 2), default=0)
    vat_amount = Column(Numeric(18, 2), default=0)
    status = Column(String(20), default="draft")
    notes = Column(Text)
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    site = relationship("Site")
    vendor = relationship("Company")
    items = relationship("PurchaseOrderItem", back_populates="order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    item_name = Column(String(200), nullable=False)
    spec = Column(String(200))
    unit = Column(String(20))
    ordered_qty = Column(Numeric(14, 4), default=0)
    received_qty = Column(Numeric(14, 4), default=0)
    unit_price = Column(Numeric(18, 2), default=0)
    amount = Column(Numeric(18, 2), default=0)
    cost_code_id = Column(Integer, ForeignKey("cost_codes.id"))
    notes = Column(Text)

    order = relationship("PurchaseOrder", back_populates="items")
    material = relationship("Material")


class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True, index=True)
    receipt_no = Column(String(30), unique=True, nullable=False)
    order_id = Column(Integer, ForeignKey("purchase_orders.id"))
    site_id = Column(Integer, ForeignKey("sites.id"))
    vendor_id = Column(Integer, ForeignKey("companies.id"))
    receipt_date = Column(Date, nullable=False)
    invoice_no = Column(String(50))
    total_amount = Column(Numeric(18, 2), default=0)
    vat_amount = Column(Numeric(18, 2), default=0)
    status = Column(String(20), default="draft")
    inspector_id = Column(Integer, ForeignKey("users.id"))
    inspected_at = Column(DateTime)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    order = relationship("PurchaseOrder")
    site = relationship("Site")
    vendor = relationship("Company")
    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")


class ReceiptItem(Base):
    __tablename__ = "receipt_items"
    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id", ondelete="CASCADE"))
    order_item_id = Column(Integer, ForeignKey("purchase_order_items.id"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    item_name = Column(String(200), nullable=False)
    unit = Column(String(20))
    received_qty = Column(Numeric(14, 4), default=0)
    returned_qty = Column(Numeric(14, 4), default=0)
    unit_price = Column(Numeric(18, 2), default=0)
    amount = Column(Numeric(18, 2), default=0)
    cost_code_id = Column(Integer, ForeignKey("cost_codes.id"))

    receipt = relationship("Receipt", back_populates="items")
    material = relationship("Material")


class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    current_qty = Column(Numeric(14, 4), default=0)
    reserved_qty = Column(Numeric(14, 4), default=0)
    available_qty = Column(Numeric(14, 4), default=0)
    avg_unit_price = Column(Numeric(18, 2), default=0)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    site = relationship("Site")
    material = relationship("Material")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    transaction_type = Column(String(20), nullable=False)
    quantity = Column(Numeric(14, 4), nullable=False)
    unit_price = Column(Numeric(18, 2), default=0)
    amount = Column(Numeric(18, 2), default=0)
    ref_type = Column(String(50))
    ref_id = Column(Integer)
    cost_code_id = Column(Integer, ForeignKey("cost_codes.id"))
    transaction_date = Column(Date, nullable=False)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    site = relationship("Site")
    material = relationship("Material")


class Subcontract(Base):
    __tablename__ = "subcontracts"
    id = Column(Integer, primary_key=True, index=True)
    subcontract_no = Column(String(30), unique=True, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"))
    vendor_id = Column(Integer, ForeignKey("companies.id"))
    contract_name = Column(String(200), nullable=False)
    cost_code_id = Column(Integer, ForeignKey("cost_codes.id"))
    contract_amount = Column(Numeric(18, 2), default=0)
    advance_payment = Column(Numeric(18, 2), default=0)
    retention_rate = Column(Numeric(6, 2), default=0)
    start_date = Column(Date)
    end_date = Column(Date)
    payment_terms = Column(Text)
    status = Column(String(20), default="active")
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    site = relationship("Site")
    vendor = relationship("Company")
    billings = relationship("SubcontractBilling", back_populates="subcontract")


class SubcontractBilling(Base):
    __tablename__ = "subcontract_billings"
    id = Column(Integer, primary_key=True, index=True)
    billing_no = Column(String(30), unique=True, nullable=False)
    subcontract_id = Column(Integer, ForeignKey("subcontracts.id"))
    site_id = Column(Integer, ForeignKey("sites.id"))
    billing_seq = Column(Integer, nullable=False)
    billing_date = Column(Date, nullable=False)
    progress_rate = Column(Numeric(6, 2), default=0)
    billing_amount = Column(Numeric(18, 2), default=0)
    vat_amount = Column(Numeric(18, 2), default=0)
    total_amount = Column(Numeric(18, 2), default=0)
    cumulative_amount = Column(Numeric(18, 2), default=0)
    status = Column(String(20), default="draft")
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    paid_at = Column(DateTime)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    subcontract = relationship("Subcontract", back_populates="billings")
    site = relationship("Site")


class LaborInput(Base):
    __tablename__ = "labor_inputs"
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"))
    employee_id = Column(Integer, ForeignKey("employees.id"))
    cost_code_id = Column(Integer, ForeignKey("cost_codes.id"))
    work_date = Column(Date, nullable=False)
    work_days = Column(Numeric(4, 1), default=1)
    daily_wage = Column(Numeric(12, 2), default=0)
    amount = Column(Numeric(14, 2), default=0)
    insurance_amount = Column(Numeric(12, 2), default=0)
    net_amount = Column(Numeric(14, 2), default=0)
    status = Column(String(20), default="draft")
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    site = relationship("Site")
    employee = relationship("Employee")
    cost_code = relationship("CostCode")


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    expense_no = Column(String(30), unique=True, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"))
    cost_code_id = Column(Integer, ForeignKey("cost_codes.id"))
    expense_date = Column(Date, nullable=False)
    expense_type = Column(String(50))
    description = Column(String(300))
    amount = Column(Numeric(14, 2), default=0)
    vat_amount = Column(Numeric(12, 2), default=0)
    vendor_id = Column(Integer, ForeignKey("companies.id"))
    receipt_no = Column(String(50))
    status = Column(String(20), default="draft")
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    notes = Column(Text)
    requested_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    site = relationship("Site")
    cost_code = relationship("CostCode")


class CostInput(Base):
    __tablename__ = "cost_inputs"
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"))
    cost_code_id = Column(Integer, ForeignKey("cost_codes.id"))
    cost_type = Column(String(20), nullable=False)
    input_date = Column(Date, nullable=False)
    amount = Column(Numeric(18, 2), default=0)
    ref_type = Column(String(50))
    ref_id = Column(Integer)
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())

    site = relationship("Site")
    cost_code = relationship("CostCode")
