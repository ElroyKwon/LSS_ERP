from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..models.common import Department, OpinionPost, User
from ..models.execution import Project
from ..models.master import Employee
from ..models.timesheet import Timesheet
from ..utils.permissions import is_system_admin, normalize_role


ToolHandler = Callable[[dict[str, Any], Session, User], dict[str, Any]]


def _today() -> date:
    return date.today()


def _week_of(day: date) -> tuple[date, date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def _parse_date(value: Any, default: date) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return default
    return default


def _num(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


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
            allowed = {row.id for row in rows}
            if emp:
                allowed.add(emp.id)
            return allowed
    return {emp.id} if emp else set()


def _employee_query(db: Session, current: User):
    q = db.query(Employee).filter(Employee.is_active == True)
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
            "title": "타임시트 제출 현황",
            "description": "권한 범위 내 직원의 주간 타임시트 제출 상태와 총 시간을 조회합니다.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "week_start": {
                        "type": "string",
                        "description": "조회할 주의 시작일(YYYY-MM-DD).",
                    },
                    "status": {
                        "type": "string",
                        "description": "미작성, 작성중, 제출, 승인, 반려 중 하나로 필터링합니다.",
                    },
                },
            },
        },
        {
            "name": "search_projects",
            "title": "프로젝트 검색",
            "description": "프로젝트 번호, 프로젝트명, 거래처명, PM명으로 프로젝트를 검색합니다.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색어"},
                    "limit": {"type": "integer", "description": "최대 결과 수", "default": 10},
                },
            },
        },
        {
            "name": "list_waiting_opinions",
            "title": "의견 청취 답변 대기",
            "description": "답변이 등록되지 않은 의견 청취 글을 최신순으로 조회합니다.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "최대 결과 수", "default": 10}
                },
            },
        },
    ]


def get_timesheet_team_status(args: dict[str, Any], db: Session, current: User) -> dict[str, Any]:
    monday, sunday = _week_of(_parse_date(args.get("week_start"), _today()))
    employees = _employee_query(db, current).order_by(Employee.department_name.asc(), Employee.name.asc()).all()
    employee_ids = [emp.id for emp in employees]
    rows = []
    sheets_by_employee: dict[int, Timesheet] = {}
    if employee_ids:
        sheets = db.query(Timesheet).filter(
            Timesheet.week_start == monday,
            Timesheet.employee_id.in_(employee_ids),
        ).all()
        sheets_by_employee = {sheet.employee_id: sheet for sheet in sheets}

    status_filter = args.get("status")
    for emp in employees:
        sheet = sheets_by_employee.get(emp.id)
        status = sheet.status if sheet else "미작성"
        if status_filter and status != status_filter:
            continue
        rows.append({
            "employee_id": emp.id,
            "employee_name": emp.name,
            "department": emp.department.name if emp.department else emp.department_name,
            "position": emp.position,
            "status": status,
            "total_hours": _num(sheet.total_hours) if sheet else 0,
            "timesheet_id": sheet.id if sheet else None,
        })

    counts: dict[str, int] = {}
    total_hours = 0.0
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        total_hours += row["total_hours"]

    return {
        "week_start": str(monday),
        "week_end": str(sunday),
        "counts": counts,
        "total_hours": round(total_hours, 2),
        "rows": rows,
    }


def search_projects(args: dict[str, Any], db: Session, current: User) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    limit = min(max(int(args.get("limit") or 10), 1), 30)
    q = db.query(Project)
    if query:
        like = f"%{query}%"
        q = q.filter(or_(
            Project.project_no.ilike(like),
            Project.project_name.ilike(like),
            Project.client_name.ilike(like),
            Project.pm_name.ilike(like),
        ))
    projects = q.order_by(Project.updated_at.desc(), Project.id.desc()).limit(limit).all()
    return {
        "query": query,
        "items": [
            {
                "id": row.id,
                "project_no": row.project_no,
                "project_name": row.project_name,
                "client_name": row.client_name,
                "status": row.status,
                "pm_name": row.pm_name,
                "contract_amount": _num(row.contract_amount),
                "contract_start": str(row.contract_start) if row.contract_start else None,
                "contract_end": str(row.contract_end) if row.contract_end else None,
            }
            for row in projects
        ],
    }


def list_waiting_opinions(args: dict[str, Any], db: Session, current: User) -> dict[str, Any]:
    limit = min(max(int(args.get("limit") or 10), 1), 30)
    rows = db.query(OpinionPost).filter(
        OpinionPost.answer.is_(None)
    ).order_by(OpinionPost.created_at.desc(), OpinionPost.id.desc()).limit(limit).all()
    total_waiting = db.query(func.count(OpinionPost.id)).filter(OpinionPost.answer.is_(None)).scalar() or 0
    return {
        "total_waiting": total_waiting,
        "items": [
            {
                "id": row.id,
                "title": row.title,
                "creator_name": row.creator.name if row.creator else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "attachment_count": len(row.attachments),
            }
            for row in rows
        ],
    }


def get_operational_summary(args: dict[str, Any], db: Session, current: User) -> dict[str, Any]:
    timesheet = get_timesheet_team_status({"week_start": args.get("week_start")}, db, current)
    opinions = list_waiting_opinions({"limit": 5}, db, current)
    active_projects = db.query(func.count(Project.id)).filter(Project.status != "완료").scalar() or 0
    recent_projects = search_projects({"limit": 5}, db, current)
    return {
        "timesheet": {
            "week_start": timesheet["week_start"],
            "week_end": timesheet["week_end"],
            "counts": timesheet["counts"],
            "total_hours": timesheet["total_hours"],
        },
        "opinions": opinions,
        "projects": {
            "active_count": active_projects,
            "recent": recent_projects["items"],
        },
    }


TOOL_HANDLERS: dict[str, ToolHandler] = {
    "get_operational_summary": get_operational_summary,
    "get_timesheet_team_status": get_timesheet_team_status,
    "search_projects": search_projects,
    "list_waiting_opinions": list_waiting_opinions,
}


def call_tool(name: str, arguments: dict[str, Any] | None, db: Session, current: User) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        raise KeyError(f"Unknown MCP tool: {name}")
    return handler(arguments or {}, db, current)

