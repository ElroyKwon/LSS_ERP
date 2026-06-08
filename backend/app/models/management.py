from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class DeptBudget(Base):
    """부서별 연간 예산 — 분기별 항목 관리"""
    __tablename__ = "dept_budgets"
    __table_args__ = (UniqueConstraint("budget_year", "department", "category"),)

    id          = Column(Integer, primary_key=True, index=True)
    budget_year = Column(Integer, nullable=False)
    department  = Column(String(100), nullable=False)
    category    = Column(String(50),  nullable=False)   # 매출목표/재료비/노무비/외주비/경비/판관비/기타
    q1          = Column(Numeric(18, 2), default=0)
    q2          = Column(Numeric(18, 2), default=0)
    q3          = Column(Numeric(18, 2), default=0)
    q4          = Column(Numeric(18, 2), default=0)
    status      = Column(String(20), default="작성중")  # 작성중/확정/승인
    notes       = Column(Text)
    created_by  = Column(Integer, ForeignKey("users.id"))
    created_at  = Column(DateTime, default=func.now())
    updated_at  = Column(DateTime, default=func.now(), onupdate=func.now())
