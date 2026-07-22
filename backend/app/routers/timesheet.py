from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sqlfunc
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime, timedelta
from ..database import get_db
from ..models.timesheet import Timesheet, TimesheetEntry, TimesheetLaborAllocation
from ..models.master import Employee, OverheadRate
from ..models.common import Department, User
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
PROJECT_SOURCES = {"실행", "영업", "공통"}
TIMESHEET_ADMIN_ROLES = {"system_admin", "accounting_manager"}
LABOR_ALLOCATION_CATEGORIES = ["급여", "상여", "퇴충"]


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
        "project_source": e.project_source or ("실행" if e.project_id else "공통"),
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


def _employee_dict(emp: Employee, labor_type: str | None = None) -> dict:
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
        "labor_type": labor_type or "원가",
        "is_active": emp.is_active,
    }


def _normalize_entry_data(entry_data: dict) -> dict:
    source = (entry_data.get("project_source") or "").strip()
    if source not in PROJECT_SOURCES:
        source = "실행" if entry_data.get("project_id") else "공통"

    project_name = (entry_data.get("project_name") or "").strip()
    if project_name == "연차":
        entry_data["project_id"] = None
        source = "공통"
        entry_data["project_name"] = "연차"
        entry_data["work_type"] = "공통 > 연차"

    entry_data["project_source"] = source
    return entry_data


def _current_employee(db: Session, current) -> Employee | None:
    if current.employee_code:
        emp = db.query(Employee).filter(Employee.emp_code == current.employee_code).first()
        if emp:
            return emp
    return db.query(Employee).filter(Employee.name == current.name).first()


def _employee_labor_type(db: Session, employee_id: int) -> str:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    user = None
    if employee and employee.emp_code:
        user = db.query(User).filter(User.employee_code == employee.emp_code).first()
    if not user and employee and employee.name:
        user = db.query(User).filter(User.name == employee.name).first()
    labor_type = user.labor_type if user else None
    return labor_type if labor_type in {"판관", "원가"} else "원가"


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
    project_source: str           = "공통"
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


class LaborAllocationRowIn(BaseModel):
    category: str
    total_amount: Decimal = Decimal(0)
    contract_amount: Decimal = Decimal(0)
    other_amount: Decimal = Decimal(0)


class LaborAllocationSaveIn(BaseModel):
    year: int
    month: int
    rows: List[LaborAllocationRowIn] = []


def _require_timesheet_admin(current) -> None:
    if normalize_role(current.role) not in TIMESHEET_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="타임시트 관리자 기능을 사용할 권한이 없습니다.")


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    if year < 2000 or year > 2100:
        raise HTTPException(status_code=400, detail="연도는 2000~2100 사이여야 합니다.")
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="월은 1~12 사이여야 합니다.")
    start = date(year, month, 1)
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, next_month - timedelta(days=1)


def _allocation_dict(row: TimesheetLaborAllocation) -> dict:
    return {
        "category": row.category,
        "total_amount": float(row.total_amount or 0),
        "contract_amount": float(row.contract_amount or 0),
        "other_amount": float(row.other_amount or 0),
    }


def _validate_labor_allocation_amounts(row: LaborAllocationRowIn) -> None:
    if row.total_amount < 0 or row.contract_amount < 0 or row.other_amount < 0:
        raise HTTPException(status_code=400, detail="인건비 배부 금액은 음수로 입력할 수 없습니다.")


def _project_label(project: Project | None, entry: TimesheetEntry) -> str:
    if project:
        return " ".join(part for part in [project.project_no, project.project_name] if part) or project.project_name
    return entry.project_name or "기타"


def _sales_type(project: Project | None, source: str) -> str:
    if source == "영업":
        return "영업"
    if source == "공통":
        return "공통"
    return project.contract_type if project and project.contract_type else "-"


@router.get("/timesheets/employees")
def list_timesheet_employees(db: Session = Depends(get_db), current=Depends(get_current_user)):
    allowed_ids = _allowed_employee_ids(db, current)
    q = db.query(Employee).filter(Employee.is_active == True)
    if allowed_ids is not None:
        if not allowed_ids:
            return []
        q = q.filter(Employee.id.in_(allowed_ids))
    rows = q.order_by(Employee.name.asc(), Employee.id.asc()).all()
    user_by_code = {
        user.employee_code: user
        for user in db.query(User).filter(User.employee_code.isnot(None)).all()
    }
    return [
        _employee_dict(row, user_by_code.get(row.emp_code).labor_type if user_by_code.get(row.emp_code) else None)
        for row in rows
    ]


@router.get("/timesheets/common-projects")
def search_common_timesheet_projects(
    q: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    keyword = (q or "").strip()
    limit = max(1, min(limit, 50))
    query = (
        db.query(TimesheetEntry.project_name)
        .join(Timesheet, Timesheet.id == TimesheetEntry.timesheet_id)
        .filter(TimesheetEntry.project_name.isnot(None))
        .filter(TimesheetEntry.project_name != "")
        .filter(
            (TimesheetEntry.project_source == "공통")
            | (TimesheetEntry.project_id.is_(None))
        )
    )

    allowed_ids = _allowed_employee_ids(db, current)
    if allowed_ids is not None:
        if not allowed_ids:
            return []
        query = query.filter(Timesheet.employee_id.in_(allowed_ids))
    if keyword:
        query = query.filter(TimesheetEntry.project_name.ilike(f"%{keyword}%"))

    rows = (
        query.group_by(TimesheetEntry.project_name)
        .order_by(sqlfunc.max(Timesheet.updated_at).desc(), TimesheetEntry.project_name.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "value": row.project_name,
            "label": row.project_name,
            "project_name": row.project_name,
            "project_source": "공통",
            "source": "공통",
            "id": None,
        }
        for row in rows
        if row.project_name
    ]


@router.get("/timesheets/admin-labor")
def get_timesheet_admin_labor(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    _require_timesheet_admin(current)
    month_start, month_end = _month_bounds(year, month)
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    saved_allocations = {
        row.category: _allocation_dict(row)
        for row in db.query(TimesheetLaborAllocation)
        .filter(
            TimesheetLaborAllocation.allocation_year == year,
            TimesheetLaborAllocation.allocation_month == month,
        )
        .all()
    }
    allocation_rows = []
    for category in LABOR_ALLOCATION_CATEGORIES:
        allocation_rows.append(
            saved_allocations.get(
                category,
                {"category": category, "total_amount": 0, "contract_amount": 0, "other_amount": 0},
            )
        )
    allocation_rows.append({
        "category": "합계",
        "total_amount": sum(float(row["total_amount"] or 0) for row in allocation_rows),
        "contract_amount": sum(float(row["contract_amount"] or 0) for row in allocation_rows),
        "other_amount": sum(float(row["other_amount"] or 0) for row in allocation_rows),
    })

    monthly_pools = {
        row.allocation_month: float(row.total_amount or 0)
        for row in db.query(
            TimesheetLaborAllocation.allocation_month,
            sqlfunc.sum(TimesheetLaborAllocation.total_amount).label("total_amount"),
        )
        .filter(TimesheetLaborAllocation.allocation_year == year)
        .group_by(TimesheetLaborAllocation.allocation_month)
        .all()
    }

    sheets = (
        db.query(Timesheet)
        .options(joinedload(Timesheet.entries).joinedload(TimesheetEntry.project))
        .filter(Timesheet.week_start <= year_end, Timesheet.week_end >= year_start)
        .all()
    )

    project_rows: dict[str, dict] = {}
    total_cost_hours_by_month = {m: 0.0 for m in range(1, 13)}

    for sheet in sheets:
        for entry in sheet.entries:
            source = entry.project_source or ("실행" if entry.project_id else "공통")
            project_key = f"{source}::{entry.project_id or entry.project_name or '기타'}"
            if project_key not in project_rows:
                project = entry.project
                project_rows[project_key] = {
                    "key": project_key,
                    "project": _project_label(project, entry),
                    "monthly_cost_hours": 0.0,
                    "monthly_admin_hours": 0.0,
                    "cumulative_cost_hours": 0.0,
                    "cumulative_admin_hours": 0.0,
                    "sales_type": _sales_type(project, source),
                    "status": project.status if project else "-",
                    "labor_total_amount": 0.0,
                    "monthly_labor": {m: 0.0 for m in range(1, 13)},
                    "_cost_hours_by_month": {m: 0.0 for m in range(1, 13)},
                }
            row = project_rows[project_key]
            labor_type = entry.labor_type if entry.labor_type in {"원가", "판관"} else "원가"

            for index, day in enumerate(DAYS):
                hours = float(getattr(entry, f"{day}_hours") or 0)
                if hours <= 0:
                    continue
                work_date = sheet.week_start + timedelta(days=index)
                if work_date.year != year:
                    continue

                work_month = work_date.month
                if labor_type == "원가":
                    row["_cost_hours_by_month"][work_month] += hours
                    total_cost_hours_by_month[work_month] += hours

                if month_start <= work_date <= month_end:
                    if labor_type == "판관":
                        row["monthly_admin_hours"] += hours
                    else:
                        row["monthly_cost_hours"] += hours
                if year_start <= work_date <= month_end:
                    if labor_type == "판관":
                        row["cumulative_admin_hours"] += hours
                    else:
                        row["cumulative_cost_hours"] += hours

    for row in project_rows.values():
        for m in range(1, 13):
            pool = monthly_pools.get(m, 0.0)
            total_hours = total_cost_hours_by_month.get(m, 0.0)
            hours = row["_cost_hours_by_month"].get(m, 0.0)
            if pool > 0 and total_hours > 0 and hours > 0:
                row["monthly_labor"][m] = round(pool * hours / total_hours)
        row["labor_total_amount"] = sum(row["monthly_labor"][m] for m in range(1, month + 1))
        row.pop("_cost_hours_by_month", None)

    return {
        "year": year,
        "month": month,
        "allocation_rows": allocation_rows,
        "project_rows": sorted(
            project_rows.values(),
            key=lambda item: (item["project"] or ""),
        ),
    }


@router.post("/timesheets/admin-labor")
def save_timesheet_admin_labor(
    data: LaborAllocationSaveIn,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    _require_timesheet_admin(current)
    _month_bounds(data.year, data.month)
    incoming = {
        row.category: row
        for row in data.rows
        if row.category in LABOR_ALLOCATION_CATEGORIES
    }
    for row in incoming.values():
        _validate_labor_allocation_amounts(row)

    existing = {
        row.category: row
        for row in db.query(TimesheetLaborAllocation)
        .filter(
            TimesheetLaborAllocation.allocation_year == data.year,
            TimesheetLaborAllocation.allocation_month == data.month,
        )
        .all()
    }

    for category in LABOR_ALLOCATION_CATEGORIES:
        source = incoming.get(category)
        if not source:
            continue
        row = existing.get(category)
        if not row:
            row = TimesheetLaborAllocation(
                allocation_year=data.year,
                allocation_month=data.month,
                category=category,
                created_by=current.id,
            )
            db.add(row)
        row.total_amount = source.total_amount
        row.contract_amount = source.contract_amount
        row.other_amount = source.other_amount
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="인건비 배부 금액 저장 중 DB 오류가 발생했습니다.")
    return get_timesheet_admin_labor(data.year, data.month, db, current)


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
    labor_type = _employee_labor_type(db, data.employee_id)
    for i, e in enumerate(data.entries):
        entry_data = _normalize_entry_data(e.model_dump())
        entry_data["labor_type"] = labor_type
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
