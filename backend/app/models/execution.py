from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Project(Base):
    __tablename__ = "projects"
    id              = Column(Integer, primary_key=True, index=True)
    project_no      = Column(String(30))
    project_name    = Column(String(300), nullable=False)
    client_id       = Column(Integer, ForeignKey("companies.id"), nullable=True)
    client_name     = Column(String(200))
    contract_form   = Column(String(20), default="원도급")
    contract_type   = Column(String(10), default="국내")
    status          = Column(String(20), default="미진행")
    contract_amount = Column(Numeric(18, 2), default=0)
    contract_rate   = Column(Numeric(6, 2), default=0)
    contract_start  = Column(Date)
    contract_end    = Column(Date)
    construct_start = Column(Date)
    construct_end   = Column(Date)
    pm_name         = Column(String(100))
    pm_dept         = Column(String(100))
    region          = Column(String(100))
    notes           = Column(Text)
    created_by      = Column(Integer, ForeignKey("users.id"))
    created_at      = Column(DateTime, default=func.now())
    updated_at      = Column(DateTime, default=func.now(), onupdate=func.now())

    client = relationship("Company", foreign_keys=[client_id])


class ProjectPlan(Base):
    """매출/투입 계획 — 프로젝트별 월간 계획"""
    __tablename__ = "project_plans"
    __table_args__ = (UniqueConstraint("project_id", "plan_year", "plan_month"),)
    id               = Column(Integer, primary_key=True, index=True)
    project_id       = Column(Integer, ForeignKey("projects.id"), nullable=False)
    plan_year        = Column(Integer, nullable=False)
    plan_month       = Column(Integer, nullable=False)           # 1–12
    revenue_plan     = Column(Numeric(18, 2), default=0)         # 매출 계획
    material_plan    = Column(Numeric(18, 2), default=0)         # 재료비
    labor_plan       = Column(Numeric(18, 2), default=0)         # 노무비
    subcontract_plan = Column(Numeric(18, 2), default=0)         # 외주비
    expense_plan     = Column(Numeric(18, 2), default=0)         # 경비
    notes            = Column(Text)
    created_by       = Column(Integer, ForeignKey("users.id"))
    created_at       = Column(DateTime, default=func.now())
    updated_at       = Column(DateTime, default=func.now(), onupdate=func.now())

    project = relationship("Project", foreign_keys=[project_id])


class PurchaseContract(Base):
    """구매/계약 — 프로젝트 관련 구매·외주 계약"""
    __tablename__ = "purchase_contracts"
    id              = Column(Integer, primary_key=True, index=True)
    contract_no     = Column(String(30))
    project_id      = Column(Integer, ForeignKey("projects.id"), nullable=True)
    vendor_name     = Column(String(200), nullable=False)        # 거래처명 (직접 입력)
    vendor_id       = Column(Integer, ForeignKey("companies.id"), nullable=True)
    contract_name   = Column(String(300), nullable=False)
    contract_type   = Column(String(20), default="자재")         # 자재/노무/외주/장비/기타
    contract_amount = Column(Numeric(18, 2), default=0)
    start_date      = Column(Date)
    end_date        = Column(Date)
    status          = Column(String(20), default="진행")         # 진행/완료/해지
    notes           = Column(Text)
    created_by      = Column(Integer, ForeignKey("users.id"))
    created_at      = Column(DateTime, default=func.now())
    updated_at      = Column(DateTime, default=func.now(), onupdate=func.now())

    project = relationship("Project", foreign_keys=[project_id])
    vendor  = relationship("Company",  foreign_keys=[vendor_id])


class ReleaseRequest(Base):
    """출고 요청 — 자재 창고 출고 요청"""
    __tablename__ = "release_requests"
    id            = Column(Integer, primary_key=True, index=True)
    request_no    = Column(String(30))
    project_id    = Column(Integer, ForeignKey("projects.id"), nullable=True)
    material_name = Column(String(200), nullable=False)          # 자재명 (직접 입력)
    material_id   = Column(Integer, ForeignKey("materials.id"), nullable=True)
    quantity      = Column(Numeric(14, 4), default=0)
    unit          = Column(String(20))
    request_date  = Column(Date)
    needed_date   = Column(Date)
    status        = Column(String(20), default="요청")           # 요청/승인/출고/취소
    notes         = Column(Text)
    created_by    = Column(Integer, ForeignKey("users.id"))
    created_at    = Column(DateTime, default=func.now())
    updated_at    = Column(DateTime, default=func.now(), onupdate=func.now())

    project  = relationship("Project",  foreign_keys=[project_id])
    material = relationship("Material", foreign_keys=[material_id])


class SalesBill(Base):
    """매출 청구 — 세금계산서 발행 요청"""
    __tablename__ = "sales_bills"
    id           = Column(Integer, primary_key=True, index=True)
    bill_no      = Column(String(30))
    project_id   = Column(Integer, ForeignKey("projects.id"), nullable=True)
    client_name  = Column(String(200))
    bill_amount  = Column(Numeric(18, 2), default=0)             # 공급가액
    vat_amount   = Column(Numeric(18, 2), default=0)             # 부가세
    total_amount = Column(Numeric(18, 2), default=0)             # 합계
    bill_date    = Column(Date)
    due_date     = Column(Date)
    invoice_no   = Column(String(50))                            # 세금계산서 번호
    invoice_date = Column(Date)
    status       = Column(String(20), default="발행요청")        # 발행요청/발행완료/확인
    notes        = Column(Text)
    created_by   = Column(Integer, ForeignKey("users.id"))
    created_at   = Column(DateTime, default=func.now())
    updated_at   = Column(DateTime, default=func.now(), onupdate=func.now())

    project = relationship("Project", foreign_keys=[project_id])


class APBill(Base):
    """매입 청구 — 하도급 지급 요청"""
    __tablename__ = "ap_bills"
    id           = Column(Integer, primary_key=True, index=True)
    bill_no      = Column(String(30))
    project_id   = Column(Integer, ForeignKey("projects.id"), nullable=True)
    vendor_name  = Column(String(200), nullable=False)
    vendor_id    = Column(Integer, ForeignKey("companies.id"), nullable=True)
    bill_amount  = Column(Numeric(18, 2), default=0)
    vat_amount   = Column(Numeric(18, 2), default=0)
    total_amount = Column(Numeric(18, 2), default=0)
    bill_date    = Column(Date)
    due_date     = Column(Date)
    status       = Column(String(20), default="지급요청")        # 지급요청/승인/지급완료
    notes        = Column(Text)
    created_by   = Column(Integer, ForeignKey("users.id"))
    created_at   = Column(DateTime, default=func.now())
    updated_at   = Column(DateTime, default=func.now(), onupdate=func.now())

    project = relationship("Project", foreign_keys=[project_id])
    vendor  = relationship("Company",  foreign_keys=[vendor_id])
