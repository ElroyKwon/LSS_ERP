from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime, timedelta
from ..database import get_db
from ..models.timesheet import Timesheet, TimesheetEntry
from ..models.master import Employee, OverheadRate
from ..models.common import Department
from ..models.execution import Project
from ..models.purchase import CostInput
from ..utils.auth import get_current_user
from ..utils import to_kst, to_kst_date
from ..utils.permissions import is_system_admin, normalize_role
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["타임시트"])

WORK_TYPES = [
    "공통 > 연차", "공통 > 교육", "공통 > 행사", "공통 > 기타",
    "영업 > 설계", "영업 > 견적", "영업 > 제안서", "영업 > 미팅", "영업 > 기타",
    "실행 > 현장관리", "실행 > 시운전", "실행 > 안전관리", "실행 > 유지보수", "실행 > 업무지원",
    "실행 > 하자처리(유상)", "실행 > 하자처리(무상)", "실행 > 기타",
    "경영지원 > 구매", "경영지원 > 총무", "경영지원 > 인사", "경영지원 > 회계",
    "경영지원 > 자금", "경영지원 > 공시", "경영지원 > 기타",
]
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _week_of(d: date):
    """날짜가 속한 주의 월요일 ~ 일요일 반환"""
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def _entry_dict(e: TimesheetEntry) -> dict:
    total = sum(float(getattr(e, f"{d}_hours") or 0) for d in DAYS)
    return {
        "id": e.id, "sort_order": e.sort_order,
        "project_id":   e.project_id,
        "project_name": e.project_name or (e.project.project_name if e.project else None),
        "spg":          e.spg or "에너지",
        "labor_type":   e.labor_type or "원가",
        "work_type":    e.work_type or "공통 > 기타",
        **{f"{d}_hours": float(getattr(e, f"{d}_hours") or 0) for d in DAYS},
        "row_total": total, "notes": e.notes,
    }


def _ts_dict(ts: Timesheet, include_entries=True) -> dict:
    d = {
        "id": ts.id,
        "employee_id":   ts.employee_id,
        "employee_name": ts.employee.name if ts.employee else None,
        "week_start":    to_kst_date(ts.week_start),
        "week_end":      to_kst_date(ts.week_end),
        "total_hours":   float(ts.total_hours or 0),
        "status":        ts.status,
        "submitted_at":  to_kst(ts.submitted_at),
        "approved_by":   ts.approved_by,
        "approved_at":   to_kst(ts.approved_at),
        "reject_reason": ts.reject_reason,
        "notes":         ts.notes,
        "created_at":    to_kst(ts.created_at),
    }
    if include_entries:
        d["entries"] = [_entry_dict(e) for e in ts.entries]
    return d


def _employee_dict(emp: Employee) -> dict:
    return {
        "id": emp.id,
        "emp_code": emp.emp_code,
        "name": emp.name,
        "department_id": emp.department_id,
        "department_name": emp.department.name if emp.department else emp.department_name,
        "department": emp.department_name,
        "position": emp.position,
        "job_title": emp.job_title,
        "email": emp.email,
        "is_active": emp.is_active,
    }


def _current_employee(db: Session, current) -> Employee | None:
    if current.employee_code:
        emp = db.query(Employee).filter(Employee.emp_code == current.employee_code).first()
        if emp:
            return emp
    return db.query(Employee).filter(Employee.name == current.name).first()


def _descendant_department_ids(db: Session, department_id: int | None) -> set[int]:
    if not department_id:
        return set()
    ids = {department_id}
    frontier = [department_id]
    while frontier:
        child_rows = db.query(Department.id).filter(
            Department.parent_id.in_(frontier),
            Department.is_active == True,
        ).all()
        children = [row.id for row in child_rows if row.id not in ids]
        ids.update(children)
        frontier = children
    return ids


def _allowed_employee_ids(db: Session, current) -> set[int] | None:
    if is_system_admin(current.role):
        return None

    current_emp = _current_employee(db, current)
    role = normalize_role(current.role)
    scope_department_id = current.department_id or (current_emp.department_id if current_emp else None)
    if role.endswith("_manager") and scope_department_id:
        department_ids = _descendant_department_ids(db, scope_department_id)
        if department_ids:
            rows = db.query(Employee.id).filter(
                Employee.is_active == True,
                Employee.department_id.in_(department_ids),
            ).all()
            scoped_ids = {row.id for row in rows}
            if current_emp:
                scoped_ids.add(current_emp.id)
            return scoped_ids

    return {current_emp.id} if current_emp else set()


def _require_employee_access(employee_id: int, db: Session, current) -> None:
    allowed_ids = _allowed_employee_ids(db, current)
    if allowed_ids is not None and employee_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="해당 직원의 타임시트를 조회할 권한이 없습니다.")


# ── Pydantic 스키마 ──────────────────────────────────────────
class EntryIn(BaseModel):
    project_id:   Optional[int]  = None
    project_name: Optional[str]  = None
    spg:          str             = "에너지"
    labor_type:   str             = "원가"
    work_type:    str             = "공통 > 기타"
    mon_hours:    Decimal         = Decimal(0)
    tue_hours:    Decimal         = Decimal(0)
    wed_hours:    Decimal         = Decimal(0)
    thu_hours:    Decimal         = Decimal(0)
    fri_hours:    Decimal         = Decimal(0)
    sat_hours:    Decimal         = Decimal(0)
    sun_hours:    Decimal         = Decimal(0)
    sort_order:   int             = 0
    notes:        Optional[str]   = None


class TimesheetCreate(BaseModel):
    employee_id: int
    week_start:  date
    entries:     List[EntryIn] = []
    notes:       Optional[str] = None


class RejectIn(BaseModel):
    reason: Optional[str] = None


@router.get("/timesheets/employees")
def list_timesheet_employees(db: Session = Depends(get_db), current=Depends(get_current_user)):
    allowed_ids = _allowed_employee_ids(db, current)
    q = db.query(Employee).filter(Employee.is_active == True)
    if allowed_ids is not None:
        if not allowed_ids:
            return []
        q = q.filter(Employee.id.in_(allowed_ids))
    rows = q.order_by(Employee.name.asc(), Employee.id.asc()).all()
    return [_employee_dict(row) for row in rows]


# ── 주간 타임시트 목록 ──────────────────────────────────────────
@router.get("/timesheets")
def list_timesheets(
    employee_id: Optional[int] = None,
    week_start:  Optional[date] = None,
    status:      Optional[str] = None,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    q = db.query(Timesheet)
    allowed_ids = _allowed_employee_ids(db, current)
    if allowed_ids is not None:
        if not allowed_ids:
            return []
        q = q.filter(Timesheet.employee_id.in_(allowed_ids))
    if employee_id:
        _require_employee_access(employee_id, db, current)
        q = q.filter(Timesheet.employee_id == employee_id)
    if week_start:  q = q.filter(Timesheet.week_start  == week_start)
    if status:      q = q.filter(Timesheet.status       == status)
    rows = q.order_by(Timesheet.week_start.desc()).all()
    return [_ts_dict(r, include_entries=False) for r in rows]


# ── 주간 타임시트 상세 (그리드 데이터) ────────────────────────
@router.get("/timesheets/week")
def get_week_timesheet(
    employee_id: int,
    week_start:  date,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    _require_employee_access(employee_id, db, _)
    monday, sunday = _week_of(week_start)
    ts = db.query(Timesheet).filter(
        Timesheet.employee_id == employee_id,
        Timesheet.week_start  == monday,
    ).first()
    if not ts:
        return {"id": None, "employee_id": employee_id,
                "week_start": str(monday), "week_end": str(sunday),
                "status": "작성중", "total_hours": 0, "entries": []}
    return _ts_dict(ts)


# ── 타임시트 저장 (upsert) ──────────────────────────────────────
@router.post("/timesheets")
def save_timesheet(data: TimesheetCreate, db: Session = Depends(get_db),
                   current=Depends(get_current_user)):
    _require_employee_access(data.employee_id, db, current)
    monday, sunday = _week_of(data.week_start)
    ts = db.query(Timesheet).filter(
        Timesheet.employee_id == data.employee_id,
        Timesheet.week_start  == monday,
    ).first()

    if ts:
        ts.notes = data.notes
        ts.status = "작성중"
        ts.submitted_at = None
        ts.approved_by = None
        ts.approved_at = None
        ts.reject_reason = None
        db.query(TimesheetEntry).filter(TimesheetEntry.timesheet_id == ts.id).delete()
    else:
        ts = Timesheet(employee_id=data.employee_id, week_start=monday, week_end=sunday,
                       status="작성중", notes=data.notes, created_by=current.id)
        db.add(ts)
        db.flush()

    total = 0
    for i, e in enumerate(data.entries):
        entry_data = e.model_dump()
        entry_data["sort_order"] = i
        entry = TimesheetEntry(**entry_data, timesheet_id=ts.id)
        row_total = sum(float(getattr(entry, f"{d}_hours") or 0) for d in DAYS)
        total += row_total
        db.add(entry)

    ts.total_hours = total
    db.commit(); db.refresh(ts)
    return _ts_dict(ts)


# ── 제출 ──────────────────────────────────────────────────────
@router.post("/timesheets/{tid}/submit")
def submit_timesheet(tid: int, db: Session = Depends(get_db),
                     current=Depends(get_current_user)):
    ts = db.query(Timesheet).filter(Timesheet.id == tid).first()
    if not ts: raise HTTPException(404, "타임시트를 찾을 수 없습니다.")
    if ts.status != "작성중": raise HTTPException(400, f"현재 상태({ts.status})에서 제출할 수 없습니다.")
    ts.status = "제출"
    ts.submitted_at = datetime.utcnow()
    db.commit()
    return {"message": "제출되었습니다."}


# ── 승인 ──────────────────────────────────────────────────────
@router.post("/timesheets/{tid}/approve")
def approve_timesheet(tid: int, db: Session = Depends(get_db),
                      current=Depends(get_current_user)):
    ts = db.query(Timesheet).filter(Timesheet.id == tid).first()
    if not ts: raise HTTPException(404, "타임시트를 찾을 수 없습니다.")
    if ts.status != "제출": raise HTTPException(400, "제출된 타임시트만 승인할 수 있습니다.")

    ts.status = "승인"
    ts.approved_by = current.id
    ts.approved_at = datetime.utcnow()

    # 프로젝트 연동: 승인 시 원가 투입 자동 생성
    rate_row = db.query(OverheadRate).filter(
        OverheadRate.rate_year == ts.week_start.year
    ).first()
    hourly_rate = float(rate_row.labor_rate) if rate_row else 0

    for entry in ts.entries:
        if entry.project_id and hourly_rate > 0:
            total_hrs = sum(float(getattr(entry, f"{d}_hours") or 0) for d in DAYS)
            if total_hrs > 0:
                cost = CostInput(
                    site_id=None, cost_type="labor",
                    description=f"타임시트 [{ts.employee.name}] {ts.week_start}~{ts.week_end} / {entry.work_type}",
                    amount=total_hrs * hourly_rate * 10000,  # 임율(만원/h) → 원
                    input_date=ts.week_end,
                    created_by=current.id,
                )
                db.add(cost)

    db.commit()
    return {"message": "승인되었습니다."}


# ── 반려 ──────────────────────────────────────────────────────
@router.post("/timesheets/{tid}/reject")
def reject_timesheet(tid: int, data: RejectIn, db: Session = Depends(get_db),
                     current=Depends(get_current_user)):
    ts = db.query(Timesheet).filter(Timesheet.id == tid).first()
    if not ts: raise HTTPException(404, "타임시트를 찾을 수 없습니다.")
    if ts.status != "제출": raise HTTPException(400, "제출된 타임시트만 반려할 수 있습니다.")
    ts.status = "반려"
    ts.reject_reason = data.reason
    db.commit()
    return {"message": "반려되었습니다."}


# ── 팀 현황 (당주 제출 현황) ──────────────────────────────────
@router.get("/timesheets/team-status")
def team_status(week_start: date, db: Session = Depends(get_db),
                current=Depends(get_current_user)):
    monday, sunday = _week_of(week_start)
    allowed_ids = _allowed_employee_ids(db, current)
    employee_q = db.query(Employee).filter(Employee.is_active == True)
    if allowed_ids is not None:
        if not allowed_ids:
            return []
        employee_q = employee_q.filter(Employee.id.in_(allowed_ids))
    employees = employee_q.all()
    submitted = {
        ts.employee_id: ts
        for ts in db.query(Timesheet).filter(Timesheet.week_start == monday).all()
    }
    result = []
    for emp in employees:
        ts = submitted.get(emp.id)
        result.append({
            "employee_id":   emp.id,
            "employee_name": emp.name,
            "department":    emp.department_name,
            "position":      emp.position,
            "status":        ts.status if ts else "미작성",
            "total_hours":   float(ts.total_hours or 0) if ts else 0,
            "timesheet_id":  ts.id if ts else None,
        })
    return result


# ── 통계 ──────────────────────────────────────────────────────
@router.get("/timesheets/stats")
def timesheet_stats(employee_id: Optional[int] = None,
                    year: Optional[int] = None, month: Optional[int] = None,
                    db: Session = Depends(get_db), current=Depends(get_current_user)):
    now = datetime.now()
    y = year or now.year; m = month or now.month
    q = db.query(Timesheet).filter(
        sqlfunc.extract("year",  Timesheet.week_start) == y,
        sqlfunc.extract("month", Timesheet.week_start) == m,
        Timesheet.status == "승인",
    )
    allowed_ids = _allowed_employee_ids(db, current)
    if allowed_ids is not None:
        if not allowed_ids:
            sheets = []
        else:
            q = q.filter(Timesheet.employee_id.in_(allowed_ids))
            if employee_id:
                _require_employee_access(employee_id, db, current)
                q = q.filter(Timesheet.employee_id == employee_id)
            sheets = q.all()
    else:
        if employee_id:
            q = q.filter(Timesheet.employee_id == employee_id)
        sheets = q.all()

    proj_hours = {}
    for ts in sheets:
        for e in ts.entries:
            key = e.project_name or "기타"
            proj_hours[key] = proj_hours.get(key, 0) + float(e.row_total if hasattr(e, 'row_total') else
                sum(float(getattr(e, f"{d}_hours") or 0) for d in DAYS))

    return {
        "month_total": sum(float(ts.total_hours or 0) for ts in sheets),
        "sheet_count": len(sheets),
        "by_project":  [{"project": k, "hours": v} for k, v in sorted(proj_hours.items(), key=lambda x: -x[1])],
    }
