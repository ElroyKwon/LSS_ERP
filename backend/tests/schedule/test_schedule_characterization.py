from copy import deepcopy
from datetime import date
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.dialects import postgresql

from app.models.common import CalendarSchedule
from app.models.master import Employee
from app.models.timesheet import Timesheet, TimesheetEntry
from app.routers import schedule
from app.services import timesheet_locking
from app.utils.auth import create_access_token


REPO_ROOT = Path(__file__).resolve().parents[3]
CALENDAR_VIEW_SHA256 = "4497afd3cf580e822846c7d751b324d4c27495fd5bf85bb9640623bf15a4fb81"


class FakeGoogleRequest:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return deepcopy(self._result)


class FakeGoogleEvents:
    def __init__(self, *, insert_result=None, existing_event=None):
        self.insert_result = insert_result or {"id": "event-created"}
        self.existing_event = existing_event or {}
        self.insert_calls = []
        self.get_calls = []
        self.update_calls = []
        self.delete_calls = []

    def insert(self, **kwargs):
        self.insert_calls.append(deepcopy(kwargs))
        return FakeGoogleRequest(self.insert_result)

    def get(self, **kwargs):
        self.get_calls.append(deepcopy(kwargs))
        return FakeGoogleRequest(self.existing_event)

    def update(self, **kwargs):
        self.update_calls.append(deepcopy(kwargs))
        return FakeGoogleRequest({"id": kwargs["eventId"]})

    def delete(self, **kwargs):
        self.delete_calls.append(deepcopy(kwargs))
        return FakeGoogleRequest({})


class FakeGoogleService:
    def __init__(self, **events_kwargs):
        self.events_resource = FakeGoogleEvents(**events_kwargs)

    def events(self):
        return self.events_resource


def _company_payload(content="Customer visit"):
    return schedule.ScheduleCreate(
        content=content,
        date="2026-07-28",
        end_date="2026-07-29",
        type="#722ed1",
        category="company",
        user_name="Payload Name Must Not Win",
        is_all_day=True,
    )


def _expected_company_event(content="Customer visit"):
    return {
        "summary": f"[Alice] {content}",
        "description": (
            f"유형: #722ed1 (사내 Timesheet 시스템 연동 - 등록자: Alice)\n"
            f'TIMESHEET_META:{{"schedule_kind":"출장","timesheet_project_id":null,'
            f'"timesheet_project_name":"{content}","timesheet_project_source":"공통"}}'
        ),
        "start": {"date": "2026-07-28", "timeZone": "Asia/Seoul"},
        "end": {"date": "2026-07-30", "timeZone": "Asia/Seoul"},
    }


def _use_fake_google(monkeypatch, service, calendar_id="calendar-company"):
    monkeypatch.setattr(
        schedule,
        "get_calendar_config_and_service",
        lambda category: (service, calendar_id),
    )


def _fail_calendar_schedule_write(db_session):
    engine = db_session.get_bind()

    def fail_write(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if (
            normalized.startswith("insert into calendar_schedules")
            or normalized.startswith("update calendar_schedules")
        ):
            raise RuntimeError("forced SQLite calendar_schedules write failure")

    event.listen(engine, "before_cursor_execute", fail_write)
    return engine, fail_write


def _fail_commit_after_first_google_update(db_session, service):
    def fail_commit(_session):
        if len(service.events_resource.update_calls) == 1:
            raise RuntimeError("forced SQLite commit failure after Google update")

    event.listen(db_session, "before_commit", fail_commit)
    return db_session, fail_commit


def _track_schedule_lock_order(db_session, service, google_method):
    ordering = []

    def track_lock(orm_execute_state):
        statement = orm_execute_state.statement
        if getattr(statement, "_for_update_arg", None) is None:
            return
        sql = " ".join(
            str(statement.compile(dialect=postgresql.dialect())).lower().split()
        )
        if " from employees " in f" {sql} ":
            ordering.append("employee")
        elif " from timesheets " in f" {sql} ":
            ordering.append("timesheet")

    original = getattr(service.events_resource, google_method)

    def track_google(**kwargs):
        ordering.append("google")
        return original(**kwargs)

    event.listen(db_session, "do_orm_execute", track_lock)
    setattr(service.events_resource, google_method, track_google)
    return ordering, track_lock


def test_ordinary_jwt_create_without_mcp_headers_preserves_google_body_and_response(
    db_session,
    ordinary_user,
    schedule_client,
    monkeypatch,
):
    service = FakeGoogleService(insert_result={"id": "event-create-1"})
    _use_fake_google(monkeypatch, service)

    token = create_access_token({"sub": str(ordinary_user.id)})
    response = schedule_client.post(
        "/api/schedules",
        headers={"Authorization": f"Bearer {token}"},
        json=_company_payload().model_dump(),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success", "id": "event-create-1"}
    assert service.events_resource.insert_calls == [
        {
            "calendarId": "calendar-company",
            "body": _expected_company_event(),
        }
    ]
    stored = db_session.query(CalendarSchedule).one()
    assert (stored.google_event_id, stored.user_name) == ("event-create-1", "Alice")
    assert db_session.query(TimesheetEntry).count() == 1


def test_ordinary_create_locks_employee_and_missing_timesheet_week_before_google(
    db_session, ordinary_user, monkeypatch,
):
    service = FakeGoogleService(insert_result={"id": "event-create-lock"})
    _use_fake_google(monkeypatch, service)
    ordering, listener = _track_schedule_lock_order(db_session, service, "insert")
    try:
        result = schedule.create_schedule(
            _company_payload("Locked create"),
            current_user=ordinary_user,
            db=db_session,
        )
    finally:
        event.remove(db_session, "do_orm_execute", listener)

    assert result == {"status": "success", "id": "event-create-lock"}
    assert ordering[:3] == ["employee", "timesheet", "google"]


def test_ordinary_update_locks_employee_then_timesheet_before_google(
    db_session, ordinary_user, monkeypatch,
):
    employee = db_session.query(Employee).filter(
        Employee.emp_code == ordinary_user.employee_code,
    ).one()
    timesheet = Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 7, 27),
        week_end=date(2026, 8, 2),
        status="작성중",
        created_by=ordinary_user.id,
    )
    row = CalendarSchedule(
        google_event_id="event-update-lock",
        category="company",
        content="Previous visit",
        type="#722ed1",
        user_name="Alice",
        date=date(2026, 7, 28),
        end_date=date(2026, 7, 29),
        created_by=ordinary_user.id,
    )
    db_session.add_all([timesheet, row])
    db_session.flush()
    db_session.add(TimesheetEntry(
        timesheet_id=timesheet.id,
        project_name="Previous visit",
        schedule_event_id=row.google_event_id,
        schedule_category=row.category,
    ))
    db_session.commit()
    service = FakeGoogleService(existing_event={
        "id": row.google_event_id,
        "summary": "[Alice] Previous visit",
    })
    _use_fake_google(monkeypatch, service)
    ordering, listener = _track_schedule_lock_order(db_session, service, "update")
    try:
        result = schedule.update_schedule(
            row.google_event_id,
            _company_payload("Locked update"),
            current_user=ordinary_user,
            db=db_session,
        )
    finally:
        event.remove(db_session, "do_orm_execute", listener)

    assert result == {"status": "success", "id": "event-update-lock"}
    assert ordering[:3] == ["employee", "timesheet", "google"]


def test_ordinary_delete_locks_employee_then_timesheet_before_google(
    db_session, ordinary_user, monkeypatch,
):
    employee = db_session.query(Employee).filter(
        Employee.emp_code == ordinary_user.employee_code,
    ).one()
    timesheet = Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 7, 27),
        week_end=date(2026, 8, 2),
        status="작성중",
        created_by=ordinary_user.id,
    )
    row = CalendarSchedule(
        google_event_id="event-delete-lock",
        category="company",
        content="Previous visit",
        type="#722ed1",
        user_name="Alice",
        created_by=ordinary_user.id,
    )
    db_session.add_all([timesheet, row])
    db_session.flush()
    db_session.add(TimesheetEntry(
        timesheet_id=timesheet.id,
        project_name="Previous visit",
        schedule_event_id=row.google_event_id,
        schedule_category=row.category,
    ))
    db_session.commit()
    service = FakeGoogleService(existing_event={
        "id": row.google_event_id,
        "summary": "[Alice] Previous visit",
    })
    _use_fake_google(monkeypatch, service)
    ordering, listener = _track_schedule_lock_order(db_session, service, "delete")
    try:
        result = schedule.delete_schedule(
            row.google_event_id,
            category=row.category,
            current_user=ordinary_user,
            db=db_session,
        )
    finally:
        event.remove(db_session, "do_orm_execute", listener)

    assert result == {"status": "success"}
    assert ordering[:3] == ["employee", "timesheet", "google"]


@pytest.mark.parametrize("action", ["update", "delete"])
def test_ordinary_update_delete_uses_post_parent_revalidated_scope_before_mutation(
    db_session,
    ordinary_user,
    monkeypatch,
    action,
):
    employee = db_session.query(Employee).filter(
        Employee.emp_code == ordinary_user.employee_code,
    ).one()
    current_week = date(2026, 8, 3)
    timesheet = Timesheet(
        employee_id=employee.id,
        week_start=current_week,
        week_end=date(2026, 8, 9),
        status="작성중",
        created_by=ordinary_user.id,
    )
    row = CalendarSchedule(
        google_event_id=f"event-{action}-scope-requery",
        category="company",
        content="Current linked scope",
        type="#722ed1",
        user_name="Alice",
        date=current_week,
        end_date=current_week,
        created_by=ordinary_user.id,
    )
    db_session.add_all([timesheet, row])
    db_session.flush()
    db_session.add(TimesheetEntry(
        timesheet_id=timesheet.id,
        project_name="Current linked scope",
        schedule_event_id=row.google_event_id,
        schedule_category=row.category,
    ))
    db_session.commit()

    service = FakeGoogleService(existing_event={
        "id": row.google_event_id,
        "summary": "[Alice] Current linked scope",
    })
    _use_fake_google(monkeypatch, service)
    stale_week = date(2026, 8, 17)
    discoveries = iter([
        {employee.id: {stale_week}},
        {employee.id: {current_week}},
    ])
    discovery_calls = []
    locked_scopes = []
    original_child_lock = timesheet_locking.lock_timesheet_scopes

    def discover_scope(*_args, **_kwargs):
        value = next(discoveries)
        discovery_calls.append(value)
        return value

    def capture_child_lock(_db, *, weeks_by_employee):
        locked_scopes.append({
            employee_id: set(weeks)
            for employee_id, weeks in weeks_by_employee.items()
        })
        return original_child_lock(
            _db,
            weeks_by_employee=weeks_by_employee,
        )

    monkeypatch.setattr(
        timesheet_locking,
        "_discover_schedule_timesheet_scope",
        discover_scope,
    )
    monkeypatch.setattr(
        timesheet_locking,
        "lock_timesheet_scopes",
        capture_child_lock,
    )
    local_mutation_name = (
        "_sync_schedule_to_timesheet"
        if action == "update"
        else "_remove_schedule_from_timesheet"
    )
    original_local_mutation = getattr(schedule, local_mutation_name)

    def guarded_local_mutation(*args, **kwargs):
        assert len(discovery_calls) == 2
        assert locked_scopes
        assert current_week in locked_scopes[-1][employee.id]
        assert stale_week not in locked_scopes[-1][employee.id]
        return original_local_mutation(*args, **kwargs)

    monkeypatch.setattr(schedule, local_mutation_name, guarded_local_mutation)

    if action == "update":
        result = schedule.update_schedule(
            row.google_event_id,
            _company_payload("Revalidated update"),
            current_user=ordinary_user,
            db=db_session,
        )
        assert result == {"status": "success", "id": row.google_event_id}
        assert locked_scopes == [{
            employee.id: {current_week, date(2026, 7, 27)},
        }]
        assert len(service.events_resource.update_calls) == 1
    else:
        result = schedule.delete_schedule(
            row.google_event_id,
            category=row.category,
            current_user=ordinary_user,
            db=db_session,
        )
        assert result == {"status": "success"}
        assert locked_scopes == [{employee.id: {current_week}}]
        assert len(service.events_resource.delete_calls) == 1


def test_ordinary_update_uses_google_summary_display_name_for_ownership(
    db_session,
    monkeypatch,
):
    existing = {"id": "event-update-owner", "summary": "[Alice] Previous visit"}
    service = FakeGoogleService(existing_event=existing)
    _use_fake_google(monkeypatch, service)
    another_user = SimpleNamespace(
        id=2,
        username="bob",
        employee_code="E002",
        name="Bob",
        labor_type="원가",
    )

    with pytest.raises(HTTPException) as exc_info:
        schedule.update_schedule(
            "event-update-owner",
            _company_payload("Updated visit"),
            current_user=another_user,
            db=db_session,
        )

    assert exc_info.value.status_code == 403
    assert service.events_resource.update_calls == []


def test_ordinary_delete_uses_google_summary_display_name_for_ownership(
    db_session,
    ordinary_user,
    monkeypatch,
):
    existing = {"id": "event-delete-owner", "summary": "[Alice] Previous visit"}
    service = FakeGoogleService(existing_event=existing)
    _use_fake_google(monkeypatch, service)
    row = CalendarSchedule(
        google_event_id="event-delete-owner",
        category="company",
        content="Previous visit",
        type="#722ed1",
        user_name="Alice",
    )
    db_session.add(row)
    db_session.commit()

    outsider = SimpleNamespace(name="Bob")
    with pytest.raises(HTTPException) as exc_info:
        schedule.delete_schedule(
            "event-delete-owner",
            category="company",
            current_user=outsider,
            db=db_session,
        )
    assert exc_info.value.status_code == 403
    assert service.events_resource.delete_calls == []

    result = schedule.delete_schedule(
        "event-delete-owner",
        category="company",
        current_user=ordinary_user,
        db=db_session,
    )

    assert result == {"status": "success"}
    assert service.events_resource.delete_calls == [
        {
            "calendarId": "calendar-company",
            "eventId": "event-delete-owner",
        }
    ]
    assert db_session.query(CalendarSchedule).count() == 0


def test_create_compensates_google_insert_after_sqlite_failure(
    db_session,
    ordinary_user,
    monkeypatch,
):
    service = FakeGoogleService(insert_result={"id": "event-create-rollback"})
    _use_fake_google(monkeypatch, service)
    listener_target, listener = _fail_calendar_schedule_write(db_session)

    try:
        with pytest.raises(HTTPException) as exc_info:
            schedule.create_schedule(
                _company_payload("Compensated create"),
                current_user=ordinary_user,
                db=db_session,
            )
    finally:
        event.remove(listener_target, "before_cursor_execute", listener)

    assert exc_info.value.status_code == 500
    assert "forced SQLite calendar_schedules write failure" in exc_info.value.detail
    assert service.events_resource.delete_calls == [
        {
            "calendarId": "calendar-company",
            "eventId": "event-create-rollback",
        }
    ]
    assert db_session.query(CalendarSchedule).count() == 0


def test_update_restores_existing_google_body_after_db_commit_failure(
    db_session,
    ordinary_user,
    monkeypatch,
):
    existing = {
        "id": "event-update-rollback",
        "summary": "[Alice] Previous visit",
        "description": "previous description",
        "start": {"date": "2026-07-20", "timeZone": "Asia/Seoul"},
        "end": {"date": "2026-07-21", "timeZone": "Asia/Seoul"},
    }
    service = FakeGoogleService(existing_event=existing)
    _use_fake_google(monkeypatch, service)
    row = CalendarSchedule(
        google_event_id="event-update-rollback",
        category="company",
        content="Previous visit",
        type="#722ed1",
        user_name="Alice",
    )
    db_session.add(row)
    db_session.commit()
    listener_target, listener = _fail_commit_after_first_google_update(db_session, service)

    try:
        with pytest.raises(HTTPException) as exc_info:
            schedule.update_schedule(
                "event-update-rollback",
                _company_payload("Compensated update"),
                current_user=ordinary_user,
                db=db_session,
            )
    finally:
        event.remove(listener_target, "before_commit", listener)

    assert exc_info.value.status_code == 500
    assert "forced SQLite commit failure after Google update" in exc_info.value.detail
    assert service.events_resource.update_calls == [
        {
            "calendarId": "calendar-company",
            "eventId": "event-update-rollback",
            "body": _expected_company_event("Compensated update"),
        },
        {
            "calendarId": "calendar-company",
            "eventId": "event-update-rollback",
            "body": existing,
        },
    ]
    assert db_session.query(CalendarSchedule).one().content == "Previous visit"


def test_calendar_view_remains_byte_unchanged():
    calendar_view = REPO_ROOT / "frontend" / "src" / "views" / "CalendarView.vue"

    assert hashlib.sha256(calendar_view.read_bytes()).hexdigest() == CALENDAR_VIEW_SHA256
