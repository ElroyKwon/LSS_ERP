from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Timesheet(Base):
    """타임시트 헤더 — 직원별 주간 단위"""
    __tablename__ = "timesheets"
    id            = Column(Integer, primary_key=True, index=True)
    employee_id   = Column(Integer, ForeignKey("employees.id"), nullable=False)
    week_start    = Column(Date, nullable=False)   # 주 시작 (월요일)
    week_end      = Column(Date, nullable=False)   # 주 종료 (일요일)
    total_hours   = Column(Numeric(6, 2), default=0)
    status        = Column(String(20), default="작성중")  # 작성중/제출/승인/반려
    submitted_at  = Column(DateTime)
    approved_by   = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at   = Column(DateTime)
    reject_reason = Column(Text)
    notes         = Column(Text)
    created_by    = Column(Integer, ForeignKey("users.id"))
    created_at    = Column(DateTime, default=func.now())
    updated_at    = Column(DateTime, default=func.now(), onupdate=func.now())

    employee = relationship("Employee", foreign_keys=[employee_id])
    entries  = relationship("TimesheetEntry", back_populates="timesheet",
                            cascade="all, delete-orphan", order_by="TimesheetEntry.sort_order")


class TimesheetEntry(Base):
    """타임시트 입력 행 — 프로젝트별 일별 시간"""
    __tablename__ = "timesheet_entries"
    id           = Column(Integer, primary_key=True, index=True)
    timesheet_id = Column(Integer, ForeignKey("timesheets.id", ondelete="CASCADE"))
    project_id   = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project_name = Column(String(300))          # 직접 입력 (프로젝트 미연동 시)
    project_source = Column(String(20), default="공통")  # 실행/영업/공통
    spg          = Column(String(20), default="에너지")
    labor_type   = Column(String(20), default="원가")
    work_type    = Column(String(200), default="기타")  # 다중 작업유형은 구분 문자열로 저장
    mon_hours    = Column(Numeric(4, 2), default=0)
    tue_hours    = Column(Numeric(4, 2), default=0)
    wed_hours    = Column(Numeric(4, 2), default=0)
    thu_hours    = Column(Numeric(4, 2), default=0)
    fri_hours    = Column(Numeric(4, 2), default=0)
    sat_hours    = Column(Numeric(4, 2), default=0)
    sun_hours    = Column(Numeric(4, 2), default=0)
    sort_order   = Column(Integer, default=0)
    notes        = Column(Text)

    timesheet = relationship("Timesheet", back_populates="entries")
    project   = relationship("Project", foreign_keys=[project_id])
