from copy import deepcopy
from datetime import date

from googleapiclient.errors import HttpError
from httplib2 import Response
import pytest
from sqlalchemy import event

from app.models.common import ApiToken, CalendarSchedule
from app.models.master import Employee
from app.models.mcp_schedule import McpScheduleOperation
from app.models.timesheet import Timesheet, TimesheetEntry
from app.routers import schedule
from app.services import timesheet_locking
from app.utils.auth import hash_api_token
from app.utils.mcp_schedule_auth import SCHEDULE_WRITE_SCOPE


class _Request:
    def __init__(self, payload, *, error=None, on_execute=None):
        self.payload = payload
        self.headers = {}
        self.error = error
        self.on_execute = on_execute

    def execute(self):
        if self.on_execute:
            self.on_execute()
        if self.error:
            raise self.error
        return deepcopy(self.payload)


class _Events:
    def __init__(self, event, *, update_error=None, missing_after_delete=False):
        self.event = deepcopy(event)
        self.update_error = update_error
        self.missing_after_delete = missing_after_delete
        self.deleted = False
        self.update_calls = []
        self.delete_calls = []
        self.insert_calls = []
        self.get_calls = []

    def insert(self, **kwargs):
        self.insert_calls.append(deepcopy(kwargs))
        return _Request({"id": "created-while-disabled"})

    def get(self, **kwargs):
        self.get_calls.append(deepcopy(kwargs))
        if self.deleted and self.missing_after_delete:
            return _Request({}, error=_http_error(404))
        return _Request(self.event)

    def update(self, **kwargs):
        self.update_calls.append(deepcopy(kwargs))
        payload = {"id": kwargs["eventId"], "etag": '"after"'}

        def apply_update():
            self.event = deepcopy(kwargs["body"])
            self.event.update(payload)

        request = _Request(payload, error=self.update_error, on_execute=apply_update)
        self.update_request = request
        return request

    def delete(self, **kwargs):
        self.delete_calls.append(deepcopy(kwargs))
        request = _Request({}, on_execute=lambda: setattr(self, "deleted", True))
        self.delete_request = request
        return request


class _Service:
    def __init__(self, event, **event_options):
        self.resource = _Events(event, **event_options)

    def events(self):
        return self.resource


def _http_error(status_code):
    return HttpError(Response({"status": str(status_code)}), b'{"error":"forced"}')


def _headers(db_session, user, *, key="update-delete-key-001", correlation="corr-update-delete-001", etag='"etag-current"'):
    raw = f"mcp-update-delete-{user.id}-{db_session.query(ApiToken).count()}"
    db_session.add(ApiToken(
        name="MCP update delete test", token_hash=hash_api_token(raw), token_prefix="mcp-update",
        user_id=user.id, scopes=[SCHEDULE_WRITE_SCOPE],
    ))
    db_session.commit()
    return {
        "Authorization": f"Bearer {raw}", "X-LSS-MCP-Schedule": "1",
        "Idempotency-Key": key, "X-Correlation-ID": correlation, "If-Match": etag,
    }


def _event(owner_id, *, etag='"etag-current"', private=True):
    value = {
        "id": "a23456789bcdefg", "etag": etag, "summary": "[Alice] Existing event",
        "description": "existing description",
        "start": {"date": "2026-08-03", "timeZone": "Asia/Seoul"},
        "end": {"date": "2026-08-04", "timeZone": "Asia/Seoul"},
    }
    if private:
        value["extendedProperties"] = {"private": {
            "lss_owner_user_id": str(owner_id), "lss_owner_employee_id": "1", "retained": "yes",
        }}
    return value


def _payload(**overrides):
    value = {
        "content": "Changed customer visit", "date": "2026-08-10", "end_date": "2026-08-10",
        "type": "#722ed1", "category": "company", "user_name": "Spoofed", "is_all_day": True,
    }
    value.update(overrides)
    return value


def _local_row(db_session, user):
    row = CalendarSchedule(
        google_event_id="a23456789bcdefg", category="company", content="Existing event", type="#722ed1",
        user_name="Alice", date=date(2026, 8, 3), end_date=date(2026, 8, 3), created_by=user.id,
    )
    db_session.add(row)
    db_session.commit()


def _use_service(monkeypatch, service):
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))


@pytest.mark.parametrize("flag_value", [None, "false", "TRUE", " true ", "yes", "1"])
def test_mcp_create_update_delete_are_disabled_by_default_before_side_effects(
    flag_value, db_session, ordinary_user, schedule_client, monkeypatch,
):
    if flag_value is None:
        monkeypatch.delenv("MCP_SCHEDULE_WRITE_ENABLED", raising=False)
    else:
        monkeypatch.setenv("MCP_SCHEDULE_WRITE_ENABLED", flag_value)
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)

    create_response = schedule_client.post(
        "/api/schedules",
        headers=_headers(
            db_session, ordinary_user,
            key="disabled-create-key", correlation="disabled-create-correlation",
        ),
        json=_payload(),
    )
    update_response = schedule_client.put(
        "/api/schedules/a23456789bcdefg",
        headers=_headers(
            db_session, ordinary_user,
            key="disabled-update-key", correlation="disabled-update-correlation",
        ),
        json=_payload(),
    )
    delete_response = schedule_client.delete(
        "/api/schedules/a23456789bcdefg?category=company",
        headers=_headers(
            db_session, ordinary_user,
            key="disabled-delete-key", correlation="disabled-delete-correlation",
        ),
    )

    assert [response.status_code for response in (create_response, update_response, delete_response)] == [403, 403, 403]
    assert [response.json()["detail"] for response in (create_response, update_response, delete_response)] == [
        "write_disabled", "write_disabled", "write_disabled",
    ]
    assert service.resource.insert_calls == []
    assert service.resource.update_calls == []
    assert service.resource.delete_calls == []
    assert service.resource.get_calls == []
    assert db_session.query(McpScheduleOperation).count() == 0
    assert db_session.query(CalendarSchedule).one().content == "Existing event"


def test_mcp_update_accepts_exact_immutable_owner_and_forwards_if_match(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)

    response = schedule_client.put(
        "/api/schedules/a23456789bcdefg", headers=_headers(db_session, ordinary_user), json=_payload(),
    )

    assert response.status_code == 200, response.text
    assert service.resource.update_request.headers["If-Match"] == '"etag-current"'
    assert service.resource.update_calls[0]["body"]["extendedProperties"]["private"]["retained"] == "yes"


def test_mcp_timed_update_adapts_iso_offset_input_to_legacy_event_builder(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)

    response = schedule_client.put(
        "/api/schedules/a23456789bcdefg",
        headers=_headers(db_session, ordinary_user),
        json=_payload(
            is_all_day=False,
            date=None,
            end_date=None,
            type="#52c41a",
            start_time="2026-08-10T00:00:00Z",
            end_time="2026-08-10T01:30:00Z",
        ),
    )

    assert response.status_code == 200, response.text
    body = service.resource.update_calls[0]["body"]
    assert body["start"]["dateTime"] == "2026-08-10T09:00:00"
    assert body["end"]["dateTime"] == "2026-08-10T10:30:00"


def test_mcp_reversed_update_time_is_stable_before_claim_and_google(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)
    headers = _headers(db_session, ordinary_user)
    invalid_payload = _payload(
        is_all_day=False,
        date=None,
        end_date=None,
        type="#52c41a",
        start_time="2026-08-10T10:30:00+09:00",
        end_time="2026-08-10T09:00:00+09:00",
    )

    first = schedule_client.put(
        "/api/schedules/a23456789bcdefg", headers=headers, json=invalid_payload,
    )
    repeated = schedule_client.put(
        "/api/schedules/a23456789bcdefg", headers=headers, json=invalid_payload,
    )

    assert first.status_code == repeated.status_code == 422
    assert first.json()["detail"] == repeated.json()["detail"] == "invalid_schedule_time"
    assert service.resource.get_calls == []
    assert service.resource.update_calls == []
    assert db_session.query(McpScheduleOperation).count() == 0


def test_mcp_update_rejects_legacy_display_owner_before_google_write(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id, private=False))
    _use_service(monkeypatch, service)

    response = schedule_client.put(
        "/api/schedules/a23456789bcdefg", headers=_headers(db_session, ordinary_user), json=_payload(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "legacy_owner_unbound"
    assert service.resource.update_calls == []


def test_mcp_update_rejects_immutable_owner_mismatch_before_google_write(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(999))
    _use_service(monkeypatch, service)

    response = schedule_client.put(
        "/api/schedules/a23456789bcdefg", headers=_headers(db_session, ordinary_user), json=_payload(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "owner_mismatch"
    assert service.resource.update_calls == []


def test_mcp_update_rejects_missing_or_stale_if_match_before_google_write(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)

    missing = schedule_client.put(
        "/api/schedules/a23456789bcdefg", headers={k: v for k, v in _headers(db_session, ordinary_user).items() if k != "If-Match"}, json=_payload(),
    )
    stale = schedule_client.put(
        "/api/schedules/a23456789bcdefg", headers=_headers(db_session, ordinary_user, key="update-delete-key-002", correlation="corr-update-delete-002", etag='"stale"'), json=_payload(),
    )

    assert missing.status_code == stale.status_code == 409
    assert missing.json()["detail"] == stale.json()["detail"] == "stale_event"
    assert service.resource.update_calls == []


def test_mcp_update_blocks_locked_union_week_before_google_call(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    employee = db_session.query(Employee).filter(Employee.emp_code == ordinary_user.employee_code).one()
    db_session.add(Timesheet(employee_id=employee.id, week_start=date(2026, 8, 10), week_end=date(2026, 8, 16), status="승인"))
    db_session.commit()
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)

    response = schedule_client.put(
        "/api/schedules/a23456789bcdefg", headers=_headers(db_session, ordinary_user), json=_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "timesheet_locked"
    assert service.resource.update_calls == []


def test_mcp_update_locked_week_first_response_and_replay_preserve_correlation(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    employee = db_session.query(Employee).filter(Employee.emp_code == ordinary_user.employee_code).one()
    db_session.add(Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 8, 10),
        week_end=date(2026, 8, 16),
        status="SUBMITTED",
    ))
    db_session.commit()
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)
    headers = _headers(db_session, ordinary_user)

    first = schedule_client.put(
        "/api/schedules/a23456789bcdefg", headers=headers, json=_payload(),
    )
    replay = schedule_client.put(
        "/api/schedules/a23456789bcdefg", headers=headers, json=_payload(),
    )

    assert first.status_code == replay.status_code == 409
    assert first.json()["detail"] == replay.json()["detail"] == "timesheet_locked"
    assert first.headers["X-Correlation-ID"] == "corr-update-delete-001"
    assert replay.headers["X-Correlation-ID"] == "corr-update-delete-001"
    assert service.resource.update_calls == []
    operation = db_session.query(McpScheduleOperation).one()
    assert operation.status == "FAILED"
    assert operation.correlation_id == "corr-update-delete-001"
    assert operation.error_json["code"] == "timesheet_locked"


def test_mcp_update_blocks_submitted_source_week_before_google_call(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    employee = db_session.query(Employee).filter(Employee.emp_code == ordinary_user.employee_code).one()
    db_session.add(Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 8, 3),
        week_end=date(2026, 8, 9),
        status="제출",
    ))
    db_session.commit()
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)

    response = schedule_client.put(
        "/api/schedules/a23456789bcdefg",
        headers=_headers(db_session, ordinary_user),
        json=_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "timesheet_locked"
    assert service.resource.update_calls == []


def test_mcp_update_same_key_replays_stored_result_without_second_google_write(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)
    headers = _headers(db_session, ordinary_user)

    first = schedule_client.put("/api/schedules/a23456789bcdefg", headers=headers, json=_payload())
    replay = schedule_client.put("/api/schedules/a23456789bcdefg", headers=headers, json=_payload())

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert len(service.resource.update_calls) == 1


def test_mcp_update_same_key_rejects_changed_content_with_same_dates(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)
    headers = _headers(db_session, ordinary_user)

    first = schedule_client.put("/api/schedules/a23456789bcdefg", headers=headers, json=_payload())
    conflict = schedule_client.put(
        "/api/schedules/a23456789bcdefg",
        headers=headers,
        json=_payload(content="Different content with identical dates"),
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "idempotency_conflict"
    assert len(service.resource.update_calls) == 1


def test_mcp_delete_forwards_if_match_and_requires_immutable_owner(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)

    response = schedule_client.delete(
        "/api/schedules/a23456789bcdefg?category=company", headers=_headers(db_session, ordinary_user),
    )

    assert response.status_code == 200
    assert service.resource.delete_request.headers["If-Match"] == '"etag-current"'


def test_mcp_delete_rejects_immutable_owner_mismatch_before_google_write(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(999))
    _use_service(monkeypatch, service)

    response = schedule_client.delete(
        "/api/schedules/a23456789bcdefg?category=company",
        headers=_headers(db_session, ordinary_user),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "owner_mismatch"
    assert service.resource.delete_calls == []


def test_mcp_delete_locked_week_first_response_and_replay_preserve_correlation(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    employee = db_session.query(Employee).filter(Employee.emp_code == ordinary_user.employee_code).one()
    db_session.add(Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 8, 3),
        week_end=date(2026, 8, 9),
        status="SUBMITTED",
    ))
    db_session.commit()
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)
    headers = _headers(db_session, ordinary_user)

    first = schedule_client.delete(
        "/api/schedules/a23456789bcdefg?category=company", headers=headers,
    )
    replay = schedule_client.delete(
        "/api/schedules/a23456789bcdefg?category=company", headers=headers,
    )

    assert first.status_code == replay.status_code == 409
    assert first.json()["detail"] == replay.json()["detail"] == "timesheet_locked"
    assert first.headers["X-Correlation-ID"] == "corr-update-delete-001"
    assert replay.headers["X-Correlation-ID"] == "corr-update-delete-001"
    assert service.resource.delete_calls == []
    operation = db_session.query(McpScheduleOperation).one()
    assert operation.status == "FAILED"
    assert operation.correlation_id == "corr-update-delete-001"
    assert operation.error_json["code"] == "timesheet_locked"


@pytest.mark.parametrize("action", ["UPDATE", "DELETE"])
def test_mcp_update_delete_uses_post_parent_revalidated_scope_before_mutation(
    db_session,
    ordinary_user,
    schedule_client,
    monkeypatch,
    mcp_schedule_writes_enabled,
    action,
):
    _local_row(db_session, ordinary_user)
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
    db_session.add(timesheet)
    db_session.flush()
    db_session.add(TimesheetEntry(
        timesheet_id=timesheet.id,
        project_name="Current linked scope",
        schedule_event_id="a23456789bcdefg",
        schedule_category="company",
    ))
    db_session.commit()

    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)
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
        if action == "UPDATE"
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
    headers = _headers(db_session, ordinary_user)

    if action == "UPDATE":
        response = schedule_client.put(
            "/api/schedules/a23456789bcdefg",
            headers=headers,
            json=_payload(),
        )
        assert locked_scopes == [{
            employee.id: {current_week, date(2026, 8, 10)},
        }]
        assert len(service.resource.update_calls) == 1
    else:
        response = schedule_client.delete(
            "/api/schedules/a23456789bcdefg?category=company",
            headers=headers,
        )
        assert locked_scopes == [{employee.id: {current_week}}]
        assert len(service.resource.delete_calls) == 1

    assert response.status_code == 200


def test_mcp_persistent_scope_churn_fails_closed_and_replays_stable_error(
    db_session,
    ordinary_user,
    schedule_client,
    monkeypatch,
    mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    owner = db_session.query(Employee).filter(
        Employee.emp_code == ordinary_user.employee_code,
    ).one()
    others = [
        Employee(emp_code=f"SCOPE-{index}", name=f"Scope Employee {index}")
        for index in range(2, 5)
    ]
    db_session.add_all(others)
    db_session.commit()
    discoveries = iter([
        {owner.id: {date(2026, 8, 3)}},
        {others[0].id: {date(2026, 8, 10)}},
        {others[1].id: {date(2026, 8, 17)}},
        {others[2].id: {date(2026, 8, 24)}},
    ])
    discovery_calls = []

    def churn_scope(*_args, **_kwargs):
        value = next(discoveries)
        discovery_calls.append(value)
        return value

    monkeypatch.setattr(
        timesheet_locking,
        "_discover_schedule_timesheet_scope",
        churn_scope,
        raising=False,
    )
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)
    headers = _headers(db_session, ordinary_user)

    first = schedule_client.put(
        "/api/schedules/a23456789bcdefg",
        headers=headers,
        json=_payload(),
    )
    replay = schedule_client.put(
        "/api/schedules/a23456789bcdefg",
        headers=headers,
        json=_payload(),
    )

    assert first.status_code == replay.status_code == 409
    assert first.json()["detail"] == replay.json()["detail"] == "timesheet_scope_unstable"
    assert first.headers["X-Correlation-ID"] == "corr-update-delete-001"
    assert replay.headers["X-Correlation-ID"] == "corr-update-delete-001"
    assert len(discovery_calls) == 4
    assert service.resource.update_calls == []
    operation = db_session.query(McpScheduleOperation).one()
    assert operation.status == "FAILED"
    assert operation.error_json["code"] == "timesheet_scope_unstable"


def test_mcp_update_db_failure_after_google_success_requires_reconciliation(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id))
    _use_service(monkeypatch, service)
    headers = _headers(db_session, ordinary_user)
    injected = False

    def fail_commit_after_google_update(_session):
        nonlocal injected
        if len(service.resource.update_calls) == 1 and not injected:
            injected = True
            raise RuntimeError("forced local commit failure after Google update")

    event.listen(db_session, "before_commit", fail_commit_after_google_update)
    try:
        response = schedule_client.put(
            "/api/schedules/a23456789bcdefg", headers=headers, json=_payload(),
        )
    finally:
        event.remove(db_session, "before_commit", fail_commit_after_google_update)

    assert response.status_code == 502
    assert response.json()["detail"] == "reconciliation_required"
    assert response.headers["X-Correlation-ID"] == "corr-update-delete-001"
    assert len(service.resource.update_calls) == 1
    operation = db_session.query(McpScheduleOperation).one()
    assert operation.status == "RECONCILIATION_REQUIRED"
    assert operation.error_json == {
        "code": "reconciliation_required",
        "status": "RECONCILIATION_REQUIRED",
        "correlation_id": "corr-update-delete-001",
        "http_status": 502,
    }

    replay = schedule_client.put(
        "/api/schedules/a23456789bcdefg", headers=headers, json=_payload(),
    )
    assert replay.status_code == 502
    assert replay.json()["detail"] == "reconciliation_required"
    assert replay.headers["X-Correlation-ID"] == "corr-update-delete-001"
    assert len(service.resource.update_calls) == 1


def test_mcp_update_google_503_is_reconciliation_required_not_failed(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id), update_error=_http_error(503))
    _use_service(monkeypatch, service)

    response = schedule_client.put(
        "/api/schedules/a23456789bcdefg",
        headers=_headers(db_session, ordinary_user),
        json=_payload(),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "reconciliation_required"
    operation = db_session.query(McpScheduleOperation).one()
    assert operation.status == "RECONCILIATION_REQUIRED"


def test_mcp_delete_db_failure_and_404_readback_requires_reconciliation(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    _local_row(db_session, ordinary_user)
    service = _Service(_event(ordinary_user.id), missing_after_delete=True)
    _use_service(monkeypatch, service)
    headers = _headers(db_session, ordinary_user)
    injected = False

    def fail_commit_after_google_delete(_session):
        nonlocal injected
        if len(service.resource.delete_calls) == 1 and not injected:
            injected = True
            raise RuntimeError("forced local commit failure after Google delete")

    event.listen(db_session, "before_commit", fail_commit_after_google_delete)
    try:
        response = schedule_client.delete(
            "/api/schedules/a23456789bcdefg?category=company", headers=headers,
        )
    finally:
        event.remove(db_session, "before_commit", fail_commit_after_google_delete)

    assert response.status_code == 502
    assert response.json()["detail"] == "reconciliation_required"
    assert response.headers["X-Correlation-ID"] == "corr-update-delete-001"
    assert len(service.resource.delete_calls) == 1
    assert len(service.resource.get_calls) == 2  # owner/etag read plus one bounded post-rollback readback
    operation = db_session.query(McpScheduleOperation).one()
    assert operation.status == "RECONCILIATION_REQUIRED"

    replay = schedule_client.delete(
        "/api/schedules/a23456789bcdefg?category=company", headers=headers,
    )

    assert replay.status_code == 502
    assert replay.json()["detail"] == "reconciliation_required"
    assert replay.headers["X-Correlation-ID"] == "corr-update-delete-001"
    assert len(service.resource.delete_calls) == 1
    assert len(service.resource.get_calls) == 2
