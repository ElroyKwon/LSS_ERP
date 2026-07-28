from copy import deepcopy
from datetime import date
import re

from sqlalchemy import event
from sqlalchemy.dialects import postgresql

from app.models.common import ApiToken
from app.models.master import Employee
from app.models.timesheet import Timesheet
from app.routers import schedule
from app.utils.auth import hash_api_token
from app.utils.mcp_schedule_auth import SCHEDULE_READ_SCOPE, SCHEDULE_WRITE_SCOPE


class _Request:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return deepcopy(self.payload)


class _Events:
    def __init__(self):
        self.insert_calls = []
        self.get_calls = []

    def insert(self, **kwargs):
        self.insert_calls.append(deepcopy(kwargs))
        return _Request({"id": kwargs["body"].get("id", "legacy-generated-id")})

    def get(self, **kwargs):
        self.get_calls.append(deepcopy(kwargs))
        return _Request({})

    def delete(self, **_kwargs):
        return _Request({})


class _Service:
    def __init__(self):
        self.resource = _Events()

    def events(self):
        return self.resource


def _token_headers(db_session, user, scopes, *, key="create-key-0001", correlation="corr-create-0001"):
    raw_token = f"mcp-create-{user.id}-{db_session.query(ApiToken).count()}"
    db_session.add(ApiToken(
        name="MCP schedule create test",
        token_hash=hash_api_token(raw_token),
        token_prefix="mcp-create",
        user_id=user.id,
        scopes=scopes,
    ))
    db_session.commit()
    return {
        "Authorization": f"Bearer {raw_token}",
        "X-LSS-MCP-Schedule": "1",
        "Idempotency-Key": key,
        "X-Correlation-ID": correlation,
    }


def _payload(**overrides):
    value = {
        "content": "Customer visit",
        "date": "2026-08-03",
        "end_date": "2026-08-03",
        "type": "#722ed1",
        "category": "company",
        "user_name": "Mallory Payload Owner",
        "is_all_day": True,
    }
    value.update(overrides)
    return value


def _use_fake_google(monkeypatch, service):
    monkeypatch.setattr(
        schedule,
        "get_calendar_config_and_service",
        lambda _category: (service, "calendar-company"),
    )


def test_ordinary_build_google_event_preserves_the_existing_mapping():
    payload = schedule.ScheduleCreate(**_payload())
    before = deepcopy(payload.model_dump())

    event = schedule.build_google_event(payload, "Alice")

    assert payload.model_dump() == before
    assert event == {
        "summary": "[Alice] Customer visit",
        "description": schedule._schedule_description(payload, "Alice"),
        "start": {"date": "2026-08-03", "timeZone": "Asia/Seoul"},
        "end": {"date": "2026-08-04", "timeZone": "Asia/Seoul"},
    }


def test_mcp_create_requires_schedule_write_before_google_insert(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    _use_fake_google(monkeypatch, service)

    response = schedule_client.post(
        "/api/schedules",
        headers=_token_headers(db_session, ordinary_user, [SCHEDULE_READ_SCOPE]),
        json=_payload(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "missing_scope"
    assert service.resource.insert_calls == []


def test_mcp_create_injects_deterministic_google_id_and_immutable_owner_properties(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    _use_fake_google(monkeypatch, service)
    headers = _token_headers(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE])

    first = schedule_client.post("/api/schedules", headers=headers, json=_payload())
    second = schedule_client.post("/api/schedules", headers=headers, json=_payload())

    assert first.status_code == second.status_code == 200
    event_id = first.json()["id"]
    assert event_id == second.json()["id"]
    assert 8 <= len(event_id) <= 1024
    assert re.fullmatch(r"[0-9a-v]+", event_id)
    assert len(service.resource.insert_calls) == 1
    body = service.resource.insert_calls[0]["body"]
    assert body["id"] == event_id
    assert body["summary"] == "[Alice] Customer visit"
    private = body["extendedProperties"]["private"]
    employee = db_session.query(Employee).filter(Employee.emp_code == "E001").one()
    assert private == {
        "lss_owner_user_id": str(ordinary_user.id),
        "lss_owner_employee_id": str(employee.id),
        "lss_event_version": "1",
        "lss_correlation_id": "corr-create-0001",
        "lss_request_hash": private["lss_request_hash"],
    }
    assert re.fullmatch(r"[0-9a-f]{64}", private["lss_request_hash"])


def test_mcp_create_locks_employee_then_missing_timesheet_week_before_google_insert(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    ordering = []
    service = _Service()
    _use_fake_google(monkeypatch, service)
    original_insert = service.resource.insert

    def track_orm_execute(orm_execute_state):
        statement = orm_execute_state.statement
        if orm_execute_state.is_select and getattr(statement, "_for_update_arg", None) is not None:
            sql = " ".join(
                str(statement.compile(dialect=postgresql.dialect())).lower().split()
            )
            if " from employees " in f" {sql} ":
                ordering.append("employee")
            elif " from timesheets " in f" {sql} ":
                ordering.append("timesheet")

    def tracked_insert(**kwargs):
        ordering.append("google")
        return original_insert(**kwargs)

    event.listen(db_session, "do_orm_execute", track_orm_execute)
    monkeypatch.setattr(service.resource, "insert", tracked_insert)
    try:
        response = schedule_client.post(
            "/api/schedules",
            headers=_token_headers(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE]),
            json=_payload(),
        )
    finally:
        event.remove(db_session, "do_orm_execute", track_orm_execute)

    assert response.status_code == 200
    assert ordering == ["employee", "timesheet", "google"]


def test_mcp_create_blocks_a_locked_destination_week_before_google_insert(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    employee = db_session.query(Employee).filter(Employee.emp_code == "E001").one()
    db_session.add(Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 8, 3),
        week_end=date(2026, 8, 9),
        status="제출",
    ))
    db_session.commit()
    service = _Service()
    _use_fake_google(monkeypatch, service)

    response = schedule_client.post(
        "/api/schedules",
        headers=_token_headers(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE]),
        json=_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "timesheet_locked"
    assert service.resource.insert_calls == []


def test_mcp_create_blocks_an_approved_destination_week_before_google_insert(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    employee = db_session.query(Employee).filter(Employee.emp_code == "E001").one()
    db_session.add(Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 8, 3),
        week_end=date(2026, 8, 9),
        status="승인",
    ))
    db_session.commit()
    service = _Service()
    _use_fake_google(monkeypatch, service)

    response = schedule_client.post(
        "/api/schedules",
        headers=_token_headers(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE]),
        json=_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "timesheet_locked"
    assert service.resource.insert_calls == []
