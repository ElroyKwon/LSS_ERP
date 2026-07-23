import json
import os
import re
import traceback
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Tuple
from fastapi import APIRouter, HTTPException, status, Query, Depends
from pydantic import BaseModel
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pathlib import Path
from dotenv import load_dotenv
from ..utils.auth import get_current_user
from ..utils.system_accounts import is_system_account_username
from ..database import get_db
from ..models.common import User, CalendarSchedule
from ..models.master import Employee
from ..models.timesheet import Timesheet, TimesheetEntry

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / "google_calendar.env")

router = APIRouter(
    prefix="/api/schedules",
    tags=["Schedules"]
)

class ScheduleCreate(BaseModel):
    content: str
    date: Optional[str] = None
    end_date: Optional[str] = None
    type: str
    category: Optional[str] = "company"
    user_name: str
    is_all_day: Optional[bool] = True
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    schedule_kind: Optional[str] = None
    timesheet_project_id: Optional[int] = None
    timesheet_project_name: Optional[str] = None
    timesheet_project_source: Optional[str] = None

SCOPES = ['https://www.googleapis.com/auth/calendar']

env_credentials_dir = os.getenv("GOOGLE_CUSTOM_CREDENTIALS_DIR")
FILE_NAME_WORK = os.getenv("GOOGLE_CUSTOM_KEY_WORK_NAME")
HARDCODED_COMPANY_ID = os.getenv("GOOGLE_CUSTOM_CALENDAR_COMPANY_ID")
FILE_NAME_REFRESH = os.getenv("GOOGLE_CUSTOM_KEY_REFRESH_NAME")
HARDCODED_REFRESH_CALENDAR_ID = os.getenv("GOOGLE_CUSTOM_CALENDAR_REFRESH_ID")

def _resolve_credentials_dir(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().replace("\\", os.sep).replace("/", os.sep)
    path = Path(normalized)
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path.resolve())


CREDENTIALS_DIR = _resolve_credentials_dir(env_credentials_dir)

_google_services_cache: Dict[str, Tuple[any, str]] = {}


def get_calendar_config_and_service(category: str):
    if category in _google_services_cache:
        return _google_services_cache[category]

    if not CREDENTIALS_DIR:
        raise HTTPException(
            status_code=500,
            detail="환경 변수 'GOOGLE_CUSTOM_CREDENTIALS_DIR'이 정의되지 않았습니다."
        )

    if category == "refresh":
        json_path = os.path.join(CREDENTIALS_DIR, FILE_NAME_REFRESH or "")
        calendar_id = HARDCODED_REFRESH_CALENDAR_ID
    else:
        json_path = os.path.join(CREDENTIALS_DIR, FILE_NAME_WORK or "")
        calendar_id = HARDCODED_COMPANY_ID

    if not calendar_id:
        raise HTTPException(
            status_code=500,
            detail=f"'{category}' 캘린더 ID 환경 변수가 정의되지 않았습니다."
        )
        
    if not json_path or not os.path.exists(json_path):
        raise HTTPException(
            status_code=500, 
            detail=f"인증에 필요한 구글 JSON 키 파일이 경로에 없습니다: {json_path}"
        )
        
    creds = service_account.Credentials.from_service_account_file(json_path, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    
    _google_services_cache[category] = (service, calendar_id)
    return service, calendar_id


def extract_event_owner(event: dict) -> str:
    raw_summary = event.get('summary', '') or ''
    if raw_summary.startswith('[') and ']' in raw_summary:
        match = re.match(r"^\[(.*?)\]\s*(.*)$", raw_summary)
        if match:
            return match.group(1).strip()
    return ''


def require_event_owner(event: dict, current_user) -> None:
    owner = extract_event_owner(event)
    current_name = (getattr(current_user, 'name', '') or '').strip()
    if not owner or owner != current_name:
        raise HTTPException(status_code=403, detail='본인이 등록한 일정만 수정 또는 삭제할 수 있습니다.')



DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PROJECT_SOURCES = {"실행", "영업", "공통"}
COMPANY_KIND_BY_COLOR = {
    "#52c41a": "외근",
    "#722ed1": "출장",
    "#fa8c16": "출장",
}
REFRESH_KIND_BY_COLOR = {
    "#bae7ff": "연차",
    "#13c2c2": "반차",
    "#eb2f96": "반반차",
    "#1890ff": "대체휴가",
    "#bfbfbf": "하계휴가",
    "#ff7a45": "병가",
    "#d9d9d9": "기타",
}
REFRESH_HOURS = {
    "반차": Decimal("4"),
    "반반차": Decimal("2"),
}
TIMESHEET_META_MARKER = "TIMESHEET_META:"


def _week_of(day: date) -> tuple[date, date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def _parse_ymd(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _iter_dates(start_day: date, end_day: date):
    current = start_day
    while current <= end_day:
        yield current
        current += timedelta(days=1)


def _current_employee(db: Session, current_user) -> Employee | None:
    employee_code = (getattr(current_user, "employee_code", None) or "").strip()
    if employee_code:
        employee = db.query(Employee).filter(Employee.emp_code == employee_code).first()
        if employee:
            return employee
    user_name = (getattr(current_user, "name", None) or "").strip()
    if user_name:
        return db.query(Employee).filter(Employee.name == user_name).first()
    return None


def _current_labor_type(db: Session, employee: Employee, current_user) -> str:
    labor_type = (getattr(current_user, "labor_type", None) or "").strip()
    if labor_type in {"판관", "원가"}:
        return labor_type

    user = None
    if employee.emp_code:
        user = db.query(User).filter(User.employee_code == employee.emp_code).first()
    if not user and employee.name:
        user = db.query(User).filter(User.name == employee.name).first()
    labor_type = (getattr(user, "labor_type", None) or "").strip() if user else ""
    return labor_type if labor_type in {"판관", "원가"} else "원가"


def _schedule_kind(payload: ScheduleCreate) -> str:
    if payload.schedule_kind:
        return payload.schedule_kind.strip()
    if payload.category == "refresh":
        return REFRESH_KIND_BY_COLOR.get(payload.type, "연차")
    return COMPANY_KIND_BY_COLOR.get(payload.type, "출장")


def _schedule_meta(payload: ScheduleCreate) -> dict:
    project_source = (payload.timesheet_project_source or "공통").strip()
    if project_source not in PROJECT_SOURCES:
        project_source = "공통"
    return {
        "schedule_kind": _schedule_kind(payload),
        "timesheet_project_id": payload.timesheet_project_id,
        "timesheet_project_name": (payload.timesheet_project_name or payload.content or "").strip(),
        "timesheet_project_source": project_source,
    }


def _parse_schedule_meta(description: str | None) -> dict:
    if not description or TIMESHEET_META_MARKER not in description:
        return {}
    raw = description.split(TIMESHEET_META_MARKER, 1)[1].splitlines()[0].strip()
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _schedule_description(payload: ScheduleCreate, user_name: str) -> str:
    meta = _schedule_meta(payload)
    return (
        f"유형: {payload.type} (사내 Timesheet 시스템 연동 - 등록자: {user_name})\n"
        f"{TIMESHEET_META_MARKER}{json.dumps(meta, ensure_ascii=False, separators=(',', ':'))}"
    )


def _recalculate_timesheet_total(db: Session, timesheet: Timesheet) -> None:
    total = Decimal("0")
    entries = db.query(TimesheetEntry).filter(TimesheetEntry.timesheet_id == timesheet.id).all()
    for entry in entries:
        for key in DAY_KEYS:
            total += Decimal(str(getattr(entry, f"{key}_hours") or 0))
    timesheet.total_hours = total


def _delete_timesheet_entries_for_schedule(db: Session, event_id: str, category: str) -> list[int]:
    entries = db.query(TimesheetEntry).filter(
        TimesheetEntry.schedule_event_id == event_id,
        TimesheetEntry.schedule_category == category,
    ).all()
    affected_ids = sorted({entry.timesheet_id for entry in entries if entry.timesheet_id})
    for entry in entries:
        db.delete(entry)
    db.flush()
    return affected_ids


def _get_or_create_timesheet(db: Session, employee: Employee, week_start: date, week_end: date, current_user) -> Timesheet:
    timesheet = db.query(Timesheet).filter(
        Timesheet.employee_id == employee.id,
        Timesheet.week_start == week_start,
    ).first()
    if timesheet:
        return timesheet
    timesheet = Timesheet(
        employee_id=employee.id,
        week_start=week_start,
        week_end=week_end,
        status="작성중",
        created_by=getattr(current_user, "id", None),
    )
    db.add(timesheet)
    db.flush()
    return timesheet


def _next_sort_order(db: Session, timesheet_id: int) -> int:
    max_order = db.query(sqlfunc.max(TimesheetEntry.sort_order)).filter(
        TimesheetEntry.timesheet_id == timesheet_id,
    ).scalar()
    return int(max_order or 0) + 1


def _set_entry_hours(entry: TimesheetEntry, hours_by_day: dict[str, Decimal]) -> None:
    for key in DAY_KEYS:
        setattr(entry, f"{key}_hours", hours_by_day.get(key, Decimal("0")))


def _sync_schedule_to_timesheet(db: Session, payload: ScheduleCreate, event_id: str, current_user) -> None:
    if is_system_account_username(getattr(current_user, "username", None)):
        return

    employee = _current_employee(db, current_user)
    if not employee:
        raise HTTPException(status_code=400, detail="로그인 사용자의 사원 정보를 찾을 수 없어 타임시트에 자동 반영할 수 없습니다.")

    _delete_timesheet_entries_for_schedule(db, event_id, payload.category or "company")

    kind = _schedule_kind(payload)
    labor_type = _current_labor_type(db, employee, current_user)
    project_source = (payload.timesheet_project_source or "공통").strip()
    if project_source not in PROJECT_SOURCES:
        project_source = "공통"
    project_id = payload.timesheet_project_id if project_source == "실행" else None

    if payload.category == "refresh":
        start_day = _parse_ymd(payload.date) if payload.date else None
        end_day = _parse_ymd(payload.end_date or payload.date) if payload.date else None
        if not start_day or not end_day:
            raise HTTPException(status_code=400, detail="휴가 일정은 기간이 필요합니다.")
        project_name = kind
        notes = (payload.content or "").strip() or None
        work_type = "공통 > 연차"
        source = "공통"
        project_id = None
        daily_hours = REFRESH_HOURS.get(kind, Decimal("8"))
        schedule_days = [(day, daily_hours) for day in _iter_dates(start_day, end_day)]
    else:
        project_name = (payload.timesheet_project_name or payload.content or "").strip()
        if not project_name:
            raise HTTPException(status_code=400, detail="일정명이 필요합니다.")
        notes = kind
        work_type = "공통 > 기타"
        source = project_source
        if kind == "외근":
            if not payload.start_time or not payload.end_time:
                raise HTTPException(status_code=400, detail="외근 일정은 시작/종료 시간이 필요합니다.")
            start_dt = datetime.strptime(payload.start_time, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(payload.end_time, "%Y-%m-%d %H:%M:%S")
            if end_dt <= start_dt:
                raise HTTPException(status_code=400, detail="종료 시간은 시작 시간보다 늦어야 합니다.")
            hours = min(Decimal(str(round((end_dt - start_dt).total_seconds() / 3600, 2))), Decimal("8"))
            schedule_days = [(start_dt.date(), hours)]
        else:
            start_day = _parse_ymd(payload.date) if payload.date else None
            end_day = _parse_ymd(payload.end_date or payload.date) if payload.date else None
            if not start_day or not end_day:
                raise HTTPException(status_code=400, detail="출장 일정은 기간이 필요합니다.")
            schedule_days = [(day, Decimal("8")) for day in _iter_dates(start_day, end_day)]

    by_week: dict[date, dict[str, Decimal]] = {}
    for day, hours in schedule_days:
        week_start, _ = _week_of(day)
        by_week.setdefault(week_start, {})[DAY_KEYS[day.weekday()]] = hours

    affected = []
    for week_start, hours_by_day in by_week.items():
        _, week_end = _week_of(week_start)
        timesheet = _get_or_create_timesheet(db, employee, week_start, week_end, current_user)
        entry = TimesheetEntry(
            timesheet_id=timesheet.id,
            project_id=project_id,
            project_name=project_name,
            project_source=source,
            spg="공통",
            labor_type=labor_type,
            work_type=work_type,
            sort_order=_next_sort_order(db, timesheet.id),
            notes=notes,
            schedule_event_id=event_id,
            schedule_category=payload.category or "company",
        )
        _set_entry_hours(entry, hours_by_day)
        db.add(entry)
        affected.append(timesheet)

    db.flush()
    for timesheet in affected:
        _recalculate_timesheet_total(db, timesheet)


def _remove_schedule_from_timesheet(db: Session, event_id: str, category: str) -> None:
    affected_ids = _delete_timesheet_entries_for_schedule(db, event_id, category)
    if not affected_ids:
        return
    timesheets = db.query(Timesheet).filter(Timesheet.id.in_(affected_ids)).all()
    for timesheet in timesheets:
        _recalculate_timesheet_total(db, timesheet)


def build_google_event(payload: ScheduleCreate, user_name: str) -> dict:
    display_summary = f"[{user_name}] {payload.content}"
    description = _schedule_description(payload, user_name)

    if payload.is_all_day:
        start_date_str = payload.date
        if not start_date_str:
            raise HTTPException(status_code=400, detail='종일 일정은 시작일이 필요합니다.')
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_dt = datetime.strptime(payload.end_date or start_date_str, '%Y-%m-%d')
        if end_dt < start_dt:
            raise HTTPException(status_code=400, detail='종료일은 시작일보다 빠를 수 없습니다.')
        end_date_str = (end_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        return {
            'summary': display_summary,
            'description': description,
            'start': {'date': start_date_str, 'timeZone': 'Asia/Seoul'},
            'end': {'date': end_date_str, 'timeZone': 'Asia/Seoul'},
        }

    if not payload.start_time or not payload.end_time:
        raise HTTPException(status_code=400, detail='시간 지정 일정은 start_time과 end_time 필드가 필요합니다.')
    start_dt = datetime.strptime(payload.start_time, '%Y-%m-%d %H:%M:%S')
    end_dt = datetime.strptime(payload.end_time, '%Y-%m-%d %H:%M:%S')
    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail='종료 시간은 시작 시간보다 늦어야 합니다.')
    return {
        'summary': display_summary,
        'description': description,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Seoul'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Seoul'},
    }


def _parse_google_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("T", " ")[:19]
    try:
        return datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _payload_start_date(payload: ScheduleCreate) -> date | None:
    if payload.is_all_day:
        return _parse_ymd(payload.date) if payload.date else None
    start_dt = _parse_google_datetime(payload.start_time)
    return start_dt.date() if start_dt else None


def _payload_end_date(payload: ScheduleCreate) -> date | None:
    if payload.is_all_day:
        return _parse_ymd(payload.end_date or payload.date) if payload.date else None
    end_dt = _parse_google_datetime(payload.end_time)
    return end_dt.date() if end_dt else _payload_start_date(payload)


def _upsert_schedule_row(
    db: Session,
    event_id: str,
    payload: ScheduleCreate,
    current_user,
    user_name: str,
) -> CalendarSchedule:
    row = db.query(CalendarSchedule).filter(
        CalendarSchedule.google_event_id == event_id,
        CalendarSchedule.category == (payload.category or "company"),
    ).first()
    if not row:
        row = CalendarSchedule(
            google_event_id=event_id,
            category=payload.category or "company",
            created_by=getattr(current_user, "id", None),
        )
        db.add(row)

    row.content = payload.content
    row.type = payload.type
    row.user_name = user_name
    row.is_all_day = bool(payload.is_all_day)
    row.date = _payload_start_date(payload)
    row.end_date = _payload_end_date(payload)
    row.start_time = None if payload.is_all_day else _parse_google_datetime(payload.start_time)
    row.end_time = None if payload.is_all_day else _parse_google_datetime(payload.end_time)
    row.schedule_kind = _schedule_kind(payload)
    row.timesheet_project_id = payload.timesheet_project_id
    row.timesheet_project_name = (payload.timesheet_project_name or payload.content or "").strip()
    row.timesheet_project_source = (payload.timesheet_project_source or "공통").strip()
    if row.timesheet_project_source not in PROJECT_SOURCES:
        row.timesheet_project_source = "공통"
    return row


def _schedule_row_to_response(row: CalendarSchedule) -> dict:
    return {
        "id": row.google_event_id,
        "content": row.content,
        "user_name": row.user_name,
        "date": row.date.strftime("%Y-%m-%d") if row.date else "",
        "type": row.type,
        "is_all_day": row.is_all_day,
        "start_time": row.start_time.strftime("%Y-%m-%d %H:%M:%S") if row.start_time else None,
        "end_time": row.end_time.strftime("%Y-%m-%d %H:%M:%S") if row.end_time else None,
        "start_date": row.date.strftime("%Y-%m-%d") if row.date else "",
        "end_date": row.end_date.strftime("%Y-%m-%d") if row.end_date else (row.date.strftime("%Y-%m-%d") if row.date else ""),
        "schedule_kind": row.schedule_kind,
        "timesheet_project_id": row.timesheet_project_id,
        "timesheet_project_name": row.timesheet_project_name,
        "timesheet_project_source": row.timesheet_project_source,
    }


def _google_event_to_schedule_row(db: Session, event: dict, category: str) -> CalendarSchedule:
    start_info = event.get('start', {})
    if not start_info:
        raise ValueError("Google event start time is missing.")
    is_all_day = 'date' in start_info

    if is_all_day:
        start_date_value = start_info.get('date')
        if not start_date_value:
            raise ValueError("Google all-day event start date is missing.")
        start_date = _parse_ymd(start_date_value)
        end_date_str = event.get('end', {}).get('date', start_info.get('date'))
        try:
            end_date = _parse_ymd(end_date_str) - timedelta(days=1)
        except Exception:
            end_date = start_date
        start_time = None
        end_time = None
    else:
        start_time = _parse_google_datetime(start_info.get('dateTime'))
        end_time = _parse_google_datetime(event.get('end', {}).get('dateTime'))
        start_date = start_time.date() if start_time else None
        end_date = end_time.date() if end_time else start_date

    raw_summary = event.get('summary', '제목 없음')
    content = raw_summary
    user_name = ""
    if raw_summary.startswith("[") and "]" in raw_summary:
        match = re.match(r"^\[(.*?)\]\s*(.*)$", raw_summary)
        if match:
            user_name = match.group(1).strip()
            content = match.group(2).strip()

    desc = event.get('description', '')
    meta = _parse_schedule_meta(desc)
    schedule_type = "success"
    if "유형:" in desc:
        try:
            raw_type = desc.split("유형:")[1].split("(")[0].strip()
            schedule_type = raw_type if raw_type else schedule_type
        except Exception:
            pass

    row = db.query(CalendarSchedule).filter(
        CalendarSchedule.google_event_id == event.get('id'),
        CalendarSchedule.category == category,
    ).first()
    if not row:
        row = CalendarSchedule(google_event_id=event.get('id'), category=category)
        db.add(row)

    row.content = content
    row.user_name = user_name or "미확인"
    row.type = schedule_type
    row.is_all_day = is_all_day
    row.date = start_date
    row.end_date = end_date
    row.start_time = start_time
    row.end_time = end_time
    row.schedule_kind = meta.get("schedule_kind") or (REFRESH_KIND_BY_COLOR.get(schedule_type) if category == "refresh" else COMPANY_KIND_BY_COLOR.get(schedule_type))
    row.timesheet_project_id = meta.get("timesheet_project_id")
    row.timesheet_project_name = meta.get("timesheet_project_name") or content
    row.timesheet_project_source = meta.get("timesheet_project_source") or "공통"
    return row


def _sync_google_events_to_db(db: Session, category: str) -> None:
    service, target_calendar_id = get_calendar_config_and_service(category)
    events_result = service.events().list(
        calendarId=target_calendar_id,
        maxResults=250,
        singleEvents=True,
        orderBy='startTime',
        timeZone='Asia/Seoul'
    ).execute()
    for event in events_result.get('items', []):
        event_id = event.get('id')
        if event_id:
            _google_event_to_schedule_row(db, event, category)
    db.commit()


@router.get("")
def get_schedules(category: str = Query("company", description="company 또는 refresh"), db: Session = Depends(get_db)):
    try:
        existing_count = db.query(CalendarSchedule).filter(
            CalendarSchedule.category == category,
        ).count()
        if existing_count == 0:
            try:
                _sync_google_events_to_db(db, category)
            except HttpError as he:
                db.rollback()
                print(f"\n=== GOOGLE CALENDAR INITIAL SYNC HTTP ERROR ({category}) ===")
                print(f"Status Code: {he.resp.status}, Reason: {he.content}")
            except Exception:
                db.rollback()
                print(f"\n=== GOOGLE CALENDAR INITIAL SYNC ERROR ({category}) ===")
                traceback.print_exc()
                print("==================================================\n")

        rows = db.query(CalendarSchedule).filter(
            CalendarSchedule.category == category,
        ).order_by(
            CalendarSchedule.date.asc().nullslast(),
            CalendarSchedule.start_time.asc().nullslast(),
            CalendarSchedule.id.asc(),
        ).all()
        return [_schedule_row_to_response(row) for row in rows]

    except Exception as e:
        print(f"\n=== DB CALENDAR FETCH ERROR ({category}) ===")
        traceback.print_exc()
        print("==================================================\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"전사일정 DB 조회 실패: {str(e)}"
        )


@router.post("")
def create_schedule(payload: ScheduleCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    service = None
    target_calendar_id = None
    event_id = None
    try:
        service, target_calendar_id = get_calendar_config_and_service(payload.category)
        user_name = (getattr(current_user, 'name', None) or payload.user_name or '미확인').strip()
        if not _current_employee(db, current_user):
            raise HTTPException(status_code=400, detail="로그인 사용자의 사원 정보를 찾을 수 없어 타임시트에 자동 반영할 수 없습니다.")
        event = build_google_event(payload, user_name)
        google_result = service.events().insert(calendarId=target_calendar_id, body=event).execute()
        event_id = google_result.get('id')
        if event_id:
            _upsert_schedule_row(db, event_id, payload, current_user, user_name)
            _sync_schedule_to_timesheet(db, payload, event_id, current_user)
            db.commit()
        else:
            raise HTTPException(status_code=500, detail="구글 캘린더 일정 ID를 받지 못했습니다.")
        return {
            "status": "success",
            "id": event_id
        }

    except HTTPException:
        db.rollback()
        if service and target_calendar_id and event_id:
            try:
                service.events().delete(calendarId=target_calendar_id, eventId=event_id).execute()
            except Exception:
                print(f"\n=== GOOGLE CALENDAR COMPENSATING DELETE FAILED ({payload.category}, {event_id}) ===")
                traceback.print_exc()
                print("==================================================\n")
        raise
    except HttpError as he:
        db.rollback()
        print(f"\n=== GOOGLE CALENDAR API HTTP ERROR ({payload.category}) ===")
        print(f"Status Code: {he.resp.status}, Reason: {he.content}")
        raise HTTPException(status_code=he.resp.status, detail="구글 캘린더 쓰기 권한이 없거나 API 오류가 발생했습니다.")
    except Exception as e:
        db.rollback()
        if service and target_calendar_id and event_id:
            try:
                service.events().delete(calendarId=target_calendar_id, eventId=event_id).execute()
            except Exception:
                print(f"\n=== GOOGLE CALENDAR COMPENSATING DELETE FAILED ({payload.category}, {event_id}) ===")
                traceback.print_exc()
                print("==================================================\n")
        print(f"\n=== GOOGLE CALENDAR INSERT ERROR ({payload.category}) ===")
        traceback.print_exc()
        print("==================================================\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"구글 API ({payload.category}) 수정 실패 원인: {str(e)}"
        )


@router.put("/{event_id}")
def update_schedule(event_id: str, payload: ScheduleCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    service = None
    target_calendar_id = None
    existing = None
    google_updated = False
    try:
        service, target_calendar_id = get_calendar_config_and_service(payload.category)
        existing = service.events().get(calendarId=target_calendar_id, eventId=event_id).execute()
        require_event_owner(existing, current_user)
        user_name = (getattr(current_user, 'name', None) or payload.user_name or '미확인').strip()
        if not _current_employee(db, current_user):
            raise HTTPException(status_code=400, detail="로그인 사용자의 사원 정보를 찾을 수 없어 타임시트에 자동 반영할 수 없습니다.")
        event = build_google_event(payload, user_name)
        _upsert_schedule_row(db, event_id, payload, current_user, user_name)
        _sync_schedule_to_timesheet(db, payload, event_id, current_user)
        service.events().update(calendarId=target_calendar_id, eventId=event_id, body=event).execute()
        google_updated = True
        db.commit()
        return {"status": "success", "id": event_id}

    except HTTPException:
        db.rollback()
        raise
    except HttpError as he:
        db.rollback()
        status_code = getattr(he.resp, 'status', 500)
        if status_code == 404:
            raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
        print(f"\n=== GOOGLE CALENDAR UPDATE ERROR ({payload.category}) ===")
        print(f"Status Code: {status_code}, Reason: {he.content}")
        raise HTTPException(status_code=status_code, detail="구글 캘린더 일정 수정 중 오류가 발생했습니다.")
    except Exception as e:
        db.rollback()
        if service and target_calendar_id and existing and google_updated:
            try:
                service.events().update(calendarId=target_calendar_id, eventId=event_id, body=existing).execute()
            except Exception:
                print(f"\n=== GOOGLE CALENDAR COMPENSATING UPDATE FAILED ({payload.category}, {event_id}) ===")
                traceback.print_exc()
                print("==================================================\n")
        print(f"\n=== GOOGLE CALENDAR UPDATE ERROR ({payload.category}) ===")
        traceback.print_exc()
        print("==================================================\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"구글 API ({payload.category}) 수정 실패 원인: {str(e)}"
        )


@router.delete("/{event_id}")
def delete_schedule(event_id: str, category: str = Query("company"), current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        service, target_calendar_id = get_calendar_config_and_service(category)
        existing = service.events().get(calendarId=target_calendar_id, eventId=event_id).execute()
        require_event_owner(existing, current_user)
        _remove_schedule_from_timesheet(db, event_id, category)
        row = db.query(CalendarSchedule).filter(
            CalendarSchedule.google_event_id == event_id,
            CalendarSchedule.category == category,
        ).first()
        if row:
            db.delete(row)
        service.events().delete(calendarId=target_calendar_id, eventId=event_id).execute()
        db.commit()
        return {"status": "success"}

    except HTTPException:
        db.rollback()
        raise
    except HttpError as he:
        db.rollback()
        status_code = getattr(he.resp, 'status', 500)
        if status_code == 404:
            raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
        print(f"\n=== GOOGLE CALENDAR DELETE ERROR ({category}) ===")
        print(f"Status Code: {status_code}, Reason: {he.content}")
        raise HTTPException(status_code=status_code, detail="구글 캘린더 일정 삭제 중 오류가 발생했습니다.")
    except Exception as e:
        db.rollback()
        print(f"\n=== GOOGLE CALENDAR DELETE ERROR ({category}) ===")
        traceback.print_exc()
        print("==================================================\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"구글 API ({category}) 삭제 실패 원인: {str(e)}"
        )
