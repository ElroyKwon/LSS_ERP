from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, extract
from typing import Optional
from datetime import date, datetime
from ..database import get_db
from ..models.vehicle import Vehicle, VehicleLog
from ..utils.auth import get_current_user
from ..utils import to_kst, to_kst_date
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api", tags=["차량일지"])

VEHICLE_TYPES = ["세단", "SUV", "승합", "화물", "기타"]
PURPOSES      = ["업무", "출장", "현장방문", "자재구매", "임원업무", "기타"]
FUEL_TYPES    = ["휘발유", "경유", "LPG", "전기", "하이브리드"]


# ─── Pydantic 스키마 ───────────────────────────────────────────
class VehicleCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    plate_no:     str
    vehicle_type: Optional[str] = "세단"
    model_name:   Optional[str] = None
    model_year:   Optional[int] = None
    color:        Optional[str] = None
    purpose:      Optional[str] = "업무용"
    fuel_type:    Optional[str] = "휘발유"
    manager_name: Optional[str] = None
    insurance_exp: Optional[date] = None
    inspect_exp:   Optional[date] = None
    current_km:   Optional[int] = 0
    notes:        Optional[str] = None


class VehicleLogCreate(BaseModel):
    vehicle_id:   int
    driver_name:  str
    driver_dept:  Optional[str] = None
    log_date:     date
    depart_time:  Optional[str] = None
    arrive_time:  Optional[str] = None
    start_km:     Optional[int] = 0
    end_km:       Optional[int] = 0
    departure:    Optional[str] = None
    destination:  Optional[str] = None
    purpose:      Optional[str] = "업무"
    project_id:   Optional[int] = None
    project_name: Optional[str] = None
    fuel_amount:  Optional[float] = 0
    fuel_cost:    Optional[int] = 0
    toll_cost:    Optional[int] = 0
    parking_cost: Optional[int] = 0
    notes:        Optional[str] = None


# ─── 직렬화 ───────────────────────────────────────────────────
def _v_dict(v: Vehicle) -> dict:
    today = date.today()
    ins_warn = v.insurance_exp and (v.insurance_exp - today).days <= 30 if v.insurance_exp else False
    isp_warn = v.inspect_exp   and (v.inspect_exp   - today).days <= 30 if v.inspect_exp   else False
    return {
        "id": v.id, "plate_no": v.plate_no,
        "vehicle_type": v.vehicle_type, "model_name": v.model_name,
        "model_year": v.model_year, "color": v.color,
        "purpose": v.purpose, "fuel_type": v.fuel_type,
        "manager_name": v.manager_name,
        "insurance_exp": to_kst_date(v.insurance_exp),
        "inspect_exp":   to_kst_date(v.inspect_exp),
        "current_km": v.current_km or 0,
        "is_active":  v.is_active,
        "notes": v.notes,
        "insurance_warning": ins_warn,
        "inspect_warning":   isp_warn,
        "created_at": to_kst(v.created_at),
    }


def _log_dict(l: VehicleLog) -> dict:
    return {
        "id": l.id,
        "vehicle_id":   l.vehicle_id,
        "plate_no":     l.vehicle.plate_no     if l.vehicle else None,
        "model_name":   l.vehicle.model_name   if l.vehicle else None,
        "driver_name":  l.driver_name,
        "driver_dept":  l.driver_dept,
        "log_date":     to_kst_date(l.log_date),
        "depart_time":  l.depart_time,
        "arrive_time":  l.arrive_time,
        "start_km":     l.start_km or 0,
        "end_km":       l.end_km   or 0,
        "distance":     l.distance or 0,
        "departure":    l.departure,
        "destination":  l.destination,
        "purpose":      l.purpose,
        "project_id":   l.project_id,
        "project_name": l.project_name or (l.project.project_name if l.project else None),
        "fuel_amount":  float(l.fuel_amount or 0),
        "fuel_cost":    l.fuel_cost    or 0,
        "toll_cost":    l.toll_cost    or 0,
        "parking_cost": l.parking_cost or 0,
        "extra_total":  (l.fuel_cost or 0) + (l.toll_cost or 0) + (l.parking_cost or 0),
        "notes": l.notes,
        "created_at": to_kst(l.created_at),
    }


# ═══════════════════════════════════════════════════
# 차량 마스터
# ═══════════════════════════════════════════════════
@router.get("/vehicles")
def list_vehicles(is_active: Optional[bool] = None,
                  db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Vehicle)
    if is_active is not None:
        q = q.filter(Vehicle.is_active == is_active)
    return [_v_dict(v) for v in q.order_by(Vehicle.plate_no).all()]


@router.post("/vehicles")
def create_vehicle(data: VehicleCreate, db: Session = Depends(get_db),
                   current=Depends(get_current_user)):
    if db.query(Vehicle).filter(Vehicle.plate_no == data.plate_no).first():
        raise HTTPException(400, "이미 등록된 차량번호입니다.")
    v = Vehicle(**data.dict(), created_by=current.id)
    db.add(v); db.commit(); db.refresh(v)
    return _v_dict(v)


@router.put("/vehicles/{vid}")
def update_vehicle(vid: int, data: VehicleCreate,
                   db: Session = Depends(get_db), _=Depends(get_current_user)):
    v = db.query(Vehicle).filter(Vehicle.id == vid).first()
    if not v: raise HTTPException(404, "차량을 찾을 수 없습니다.")
    for f, val in data.dict(exclude_none=False).items():
        setattr(v, f, val)
    db.commit(); db.refresh(v)
    return _v_dict(v)


@router.delete("/vehicles/{vid}")
def delete_vehicle(vid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    v = db.query(Vehicle).filter(Vehicle.id == vid).first()
    if not v: raise HTTPException(404, "차량을 찾을 수 없습니다.")
    db.delete(v); db.commit()
    return {"message": "삭제되었습니다."}


# ═══════════════════════════════════════════════════
# 운행 일지
# ═══════════════════════════════════════════════════
@router.get("/vehicle-logs")
def list_logs(vehicle_id: Optional[int] = None,
              driver_name: Optional[str] = None,
              date_from: Optional[date] = None,
              date_to:   Optional[date] = None,
              year:  Optional[int] = None,
              month: Optional[int] = None,
              db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(VehicleLog)
    if vehicle_id:  q = q.filter(VehicleLog.vehicle_id == vehicle_id)
    if driver_name: q = q.filter(VehicleLog.driver_name.ilike(f"%{driver_name}%"))
    if date_from:   q = q.filter(VehicleLog.log_date >= date_from)
    if date_to:     q = q.filter(VehicleLog.log_date <= date_to)
    if year:        q = q.filter(extract("year",  VehicleLog.log_date) == year)
    if month:       q = q.filter(extract("month", VehicleLog.log_date) == month)
    return [_log_dict(l) for l in q.order_by(VehicleLog.log_date.desc()).all()]


@router.post("/vehicle-logs")
def create_log(data: VehicleLogCreate, db: Session = Depends(get_db),
               current=Depends(get_current_user)):
    d = data.dict()
    d["distance"] = max(0, (d.get("end_km") or 0) - (d.get("start_km") or 0))
    log = VehicleLog(**d, created_by=current.id)
    db.add(log)
    # 차량 현재 km 업데이트
    if d["end_km"]:
        v = db.query(Vehicle).filter(Vehicle.id == data.vehicle_id).first()
        if v and (v.current_km or 0) < d["end_km"]:
            v.current_km = d["end_km"]
    db.commit(); db.refresh(log)
    return _log_dict(log)


@router.put("/vehicle-logs/{lid}")
def update_log(lid: int, data: VehicleLogCreate,
               db: Session = Depends(get_db), _=Depends(get_current_user)):
    log = db.query(VehicleLog).filter(VehicleLog.id == lid).first()
    if not log: raise HTTPException(404, "일지를 찾을 수 없습니다.")
    d = data.dict()
    d["distance"] = max(0, (d.get("end_km") or 0) - (d.get("start_km") or 0))
    for f, val in d.items(): setattr(log, f, val)
    db.commit(); db.refresh(log)
    return _log_dict(log)


@router.delete("/vehicle-logs/{lid}")
def delete_log(lid: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    log = db.query(VehicleLog).filter(VehicleLog.id == lid).first()
    if not log: raise HTTPException(404, "일지를 찾을 수 없습니다.")
    db.delete(log); db.commit()
    return {"message": "삭제되었습니다."}


# ═══════════════════════════════════════════════════
# 통계
# ═══════════════════════════════════════════════════
@router.get("/vehicle-stats")
def vehicle_stats(year: Optional[int] = None, month: Optional[int] = None,
                  db: Session = Depends(get_db), _=Depends(get_current_user)):
    now = datetime.now()
    y = year or now.year; m = month or now.month

    q = db.query(VehicleLog).filter(
        extract("year",  VehicleLog.log_date) == y,
        extract("month", VehicleLog.log_date) == m,
    )
    logs = q.all()

    total_distance = sum(l.distance or 0 for l in logs)
    total_fuel_cost = sum(l.fuel_cost or 0 for l in logs)
    total_toll = sum(l.toll_cost or 0 for l in logs)
    total_parking = sum(l.parking_cost or 0 for l in logs)

    # 차량별 통계
    by_vehicle = {}
    for l in logs:
        key = l.vehicle.plate_no if l.vehicle else "기타"
        if key not in by_vehicle:
            by_vehicle[key] = {"plate_no": key, "count": 0, "distance": 0, "fuel_cost": 0}
        by_vehicle[key]["count"]     += 1
        by_vehicle[key]["distance"]  += l.distance or 0
        by_vehicle[key]["fuel_cost"] += l.fuel_cost or 0

    # 월별 트렌드 (당년 12개월)
    monthly = []
    for mo in range(1, 13):
        mq = db.query(VehicleLog).filter(
            extract("year",  VehicleLog.log_date) == y,
            extract("month", VehicleLog.log_date) == mo,
        )
        ml = mq.all()
        monthly.append({
            "month": mo,
            "count":    len(ml),
            "distance": sum(l.distance or 0 for l in ml),
            "fuel_cost": sum(l.fuel_cost or 0 for l in ml),
        })

    return {
        "year": y, "month": m,
        "summary": {
            "count":          len(logs),
            "total_distance": total_distance,
            "fuel_cost":      total_fuel_cost,
            "toll_cost":      total_toll,
            "parking_cost":   total_parking,
            "total_extra":    total_fuel_cost + total_toll + total_parking,
        },
        "by_vehicle": list(by_vehicle.values()),
        "monthly":    monthly,
    }
