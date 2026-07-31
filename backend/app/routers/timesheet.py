from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sqlfunc
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime, timedelta
import json
from ..database import get_db
from ..models.timesheet import Timesheet, TimesheetEntry, TimesheetLaborAllocation, TimesheetMonthlyClose
from ..models.master import Employee, OverheadRate
from ..models.common import Department, User, Holiday
from ..models.execution import Project, ProjectPurchasePlanRow
from ..models.purchase import CostInput
from ..utils.auth import get_current_user
from ..utils import to_kst, to_kst_date
from ..utils.permissions import is_system_admin, normalize_role
from ..utils.system_accounts import exclude_system_account_employees, is_system_account_employee
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
CONTRACT_REVENUE_TYPES = {"공사", "공사진행율", "상품매출", "시운전"}
OTHER_REVENUE_TYPES = {"유지보수", "서비스"}


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


def _timesheet_activity_subquery(db: Session):
    entry_hours = (
        sqlfunc.coalesce(TimesheetEntry.mon_hours, 0)
        + sqlfunc.coalesce(TimesheetEntry.tue_hours, 0)
        + sqlfunc.coalesce(TimesheetEntry.wed_hours, 0)
        + sqlfunc.coalesce(TimesheetEntry.thu_hours, 0)
        + sqlfunc.coalesce(TimesheetEntry.fri_hours, 0)
        + sqlfunc.coalesce(TimesheetEntry.sat_hours, 0)
        + sqlfunc.coalesce(TimesheetEntry.sun_hours, 0)
    )
    return (
        db.query(
            TimesheetEntry.timesheet_id.label("timesheet_id"),
            sqlfunc.count(TimesheetEntry.id).label("entry_count"),
            sqlfunc.coalesce(sqlfunc.sum(entry_hours), 0).label("entry_hours"),
        )
        .group_by(TimesheetEntry.timesheet_id)
        .subquery()
    )


def _order_timesheets_by_activity(q, activity, week_first: bool = False):
    order = []
    if week_first:
        order.append(Timesheet.week_start.desc())
    order.extend([
        sqlfunc.coalesce(activity.c.entry_hours, 0).desc(),
        Timesheet.total_hours.desc(),
        sqlfunc.coalesce(activity.c.entry_count, 0).desc(),
        Timesheet.week_start.desc(),
        Timesheet.updated_at.desc(),
        Timesheet.id.desc(),
    ])
    return q.order_by(None).outerjoin(activity, activity.c.timesheet_id == Timesheet.id).order_by(*order)


def _active_timesheets_for_week(
    db: Session,
    monday: date,
    sunday: date,
    *,
    week_first: bool = False,
):
    activity = _timesheet_activity_subquery(db)
    return _order_timesheets_by_activity(db.query(Timesheet).filter(
        Timesheet.week_start <= sunday,
        Timesheet.week_end >= monday,
    ), activity, week_first=week_first)


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


def _match_execution_project(db: Session, project_text: str | None) -> Project | None:
    text = (project_text or "").strip()
    if not text:
        return None

    candidates = [text]
    if " " in text:
        first, rest = text.split(" ", 1)
        candidates.extend([first.strip(), rest.strip()])

    for value in [item for item in candidates if item]:
        project = (
            db.query(Project)
            .filter((Project.project_no == value) | (Project.project_name == value))
            .order_by(Project.id.asc())
            .first()
        )
        if project:
            return project

    if len(text) < 3:
        return None

    return (
        db.query(Project)
        .filter(Project.project_name.ilike(f"%{text}%"))
        .order_by(Project.id.asc())
        .first()
    )


def _resolve_entry_project(db: Session, entry_data: dict) -> dict:
    if entry_data.get("project_id"):
        entry_data["project_source"] = "실행"
        return entry_data

    project_name = (entry_data.get("project_name") or "").strip()
    if project_name in {"연차", "반차", "반반차"}:
        return entry_data

    project = _match_execution_project(db, project_name)
    if project:
        entry_data["project_id"] = project.id
        entry_data["project_name"] = project.project_name
        entry_data["project_source"] = "실행"
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
            scoped_ids = {
                row.id
                for row in rows
                if not is_system_account_employee(db, row.id)
            }
            if current_emp and not is_system_account_employee(db, current_emp.id):
                scoped_ids.add(current_emp.id)
            return scoped_ids

    if current_emp and not is_system_account_employee(db, current_emp.id):
        return {current_emp.id}
    return set()


def _require_employee_access(employee_id: int, db: Session, current) -> None:
    if is_system_account_employee(db, employee_id):
        raise HTTPException(status_code=403, detail="운영 계정은 업무 데이터 대상에서 제외됩니다.")
    allowed_ids = _allowed_employee_ids(db, current)
    if allowed_ids is not None and employee_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="해당 직원의 타임시트를 조회할 권한이 없습니다.")


def _holiday_map_for_range(db: Session, start_day: date, end_day: date) -> dict[date, str]:
    years = {str(start_day.year), str(end_day.year)}
    rows = db.query(Holiday).filter(Holiday.year.in_(years)).all()
    holidays: dict[date, str] = {}
    for row in rows:
        try:
            holiday_date = date(int(row.year), int(row.month), int(row.day))
        except (TypeError, ValueError):
            continue
        if start_day <= holiday_date <= end_day:
            holidays[holiday_date] = row.content or "공휴일"
    return holidays


def _blocked_timesheet_dates(db: Session, monday: date, sunday: date) -> dict[date, str]:
    holidays = _holiday_map_for_range(db, monday, sunday)
    blocked: dict[date, str] = {}
    for index in range(7):
        work_date = monday + timedelta(days=index)
        if work_date.weekday() >= 5:
            blocked[work_date] = "주말"
        if work_date in holidays:
            blocked[work_date] = holidays[work_date]
    return blocked


def _validate_workday_hours(data: "TimesheetCreate", db: Session, monday: date, sunday: date) -> None:
    blocked = _blocked_timesheet_dates(db, monday, sunday)
    if not blocked:
        return
    invalid_dates = []
    for entry in data.entries:
        for index, day in enumerate(DAYS):
            work_date = monday + timedelta(days=index)
            if work_date not in blocked:
                continue
            if float(getattr(entry, f"{day}_hours") or 0) > 0:
                invalid_dates.append(f"{work_date.isoformat()}({blocked[work_date]})")
    if invalid_dates:
        dates = ", ".join(dict.fromkeys(invalid_dates))
        raise HTTPException(
            status_code=400,
            detail=f"주말 및 공휴일에는 타임시트를 입력할 수 없습니다: {dates}",
        )


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
    contract_ratio_amount: Decimal = Decimal(0)
    contract_actual_amount: Decimal = Decimal(0)
    contract_diff_amount: Decimal = Decimal(0)
    other_ratio_amount: Decimal = Decimal(0)
    other_actual_amount: Decimal = Decimal(0)
    other_diff_amount: Decimal = Decimal(0)


class ProjectLaborRowIn(BaseModel):
    key: Optional[str] = None
    project_id: Optional[int] = None
    labor_total_amount: Decimal = Decimal(0)
    monthly_labor: dict[str, Decimal] = {}


class LaborAllocationSaveIn(BaseModel):
    year: int
    month: int
    rows: List[LaborAllocationRowIn] = []
    project_rows: List[ProjectLaborRowIn] = []


def _require_timesheet_admin(current) -> None:
    if normalize_role(current.role) not in TIMESHEET_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="타임시트 관리자 기능을 사용할 권한이 없습니다.")


def _is_timesheet_admin(current) -> bool:
    return normalize_role(current.role) in TIMESHEET_ADMIN_ROLES


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
        "contract_ratio_amount": float(row.contract_ratio_amount or 0),
        "contract_actual_amount": float(row.contract_actual_amount or 0),
        "contract_diff_amount": float(row.contract_diff_amount or 0),
        "other_ratio_amount": float(row.other_ratio_amount or 0),
        "other_actual_amount": float(row.other_actual_amount or 0),
        "other_diff_amount": float(row.other_diff_amount or 0),
    }


def _validate_labor_allocation_amounts(row: LaborAllocationRowIn) -> None:
    amounts = [
        row.total_amount,
        row.contract_amount,
        row.other_amount,
        row.contract_ratio_amount,
        row.contract_actual_amount,
        row.other_ratio_amount,
        row.other_actual_amount,
    ]
    if any(amount < 0 for amount in amounts):
        raise HTTPException(status_code=400, detail="인건비 배부 금액은 음수로 입력할 수 없습니다.")


def _closed_months_in_week(db: Session, monday: date, sunday: date) -> list[TimesheetMonthlyClose]:
    months = {
        (monday + timedelta(days=index)).year * 100 + (monday + timedelta(days=index)).month
        for index in range(7)
    }
    return (
        db.query(TimesheetMonthlyClose)
        .filter(TimesheetMonthlyClose.is_closed == True)
        .filter((TimesheetMonthlyClose.close_year * 100 + TimesheetMonthlyClose.close_month).in_(months))
        .all()
    )


def _assert_timesheet_month_open(db: Session, monday: date, sunday: date, current) -> None:
    if _is_timesheet_admin(current):
        return
    closed = _closed_months_in_week(db, monday, sunday)
    if closed:
        labels = ", ".join(f"{row.close_year}.{row.close_month:02d}" for row in closed)
        raise HTTPException(status_code=403, detail=f"{labels} 타임시트가 월 마감되어 수정할 수 없습니다.")


def _project_label(project: Project | None, entry: TimesheetEntry) -> str:
    if project:
        return " ".join(part for part in [project.project_no, project.project_name] if part) or project.project_name
    return entry.project_name or "기타"


def _project_meta_value(project: Project | None, key: str, fallback=None):
    if not project:
        return fallback
    value = getattr(project, key, None)
    if value not in (None, ""):
        return value
    try:
        data = json.loads(project.excel_data_json or "{}")
        if isinstance(data, dict):
            return data.get(key, fallback)
    except (TypeError, ValueError):
        pass
    return fallback


def _sales_type(project: Project | None, source: str) -> str:
    if source == "영업":
        return "영업"
    if source == "공통":
        return "공통"
    return _project_meta_value(project, "revenue_type", "-") or "-"


def _revenue_group(sales_type: str | None) -> str:
    normalized = (sales_type or "").strip()
    if normalized in CONTRACT_REVENUE_TYPES:
        return "contract"
    if normalized in OTHER_REVENUE_TYPES:
        return "other"
    return "other"


@router.get("/timesheets/employees")
def list_timesheet_employees(db: Session = Depends(get_db), current=Depends(get_current_user)):
    allowed_ids = _allowed_employee_ids(db, current)
    q = db.query(Employee).filter(Employee.is_active == True)
    q = exclude_system_account_employees(q, db)
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
        .join(Employee, Employee.id == Timesheet.employee_id)
        .filter(TimesheetEntry.project_name.isnot(None))
        .filter(TimesheetEntry.project_name != "")
        .filter(
            (TimesheetEntry.project_source == "공통")
            | (TimesheetEntry.project_id.is_(None))
        )
    )
    query = exclude_system_account_employees(query, db)

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


def _build_timesheet_admin_labor(
    year: int,
    month: int,
    db: Session,
    persist_calculated: bool = False,
) -> dict:
    month_start, month_end = _month_bounds(year, month)
    year_end = date(year, 12, 31)

    allocation_models = {
        row.category: row
        for row in db.query(TimesheetLaborAllocation)
        .filter(
            TimesheetLaborAllocation.allocation_year == year,
            TimesheetLaborAllocation.allocation_month == month,
        )
        .all()
    }
    allocation_rows: list[dict] = []
    for category in LABOR_ALLOCATION_CATEGORIES:
        model = allocation_models.get(category)
        allocation_rows.append(_allocation_dict(model) if model else {
            "category": category,
            "total_amount": 0,
            "contract_amount": 0,
            "other_amount": 0,
            "contract_ratio_amount": 0,
            "contract_actual_amount": 0,
            "contract_diff_amount": 0,
            "other_ratio_amount": 0,
            "other_actual_amount": 0,
            "other_diff_amount": 0,
        })

    cumulative_pools = {
        row.allocation_month: float(row.total_amount or 0)
        for row in db.query(
            TimesheetLaborAllocation.allocation_month,
            sqlfunc.sum(TimesheetLaborAllocation.total_amount).label("total_amount"),
        )
        .filter(TimesheetLaborAllocation.allocation_year == year)
        .group_by(TimesheetLaborAllocation.allocation_month)
        .all()
    }
    monthly_pools: dict[int, float] = {}
    previous_pool = 0.0
    for pool_month in range(1, 13):
        current_pool = cumulative_pools.get(pool_month, previous_pool)
        monthly_pools[pool_month] = max(0.0, current_pool - previous_pool)
        previous_pool = current_pool

    sheets = (
        db.query(Timesheet)
        .options(joinedload(Timesheet.entries).joinedload(TimesheetEntry.project))
        .join(Employee, Employee.id == Timesheet.employee_id)
        .filter(Timesheet.week_start <= year_end)
    )
    sheets = exclude_system_account_employees(sheets, db).all()

    project_rows: dict[str, dict] = {}
    total_cost_hours_by_month = {m: 0.0 for m in range(1, 13)}

    for sheet in sheets:
        for entry in sheet.entries:
            source = entry.project_source or ("실행" if entry.project_id else "공통")
            project_key = f"{source}::{entry.project_id or entry.project_name or '기타'}"
            if project_key not in project_rows:
                project = entry.project
                sales_type = _sales_type(project, source)
                project_rows[project_key] = {
                    "key": project_key,
                    "project_id": project.id if project else None,
                    "project_no": project.project_no if project else "",
                    "project": _project_label(project, entry),
                    "monthly_cost_hours": 0.0,
                    "monthly_admin_hours": 0.0,
                    "cumulative_cost_hours": 0.0,
                    "cumulative_admin_hours": 0.0,
                    "sales_type": sales_type,
                    "revenue_group": _revenue_group(sales_type),
                    "status": project.status if project else "-",
                    "labor_total_amount": 0.0,
                    "monthly_labor": {m: 0.0 for m in range(1, 13)},
                    "_cost_hours_by_month": {m: 0.0 for m in range(1, 13)},
                    "_project_sort": project.id if project else 999999999,
                }
            row = project_rows[project_key]
            labor_type = entry.labor_type if entry.labor_type in {"원가", "판관"} else "원가"

            for index, day in enumerate(DAYS):
                hours = float(getattr(entry, f"{day}_hours") or 0)
                if hours <= 0:
                    continue
                work_date = sheet.week_start + timedelta(days=index)

                if work_date.year == year and labor_type == "원가":
                    work_month = work_date.month
                    row["_cost_hours_by_month"][work_month] += hours
                    total_cost_hours_by_month[work_month] += hours

                if month_start <= work_date <= month_end:
                    if labor_type == "판관":
                        row["monthly_admin_hours"] += hours
                    else:
                        row["monthly_cost_hours"] += hours
                if work_date <= month_end:
                    if labor_type == "판관":
                        row["cumulative_admin_hours"] += hours
                    else:
                        row["cumulative_cost_hours"] += hours

    total_cumulative_cost_hours = sum(row["cumulative_cost_hours"] for row in project_rows.values())
    group_cumulative_cost_hours = {"contract": 0.0, "other": 0.0}
    for row in project_rows.values():
        for m in range(1, 13):
            pool = monthly_pools.get(m, 0.0)
            total_hours = total_cost_hours_by_month.get(m, 0.0)
            hours = row["_cost_hours_by_month"].get(m, 0.0)
            if pool > 0 and total_hours > 0 and hours > 0:
                row["monthly_labor"][m] = round(pool * hours / total_hours)
        row["labor_total_amount"] = sum(row["monthly_labor"][m] for m in range(1, month + 1))
        group_cumulative_cost_hours[row["revenue_group"]] = (
            group_cumulative_cost_hours.get(row["revenue_group"], 0.0) + row["cumulative_cost_hours"]
        )
        row.pop("_cost_hours_by_month", None)

    group_actual_amounts = {"contract": 0.0, "other": 0.0}
    for row in project_rows.values():
        group_actual_amounts[row["revenue_group"]] = (
            group_actual_amounts.get(row["revenue_group"], 0.0) + row["labor_total_amount"]
        )

    contract_ratio = group_cumulative_cost_hours["contract"] / total_cumulative_cost_hours if total_cumulative_cost_hours > 0 else 0
    other_ratio = group_cumulative_cost_hours["other"] / total_cumulative_cost_hours if total_cumulative_cost_hours > 0 else 0
    total_allocation_amount = sum(float(row["total_amount"] or 0) for row in allocation_rows)

    for row in allocation_rows:
        total_amount = float(row["total_amount"] or 0)
        share = total_amount / total_allocation_amount if total_allocation_amount > 0 else 0
        row["contract_ratio_amount"] = round(total_amount * contract_ratio)
        row["contract_actual_amount"] = round(group_actual_amounts["contract"] * share)
        row["contract_diff_amount"] = row["contract_ratio_amount"] - row["contract_actual_amount"]
        row["other_ratio_amount"] = round(total_amount * other_ratio)
        row["other_actual_amount"] = round(group_actual_amounts["other"] * share)
        row["other_diff_amount"] = row["other_ratio_amount"] - row["other_actual_amount"]
        row["contract_amount"] = row["contract_ratio_amount"]
        row["other_amount"] = row["other_ratio_amount"]

        model = allocation_models.get(row["category"])
        stored_fields = [
            "contract_amount",
            "other_amount",
            "contract_ratio_amount",
            "contract_actual_amount",
            "contract_diff_amount",
            "other_ratio_amount",
            "other_actual_amount",
            "other_diff_amount",
        ]
        if model and any(float(getattr(model, field) or 0) != 0 for field in stored_fields):
            for field in stored_fields:
                row[field] = float(getattr(model, field) or 0)
        if persist_calculated and model:
            model.contract_amount = row["contract_amount"]
            model.other_amount = row["other_amount"]
            model.contract_ratio_amount = row["contract_ratio_amount"]
            model.contract_actual_amount = row["contract_actual_amount"]
            model.contract_diff_amount = row["contract_diff_amount"]
            model.other_ratio_amount = row["other_ratio_amount"]
            model.other_actual_amount = row["other_actual_amount"]
            model.other_diff_amount = row["other_diff_amount"]

    numeric_fields = [
        "total_amount",
        "contract_amount",
        "other_amount",
        "contract_ratio_amount",
        "contract_actual_amount",
        "contract_diff_amount",
        "other_ratio_amount",
        "other_actual_amount",
        "other_diff_amount",
    ]
    allocation_rows.append({
        "category": "합계",
        **{field: sum(float(row[field] or 0) for row in allocation_rows) for field in numeric_fields},
    })

    saved_purchase_rows = {
        row.project_id: row
        for row in db.query(ProjectPurchasePlanRow)
        .filter(ProjectPurchasePlanRow.plan_year == year)
        .filter(ProjectPurchasePlanRow.project_id.isnot(None))
        .all()
    }
    for row in project_rows.values():
        saved_row = saved_purchase_rows.get(row.get("project_id"))
        if not saved_row:
            continue
        try:
            data = json.loads(saved_row.data_json or "{}")
            if not isinstance(data, dict):
                data = {}
        except (TypeError, ValueError):
            data = {}
        has_saved_labor = False
        for month_index in range(1, 13):
            key = f"labor_cost_{month_index}월"
            if key in data:
                has_saved_labor = True
                row["monthly_labor"][month_index] = round(float(data.get(key) or 0))
        if has_saved_labor:
            row["labor_total_amount"] = sum(row["monthly_labor"][m] for m in range(1, month + 1))

    close_row = db.query(TimesheetMonthlyClose).filter(
        TimesheetMonthlyClose.close_year == year,
        TimesheetMonthlyClose.close_month == month,
    ).first()

    sorted_project_rows = sorted(
        project_rows.values(),
        key=lambda item: (
            0 if item.get("project_id") else 1,
            item.get("_project_sort") or 999999999,
            item.get("project_no") or "",
            item.get("project") or "",
        ),
    )
    for row in sorted_project_rows:
        row.pop("_project_sort", None)

    return {
        "year": year,
        "month": month,
        "is_closed": bool(close_row and close_row.is_closed),
        "closed_at": to_kst(close_row.closed_at) if close_row else None,
        "allocation_rows": allocation_rows,
        "project_rows": sorted_project_rows,
    }


def _apply_allocation_overrides(result: dict, incoming: dict[str, LaborAllocationRowIn]) -> None:
    override_fields = [
        "total_amount",
        "contract_amount",
        "other_amount",
        "contract_ratio_amount",
        "contract_actual_amount",
        "contract_diff_amount",
        "other_ratio_amount",
        "other_actual_amount",
        "other_diff_amount",
    ]
    for row in result.get("allocation_rows", []):
        if row.get("category") == "합계":
            continue
        source = incoming.get(row.get("category"))
        if not source:
            continue
        for field in override_fields:
            row[field] = float(getattr(source, field) or 0)


def _persist_allocation_rows(
    db: Session,
    year: int,
    month: int,
    allocation_rows: list[dict],
    existing: dict[str, TimesheetLaborAllocation],
    current,
) -> None:
    editable_rows = [row for row in allocation_rows if row.get("category") in LABOR_ALLOCATION_CATEGORIES]
    for source in editable_rows:
        category = source["category"]
        row = existing.get(category)
        if not row:
            row = TimesheetLaborAllocation(
                allocation_year=year,
                allocation_month=month,
                category=category,
                created_by=current.id,
            )
            db.add(row)
            existing[category] = row
        row.total_amount = source.get("total_amount") or 0
        row.contract_amount = source.get("contract_amount") or 0
        row.other_amount = source.get("other_amount") or 0
        row.contract_ratio_amount = source.get("contract_ratio_amount") or 0
        row.contract_actual_amount = source.get("contract_actual_amount") or 0
        row.contract_diff_amount = source.get("contract_diff_amount") or 0
        row.other_ratio_amount = source.get("other_ratio_amount") or 0
        row.other_actual_amount = source.get("other_actual_amount") or 0
        row.other_diff_amount = source.get("other_diff_amount") or 0


def _apply_project_labor_overrides(result: dict, incoming_rows: list[ProjectLaborRowIn]) -> None:
    by_project_id = {row.project_id: row for row in incoming_rows if row.project_id}
    by_key = {row.key: row for row in incoming_rows if row.key}
    for row in result.get("project_rows", []):
        source = by_project_id.get(row.get("project_id")) or by_key.get(row.get("key"))
        if not source:
            continue
        source_monthly = source.monthly_labor or {}
        monthly_labor = row.get("monthly_labor") or {}
        for month_index in range(1, 13):
            value = source_monthly.get(str(month_index))
            if value is None:
                value = source_monthly.get(month_index)
            if value is not None:
                monthly_labor[month_index] = round(float(value or 0))
        row["monthly_labor"] = monthly_labor
        row["labor_total_amount"] = sum(monthly_labor.get(m, 0) for m in range(1, result.get("month", 12) + 1))


def _upsert_purchase_plan_labor_costs(db: Session, year: int, project_rows: list[dict], current) -> None:
    for labor_row in project_rows:
        project_id = labor_row.get("project_id")
        if not project_id:
            continue
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            continue

        row_key = f"project:{project.id}"
        plan_row = db.query(ProjectPurchasePlanRow).filter(
            ProjectPurchasePlanRow.plan_year == year,
            ProjectPurchasePlanRow.row_key == row_key,
        ).first()
        if not plan_row:
            plan_row = ProjectPurchasePlanRow(
                plan_year=year,
                row_key=row_key,
                project_id=project.id,
                created_by=current.id,
                data_json="{}",
            )
            db.add(plan_row)

        try:
            data = json.loads(plan_row.data_json or "{}")
            if not isinstance(data, dict):
                data = {}
        except (TypeError, ValueError):
            data = {}

        data.update({
            "id": data.get("id") or row_key,
            "project_id": project.id,
            "job_no": project.project_no or data.get("job_no") or "",
            "project_name": project.project_name or data.get("project_name") or "",
            "contract_company": project.client_name or data.get("contract_company") or "",
            "domestic_overseas": data.get("domestic_overseas") or ("해외" if project.contract_type == "국외" else "내수"),
            "progress_status": project.status or data.get("progress_status") or "",
            "contract_date": data.get("contract_date") or to_kst_date(project.contract_start),
            "completion_date": data.get("completion_date") or to_kst_date(project.construct_end or project.contract_end),
        })
        monthly_labor = labor_row.get("monthly_labor") or {}
        for month_index in range(1, 13):
            data[f"labor_cost_{month_index}월"] = round(float(monthly_labor.get(month_index) or monthly_labor.get(str(month_index)) or 0))
        data["labor_cost_total"] = sum(float(data.get(f"labor_cost_{month_index}월") or 0) for month_index in range(1, 13))

        plan_row.project_id = project.id
        plan_row.data_json = json.dumps(data, ensure_ascii=False, default=str)


def _close_timesheet_month(db: Session, year: int, month: int, current) -> None:
    close_row = db.query(TimesheetMonthlyClose).filter(
        TimesheetMonthlyClose.close_year == year,
        TimesheetMonthlyClose.close_month == month,
    ).first()
    now = datetime.utcnow()
    if not close_row:
        close_row = TimesheetMonthlyClose(
            close_year=year,
            close_month=month,
            is_closed=True,
            closed_by=current.id,
            closed_at=now,
        )
        db.add(close_row)
    else:
        close_row.is_closed = True
        close_row.closed_by = current.id
        close_row.closed_at = now


@router.get("/timesheets/admin-labor")
def get_timesheet_admin_labor(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    _require_timesheet_admin(current)
    return _build_timesheet_admin_labor(year, month, db)


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
    try:
        db.flush()
        result = _build_timesheet_admin_labor(data.year, data.month, db)
        _apply_allocation_overrides(result, incoming)
        _apply_project_labor_overrides(result, data.project_rows)
        _persist_allocation_rows(db, data.year, data.month, result["allocation_rows"], existing, current)
        _upsert_purchase_plan_labor_costs(db, data.year, result["project_rows"], current)
        _close_timesheet_month(db, data.year, data.month, current)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="인건비 배부 금액 저장 중 DB 오류가 발생했습니다.")
    return _build_timesheet_admin_labor(data.year, data.month, db)


# ── 주간 타임시트 목록 ──────────────────────────────────────────
@router.get("/timesheets")
def list_timesheets(
    employee_id: Optional[int] = None,
    week_start:  Optional[date] = None,
    status:      Optional[str] = None,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    q = db.query(Timesheet).join(Employee, Employee.id == Timesheet.employee_id)
    q = exclude_system_account_employees(q, db)
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
    activity = _timesheet_activity_subquery(db)
    rows = _order_timesheets_by_activity(q, activity, week_first=True).all()
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
    ts = _active_timesheets_for_week(db, monday, sunday).filter(
        Timesheet.employee_id == employee_id,
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
    _assert_timesheet_month_open(db, monday, sunday, current)
    _validate_workday_hours(data, db, monday, sunday)
    activity = _timesheet_activity_subquery(db)
    ts = _order_timesheets_by_activity(db.query(Timesheet).filter(
        Timesheet.employee_id == data.employee_id,
        Timesheet.week_start  == monday,
    ), activity).first()

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
        entry_data = _resolve_entry_project(db, entry_data)
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
    employee_q = exclude_system_account_employees(employee_q, db)
    if allowed_ids is not None:
        if not allowed_ids:
            return []
        employee_q = employee_q.filter(Employee.id.in_(allowed_ids))
    employees = employee_q.all()
    submitted = {}
    for ts in _active_timesheets_for_week(db, monday, sunday).all():
        submitted.setdefault(ts.employee_id, ts)
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
    q = q.join(Employee, Employee.id == Timesheet.employee_id)
    q = exclude_system_account_employees(q, db)
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
