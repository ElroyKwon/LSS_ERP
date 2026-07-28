from __future__ import annotations

from datetime import date

import httpx
import pytest

from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.errors import ERPError
from lss_erp_mcp.schemas.schedule import (
    ScheduleMutationRequest,
    SchedulePreflightRequest,
)
from tests.contract_server.app import create_contract_app
from tests.contract_server.state import ContractState


EVENT_ID = "abcde123"
ETAG = '"etag-1"'
CORRELATION_ID = "corr-stub_001"
IDEMPOTENCY_KEY = "schedule-stub-001"


def mutation(*, content: str = "contract schedule") -> dict[str, object]:
    return {
        "content": content,
        "type": "#123456",
        "category": "company",
        "is_all_day": True,
        "date": "2026-07-28",
        "end_date": "2026-07-28",
        "schedule_kind": "project",
    }


def write_headers(
    *,
    key: str = IDEMPOTENCY_KEY,
    correlation_id: str = CORRELATION_ID,
    etag: str | None = None,
) -> dict[str, str]:
    headers = {
        "Idempotency-Key": key,
        "X-Correlation-ID": correlation_id,
        "X-LSS-MCP-Schedule": "1",
    }
    if etag is not None:
        headers["If-Match"] = etag
    return headers


@pytest.mark.asyncio
async def test_schedule_stub_supports_read_detail_preflight_and_status() -> None:
    state = ContractState()
    state.schedule_operations[(state.user_id, CORRELATION_ID)] = {
        "owner_user_id": state.user_id,
        "correlation_id": CORRELATION_ID,
        "status": "SUCCEEDED",
        "event_id": EVENT_ID,
        "result": {
            "status": "SUCCEEDED",
            "event_id": EVENT_ID,
            "correlation_id": CORRELATION_ID,
            "write_applied": True,
        },
        "error": {},
    }
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        listing = await client.list_schedules(
            category="company",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
        )
        detail = await client.get_schedule(EVENT_ID, category="company")
        preflight = await client.preflight_schedule(
            SchedulePreflightRequest.model_validate(
                {
                    "action": "UPDATE",
                    "category": "company",
                    "event_id": EVENT_ID,
                    "desired": {
                        "is_all_day": True,
                        "date": "2026-07-29",
                        "end_date": "2026-07-29",
                    },
                }
            )
        )
        operation = await client.get_schedule_operation(CORRELATION_ID)

    assert listing.count == 1
    assert detail.event_id == EVENT_ID
    assert detail.etag == ETAG
    assert preflight.write_allowed is True
    assert preflight.owner_binding.state == "BOUND"
    assert operation.status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_schedule_stub_denies_missing_read_and_write_scopes() -> None:
    state = ContractState()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        state.scopes.discard("schedule:read")
        read_denied = await client.get("/api/mcp/schedules")
        state.scopes.add("schedule:read")
        state.scopes.discard("schedule:write")
        write_denied = await client.post(
            "/api/schedules",
            json={**mutation(), "user_name": ""},
            headers=write_headers(),
        )

    assert read_denied.status_code == 403
    assert read_denied.json()["error"]["code"] == "missing_scope"
    assert write_denied.status_code == 403
    assert write_denied.json()["error"]["code"] == "missing_scope"
    assert state.schedule_write_count == 0


@pytest.mark.asyncio
async def test_preflight_reports_locked_timesheet_without_write_authority() -> None:
    state = ContractState(schedule_timesheet_status="제출")
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        result = await client.preflight_schedule(
            SchedulePreflightRequest.model_validate(
                {
                    "action": "DELETE",
                    "category": "company",
                    "event_id": EVENT_ID,
                }
            )
        )

    assert result.write_allowed is False
    assert result.denial_reasons == ["timesheet_locked"]
    assert result.timesheet_statuses[0].status == "제출"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("owner_state", "denial"),
    [
        ("LEGACY_OWNER_UNBOUND", "legacy_owner_unbound"),
        ("OWNER_MISMATCH", "owner_mismatch"),
    ],
)
async def test_preflight_preserves_owner_denial_states(
    owner_state: str,
    denial: str,
) -> None:
    state = ContractState(schedule_owner_state=owner_state)
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        detail = await client.get_schedule(EVENT_ID, category="company")
        result = await client.preflight_schedule(
            SchedulePreflightRequest.model_validate(
                {
                    "action": "DELETE",
                    "category": "company",
                    "event_id": EVENT_ID,
                }
            )
        )

    assert detail.owner_binding.state == owner_state
    assert detail.eligibility.denial_reasons == [denial]
    assert result.owner_binding.state == owner_state
    assert result.denial_reasons == [denial]


@pytest.mark.asyncio
async def test_stale_etag_is_rejected_before_schedule_mutation() -> None:
    state = ContractState()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.put(
            f"/api/schedules/{EVENT_ID}",
            json={**mutation(content="changed"), "user_name": ""},
            headers=write_headers(etag='"stale"'),
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stale_event"
    assert state.schedule_write_count == 0
    assert state.schedules[EVENT_ID]["content"] == "contract schedule"


@pytest.mark.asyncio
async def test_same_key_replays_once_and_different_payload_conflicts() -> None:
    state = ContractState()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        first = await client.post(
            "/api/schedules",
            json={**mutation(), "user_name": ""},
            headers=write_headers(),
        )
        replay = await client.post(
            "/api/schedules",
            json={**mutation(), "user_name": ""},
            headers=write_headers(),
        )
        conflict = await client.post(
            "/api/schedules",
            json={**mutation(content="different"), "user_name": ""},
            headers=write_headers(),
        )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert state.schedule_write_count == 1


@pytest.mark.asyncio
async def test_update_same_key_with_changed_if_match_conflicts() -> None:
    state = ContractState()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        first = await client.put(
            f"/api/schedules/{EVENT_ID}",
            json={**mutation(content="updated once"), "user_name": ""},
            headers=write_headers(etag=ETAG),
        )
        changed_etag = await client.put(
            f"/api/schedules/{EVENT_ID}",
            json={**mutation(content="updated once"), "user_name": ""},
            headers=write_headers(etag='"etag-2"'),
        )

    assert first.status_code == 200
    assert changed_etag.status_code == 409
    assert changed_etag.json()["error"]["code"] == "idempotency_conflict"
    assert state.schedule_write_count == 1


@pytest.mark.asyncio
async def test_operation_status_requires_write_scope_owner_and_exact_not_found() -> None:
    state = ContractState()
    state.schedule_operations[(state.user_id, CORRELATION_ID)] = {
        "owner_user_id": state.user_id,
        "correlation_id": CORRELATION_ID,
        "status": "IN_PROGRESS",
        "event_id": None,
        "result": {},
        "error": {},
    }
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        state.scopes.discard("schedule:write")
        denied = await client.get(
            f"/api/mcp/schedules/operations/{CORRELATION_ID}"
        )
        state.scopes.add("schedule:write")
        state.user_id += 1
        other_user = await client.get(
            f"/api/mcp/schedules/operations/{CORRELATION_ID}"
        )
        missing = await client.get(
            "/api/mcp/schedules/operations/corr-missing_001"
        )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "missing_scope"
    assert other_user.status_code == 404
    assert other_user.json()["error"]["code"] == "operation_not_found"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "operation_not_found"


@pytest.mark.asyncio
async def test_idempotency_key_is_namespaced_by_authenticated_user() -> None:
    state = ContractState()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        first = await client.post(
            "/api/schedules",
            json={**mutation(), "user_name": ""},
            headers=write_headers(correlation_id="corr-user10_001"),
        )
        state.user_id = 11
        second = await client.post(
            "/api/schedules",
            json={**mutation(), "user_name": ""},
            headers=write_headers(correlation_id="corr-user11_001"),
        )
        hidden = await client.get(
            "/api/mcp/schedules/operations/corr-user10_001"
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    assert state.schedule_write_count == 2
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "operation_not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "owner_state", "timesheet_status", "http_status", "code"),
    [
        ("UPDATE", "LEGACY_OWNER_UNBOUND", "작성중", 403, "legacy_owner_unbound"),
        ("DELETE", "OWNER_MISMATCH", "작성중", 403, "owner_mismatch"),
        ("UPDATE", "BOUND", "제출", 409, "timesheet_locked"),
        ("CREATE", "BOUND", "승인", 409, "timesheet_locked"),
    ],
)
async def test_commit_revalidates_owner_and_timesheet_before_mutation(
    action: str,
    owner_state: str,
    timesheet_status: str,
    http_status: int,
    code: str,
) -> None:
    state = ContractState(
        schedule_owner_state=owner_state,
        schedule_timesheet_status=timesheet_status,
    )
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        if action == "CREATE":
            response = await client.post(
                "/api/schedules",
                json={**mutation(), "user_name": ""},
                headers=write_headers(),
            )
        elif action == "UPDATE":
            response = await client.put(
                f"/api/schedules/{EVENT_ID}",
                json={**mutation(content="blocked"), "user_name": ""},
                headers=write_headers(etag=ETAG),
            )
        else:
            response = await client.delete(
                f"/api/schedules/{EVENT_ID}",
                params={"category": "company"},
                headers=write_headers(etag=ETAG),
            )

    assert response.status_code == http_status
    assert response.json()["error"]["code"] == code
    assert state.schedule_write_count == 0
    assert EVENT_ID in state.schedules


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "owner_state"),
    [
        ("UPDATE", "LEGACY_OWNER_UNBOUND"),
        ("DELETE", "OWNER_MISMATCH"),
    ],
)
async def test_owner_denial_is_not_replayed_after_owner_evidence_is_corrected(
    action: str,
    owner_state: str,
) -> None:
    state = ContractState(schedule_owner_state=owner_state)
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        if action == "UPDATE":
            first = await client.put(
                f"/api/schedules/{EVENT_ID}",
                json={**mutation(content="corrected-owner"), "user_name": ""},
                headers=write_headers(etag=ETAG),
            )
        else:
            first = await client.delete(
                f"/api/schedules/{EVENT_ID}",
                params={"category": "company"},
                headers=write_headers(etag=ETAG),
            )

        state.schedule_owner_state = "BOUND"

        if action == "UPDATE":
            retry = await client.put(
                f"/api/schedules/{EVENT_ID}",
                json={**mutation(content="corrected-owner"), "user_name": ""},
                headers=write_headers(etag=ETAG),
            )
        else:
            retry = await client.delete(
                f"/api/schedules/{EVENT_ID}",
                params={"category": "company"},
                headers=write_headers(etag=ETAG),
            )

    assert first.status_code == 403
    assert retry.status_code == 200
    assert state.schedule_write_count == 1


@pytest.mark.asyncio
async def test_exact_replay_precedes_mutable_timesheet_revalidation() -> None:
    state = ContractState()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        first = await client.post(
            "/api/schedules",
            json={**mutation(), "user_name": ""},
            headers=write_headers(),
        )
        state.schedule_timesheet_status = "제출"
        replay = await client.post(
            "/api/schedules",
            json={**mutation(), "user_name": ""},
            headers=write_headers(),
        )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert state.schedule_write_count == 1


@pytest.mark.asyncio
async def test_locked_denial_replay_stays_stable_after_timesheet_unlocks() -> None:
    state = ContractState(schedule_timesheet_status="제출")
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        first = await client.post(
            "/api/schedules",
            json={**mutation(), "user_name": ""},
            headers=write_headers(),
        )
        state.schedule_timesheet_status = "작성중"
        replay = await client.post(
            "/api/schedules",
            json={**mutation(), "user_name": ""},
            headers=write_headers(),
        )

    assert first.status_code == 409
    assert replay.status_code == 409
    assert replay.json() == first.json()
    assert replay.json()["error"]["code"] == "timesheet_locked"
    assert state.schedule_write_count == 0


@pytest.mark.asyncio
async def test_response_loss_after_create_keeps_observable_success() -> None:
    state = ContractState(
        schedule_faults={"CREATE": "response_loss"},
    )
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.create_schedule(
                ScheduleMutationRequest.model_validate(mutation()),
                idempotency_key=IDEMPOTENCY_KEY,
                correlation_id=CORRELATION_ID,
            )
        status = await client.get_schedule_operation(CORRELATION_ID)

    assert caught.value.status_code == 504
    assert state.schedule_write_count == 1
    assert status.status == "SUCCEEDED"
    assert status.event_id in state.schedules


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "fault", "expected_status"),
    [
        ("UPDATE", "partial_failure", "RECONCILIATION_REQUIRED"),
        ("DELETE", "manual_review", "MANUAL_REVIEW"),
    ],
)
async def test_partial_write_faults_keep_operation_evidence(
    action: str,
    fault: str,
    expected_status: str,
) -> None:
    state = ContractState(schedule_faults={action: fault})
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        if action == "UPDATE":
            response = await client.put(
                f"/api/schedules/{EVENT_ID}",
                json={**mutation(content="partially applied"), "user_name": ""},
                headers=write_headers(etag=ETAG),
            )
        else:
            response = await client.delete(
                f"/api/schedules/{EVENT_ID}",
                params={"category": "company"},
                headers=write_headers(etag=ETAG),
            )
        if action == "UPDATE":
            replay = await client.put(
                f"/api/schedules/{EVENT_ID}",
                json={**mutation(content="partially applied"), "user_name": ""},
                headers=write_headers(etag=ETAG),
            )
        else:
            replay = await client.delete(
                f"/api/schedules/{EVENT_ID}",
                params={"category": "company"},
                headers=write_headers(etag=ETAG),
            )
        status = await client.get(
            f"/api/mcp/schedules/operations/{CORRELATION_ID}"
        )

    assert response.status_code == 502
    assert replay.status_code == 502
    assert replay.json() == response.json()
    expected_code = (
        "reconciliation_required" if action == "UPDATE" else "manual_review"
    )
    assert response.json()["error"]["code"] == expected_code
    assert status.status_code == 200
    assert status.json()["data"]["status"] == expected_status
    stored_error = status.json()["data"]["error"]
    if action == "UPDATE":
        assert stored_error["code"] == "reconciliation_required"
    else:
        assert stored_error["code"] == "conflicting_evidence"
    assert stored_error["http_status"] == 502
    assert state.schedule_write_count == 1
    if action == "UPDATE":
        assert state.schedules[EVENT_ID]["content"] == "partially applied"
    else:
        assert EVENT_ID not in state.schedules
