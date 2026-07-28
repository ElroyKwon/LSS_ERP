from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta

import pytest

from lss_erp_mcp.errors import ERPError
from lss_erp_mcp.schedule_confirmation import (
    ScheduleConfirmationStore,
    ScheduleConfirmationUnavailable,
)
from lss_erp_mcp.schemas.schedule import (
    ScheduleDeleteResult,
    ScheduleMutationRequest,
    ScheduleOperationData,
    ScheduleUpsertResult,
)
from lss_erp_mcp.schemas.timesheet import CurrentUser
from lss_erp_mcp.tools.schedules import (
    commit_schedule,
    derive_schedule_correlation_id,
    get_operation_status,
)


EVENT_ID = "abcde123"
ETAG = '"etag-1"'
KEY = "schedule-operation-001"


def proposal() -> dict[str, object]:
    return {
        "content": "private meeting",
        "type": "#123456",
        "category": "company",
        "is_all_day": True,
        "date": "2026-07-28",
        "end_date": "2026-07-28",
        "schedule_kind": "project",
    }


class RecordingStore(ScheduleConfirmationStore):
    def __init__(self) -> None:
        super().__init__(lease_factory=lambda: "l" * 43)
        self.released: list[tuple[str, str | None]] = []
        self.consumed: list[tuple[str, str | None]] = []

    def release(self, token: str, lease_id: str | None = None) -> None:
        self.released.append((token, lease_id))
        super().release(token, lease_id)

    def consume(self, token: str, lease_id: str | None = None) -> None:
        self.consumed.append((token, lease_id))
        super().consume(token, lease_id)


class ConsumeFailureStore(RecordingStore):
    def consume(self, token: str, lease_id: str | None = None) -> None:
        self.consumed.append((token, lease_id))
        raise RuntimeError("private consume failure")


class PostConsumeFailureStore(RecordingStore):
    def consume(self, token: str, lease_id: str | None = None) -> None:
        self.consumed.append((token, lease_id))
        ScheduleConfirmationStore.consume(self, token, lease_id)
        raise RuntimeError("private post-consume failure")


class ReleaseFailureStore(RecordingStore):
    def release(self, token: str, lease_id: str | None = None) -> None:
        self.released.append((token, lease_id))
        raise RuntimeError("private release failure")


class FakeClient:
    def __init__(self) -> None:
        self.writes: list[tuple[str, object, dict[str, object]]] = []
        self.status_calls: list[str] = []

    async def get_current_user(self) -> CurrentUser:
        return CurrentUser(
            user_id=7,
            employee_id=11,
            employee_code="E007",
            display_name="Test User",
            client_id="mcp-test",
            resource="erp",
            scopes=["schedule:read", "schedule:write"],
        )

    async def create_schedule(
        self,
        request: ScheduleMutationRequest,
        **kwargs: object,
    ) -> ScheduleUpsertResult:
        self.writes.append(("CREATE", request, kwargs))
        return ScheduleUpsertResult(status="success", id=EVENT_ID)

    async def update_schedule(
        self,
        event_id: str,
        request: ScheduleMutationRequest,
        **kwargs: object,
    ) -> ScheduleUpsertResult:
        self.writes.append(("UPDATE", (event_id, request), kwargs))
        return ScheduleUpsertResult(status="success", id=event_id)

    async def delete_schedule(
        self,
        event_id: str,
        **kwargs: object,
    ) -> ScheduleDeleteResult:
        self.writes.append(("DELETE", event_id, kwargs))
        return ScheduleDeleteResult(status="success")

    async def get_schedule_operation(
        self,
        correlation_id: str,
    ) -> ScheduleOperationData:
        self.status_calls.append(correlation_id)
        return ScheduleOperationData.model_validate(
            {
                "correlation_id": correlation_id,
                "status": "SUCCEEDED",
                "event_id": EVENT_ID,
                "result": {
                    "status": "SUCCEEDED",
                    "event_id": EVENT_ID,
                    "correlation_id": correlation_id,
                    "write_applied": True,
                },
                "error": {},
            }
        )


def put(
    store: ScheduleConfirmationStore,
    action: str,
) -> str:
    return store.put(
        user_id=7,
        action=action,
        category="company",
        event_id=None if action == "CREATE" else EVENT_ID,
        expected_etag=None if action == "CREATE" else ETAG,
        proposal={} if action == "DELETE" else proposal(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["CREATE", "UPDATE", "DELETE"])
async def test_commit_calls_exact_typed_write_and_consumes_owner_lease(
    action: str,
) -> None:
    store = RecordingStore()
    client = FakeClient()
    token = put(store, action)

    result = await commit_schedule(
        client,
        store,
        write_enabled=True,
        confirmation_token=token,
        idempotency_key=KEY,
        correlation_id_factory=lambda: "corr-test_001",
    )

    assert result == {
        "status": "SUCCEEDED",
        "action": action,
        "event_id": EVENT_ID,
        "correlation_id": "corr-test_001",
        "idempotency_key": KEY,
        "replayed": False,
        "write_applied": True,
        "reconciliation_required": False,
        "confirmation_finalization": "CONSUMED",
    }
    assert len(client.writes) == 1
    called_action, _request, kwargs = client.writes[0]
    assert called_action == action
    assert kwargs["idempotency_key"] == KEY
    assert kwargs["correlation_id"] == "corr-test_001"
    if action != "CREATE":
        assert kwargs["etag"] == ETAG
    assert store.released == []
    assert store.consumed == [(token, "l" * 43)]
    with pytest.raises(ScheduleConfirmationUnavailable):
        store.get(token)


@pytest.mark.asyncio
async def test_commit_gate_is_independent_and_checked_before_confirmation() -> None:
    store = RecordingStore()
    client = FakeClient()

    with pytest.raises(PermissionError, match="schedule commit tool is disabled"):
        await commit_schedule(
            client,
            store,
            write_enabled=False,
            confirmation_token="not-used",
            idempotency_key=KEY,
        )

    assert client.writes == []
    assert store.released == []
    assert store.consumed == []


@pytest.mark.asyncio
async def test_invalid_stored_proposal_releases_the_matching_lease_pre_send() -> None:
    store = RecordingStore()
    client = FakeClient()
    token = store.put(
        user_id=7,
        action="CREATE",
        category="company",
        event_id=None,
        expected_etag=None,
        proposal={"invalid": "redacted"},
    )

    with pytest.raises(ValueError, match="invalid_schedule_proposal"):
        await commit_schedule(
            client,
            store,
            write_enabled=True,
            confirmation_token=token,
            idempotency_key=KEY,
            correlation_id_factory=lambda: "corr-test_001",
        )

    assert client.writes == []
    assert store.released == [(token, "l" * 43)]
    assert store.consumed == []
    assert store.get(token).action == "CREATE"


@pytest.mark.asyncio
async def test_pre_send_release_failure_is_bounded_and_keeps_lease_fail_closed() -> None:
    store = ReleaseFailureStore()
    client = FakeClient()
    token = store.put(
        user_id=7,
        action="CREATE",
        category="company",
        event_id=None,
        expected_etag=None,
        proposal={"invalid": "redacted"},
    )

    with pytest.raises(ValueError, match="^confirmation_release_failed$"):
        await commit_schedule(
            client,
            store,
            write_enabled=True,
            confirmation_token=token,
            idempotency_key=KEY,
            correlation_id_factory=lambda: "corr-test_001",
        )

    assert client.writes == []
    assert store.released == [(token, "l" * 43)]
    with pytest.raises(
        ScheduleConfirmationUnavailable,
        match="confirmation_commit_in_progress",
    ):
        await commit_schedule(
            client,
            store,
            write_enabled=True,
            confirmation_token=token,
            idempotency_key=KEY,
        )


@pytest.mark.asyncio
async def test_invalid_target_binding_releases_matching_lease_pre_send() -> None:
    store = RecordingStore()
    client = FakeClient()
    token = store.put(
        user_id=7,
        action="DELETE",
        category="company",
        event_id="bad/id",
        expected_etag=ETAG,
        proposal={},
    )

    with pytest.raises(ValueError, match="invalid_schedule_confirmation"):
        await commit_schedule(
            client,
            store,
            write_enabled=True,
            confirmation_token=token,
            idempotency_key=KEY,
            correlation_id_factory=lambda: "corr-test_001",
        )

    assert client.writes == []
    assert store.released == [(token, "l" * 43)]
    assert store.consumed == []


@pytest.mark.asyncio
async def test_changed_confirmation_is_rejected_without_write() -> None:
    store = RecordingStore()
    client = FakeClient()
    token = put(store, "CREATE")
    store._items[token].proposal["content"] = "tampered"

    with pytest.raises(
        ScheduleConfirmationUnavailable,
        match="integrity check failed",
    ):
        await commit_schedule(
            client,
            store,
            write_enabled=True,
            confirmation_token=token,
            idempotency_key=KEY,
        )

    assert client.writes == []


@pytest.mark.asyncio
async def test_missing_or_expired_confirmation_is_rejected_without_write() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    clock_values = iter([now, now, now + timedelta(seconds=2)])
    store = RecordingStore()
    store.ttl = timedelta(seconds=1)
    store.clock = lambda: next(clock_values)
    client = FakeClient()
    token = put(store, "CREATE")

    for invalid_token in ("missing-confirmation-token-value", token):
        with pytest.raises(ScheduleConfirmationUnavailable):
            await commit_schedule(
                client,
                store,
                write_enabled=True,
                confirmation_token=invalid_token,
                idempotency_key=KEY,
            )

    assert client.writes == []


@pytest.mark.asyncio
async def test_unexpected_exception_after_write_entry_requires_reconciliation() -> None:
    class UnexpectedClient(FakeClient):
        async def create_schedule(
            self,
            request: ScheduleMutationRequest,
            **kwargs: object,
        ) -> ScheduleUpsertResult:
            self.writes.append(("CREATE", request, kwargs))
            raise RuntimeError("private transport internals")

    store = RecordingStore()
    client = UnexpectedClient()
    token = put(store, "CREATE")

    result = await commit_schedule(
        client,
        store,
        write_enabled=True,
        confirmation_token=token,
        idempotency_key=KEY,
        correlation_id_factory=lambda: "corr-unexpected_001",
    )

    assert result == {
        "status": "RECONCILIATION_REQUIRED",
        "action": "CREATE",
        "event_id": None,
        "correlation_id": "corr-unexpected_001",
        "idempotency_key": KEY,
        "replayed": False,
        "write_applied": None,
        "reconciliation_required": True,
        "error_code": "unexpected_schedule_write_failure",
        "confirmation_finalization": "CONSUMED",
    }
    assert len(client.writes) == 1
    assert store.released == []
    assert store.consumed == [(token, "l" * 43)]
    with pytest.raises(ScheduleConfirmationUnavailable):
        store.get(token)


@pytest.mark.asyncio
async def test_value_error_after_write_entry_is_not_treated_as_pre_send() -> None:
    class ValueErrorClient(FakeClient):
        async def create_schedule(
            self,
            request: ScheduleMutationRequest,
            **kwargs: object,
        ) -> ScheduleUpsertResult:
            self.writes.append(("CREATE", request, kwargs))
            raise ValueError("private client detail")

    store = RecordingStore()
    client = ValueErrorClient()
    token = put(store, "CREATE")

    result = await commit_schedule(
        client,
        store,
        write_enabled=True,
        confirmation_token=token,
        idempotency_key=KEY,
        correlation_id_factory=lambda: "corr-valueerror_001",
    )

    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert result["error_code"] == "unexpected_schedule_write_failure"
    assert result["confirmation_finalization"] == "CONSUMED"
    assert store.released == []
    with pytest.raises(ScheduleConfirmationUnavailable):
        store.get(token)


@pytest.mark.asyncio
async def test_success_is_not_masked_when_consume_fails_fail_closed() -> None:
    store = ConsumeFailureStore()
    client = FakeClient()
    token = put(store, "CREATE")

    result = await commit_schedule(
        client,
        store,
        write_enabled=True,
        confirmation_token=token,
        idempotency_key=KEY,
        correlation_id_factory=lambda: "corr-consume_001",
    )

    assert result["status"] == "SUCCEEDED"
    assert result["correlation_id"] == "corr-consume_001"
    assert result["confirmation_finalization"] == "INFLIGHT_FAIL_CLOSED"
    assert len(client.writes) == 1
    with pytest.raises(
        ScheduleConfirmationUnavailable,
        match="confirmation_commit_in_progress",
    ):
        await commit_schedule(
            client,
            store,
            write_enabled=True,
            confirmation_token=token,
            idempotency_key=KEY,
        )
    assert len(client.writes) == 1


@pytest.mark.asyncio
async def test_post_consume_failure_is_conservative_and_cannot_replay() -> None:
    store = PostConsumeFailureStore()
    client = FakeClient()
    token = put(store, "CREATE")

    result = await commit_schedule(
        client,
        store,
        write_enabled=True,
        confirmation_token=token,
        idempotency_key=KEY,
        correlation_id_factory=lambda: "corr-postconsume_001",
    )

    assert result["status"] == "SUCCEEDED"
    assert result["confirmation_finalization"] == "INFLIGHT_FAIL_CLOSED"
    with pytest.raises(ScheduleConfirmationUnavailable):
        await commit_schedule(
            client,
            store,
            write_enabled=True,
            confirmation_token=token,
            idempotency_key=KEY,
        )
    assert len(client.writes) == 1


@pytest.mark.asyncio
async def test_uncertain_result_is_not_masked_when_consume_fails_fail_closed() -> None:
    class TimeoutClient(FakeClient):
        async def create_schedule(
            self,
            request: ScheduleMutationRequest,
            **kwargs: object,
        ) -> ScheduleUpsertResult:
            self.writes.append(("CREATE", request, kwargs))
            raise ERPError("upstream_timeout", "private timeout detail", True)

    store = ConsumeFailureStore()
    client = TimeoutClient()
    token = put(store, "CREATE")

    result = await commit_schedule(
        client,
        store,
        write_enabled=True,
        confirmation_token=token,
        idempotency_key=KEY,
        correlation_id_factory=lambda: "corr-consume_002",
    )

    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert result["error_code"] == "upstream_timeout"
    assert result["confirmation_finalization"] == "INFLIGHT_FAIL_CLOSED"
    with pytest.raises(
        ScheduleConfirmationUnavailable,
        match="confirmation_commit_in_progress",
    ):
        await commit_schedule(
            client,
            store,
            write_enabled=True,
            confirmation_token=token,
            idempotency_key=KEY,
        )
    assert len(client.writes) == 1


@pytest.mark.asyncio
async def test_cancellation_after_write_entry_consumes_then_propagates() -> None:
    class CancelledClient(FakeClient):
        async def create_schedule(
            self,
            request: ScheduleMutationRequest,
            **kwargs: object,
        ) -> ScheduleUpsertResult:
            self.writes.append(("CREATE", request, kwargs))
            raise asyncio.CancelledError

    store = RecordingStore()
    client = CancelledClient()
    token = put(store, "CREATE")

    with pytest.raises(asyncio.CancelledError):
        await commit_schedule(
            client,
            store,
            write_enabled=True,
            confirmation_token=token,
            idempotency_key=KEY,
            correlation_id_factory=lambda: "corr-cancelled_001",
        )

    assert len(client.writes) == 1
    assert store.consumed == [(token, "l" * 43)]
    with pytest.raises(ScheduleConfirmationUnavailable):
        store.get(token)


@pytest.mark.asyncio
async def test_operation_status_uses_validated_typed_status_client() -> None:
    client = FakeClient()

    result = await get_operation_status(client, "corr-test_001")

    assert result["status"] == "SUCCEEDED"
    assert result["correlation_id"] == "corr-test_001"
    assert client.status_calls == ["corr-test_001"]


def test_generated_correlation_contract_is_bounded() -> None:
    pattern = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
    assert pattern.fullmatch("corr-test_001")


def test_default_correlation_is_stable_and_recoverable_from_user_and_key() -> None:
    first = derive_schedule_correlation_id(7, KEY)
    second = derive_schedule_correlation_id(7, KEY)

    assert first == second
    assert re.fullmatch(r"^schedule_v1_[0-9a-f]{40}$", first)
    assert KEY not in first


def test_default_correlation_separates_users_with_the_same_key() -> None:
    assert derive_schedule_correlation_id(7, KEY) != derive_schedule_correlation_id(
        8,
        KEY,
    )
