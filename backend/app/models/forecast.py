from sqlalchemy import Column, Integer, String, DateTime, Date, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class RevenueForecast(Base):
    __tablename__ = "revenue_forecasts"
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"))
    forecast_year = Column(Integer, nullable=False)
    forecast_month = Column(Integer, nullable=False)
    forecast_amount = Column(Numeric(18, 2), default=0)
    actual_amount = Column(Numeric(18, 2), default=0)
    achievement_rate = Column(Numeric(8, 4), default=0)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    site = relationship("Site")


class SalesPipeline(Base):
    __tablename__ = "sales_pipelines"
    id = Column(Integer, primary_key=True, index=True)
    pipeline_name = Column(String(200), nullable=False)
    client_id = Column(Integer, ForeignKey("companies.id"))
    expected_amount = Column(Numeric(18, 2), default=0)
    probability = Column(Integer, default=50)
    weighted_amount = Column(Numeric(18, 2), default=0)
    expected_date = Column(Date)
    sales_manager_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(20), default="active")
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    client = relationship("Company")
    sales_manager = relationship("User", foreign_keys=[sales_manager_id])


class FundPlan(Base):
    __tablename__ = "fund_plans"
    id = Column(Integer, primary_key=True, index=True)
    plan_year = Column(Integer, nullable=False)
    plan_month = Column(Integer, nullable=False)
    planned_income = Column(Numeric(18, 2), default=0)
    planned_expense = Column(Numeric(18, 2), default=0)
    planned_balance = Column(Numeric(18, 2), default=0)
    actual_income = Column(Numeric(18, 2), default=0)
    actual_expense = Column(Numeric(18, 2), default=0)
    actual_balance = Column(Numeric(18, 2), default=0)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
