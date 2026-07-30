from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..models.common import CalendarSchedule, Department, OpinionPost, User
from ..models.execution import Project
from ..models.master import Employee
from ..models.timesheet import Timesheet
from ..utils.permissions import is_system_admin, normalize_role
from ..utils.system_accounts import exclude_system_account_employees, is_system_account_employee


ToolHandler = Callable[[dict[str, Any], Session, User], dict[str, Any]]

PROJECT_STATUS_ALIASES = {
    "진행": "진행중",
    "진행 중": "진행중",
    "종료": "완료",
    "종료됨": "완료",
    "완료됨": "완료",
}
PROJECT_STANDARD_STATUSES = {"미진행", "진행중", "완료"}
COMPANY_SCHEDULE_KIND_BY_COLOR = {
    "#52c41a": "외근",
    "#722ed1": "출장",
    "#fa8c16": "출장",
}
REFRESH_SCHEDULE_KIND_BY_COLOR = {
    "#bae7ff": "연차",
    "#13c2c2": "반차",
    "#eb2f96": "반반차",
    "#1890ff": "대체휴가",
    "#bfbfbf": "하계휴가",
    "#ff7a45": "병가",
    "#d9d9d9": "기타",
}


def _today() -> date:
    return date.today()


def _week_of(day: date) -> tuple[date, date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def _month_of(day: date) -> tuple[date, date]:
    start = day.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    return start, next_month - timedelta(days=1)


def _parse_date(value: Any, default: date) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return default
    return default


def _parse_optional_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _period_from_args(args: dict[str, Any]) -> tuple[date, date, str]:
    period_start = _parse_optional_date(args.get("period_start"))
    period_end = _parse_optional_date(args.get("period_end"))
    if period_start and period_end:
        return period_start, period_end, "기간"

    unit = str(args.get("unit") or "").strip().lower()
    base_day = _parse_date(args.get("date") or args.get("week_start") or args.get("month"), _today())
    if unit in {"day", "일", "daily"}:
        return base_day, base_day, "일"
    if unit in {"month", "월", "monthly"}:
        start, end = _month_of(base_day)
        return start, end, "월"

    start, end = _week_of(base_day)
    return start, end, "주"


def _num(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def _normalize_project_status(value: Any) -> str:
    status = str(value or "").strip()
    status = PROJECT_STATUS_ALIASES.get(status, status)
    return status if status in PROJECT_STANDARD_STATUSES else (status or "미지정")


def _project_status_filter_values(value: Any) -> list[str]:
    normalized = _normalize_project_status(value)
    values = [normalized]
    values.extend(alias for alias, status in PROJECT_STATUS_ALIASES.items() if status == normalized)
    return values


def _current_employee(db: Session, current: User) -> Employee | None:
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
        rows = db.query(Department.id).filter(
            Department.parent_id.in_(frontier),
            Department.is_active == True,
        ).all()
        children = [row.id for row in rows if row.id not in ids]
        ids.update(children)
        frontier = children
    return ids


def _allowed_employee_ids(db: Session, current: User) -> set[int] | None:
    if is_system_admin(current.role):
        return None

    emp = _current_employee(db, current)
    role = normalize_role(current.role)
    scope_department_id = current.department_id or (emp.department_id if emp else None)
    if role.endswith("_manager") and scope_department_id:
        department_ids = _descendant_department_ids(db, scope_department_id)
        if department_ids:
            rows = db.query(Employee.id).filter(
                Employee.is_active == True,
                Employee.department_id.in_(department_ids),
            ).all()
            allowed = {
                row.id
                for row in rows
                if not is_system_account_employee(db, row.id)
            }
            if emp and not is_system_account_employee(db, emp.id):
                allowed.add(emp.id)
            return allowed
    if emp and not is_system_account_employee(db, emp.id):
        return {emp.id}
    return set()


def _employee_query(db: Session, current: User):
    q = db.query(Employee).filter(Employee.is_active == True)
    q = exclude_system_account_employees(q, db)
    allowed_ids = _allowed_employee_ids(db, current)
    if allowed_ids is not None:
        if not allowed_ids:
            return q.filter(Employee.id == -1)
        q = q.filter(Employee.id.in_(allowed_ids))
    return q


def list_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_operational_summary",
            "title": "ERP 운영 요약",
            "description": "현재 사용자 권한 안에서 타임시트, 의견 청취, 프로젝트 현황을 요약합니다.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "week_start": {
                        "type": "string",
                        "description": "조회할 주의 시작일(YYYY-MM-DD). 생략하면 이번 주를 사용합니다.",
                    }
                },
            },
        },
        {
            "name": "get_timesheet_team_status",
            "title": "타임시트 저장 현황",
            "description": "권한 범위 내 직원의 주간 타임시트 작성/저장 상태와 총 시간을 조회합니다.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "week_start": {
                        "type": "string",
                        "description": "조회할 주의 시작일(YYYY-MM-DD).",
                    },
                    "period_start": {
                        "type": "string",
                        "description": "조회 기간 시작일(YYYY-MM-DD). 월간/기간 조회에 사용합니다.",
                    },
                    "period_end": {
                        "type": "string",
                        "description": "조회 기간 종료일(YYYY-MM-DD). 월간/기간 조회에 사용합니다.",
                    },
                    "status": {
                        "type": "string",
                        "description": "미작성, 작성중 중 하나로 필터링합니다.",
                    },
                },
            },
        },
        {
            "name": "get_schedule_status",
            "title": "전사일정 현황",
            "description": "일/주/월 단위 외근, 출장, 휴가 현황을 DB 기준으로 집계합니다.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "unit": {
                        "type": "string",
                        "description": "day, week, month 중 하나입니다. 생략하면 week입니다.",
                        "default": "week",
                    },
                    "date": {
                        "type": "string",
                        "description": "조회 기준일(YYYY-MM-DD).",
                    },
                    "week_start": {
                        "type": "string",
                        "description": "조회할 주의 시작일(YYYY-MM-DD).",
                    },
                    "period_start": {
                        "type": "string",
                        "description": "조회 기간 시작일(YYYY-MM-DD).",
                    },
                    "period_end": {
                        "type": "string",
                        "description": "조회 기간 종료일(YYYY-MM-DD).",
                    },
                    "schedule_type": {
                        "type": "string",
                        "description": "외근, 출장, 휴가 중 하나로 필터링합니다.",
                    },
                },
            },
        },
        {
            "name": "search_projects",
            "title": "프로젝트 검색",
            "description": "프로젝트 번호, 프로젝트명, 거래처명, PM명으로 프로젝트를 검색하고 상태/정렬 조건을 적용합니다.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색어"},
                    "status": {
                        "type": "string",
                        "description": "미진행, 진행중, 완료 중 하나로 필터링합니다.",
                    },
                    "order_by": {
                        "type": "string",
                        "description": "recent, amount_desc, amount_asc, end_date 중 하나로 정렬합니다.",
                        "default": "recent",
                    },
                    "limit": {"type": "integer", "description": "최대 결과 수. 생략하면 전체를 조회합니다."},
                },
            },
        },
        {
            "name": "list_waiting_opinions",
            "title": "의견 청취 조회",
            "description": "의견 청취 글을 답변 상태, 검색어, 첨부 여부로 필터링해 최신순으로 조회합니다.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "waiting, answered, all 중 하나로 필터링합니다.",
                        "default": "waiting",
                    },
                    "query": {"type": "string", "description": "제목/내용 검색어"},
                    "has_attachments": {"type": "boolean", "description": "첨부 파일이 있는 의견만 조회합니다."},
                    "limit": {"type": "integer", "description": "최대 결과 수. 생략하면 전체를 조회합니다."}
                },
            },
        },
    ]


def get_timesheet_team_status(args: dict[str, Any], db: Session, current: User) -> dict[str, Any]:
    period_start = _parse_optional_date(args.get("period_start"))
    period_end = _parse_optional_date(args.get("period_end"))
    period_unit = "기간"
    if not period_start or not period_end:
        monday, sunday = _week_of(_parse_date(args.get("week_start"), _today()))
        period_start, period_end = monday, sunday
        period_unit = "주"
    elif period_start.day == 1 and period_end.day >= 28:
        period_unit = "월"

    employees = _employee_query(db, current).order_by(Employee.department_name.asc(), Employee.name.asc()).all()
    employee_ids = [emp.id for emp in employees]
    rows = []
    sheets_by_employee: dict[int, list[Timesheet]] = {}
    if employee_ids:
        sheets = db.query(Timesheet).filter(
            Timesheet.week_start <= period_end,
            Timesheet.week_end >= period_start,
            Timesheet.employee_id.in_(employee_ids),
        ).all()
        for sheet in sheets:
            sheets_by_employee.setdefault(sheet.employee_id, []).append(sheet)

    status_filter = args.get("status")
    all_counts: dict[str, int] = {}
    for emp in employees:
        sheets = sheets_by_employee.get(emp.id, [])
        total_hours = sum(_num(sheet.total_hours) for sheet in sheets)
        status = "작성중" if total_hours > 0 else "미작성"
        all_counts[status] = all_counts.get(status, 0) + 1
        if status_filter and status != status_filter:
            continue
        rows.append({
            "employee_id": emp.id,
            "employee_name": emp.name,
            "department": emp.department.name if emp.department else emp.department_name,
            "position": emp.position,
            "status": status,
            "total_hours": total_hours,
            "timesheet_id": sheets[0].id if len(sheets) == 1 else None,
            "timesheet_count": len(sheets),
        })

    counts: dict[str, int] = {}
    total_hours = 0.0
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        total_hours += row["total_hours"]

    return {
        "week_start": str(period_start),
        "week_end": str(period_end),
        "period_start": str(period_start),
        "period_end": str(period_end),
        "period_unit": period_unit,
        "counts": counts,
        "all_counts": all_counts,
        "status_filter": status_filter,
        "total_hours": round(total_hours, 2),
        "rows": rows,
    }


def _schedule_kind(row: CalendarSchedule) -> str:
    if row.schedule_kind:
        return row.schedule_kind
    if row.category == "refresh":
        return REFRESH_SCHEDULE_KIND_BY_COLOR.get(row.type, "휴가")
    return COMPANY_SCHEDULE_KIND_BY_COLOR.get(row.type, "출장")


def _schedule_bucket(row: CalendarSchedule) -> str:
    if row.category == "refresh":
        return "휴가"
    kind = _schedule_kind(row)
    return "외근" if kind == "외근" else "출장"


def _schedule_dates(row: CalendarSchedule) -> tuple[date | None, date | None]:
    start = row.date or (row.start_time.date() if row.start_time else None)
    end = row.end_date or row.date or (row.end_time.date() if row.end_time else start)
    return start, end


def _overlap_days(start: date | None, end: date | None, period_start: date, period_end: date) -> int:
    if not start:
        return 0
    actual_end = end or start
    overlap_start = max(start, period_start)
    overlap_end = min(actual_end, period_end)
    if overlap_end < overlap_start:
        return 0
    return (overlap_end - overlap_start).days + 1


def get_schedule_status(args: dict[str, Any], db: Session, current: User) -> dict[str, Any]:
    period_start, period_end, period_unit = _period_from_args(args)
    type_filter = str(args.get("schedule_type") or "").strip()

    rows = db.query(CalendarSchedule).filter(
        CalendarSchedule.date <= period_end,
        func.coalesce(CalendarSchedule.end_date, CalendarSchedule.date) >= period_start,
    ).order_by(
        CalendarSchedule.date.asc().nullslast(),
        CalendarSchedule.start_time.asc().nullslast(),
        CalendarSchedule.user_name.asc(),
        CalendarSchedule.id.asc(),
    ).all()

    counts = {"외근": 0, "출장": 0, "휴가": 0}
    kinds: dict[str, int] = {}
    users: dict[str, dict[str, Any]] = {}
    daily: dict[str, dict[str, int]] = {}
    items = []

    for row in rows:
        bucket = _schedule_bucket(row)
        if type_filter and bucket != type_filter and _schedule_kind(row) != type_filter:
            continue

        start, end = _schedule_dates(row)
        days = _overlap_days(start, end, period_start, period_end)
        if days <= 0:
            continue

        kind = _schedule_kind(row)
        counts[bucket] = counts.get(bucket, 0) + 1
        kinds[kind] = kinds.get(kind, 0) + 1
        user_name = row.user_name or "미확인"
        user_summary = users.setdefault(user_name, {"user_name": user_name, "외근": 0, "출장": 0, "휴가": 0, "total": 0})
        user_summary[bucket] = user_summary.get(bucket, 0) + 1
        user_summary["total"] += 1

        current_day = max(start or period_start, period_start)
        last_day = min(end or current_day, period_end)
        while current_day <= last_day:
            day_key = str(current_day)
            daily.setdefault(day_key, {"외근": 0, "출장": 0, "휴가": 0})
            daily[day_key][bucket] += 1
            current_day += timedelta(days=1)

        items.append({
            "id": row.id,
            "category": row.category,
            "schedule_type": bucket,
            "kind": kind,
            "content": row.content,
            "user_name": user_name,
            "date": str(start) if start else None,
            "end_date": str(end) if end else None,
            "days": days,
            "start_time": row.start_time.isoformat() if row.start_time else None,
            "end_time": row.end_time.isoformat() if row.end_time else None,
            "timesheet_project_name": row.timesheet_project_name,
            "timesheet_project_source": row.timesheet_project_source,
        })

    return {
        "period_start": str(period_start),
        "period_end": str(period_end),
        "period_unit": period_unit,
        "schedule_type_filter": type_filter or None,
        "counts": counts,
        "kind_counts": kinds,
        "total_count": len(items),
        "users": sorted(users.values(), key=lambda item: (-item["total"], item["user_name"])),
        "daily": [{"date": key, **value} for key, value in sorted(daily.items())],
        "items": items,
    }


def search_projects(args: dict[str, Any], db: Session, current: User) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    limit = args.get("limit")
    limit = min(max(int(limit), 1), 500) if limit is not None else None
    status_filter = str(args.get("status") or "").strip()
    normalized_status_filter = _normalize_project_status(status_filter) if status_filter else ""
    order_by = str(args.get("order_by") or "recent")
    q = db.query(Project)
    if query:
        like = f"%{query}%"
        q = q.filter(or_(
            Project.project_no.ilike(like),
            Project.project_name.ilike(like),
            Project.client_name.ilike(like),
            Project.pm_name.ilike(like),
        ))
    if status_filter:
        q = q.filter(Project.status.in_(_project_status_filter_values(status_filter)))

    total_count = q.count()
    status_rows = q.with_entities(Project.status, func.count(Project.id)).group_by(Project.status).all()
    status_counts: dict[str, int] = {}
    for status, count in status_rows:
        normalized_status = _normalize_project_status(status)
        status_counts[normalized_status] = status_counts.get(normalized_status, 0) + count
    total_amount = q.with_entities(func.coalesce(func.sum(Project.contract_amount), 0)).scalar() or 0

    if order_by == "amount_desc":
        q = q.order_by(Project.contract_amount.desc(), Project.updated_at.desc(), Project.id.desc())
    elif order_by == "amount_asc":
        q = q.order_by(Project.contract_amount.asc(), Project.updated_at.desc(), Project.id.desc())
    elif order_by == "end_date":
        q = q.order_by(Project.contract_end.asc().nullslast(), Project.updated_at.desc(), Project.id.desc())
    else:
        order_by = "recent"
        q = q.order_by(Project.updated_at.desc(), Project.id.desc())

    projects = q.limit(limit).all() if limit else q.all()
    return {
        "query": query,
        "status_filter": normalized_status_filter or None,
        "order_by": order_by,
        "total_count": total_count,
        "status_counts": status_counts,
        "total_contract_amount": _num(total_amount),
        "items": [
            {
                "id": row.id,
                "project_no": row.project_no,
                "project_name": row.project_name,
                "client_name": row.client_name,
                "status": _normalize_project_status(row.status),
                "pm_name": row.pm_name,
                "contract_amount": _num(row.contract_amount),
                "contract_start": str(row.contract_start) if row.contract_start else None,
                "contract_end": str(row.contract_end) if row.contract_end else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in projects
        ],
    }


def list_waiting_opinions(args: dict[str, Any], db: Session, current: User) -> dict[str, Any]:
    limit = args.get("limit")
    limit = min(max(int(limit), 1), 500) if limit is not None else None
    status_filter = str(args.get("status") or "waiting").strip()
    query = str(args.get("query") or "").strip()
    has_attachments = args.get("has_attachments")
    q = db.query(OpinionPost)
    if query:
        like = f"%{query}%"
        q = q.filter(or_(OpinionPost.title.ilike(like), OpinionPost.content.ilike(like)))
    if status_filter == "waiting":
        q = q.filter(OpinionPost.answer.is_(None))
    elif status_filter == "answered":
        q = q.filter(OpinionPost.answer.isnot(None))
    else:
        status_filter = "all"
    if has_attachments is True:
        q = q.filter(OpinionPost.attachments.any())

    total_count = q.count()
    q = q.order_by(OpinionPost.created_at.desc(), OpinionPost.id.desc())
    rows = q.limit(limit).all() if limit else q.all()
    total_waiting = db.query(func.count(OpinionPost.id)).filter(OpinionPost.answer.is_(None)).scalar() or 0
    total_answered = db.query(func.count(OpinionPost.id)).filter(OpinionPost.answer.isnot(None)).scalar() or 0
    return {
        "status_filter": status_filter,
        "query": query,
        "has_attachments": has_attachments is True,
        "total_count": total_count,
        "total_waiting": total_waiting,
        "total_answered": total_answered,
        "items": [
            {
                "id": row.id,
                "title": row.title,
                "status": "answered" if row.answer else "waiting",
                "creator_name": row.creator.name if row.creator else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "answered_at": row.answered_at.isoformat() if row.answered_at else None,
                "answerer_name": row.answerer.name if row.answerer else None,
                "attachment_count": len(row.attachments),
            }
            for row in rows
        ],
    }


def get_operational_summary(args: dict[str, Any], db: Session, current: User) -> dict[str, Any]:
    timesheet_args = {
        "week_start": args.get("week_start"),
        "period_start": args.get("period_start"),
        "period_end": args.get("period_end"),
    }
    timesheet = get_timesheet_team_status(timesheet_args, db, current)
    schedules = get_schedule_status({
        "week_start": args.get("week_start"),
        "period_start": args.get("period_start"),
        "period_end": args.get("period_end"),
    }, db, current)
    opinions = list_waiting_opinions({"status": "waiting"}, db, current)
    active_projects = db.query(func.count(Project.id)).filter(
        Project.status.in_(_project_status_filter_values("진행중"))
    ).scalar() or 0
    project_summary = search_projects({"status": "진행중", "order_by": "recent"}, db, current)
    return {
        "timesheet": {
            "week_start": timesheet["week_start"],
            "week_end": timesheet["week_end"],
            "period_start": timesheet["period_start"],
            "period_end": timesheet["period_end"],
            "period_unit": timesheet["period_unit"],
            "counts": timesheet["counts"],
            "all_counts": timesheet["all_counts"],
            "total_hours": timesheet["total_hours"],
            "rows": timesheet["rows"],
        },
        "opinions": opinions,
        "schedules": schedules,
        "projects": {
            "active_count": active_projects,
            "total_count": project_summary["total_count"],
            "status_counts": project_summary["status_counts"],
            "total_contract_amount": project_summary["total_contract_amount"],
            "recent": project_summary["items"],
        },
    }


TOOL_HANDLERS: dict[str, ToolHandler] = {
    "get_operational_summary": get_operational_summary,
    "get_timesheet_team_status": get_timesheet_team_status,
    "get_schedule_status": get_schedule_status,
    "search_projects": search_projects,
    "list_waiting_opinions": list_waiting_opinions,
}


def call_tool(name: str, arguments: dict[str, Any] | None, db: Session, current: User) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        raise KeyError(f"Unknown MCP tool: {name}")
    return handler(arguments or {}, db, current)
