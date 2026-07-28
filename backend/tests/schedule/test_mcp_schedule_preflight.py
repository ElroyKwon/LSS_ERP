from datetime import date, datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from googleapiclient.errors import HttpError

from app.database import get_db
from app.models.common import ApiToken, CalendarSchedule
from app.models.master import Employee
from app.models.timesheet import Timesheet
from app.utils.auth import hash_api_token
from app.utils.mcp_schedule_auth import SCHEDULE_READ_SCOPE, SCHEDULE_WRITE_SCOPE

# Task 4 RED: this import must fail until the separate read-only control service exists.
from app.routers import mcp_schedule


def _make_token(db_session, user, scopes):
    raw_token = f"mcp-preflight-{user.id}-{db_session.query(ApiToken).count()}"
    db_session.add(ApiToken(
        name="MCP preflight test",
        token_hash=hash_api_token(raw_token),
        token_prefix="mcp-preflight",
        user_id=user.id,
        scopes=scopes,
    ))
    db_session.commit()
    return {"Authorization": f"Bearer {raw_token}"}


def _client(db_session):
    app = FastAPI()
    app.include_router(mcp_schedule.router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


class _Request:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class _Events:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        return _Request(self.payload)

    def insert(self, **kwargs):
        self.calls.append(("insert", kwargs))
        raise AssertionError("preflight must not insert Google events")

    def update(self, **kwargs):
        self.calls.append(("update", kwargs))
        raise AssertionError("preflight must not update Google events")

    def delete(self, **kwargs):
        self.calls.append(("delete", kwargs))
        raise AssertionError("preflight must not delete Google events")


class _Service:
    def __init__(self, payload):
        self.resource = _Events(payload)

    def events(self):
        return self.resource


def _google_event(
    event_id,
    owner_id,
    *,
    start_date="2026-07-27",
    end_date="2026-07-27",
    start_time=None,
    end_time=None,
):
    event = {
        "id": event_id,
        "etag": '"preflight-etag"',
        "summary": "[Alice] summary cannot establish immutable ownership",
        "description": "sensitive event description",
        "extendedProperties": {"private": {"lss_owner_user_id": str(owner_id)}},
    }
    if start_time is not None and end_time is not None:
        event["start"] = {"dateTime": start_time, "timeZone": "Asia/Seoul"}
        event["end"] = {"dateTime": end_time, "timeZone": "Asia/Seoul"}
    else:
        event["start"] = {"date": start_date, "timeZone": "Asia/Seoul"}
        event["end"] = {
            "date": (date.fromisoformat(end_date) + timedelta(days=1)).isoformat(),
            "timeZone": "Asia/Seoul",
        }
    return event


def test_preflight_is_read_only_and_reports_normalized_impact(db_session, ordinary_user, monkeypatch):
    event_id = "a23456789bcdefg"
    db_session.add(CalendarSchedule(
        google_event_id=event_id,
        category="company",
        content="old private content",
        type="#722ed1",
        user_name="Alice",
        date=date(2026, 7, 27),
        end_date=date(2026, 7, 27),
        created_by=ordinary_user.id,
    ))
    db_session.commit()
    service = _Service(_google_event(event_id, ordinary_user.id))
    monkeypatch.setattr(
        mcp_schedule,
        "get_calendar_config_and_service",
        lambda category: (service, f"calendar-{category}"),
    )
    headers = _make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE])
    observed_sql = []

    def record_write(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            observed_sql.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", record_write)
    try:
        with _client(db_session) as client:
                response = client.post(
                    "/api/mcp/schedules/preflight",
                    headers=headers,
                json={
                    "action": "UPDATE",
                    "category": "company",
                    "event_id": event_id,
                    "desired": {"is_all_day": True, "date": "2026-08-03", "end_date": "2026-08-04", "content": "new private content"},
                },
            )
    finally:
        event.remove(engine, "before_cursor_execute", record_write)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["action"] == "UPDATE"
    assert data["current"]["start_date"] == "2026-07-27"
    assert data["desired"] == {"is_all_day": True, "start_date": "2026-08-03", "end_date": "2026-08-04"}
    assert data["affected_weeks"] == ["2026-07-27", "2026-08-03"]
    assert data["etag"] == '"preflight-etag"'
    assert data["write_allowed"] is True
    assert data["denial_reasons"] == []
    assert observed_sql == []
    assert [name for name, _kwargs in service.resource.calls] == ["get"]
    assert db_session.query(CalendarSchedule).count() == 1


def test_preflight_rejects_google_and_local_schedule_time_drift_without_confirmation(
    db_session, ordinary_user, monkeypatch,
):
    event_id = "a23456789bcdefg"
    db_session.add(CalendarSchedule(
        google_event_id=event_id,
        category="company",
        content="hidden local content",
        type="#722ed1",
        user_name="Alice",
        date=date(2026, 7, 27),
        end_date=date(2026, 7, 27),
        created_by=ordinary_user.id,
    ))
    db_session.commit()
    service = _Service(_google_event(
        event_id,
        ordinary_user.id,
        start_date="2026-07-28",
        end_date="2026-07-28",
    ))
    monkeypatch.setattr(
        mcp_schedule,
        "get_calendar_config_and_service",
        lambda category: (service, f"calendar-{category}"),
    )

    with _client(db_session) as client:
        response = client.post(
            "/api/mcp/schedules/preflight",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE]),
            json={
                "action": "UPDATE",
                "category": "company",
                "event_id": event_id,
                "desired": {
                    "is_all_day": True,
                    "date": "2026-08-03",
                    "end_date": "2026-08-03",
                },
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "schedule_state_drift"
    assert "confirmation_token" not in str(response.json())
    assert "hidden local content" not in str(response.json())
    assert [name for name, _kwargs in service.resource.calls] == ["get"]


def test_preflight_denies_legacy_owner_and_locked_timesheets_without_mutation(
    db_session, ordinary_user, monkeypatch,
):
    event_id = "a23456789bcdefg"
    employee = db_session.query(Employee).filter(Employee.emp_code == ordinary_user.employee_code).one()
    db_session.add(CalendarSchedule(
        google_event_id=event_id,
        category="company",
        content="hidden",
        type="#722ed1",
        user_name="Alice",
        date=date(2026, 7, 27),
        end_date=date(2026, 7, 27),
        created_by=ordinary_user.id,
    ))
    db_session.add(Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 8, 3),
        week_end=date(2026, 8, 9),
        status="제출",
    ))
    db_session.commit()
    legacy_event = _google_event(event_id, ordinary_user.id)
    legacy_event["extendedProperties"] = {"private": {}}
    service = _Service(legacy_event)
    monkeypatch.setattr(
        mcp_schedule,
        "get_calendar_config_and_service",
        lambda category: (service, f"calendar-{category}"),
    )

    with _client(db_session) as client:
        response = client.post(
            "/api/mcp/schedules/preflight",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE]),
            json={
                "action": "UPDATE",
                "category": "company",
                "event_id": event_id,
                "desired": {"is_all_day": True, "date": "2026-08-03", "end_date": "2026-08-03"},
            },
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["write_allowed"] is False
    assert data["denial_reasons"] == ["legacy_owner_unbound", "timesheet_locked"]
    assert data["timesheet_statuses"] == [{"week_start": "2026-08-03", "status": "제출"}]
    assert [name for name, _kwargs in service.resource.calls] == ["get"]


def test_preflight_requires_write_scope_not_read_scope(db_session, ordinary_user):
    with _client(db_session) as client:
        response = client.post(
            "/api/mcp/schedules/preflight",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_READ_SCOPE]),
            json={
                "action": "CREATE",
                "category": "company",
                "desired": {"is_all_day": True, "date": "2026-08-03", "end_date": "2026-08-03"},
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "missing_scope"


def test_preflight_denies_a_locked_intermediate_week_in_current_and_desired_ranges(
    db_session, ordinary_user, monkeypatch,
):
    event_id = "a23456789bcdefg"
    employee = db_session.query(Employee).filter(Employee.emp_code == ordinary_user.employee_code).one()
    db_session.add(CalendarSchedule(
        google_event_id=event_id,
        category="company",
        content="hidden",
        type="#722ed1",
        user_name="Alice",
        date=date(2026, 7, 20),
        end_date=date(2026, 8, 17),
        created_by=ordinary_user.id,
    ))
    # This locked week is neither endpoint of the current nor desired interval.
    db_session.add(Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 8, 10),
        week_end=date(2026, 8, 16),
        status="제출",
    ))
    db_session.commit()
    service = _Service(_google_event(
        event_id,
        ordinary_user.id,
        start_date="2026-07-20",
        end_date="2026-08-17",
    ))
    monkeypatch.setattr(
        mcp_schedule,
        "get_calendar_config_and_service",
        lambda category: (service, f"calendar-{category}"),
    )

    with _client(db_session) as client:
        response = client.post(
            "/api/mcp/schedules/preflight",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE]),
            json={
                "action": "UPDATE",
                "category": "company",
                "event_id": event_id,
                "desired": {"is_all_day": True, "date": "2026-08-24", "end_date": "2026-09-07"},
            },
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["affected_weeks"] == [
        "2026-07-20", "2026-07-27", "2026-08-03", "2026-08-10",
        "2026-08-17", "2026-08-24", "2026-08-31", "2026-09-07",
    ]
    assert data["timesheet_statuses"] == [{"week_start": "2026-08-10", "status": "제출"}]
    assert data["write_allowed"] is False
    assert data["denial_reasons"] == ["timesheet_locked"]


def test_preflight_validates_and_normalizes_exact_all_day_and_timed_proposals(db_session, ordinary_user):
    headers = _make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE])
    valid_timed = {
        "action": "CREATE",
        "category": "company",
        "desired": {
            "is_all_day": False,
            "start_time": "2026-08-03T09:00:00",
            "end_time": "2026-08-03T17:00:00",
            "content": "this free text must not be reflected",
        },
    }
    invalid_cases = [
        (
            "missing timed end",
            {"action": "CREATE", "category": "company", "desired": {"is_all_day": False, "start_time": "2026-08-03T09:00:00"}},
        ),
        (
            "mixed all-day and timed fields",
            {"action": "CREATE", "category": "company", "desired": {"is_all_day": False, "date": "2026-08-03", "start_time": "2026-08-03T09:00:00", "end_time": "2026-08-03T17:00:00"}},
        ),
        (
            "reversed timed range",
            {"action": "CREATE", "category": "company", "desired": {"is_all_day": False, "start_time": "2026-08-03T17:00:00", "end_time": "2026-08-03T09:00:00"}},
        ),
        (
            "reversed all-day range",
            {"action": "CREATE", "category": "company", "desired": {"is_all_day": True, "date": "2026-08-04", "end_date": "2026-08-03"}},
        ),
        (
            "over the 31-day maximum",
            {"action": "CREATE", "category": "company", "desired": {"is_all_day": True, "date": "2026-08-01", "end_date": "2026-09-02"}},
        ),
    ]
    maximum_all_day = {
        "action": "CREATE",
        "category": "company",
        "desired": {"is_all_day": True, "date": "2026-08-01", "end_date": "2026-09-01"},
    }

    with _client(db_session) as client:
        timed_response = client.post("/api/mcp/schedules/preflight", headers=headers, json=valid_timed)
        maximum_response = client.post("/api/mcp/schedules/preflight", headers=headers, json=maximum_all_day)
        invalid_responses = [
            (name, client.post("/api/mcp/schedules/preflight", headers=headers, json=payload))
            for name, payload in invalid_cases
        ]

    assert timed_response.status_code == 200
    assert timed_response.json()["data"]["desired"] == {
        "is_all_day": False,
        "start_time": "2026-08-03T09:00:00+09:00",
        "end_time": "2026-08-03T17:00:00+09:00",
    }
    assert maximum_response.status_code == 200
    assert maximum_response.json()["data"]["desired"] == {
        "is_all_day": True,
        "start_date": "2026-08-01",
        "end_date": "2026-09-01",
    }
    assert all(response.status_code == 422 for _name, response in invalid_responses)


def test_preflight_rejects_mixed_datetime_awareness_and_accepts_matched_awareness(
    db_session, ordinary_user,
):
    headers = _make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE])
    naive = {
        "action": "CREATE",
        "category": "company",
        "desired": {"is_all_day": False, "start_time": "2026-08-03T09:00:00", "end_time": "2026-08-03T17:00:00"},
    }
    aware_cross_offset = {
        "action": "CREATE",
        "category": "company",
        "desired": {
            "is_all_day": False,
            "start_time": "2026-08-03T09:00:00+09:00",
            "end_time": "2026-08-03T00:30:00+00:00",
        },
    }
    mixed_naive_to_aware = {
        "action": "CREATE",
        "category": "company",
        "desired": {"is_all_day": False, "start_time": "2026-08-03T09:00:00", "end_time": "2026-08-03T17:00:00+09:00"},
    }
    mixed_aware_to_naive = {
        "action": "CREATE",
        "category": "company",
        "desired": {"is_all_day": False, "start_time": "2026-08-03T09:00:00+09:00", "end_time": "2026-08-03T17:00:00"},
    }
    equal_aware = {
        "action": "CREATE",
        "category": "company",
        "desired": {"is_all_day": False, "start_time": "2026-08-03T09:00:00+09:00", "end_time": "2026-08-03T00:00:00+00:00"},
    }

    with _client(db_session) as client:
        naive_response = client.post("/api/mcp/schedules/preflight", headers=headers, json=naive)
        aware_response = client.post("/api/mcp/schedules/preflight", headers=headers, json=aware_cross_offset)
        mixed_responses = [
            client.post("/api/mcp/schedules/preflight", headers=headers, json=payload)
            for payload in (mixed_naive_to_aware, mixed_aware_to_naive, equal_aware)
        ]

    assert naive_response.status_code == 200
    assert aware_response.status_code == 200
    assert aware_response.json()["data"]["desired"] == {
        "is_all_day": False,
        "start_time": "2026-08-03T09:00:00+09:00",
        "end_time": "2026-08-03T09:30:00+09:00",
    }
    assert all(response.status_code == 422 for response in mixed_responses)


def test_preflight_uses_kst_for_aware_timed_impacts_and_locks_the_kst_week(
    db_session, ordinary_user, monkeypatch,
):
    event_id = "a23456789bcdefg"
    employee = db_session.query(Employee).filter(Employee.emp_code == ordinary_user.employee_code).one()
    db_session.add(CalendarSchedule(
        google_event_id=event_id,
        category="company",
        content="hidden",
        type="#722ed1",
        user_name="Alice",
        is_all_day=False,
        date=date(2026, 8, 2),
        end_date=date(2026, 8, 2),
        start_time=datetime(2026, 8, 2, 15, 30),
        end_time=datetime(2026, 8, 2, 16, 30),
        created_by=ordinary_user.id,
    ))
    db_session.add(Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 8, 3),
        week_end=date(2026, 8, 9),
        status="제출",
    ))
    db_session.commit()
    service = _Service(_google_event(
        event_id,
        ordinary_user.id,
        start_time="2026-08-02T15:30:00+09:00",
        end_time="2026-08-02T16:30:00+09:00",
    ))
    monkeypatch.setattr(
        mcp_schedule,
        "get_calendar_config_and_service",
        lambda category: (service, f"calendar-{category}"),
    )

    with _client(db_session) as client:
        response = client.post(
            "/api/mcp/schedules/preflight",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE]),
            json={
                "action": "UPDATE",
                "category": "company",
                "event_id": event_id,
                "desired": {
                    "is_all_day": False,
                    "start_time": "2026-08-02T15:30:00+00:00",
                    "end_time": "2026-08-02T16:30:00+00:00",
                },
            },
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["desired"] == {
        "is_all_day": False,
        "start_time": "2026-08-03T00:30:00+09:00",
        "end_time": "2026-08-03T01:30:00+09:00",
    }
    assert data["affected_weeks"] == ["2026-07-27", "2026-08-03"]
    assert data["timesheet_statuses"] == [{"week_start": "2026-08-03", "status": "제출"}]
    assert data["write_allowed"] is False
    assert data["denial_reasons"] == ["timesheet_locked"]


def test_foreign_event_preflight_is_non_disclosing_and_does_not_call_google(
    db_session, ordinary_user, monkeypatch,
):
    foreign_user = type(ordinary_user)(
        username="foreign-preflight-owner",
        employee_code="E099",
        password_hash="not-used",
        name="Foreign",
    )
    db_session.add(foreign_user)
    db_session.flush()
    event_id = "a23456789bcdefg"
    db_session.add(CalendarSchedule(
        google_event_id=event_id,
        category="company",
        content="foreign private content",
        type="#722ed1",
        user_name="Foreign",
        date=date(2026, 8, 3),
        end_date=date(2026, 8, 3),
        created_by=foreign_user.id,
    ))
    db_session.commit()
    service = _Service(_google_event(
        event_id,
        foreign_user.id,
        start_date="2026-08-03",
        end_date="2026-08-03",
    ))
    monkeypatch.setattr(
        mcp_schedule,
        "get_calendar_config_and_service",
        lambda category: (service, f"calendar-{category}"),
    )

    with _client(db_session) as client:
        response = client.post(
            "/api/mcp/schedules/preflight",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE]),
            json={
                "action": "UPDATE",
                "category": "company",
                "event_id": event_id,
                "desired": {"is_all_day": True, "date": "2026-08-03", "end_date": "2026-08-03"},
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "schedule_not_found"
    assert service.resource.calls == []
    assert "foreign" not in response.text.lower()


def test_preflight_denies_when_authenticated_user_has_no_employee_mapping(db_session):
    # The service dependency needs persistent API-token users; use real rows through the client.
    from app.models.common import User

    db_session.add_all([
        User(username="no-employee-code", password_hash="not-used", name="No code"),
        User(username="missing-employee", employee_code="NO-EMPLOYEE", password_hash="not-used", name="Missing employee"),
    ])
    db_session.commit()
    users = db_session.query(User).filter(User.username.in_(["no-employee-code", "missing-employee"])).order_by(User.id).all()

    with _client(db_session) as client:
        responses = [
            client.post(
                "/api/mcp/schedules/preflight",
                headers=_make_token(db_session, user, [SCHEDULE_WRITE_SCOPE]),
                json={
                    "action": "CREATE",
                    "category": "company",
                    "desired": {"is_all_day": True, "date": "2026-08-03", "end_date": "2026-08-03"},
                },
            )
            for user in users
        ]

    assert all(response.status_code == 200 for response in responses)
    assert all(response.json()["data"]["write_allowed"] is False for response in responses)
    assert all(response.json()["data"]["denial_reasons"] == ["employee_not_found"] for response in responses)


def test_preflight_normalizes_google_failures_without_secret_leakage(
    db_session, ordinary_user, monkeypatch,
):
    event_id = "a23456789bcdefg"
    db_session.add(CalendarSchedule(
        google_event_id=event_id,
        category="company",
        content="hidden",
        type="#722ed1",
        user_name="Alice",
        date=date(2026, 8, 3),
        end_date=date(2026, 8, 3),
        created_by=ordinary_user.id,
    ))
    db_session.commit()
    secret = "Bearer super-secret-calendar-credential"
    cases = [
        (RuntimeError(secret), 502, "upstream_unavailable"),
        (HttpError(SimpleNamespace(status=404, reason=secret), secret.encode()), 404, "schedule_not_found"),
    ]
    headers = _make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE])

    with _client(db_session) as client:
        for upstream_error, expected_status, expected_code in cases:
            service = _Service(upstream_error)
            monkeypatch.setattr(
                mcp_schedule,
                "get_calendar_config_and_service",
                lambda category, current_service=service: (current_service, f"calendar-{category}"),
            )
            response = client.post(
                "/api/mcp/schedules/preflight",
                headers=headers,
                json={
                    "action": "UPDATE",
                    "category": "company",
                    "event_id": event_id,
                    "desired": {"is_all_day": True, "date": "2026-08-03", "end_date": "2026-08-03"},
                },
            )
            assert response.status_code == expected_status
            assert response.json()["detail"] == expected_code
            assert secret not in response.text


def test_preflight_normalizes_calendar_factory_failure_without_secret_leakage(
    db_session, ordinary_user, monkeypatch,
):
    event_id = "a23456789bcdefg"
    db_session.add(CalendarSchedule(
        google_event_id=event_id,
        category="company",
        content="hidden",
        type="#722ed1",
        user_name="Alice",
        date=date(2026, 8, 3),
        end_date=date(2026, 8, 3),
        created_by=ordinary_user.id,
    ))
    db_session.commit()
    secret = r"factory-secret C:\private\service-account.json"

    def failing_factory(_category):
        raise RuntimeError(secret)

    monkeypatch.setattr(mcp_schedule, "get_calendar_config_and_service", failing_factory)
    with _client(db_session) as client:
        response = client.post(
            "/api/mcp/schedules/preflight",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE]),
            json={
                "action": "UPDATE",
                "category": "company",
                "event_id": event_id,
                "desired": {"is_all_day": True, "date": "2026-08-03", "end_date": "2026-08-03"},
            },
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "upstream_unavailable"
    assert secret not in response.text
