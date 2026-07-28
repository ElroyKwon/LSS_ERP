from copy import deepcopy

import pytest
from fastapi import HTTPException
from googleapiclient.errors import HttpError
from httplib2 import Response
from sqlalchemy.orm import sessionmaker

from app.models.common import ApiToken
from app.models.mcp_schedule import McpScheduleOperation
from app.models.timesheet import Timesheet
from app.routers import schedule
from app.utils.auth import hash_api_token
from app.utils.mcp_schedule_auth import SCHEDULE_WRITE_SCOPE


class _Request:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return deepcopy(self.payload)


class _Events:
    def __init__(self):
        self.insert_calls = []
        self.get_calls = []
        self.event_by_id = {}

    def insert(self, **kwargs):
        self.insert_calls.append(deepcopy(kwargs))
        event_id = kwargs["body"].get("id", "legacy-id")
        self.event_by_id[event_id] = deepcopy(kwargs["body"])
        return _Request({"id": event_id})

    def get(self, **kwargs):
        self.get_calls.append(deepcopy(kwargs))
        return _Request(self.event_by_id[kwargs["eventId"]])

    def delete(self, **_kwargs):
        return _Request({})


class _Service:
    def __init__(self):
        self.resource = _Events()

    def events(self):
        return self.resource


def _http_error(status_code):
    return HttpError(Response({"status": str(status_code)}), b'{"error":"forced"}')


def _headers(db_session, user, *, key="create-key-0002", correlation="corr-create-0002"):
    raw_token = f"mcp-idempotency-{user.id}-{db_session.query(ApiToken).count()}"
    db_session.add(ApiToken(
        name="MCP schedule idempotency test",
        token_hash=hash_api_token(raw_token),
        token_prefix="mcp-idempotency",
        user_id=user.id,
        scopes=[SCHEDULE_WRITE_SCOPE],
    ))
    db_session.commit()
    return {
        "Authorization": f"Bearer {raw_token}",
        "X-LSS-MCP-Schedule": "1",
        "Idempotency-Key": key,
        "X-Correlation-ID": correlation,
    }


def _payload(content="Customer visit"):
    return {
        "content": content,
        "date": "2026-08-03",
        "end_date": "2026-08-03",
        "type": "#722ed1",
        "category": "company",
        "user_name": "Spoofed owner",
        "is_all_day": True,
    }


def test_same_mcp_idempotency_key_with_changed_canonical_payload_is_a_stable_conflict(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)

    first = schedule_client.post("/api/schedules", headers=headers, json=_payload())
    conflict = schedule_client.post("/api/schedules", headers=headers, json=_payload("Changed visit"))

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "idempotency_conflict"
    assert len(service.resource.insert_calls) == 1


def test_same_key_with_effective_content_whitespace_change_is_a_conflict(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)

    first = schedule_client.post("/api/schedules", headers=headers, json=_payload("Customer visit"))
    conflict = schedule_client.post("/api/schedules", headers=headers, json=_payload(" Customer visit "))

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "idempotency_conflict"
    assert len(service.resource.insert_calls) == 1


def test_raw_category_whitespace_is_rejected_before_a_second_journal_or_google_insert(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)

    first = schedule_client.post("/api/schedules", headers=headers, json=_payload())
    invalid = schedule_client.post("/api/schedules", headers=headers, json={**_payload(), "category": " company "})

    assert first.status_code == 200
    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "invalid_category"
    assert db_session.query(McpScheduleOperation).count() == 1
    assert len(service.resource.insert_calls) == 1


def test_in_progress_replay_reconciles_the_deterministic_google_event_without_reinsert(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)

    first = schedule_client.post("/api/schedules", headers=headers, json=_payload())
    assert first.status_code == 200
    operation = db_session.query(McpScheduleOperation).one()
    operation.status = "IN_PROGRESS"
    operation.result_json = None
    db_session.commit()

    replay = schedule_client.post("/api/schedules", headers=headers, json=_payload())

    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert len(service.resource.insert_calls) == 1
    assert len(service.resource.get_calls) == 1
    db_session.refresh(operation)
    assert operation.status == "SUCCEEDED"
    assert operation.result_json == {
        "status": "SUCCEEDED",
        "event_id": first.json()["id"],
        "correlation_id": "corr-create-0002",
        "write_applied": True,
    }


def test_succeeded_create_replay_ignores_later_locked_timesheet(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)

    first = schedule_client.post("/api/schedules", headers=headers, json=_payload())
    assert first.status_code == 200
    timesheet = db_session.query(Timesheet).one()
    timesheet.status = "제출"
    db_session.commit()

    replay = schedule_client.post("/api/schedules", headers=headers, json=_payload())

    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert len(service.resource.insert_calls) == 1
    assert len(service.resource.get_calls) == 0


@pytest.mark.parametrize(
    ("stored_status", "stored_code", "stored_http", "expected_detail"),
    [
        ("FAILED", "create_compensated", 500, "create_compensated"),
        ("MANUAL_REVIEW", "conflicting_evidence", 409, "manual_review"),
    ],
)
def test_terminal_create_replay_returns_stored_state_code_and_correlation_without_google_write(
    db_session,
    ordinary_user,
    schedule_client,
    monkeypatch,
    stored_status,
    stored_code,
    stored_http,
    expected_detail,
    mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)
    first = schedule_client.post("/api/schedules", headers=headers, json=_payload())
    assert first.status_code == 200
    operation = db_session.query(McpScheduleOperation).one()
    operation.status = stored_status
    operation.result_json = None
    operation.error_json = {
        "code": stored_code,
        "status": stored_status,
        "correlation_id": "corr-create-0002",
        "http_status": stored_http,
    }
    db_session.commit()
    insert_count = len(service.resource.insert_calls)

    replay = schedule_client.post("/api/schedules", headers=headers, json=_payload())

    assert replay.status_code == stored_http
    assert replay.json()["detail"] == expected_detail
    assert replay.headers["X-Correlation-ID"] == "corr-create-0002"
    assert len(service.resource.insert_calls) == insert_count
    assert service.resource.get_calls == []
    db_session.refresh(operation)
    assert operation.status == stored_status
    assert operation.error_json["code"] == stored_code


def test_reconciliation_required_create_replay_keeps_stored_state_when_readback_unavailable(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)
    first = schedule_client.post("/api/schedules", headers=headers, json=_payload())
    assert first.status_code == 200
    operation = db_session.query(McpScheduleOperation).one()
    operation.status = "RECONCILIATION_REQUIRED"
    operation.result_json = None
    operation.error_json = {
        "code": "reconciliation_required",
        "status": "RECONCILIATION_REQUIRED",
        "correlation_id": "corr-create-0002",
        "http_status": 502,
    }
    service.resource.event_by_id.clear()
    db_session.commit()
    insert_count = len(service.resource.insert_calls)

    replay = schedule_client.post("/api/schedules", headers=headers, json=_payload())

    assert replay.status_code == 502
    assert replay.json()["detail"] == "reconciliation_required"
    assert replay.headers["X-Correlation-ID"] == "corr-create-0002"
    assert len(service.resource.insert_calls) == insert_count
    assert len(service.resource.get_calls) == 1
    db_session.refresh(operation)
    assert operation.status == "RECONCILIATION_REQUIRED"
    assert operation.error_json == {
        "code": "reconciliation_required",
        "status": "RECONCILIATION_REQUIRED",
        "correlation_id": "corr-create-0002",
        "http_status": 502,
    }


def test_reconcile_observed_create_local_failure_never_deletes_prior_event(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    class _TrackedDeleteEvents(_Events):
        def __init__(self):
            super().__init__()
            self.delete_calls = []

        def delete(self, **kwargs):
            self.delete_calls.append(deepcopy(kwargs))
            return _Request({})

    service = _Service()
    service.resource = _TrackedDeleteEvents()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)
    first = schedule_client.post("/api/schedules", headers=headers, json=_payload())
    assert first.status_code == 200
    operation = db_session.query(McpScheduleOperation).one()
    operation.status = "IN_PROGRESS"
    operation.result_json = None
    db_session.commit()
    monkeypatch.setattr(
        schedule,
        "_upsert_schedule_row",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("forced replay reconstruction failure")),
    )

    replay = schedule_client.post("/api/schedules", headers=headers, json=_payload())

    assert replay.status_code == 502
    assert replay.json()["detail"] == "reconciliation_required"
    assert len(service.resource.insert_calls) == 1
    assert len(service.resource.get_calls) == 1
    assert service.resource.delete_calls == []


def test_mcp_google_failure_records_a_redacted_reconciliation_state(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    class _FailingEvents(_Events):
        def insert(self, **kwargs):
            self.insert_calls.append(deepcopy(kwargs))
            raise RuntimeError("Bearer secret-token C:\\private\\calendar.json")

    service = _Service()
    service.resource = _FailingEvents()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))

    response = schedule_client.post("/api/schedules", headers=_headers(db_session, ordinary_user), json=_payload())

    assert response.status_code == 502
    assert response.json()["detail"] == "reconciliation_required"
    assert "secret-token" not in response.text
    operation = db_session.query(McpScheduleOperation).one()
    assert operation.status == "RECONCILIATION_REQUIRED"
    assert operation.error_json == {
        "code": "reconciliation_required",
        "status": "RECONCILIATION_REQUIRED",
        "correlation_id": "corr-create-0002",
        "http_status": 502,
    }
    assert operation.result_json in (None, {})


def test_mcp_create_http_error_first_response_and_replay_preserve_correlation_without_rewrite(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    class _HttpErrorEvents(_Events):
        def __init__(self):
            super().__init__()
            self.delete_calls = []

        def insert(self, **kwargs):
            self.insert_calls.append(deepcopy(kwargs))
            raise _http_error(503)

        def delete(self, **kwargs):
            self.delete_calls.append(deepcopy(kwargs))
            return _Request({})

    service = _Service()
    service.resource = _HttpErrorEvents()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)

    first = schedule_client.post("/api/schedules", headers=headers, json=_payload())
    operation = db_session.query(McpScheduleOperation).one()
    first_insert_count = len(service.resource.insert_calls)
    replay = schedule_client.post("/api/schedules", headers=headers, json=_payload())

    assert first.status_code == replay.status_code == 502
    assert first.json()["detail"] == replay.json()["detail"] == "reconciliation_required"
    assert first.headers["X-Correlation-ID"] == "corr-create-0002"
    assert replay.headers["X-Correlation-ID"] == "corr-create-0002"
    assert len(service.resource.insert_calls) == first_insert_count == 1
    assert len(service.resource.get_calls) == 1
    assert service.resource.delete_calls == []
    db_session.refresh(operation)
    assert operation.status == "RECONCILIATION_REQUIRED"
    assert operation.error_json == {
        "code": "reconciliation_required",
        "status": "RECONCILIATION_REQUIRED",
        "correlation_id": "corr-create-0002",
        "http_status": 502,
    }


def test_mcp_timeout_observes_the_deterministic_event_before_compensating(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    class _TimeoutAfterAcceptEvents(_Events):
        def __init__(self):
            super().__init__()
            self.delete_calls = []

        def insert(self, **kwargs):
            self.insert_calls.append(deepcopy(kwargs))
            self.event_by_id[kwargs["body"]["id"]] = deepcopy(kwargs["body"])
            raise TimeoutError("Bearer timeout-secret")

        def delete(self, **kwargs):
            self.delete_calls.append(deepcopy(kwargs))
            return _Request({})

    service = _Service()
    service.resource = _TimeoutAfterAcceptEvents()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))

    response = schedule_client.post("/api/schedules", headers=_headers(db_session, ordinary_user), json=_payload())

    assert response.status_code == 500
    assert response.json()["detail"] == "create_compensated"
    assert "timeout-secret" not in response.text
    assert len(service.resource.insert_calls) == len(service.resource.get_calls) == len(service.resource.delete_calls) == 1
    operation = db_session.query(McpScheduleOperation).one()
    assert operation.status == "FAILED"
    assert operation.error_json["code"] == "create_compensated"


def test_response_loss_after_durable_claim_reconciles_in_a_fresh_session_without_reinsert(
    db_session, ordinary_user, monkeypatch, mcp_schedule_writes_enabled,
):
    class ProcessLost(BaseException):
        pass

    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)
    request = type("Request", (), {"headers": headers})()
    ordering = []
    original_commit = db_session.commit
    original_insert = service.resource.insert

    def tracked_commit():
        ordering.append("commit")
        return original_commit()

    def tracked_insert(**kwargs):
        ordering.append("insert")
        return original_insert(**kwargs)

    monkeypatch.setattr(db_session, "commit", tracked_commit)
    monkeypatch.setattr(service.resource, "insert", tracked_insert)
    original_upsert = schedule._upsert_schedule_row
    monkeypatch.setattr(schedule, "_upsert_schedule_row", lambda *_args: (_ for _ in ()).throw(ProcessLost()))

    with pytest.raises(ProcessLost):
        schedule.create_schedule(schedule.ScheduleCreate(**_payload()), current_user=ordinary_user, db=db_session, request=request)

    assert ordering[:2] == ["commit", "insert"]
    db_session.close()
    FreshSession = sessionmaker(bind=db_session.get_bind(), autocommit=False, autoflush=False)
    retry_session = FreshSession()
    try:
        retry_user = retry_session.get(type(ordinary_user), ordinary_user.id)
        operation = retry_session.query(McpScheduleOperation).one()
        assert operation.status == "IN_PROGRESS"
        monkeypatch.setattr(schedule, "_upsert_schedule_row", original_upsert)
        result = schedule.create_schedule(
            schedule.ScheduleCreate(**_payload()), current_user=retry_user, db=retry_session, request=request,
        )
        assert result["id"] == operation.event_id
        assert len(service.resource.insert_calls) == 1
        assert len(service.resource.get_calls) == 1
        retry_session.refresh(operation)
        assert operation.status == "SUCCEEDED"
    finally:
        retry_session.close()


@pytest.mark.parametrize(
    ("delete_fails", "expected_status", "expected_code", "expected_http"),
    [
        (False, "FAILED", "create_compensated", 500),
        (True, "RECONCILIATION_REQUIRED", "reconciliation_required", 502),
    ],
)
def test_mcp_local_failure_classifies_compensation_evidence_without_secret_leakage(
    db_session, ordinary_user, schedule_client, monkeypatch,
    delete_fails, expected_status, expected_code, expected_http, mcp_schedule_writes_enabled,
):
    class _CompensationEvents(_Events):
        def __init__(self):
            super().__init__()
            self.delete_calls = []

        def delete(self, **kwargs):
            self.delete_calls.append(deepcopy(kwargs))
            if delete_fails:
                raise RuntimeError("Bearer delete-secret C:\\private\\calendar.json")
            return _Request({})

    service = _Service()
    service.resource = _CompensationEvents()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    monkeypatch.setattr(schedule, "_upsert_schedule_row", lambda *_args: (_ for _ in ()).throw(RuntimeError("Bearer db-secret")))

    response = schedule_client.post("/api/schedules", headers=_headers(db_session, ordinary_user), json=_payload())

    assert response.status_code == expected_http
    assert response.json()["detail"] == expected_code
    assert "secret" not in response.text.lower()
    assert len(service.resource.insert_calls) == len(service.resource.delete_calls) == 1
    operation = db_session.query(McpScheduleOperation).one()
    assert operation.status == expected_status
    assert operation.error_json == {
        "code": expected_code,
        "status": expected_status,
        "correlation_id": "corr-create-0002",
        "http_status": expected_http,
    }


@pytest.mark.parametrize(
    ("delete_fails", "expected_status", "expected_code", "expected_http"),
    [
        (False, "FAILED", "create_compensated", 422),
        (True, "RECONCILIATION_REQUIRED", "reconciliation_required", 502),
    ],
)
def test_mcp_post_insert_http_exception_uses_the_same_compensation_classification(
    db_session, ordinary_user, schedule_client, monkeypatch,
    delete_fails, expected_status, expected_code, expected_http, mcp_schedule_writes_enabled,
):
    class _CompensationEvents(_Events):
        def __init__(self):
            super().__init__()
            self.delete_calls = []

        def delete(self, **kwargs):
            self.delete_calls.append(deepcopy(kwargs))
            if delete_fails:
                raise RuntimeError("Bearer delete-secret")
            return _Request({})

    service = _Service()
    service.resource = _CompensationEvents()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    monkeypatch.setattr(
        schedule,
        "_sync_schedule_to_timesheet",
        lambda *_args: (_ for _ in ()).throw(HTTPException(status_code=422, detail="Bearer local-secret")),
    )

    response = schedule_client.post("/api/schedules", headers=_headers(db_session, ordinary_user), json=_payload())

    assert response.status_code == expected_http
    assert response.json()["detail"] == expected_code
    assert "secret" not in response.text.lower()
    assert len(service.resource.insert_calls) == len(service.resource.delete_calls) == 1
    operation = db_session.query(McpScheduleOperation).one()
    assert operation.status == expected_status
    assert operation.error_json["code"] == expected_code
    if delete_fails:
        assert response.headers["X-Correlation-ID"] == "corr-create-0002"


@pytest.mark.parametrize("mutation", ["wrong_id", "wrong_hash", "wrong_owner"])
def test_replay_never_reconciles_succeeded_when_deterministic_google_evidence_mismatches(
    db_session, ordinary_user, schedule_client, monkeypatch, mutation, mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)
    first = schedule_client.post("/api/schedules", headers=headers, json=_payload())
    assert first.status_code == 200
    operation = db_session.query(McpScheduleOperation).one()
    operation.status = "IN_PROGRESS"
    operation.result_json = None
    event = service.resource.event_by_id[operation.event_id]
    if mutation == "wrong_id":
        event["id"] = "00000000wrongid"
    elif mutation == "wrong_hash":
        event["extendedProperties"]["private"]["lss_request_hash"] = "0" * 64
    else:
        event["extendedProperties"]["private"]["lss_owner_user_id"] = "9999"
    db_session.commit()

    replay = schedule_client.post("/api/schedules", headers=headers, json=_payload())

    assert replay.status_code == 409
    assert replay.json()["detail"] == "manual_review"
    assert len(service.resource.insert_calls) == 1
    db_session.refresh(operation)
    assert operation.status == "MANUAL_REVIEW"
    assert operation.result_json in (None, {})


def test_mcp_timed_iso_values_are_kst_normalized_before_legacy_create_and_hash(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)
    first_payload = {
        **_payload("유니코드 일정"),
        "is_all_day": False,
        "date": None,
        "end_date": None,
        "start_time": "2026-08-03T00:00:00Z",
        "end_time": "2026-08-03T01:00:00Z",
        "type": "#52c41a",
        "schedule_kind": "  외근  ",
        "timesheet_project_id": 12345,
        "timesheet_project_name": "  프로젝트  ",
        "timesheet_project_source": "공통",
    }
    equivalent_offset = {
        **first_payload,
        "start_time": "2026-08-03T09:00:00+09:00",
        "end_time": "2026-08-03T10:00:00+09:00",
    }

    first = schedule_client.post("/api/schedules", headers=headers, json=first_payload)
    replay = schedule_client.post("/api/schedules", headers=headers, json=equivalent_offset)

    assert first.status_code == replay.status_code == 200
    assert first.json()["id"] == replay.json()["id"]
    assert len(service.resource.insert_calls) == 1
    body = service.resource.insert_calls[0]["body"]
    assert body["start"] == {"dateTime": "2026-08-03T09:00:00", "timeZone": "Asia/Seoul"}
    assert body["end"] == {"dateTime": "2026-08-03T10:00:00", "timeZone": "Asia/Seoul"}


def test_mcp_timed_reversed_kst_values_fail_before_google_insert(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    response = schedule_client.post(
        "/api/schedules",
        headers=_headers(db_session, ordinary_user),
        json={
            **_payload(),
            "type": "#52c41a",
            "schedule_kind": "외근",
            "is_all_day": False,
            "date": None,
            "end_date": None,
            "start_time": "2026-08-03T10:00:00+09:00",
            "end_time": "2026-08-03T09:00:00+09:00",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "create_rejected"
    assert service.resource.insert_calls == []


def test_mcp_effect_snapshot_distinguishes_none_and_effective_whitespace_fields(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    headers = _headers(db_session, ordinary_user)
    first = schedule_client.post("/api/schedules", headers=headers, json={**_payload(), "schedule_kind": None, "timesheet_project_name": None, "timesheet_project_source": None})
    conflict = schedule_client.post("/api/schedules", headers=headers, json={**_payload(), "schedule_kind": " ", "timesheet_project_name": " ", "timesheet_project_source": " "})

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "idempotency_conflict"


def test_mcp_correlation_id_collision_is_a_stable_conflict(
    db_session, ordinary_user, schedule_client, monkeypatch, mcp_schedule_writes_enabled,
):
    service = _Service()
    monkeypatch.setattr(schedule, "get_calendar_config_and_service", lambda _category: (service, "calendar-company"))
    first = schedule_client.post("/api/schedules", headers=_headers(db_session, ordinary_user, key="create-key-correlation-a", correlation="corr-shared-0001"), json=_payload())
    conflict = schedule_client.post("/api/schedules", headers=_headers(db_session, ordinary_user, key="create-key-correlation-b", correlation="corr-shared-0001"), json=_payload("other"))

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "correlation_id_conflict"
