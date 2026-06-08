from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Vehicle(Base):
    """차량 마스터"""
    __tablename__ = "vehicles"
    id            = Column(Integer, primary_key=True, index=True)
    plate_no      = Column(String(20), unique=True, nullable=False)  # 차량번호
    vehicle_type  = Column(String(50))       # 차종 (세단/SUV/승합/화물/기타)
    model_name    = Column(String(100))      # 모델명
    model_year    = Column(Integer)          # 연식
    color         = Column(String(30))       # 색상
    purpose       = Column(String(30), default="업무용")  # 업무용/현장용/임원용
    fuel_type     = Column(String(20), default="휘발유")  # 휘발유/경유/LPG/전기
    manager_name  = Column(String(100))      # 관리 담당자
    insurance_exp = Column(Date)             # 보험 만료일
    inspect_exp   = Column(Date)             # 정기검사 만료일
    current_km    = Column(Integer, default=0)  # 현재 누적 km
    is_active     = Column(Boolean, default=True)
    notes         = Column(Text)
    created_by    = Column(Integer, ForeignKey("users.id"))
    created_at    = Column(DateTime, default=func.now())
    updated_at    = Column(DateTime, default=func.now(), onupdate=func.now())


class VehicleLog(Base):
    """차량 운행 일지"""
    __tablename__ = "vehicle_logs"
    id            = Column(Integer, primary_key=True, index=True)
    vehicle_id    = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    driver_name   = Column(String(100), nullable=False)   # 운전자 (직접 입력)
    driver_dept   = Column(String(100))                   # 소속 부서
    log_date      = Column(Date, nullable=False)          # 운행일
    depart_time   = Column(String(5))                     # 출발 시각 (HH:MM)
    arrive_time   = Column(String(5))                     # 도착 시각
    start_km      = Column(Integer, default=0)            # 출발 km
    end_km        = Column(Integer, default=0)            # 도착 km
    distance      = Column(Integer, default=0)            # 주행거리 (자동계산)
    departure     = Column(String(200))                   # 출발지
    destination   = Column(String(200))                   # 도착지
    purpose       = Column(String(50), default="업무")    # 목적
    project_id    = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project_name  = Column(String(300))                   # 프로젝트 (직접 입력)
    fuel_amount   = Column(Numeric(8, 2), default=0)      # 주유량 (L)
    fuel_cost     = Column(Integer, default=0)            # 주유 비용 (원)
    toll_cost     = Column(Integer, default=0)            # 통행료
    parking_cost  = Column(Integer, default=0)            # 주차비
    notes         = Column(Text)
    created_by    = Column(Integer, ForeignKey("users.id"))
    created_at    = Column(DateTime, default=func.now())
    updated_at    = Column(DateTime, default=func.now(), onupdate=func.now())

    vehicle = relationship("Vehicle",  foreign_keys=[vehicle_id])
    project = relationship("Project",  foreign_keys=[project_id])
