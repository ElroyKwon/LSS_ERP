from datetime import date, datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError

from app.database import get_db
from app.models.common import ApiToken, CalendarSchedule, User
from app.models.mcp_schedule import McpScheduleOperation
from app.utils.auth import hash_api_token
from app.utils.mcp_schedule_auth import SCHEDULE_READ_SCOPE, SCHEDULE_WRITE_SCOPE

# Task 4 RED: this import must fail until the additive MCP schedule router exists.
from app.routers import mcp_schedule


def _make_token(db_session, user, scopes):
    raw_token = f"mcp-contract-{user.id}-{db_session.query(ApiToken).count()}"
    db_session.add(ApiToken(
        name="MCP schedule contract test",
        token_hash=hash_api_token(raw_token),
        token_prefix="mcp-contract",
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

    def insert(self, **kwargs):  # pragma: no cover - assertion guard
        self.calls.append(("insert", kwargs))
        raise AssertionError("MCP read routes must not insert Google events")

    def update(self, **kwargs):  # pragma: no cover - assertion guard
        self.calls.append(("update", kwargs))
        raise AssertionError("MCP read routes must not update Google events")

    def delete(self, **kwargs):  # pragma: no cover - assertion guard
        self.calls.append(("delete", kwargs))
        raise AssertionError("MCP read routes must not delete Google events")


class _Service:
    def __init__(self, payload):
        self.resource = _Events(payload)

    def events(self):
        return self.resource


def _google_event(
    event_id,
    owner_id,
    *,
    etag='"etag-safe"',
    start_date="2026-07-28",
    end_date="2026-07-28",
):
    return {
        "id": event_id,
        "etag": etag,
        "summary": "[Alice] description must not be exposed",
        "description": "sensitive description must not be exposed",
        "start": {"date": start_date, "timeZone": "Asia/Seoul"},
        "end": {
            "date": (date.fromisoformat(end_date) + timedelta(days=1)).isoformat(),
            "timeZone": "Asia/Seoul",
        },
        "extendedProperties": {
            "private": {
                "lss_owner_user_id": str(owner_id),
                "lss_owner_employee_id": "E001",
            },
        },
    }


def test_list_uses_object_envelope_and_redacts_free_text(db_session, ordinary_user):
    db_session.add(CalendarSchedule(
        google_event_id="a23456789bcdefg",
        category="company",
        content="private customer meeting content",
        type="#722ed1",
        user_name="Alice",
        date=date(2026, 7, 28),
        end_date=date(2026, 7, 29),
        created_by=ordinary_user.id,
    ))
    db_session.commit()

    with _client(db_session) as client:
        response = client.get(
            "/api/mcp/schedules?category=company&start_date=2026-07-01&end_date=2026-07-31&limit=10",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_READ_SCOPE]),
        )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"success", "data", "error", "meta"}
    assert payload["success"] is True and payload["error"] is None
    assert set(payload["meta"]) == {"correlation_id", "timestamp"}
    assert datetime.fromisoformat(payload["meta"]["timestamp"].replace("Z", "+00:00"))
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"] == [{
        "event_id": "a23456789bcdefg",
        "category": "company",
        "start_date": "2026-07-28",
        "end_date": "2026-07-29",
        "is_all_day": True,
        "schedule_kind": None,
    }]
    assert "content" not in str(payload)


def test_list_validates_category_date_range_and_bounded_limit(db_session, ordinary_user):
    headers = _make_token(db_session, ordinary_user, [SCHEDULE_READ_SCOPE])
    with _client(db_session) as client:
        bad_category = client.get("/api/mcp/schedules?category=other", headers=headers)
        bad_range = client.get(
            "/api/mcp/schedules?start_date=2026-08-01&end_date=2026-07-01", headers=headers,
        )
        bad_limit = client.get("/api/mcp/schedules?limit=101", headers=headers)

    assert bad_category.status_code == 422
    assert bad_range.status_code == 422
    assert bad_limit.status_code == 422


def test_list_redacts_but_safely_returns_a_timed_schedule_shape(db_session, ordinary_user):
    db_session.add(CalendarSchedule(
        google_event_id="a23456789bcdefg",
        category="company",
        content="private timed meeting",
        type="#722ed1",
        user_name="Alice",
        is_all_day=False,
        date=date(2026, 8, 3),
        end_date=date(2026, 8, 3),
        start_time=datetime(2026, 8, 3, 9, 0),
        end_time=datetime(2026, 8, 3, 17, 0),
        created_by=ordinary_user.id,
    ))
    db_session.commit()

    with _client(db_session) as client:
        response = client.get(
            "/api/mcp/schedules?category=company",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_READ_SCOPE]),
        )

    assert response.status_code == 200
    assert response.json()["data"]["items"] == [{
        "event_id": "a23456789bcdefg",
        "category": "company",
        "is_all_day": False,
        "schedule_kind": None,
        "start_time": "2026-08-03T09:00:00+09:00",
        "end_time": "2026-08-03T17:00:00+09:00",
    }]


def test_read_scope_returns_redacted_enterprise_schedule_but_never_cross_owner_write_eligibility(
    db_session, ordinary_user, monkeypatch,
):
    other_user = User(
        username="enterprise-schedule-owner",
        employee_code="E002",
        password_hash="not-used",
        name="Bob",
    )
    db_session.add(other_user)
    db_session.flush()
    event_id = "b23456789bcdefg"
    db_session.add(CalendarSchedule(
        google_event_id=event_id,
        category="company",
        content="other employee private content",
        type="#722ed1",
        user_name="Bob",
        date=date(2026, 7, 28),
        end_date=date(2026, 7, 28),
        created_by=other_user.id,
    ))
    db_session.commit()
    service = _Service(_google_event(event_id, other_user.id))
    monkeypatch.setattr(
        mcp_schedule,
        "get_calendar_config_and_service",
        lambda category: (service, f"calendar-{category}"),
    )
    headers = _make_token(db_session, ordinary_user, [SCHEDULE_READ_SCOPE])

    with _client(db_session) as client:
        listed = client.get("/api/mcp/schedules?category=company", headers=headers)
        detail = client.get(
            f"/api/mcp/schedules/{event_id}?category=company",
            headers=headers,
        )

    assert listed.status_code == 200
    assert listed.json()["data"]["items"] == [{
        "event_id": event_id,
        "category": "company",
        "start_date": "2026-07-28",
        "end_date": "2026-07-28",
        "is_all_day": True,
        "schedule_kind": None,
    }]
    assert "private content" not in str(listed.json())
    assert detail.status_code == 200
    assert detail.json()["data"]["owner_binding"] == {
        "state": "OWNER_MISMATCH",
        "write_allowed": False,
    }
    assert detail.json()["data"]["eligibility"] == {
        "write_allowed": False,
        "denial_reasons": ["owner_mismatch"],
    }
    assert "private content" not in str(detail.json())


def test_read_routes_require_exact_read_scope_and_validate_event_id(db_session, ordinary_user):
    write_headers = _make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE])
    read_headers = _make_token(db_session, ordinary_user, [SCHEDULE_READ_SCOPE])
    with _client(db_session) as client:
        denied = client.get("/api/mcp/schedules", headers=write_headers)
        invalid_event_id = client.get("/api/mcp/schedules/not/valid", headers=read_headers)

    assert denied.status_code == 403
    assert denied.json()["detail"] == "missing_scope"
    assert invalid_event_id.status_code == 404


def test_detail_reports_immutable_owner_binding_etag_and_eligibility(
    db_session, ordinary_user, monkeypatch,
):
    event_id = "a23456789bcdefg"
    db_session.add(CalendarSchedule(
        google_event_id=event_id,
        category="company",
        content="hidden",
        type="#722ed1",
        user_name="Alice",
        date=date(2026, 7, 28),
        created_by=ordinary_user.id,
    ))
    db_session.commit()
    service = _Service(_google_event(event_id, ordinary_user.id))
    monkeypatch.setattr(
        mcp_schedule,
        "get_calendar_config_and_service",
        lambda category: (service, f"calendar-{category}"),
    )

    with _client(db_session) as client:
        response = client.get(
            f"/api/mcp/schedules/{event_id}?category=company",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_READ_SCOPE]),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["event_id"] == event_id
    assert data["etag"] == '"etag-safe"'
    assert data["owner_binding"] == {"state": "BOUND", "write_allowed": True}
    assert data["eligibility"] == {"write_allowed": True, "denial_reasons": []}
    assert "description" not in str(data)
    assert [name for name, _kwargs in service.resource.calls] == ["get"]


def test_detail_rejects_google_and_local_schedule_time_drift(
    db_session, ordinary_user, monkeypatch,
):
    event_id = "a23456789bcdefg"
    db_session.add(CalendarSchedule(
        google_event_id=event_id,
        category="company",
        content="hidden local content",
        type="#722ed1",
        user_name="Alice",
        date=date(2026, 7, 28),
        end_date=date(2026, 7, 28),
        created_by=ordinary_user.id,
    ))
    db_session.commit()
    service = _Service(_google_event(
        event_id,
        ordinary_user.id,
        start_date="2026-07-30",
        end_date="2026-07-30",
    ))
    monkeypatch.setattr(
        mcp_schedule,
        "get_calendar_config_and_service",
        lambda category: (service, f"calendar-{category}"),
    )

    with _client(db_session) as client:
        response = client.get(
            f"/api/mcp/schedules/{event_id}?category=company",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_READ_SCOPE]),
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "schedule_state_drift"
    assert "hidden local content" not in str(response.json())
    assert [name for name, _kwargs in service.resource.calls] == ["get"]


def test_status_is_visible_only_to_its_authenticated_owner(db_session, ordinary_user):
    other_user = User(
        username="status-owner-two",
        employee_code="E002",
        password_hash="not-used",
        name="Bob",
    )
    db_session.add(other_user)
    db_session.flush()
    operation = McpScheduleOperation(
        user_id=ordinary_user.id,
        category="company",
        action="CREATE",
        event_id="a23456789bcdefg",
        idempotency_key="status-key",
        correlation_id="correlation-status-001",
        request_hash="a" * 64,
        status="SUCCEEDED",
        result_json={"status": "SUCCEEDED", "event_id": "a23456789bcdefg", "etag": '"etag-safe"'},
        error_json={"message": "must already be redacted"},
    )
    db_session.add(operation)
    db_session.commit()

    with _client(db_session) as client:
        owner = client.get(
            "/api/mcp/schedules/operations/correlation-status-001",
            headers=_make_token(db_session, ordinary_user, [SCHEDULE_WRITE_SCOPE]),
        )
        outsider = client.get(
            "/api/mcp/schedules/operations/correlation-status-001",
            headers=_make_token(db_session, other_user, [SCHEDULE_WRITE_SCOPE]),
        )

    assert owner.status_code == 200
    assert owner.json()["data"]["status"] == "SUCCEEDED"
    assert owner.json()["data"]["result"] == {
        "status": "SUCCEEDED", "event_id": "a23456789bcdefg", "etag": '"etag-safe"',
    }
    assert owner.json()["data"]["error"] == {}
    assert outsider.status_code == 404


def test_detail_normalizes_factory_and_google_failures_without_secret_leakage(
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
    headers = _make_token(db_session, ordinary_user, [SCHEDULE_READ_SCOPE])
    secret = r"Bearer detail-secret C:\private\google-credentials.json"
    cases = [
        ("factory", RuntimeError(secret), 502, "upstream_unavailable"),
        ("google", RuntimeError(secret), 502, "upstream_unavailable"),
        ("google", HttpError(SimpleNamespace(status=503, reason=secret), secret.encode()), 502, "upstream_unavailable"),
        ("google", HttpError(SimpleNamespace(status=404, reason=secret), secret.encode()), 404, "schedule_not_found"),
    ]

    with _client(db_session) as client:
        for source, upstream_error, expected_status, expected_code in cases:
            if source == "factory":
                def failing_factory(_category, error=upstream_error):
                    raise error

                monkeypatch.setattr(mcp_schedule, "get_calendar_config_and_service", failing_factory)
            else:
                service = _Service(upstream_error)
                monkeypatch.setattr(
                    mcp_schedule,
                    "get_calendar_config_and_service",
                    lambda category, current_service=service: (current_service, f"calendar-{category}"),
                )
            response = client.get(f"/api/mcp/schedules/{event_id}?category=company", headers=headers)
            assert response.status_code == expected_status
            assert response.json()["detail"] == expected_code
            assert secret not in response.text
