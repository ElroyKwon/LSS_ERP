from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"))
    site_id = Column(Integer, ForeignKey("sites.id"))
    version = Column(Integer, default=1)
    budget_name = Column(String(100))
    total_amount = Column(Numeric(18, 2), default=0)
    status = Column(String(20), default="active")
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    site = relationship("Site")
    contract = relationship("Contract")
    items = relationship("BudgetItem", back_populates="budget", cascade="all, delete-orphan")


class BudgetItem(Base):
    __tablename__ = "budget_items"
    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="CASCADE"))
    cost_code_id = Column(Integer, ForeignKey("cost_codes.id"))
    cost_type = Column(String(20))
    item_name = Column(String(200))
    budgeted_amount = Column(Numeric(18, 2), default=0)
    execution_amount = Column(Numeric(18, 2), default=0)
    actual_amount = Column(Numeric(18, 2), default=0)
    notes = Column(Text)

    budget = relationship("Budget", back_populates="items")
    cost_code = relationship("CostCode")
