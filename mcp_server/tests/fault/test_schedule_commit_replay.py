from __future__ import annotations

import pytest

from lss_erp_mcp.errors import ERPError
from lss_erp_mcp.schedule_confirmation import (
    ScheduleConfirmationStore,
    ScheduleConfirmationUnavailable,
)
from lss_erp_mcp.schemas.schedule import ScheduleMutationRequest
from lss_erp_mcp.schemas.schedule import ScheduleOperationData
from lss_erp_mcp.schemas.timesheet import CurrentUser
from lss_erp_mcp.tools.schedules import commit_schedule, get_operation_status


KEY = "schedule-operation-001"


class TimeoutClient:
    def __init__(self) -> None:
        self.write_calls = 0

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
        _request: ScheduleMutationRequest,
        **_kwargs: object,
    ) -> None:
        self.write_calls += 1
        raise ERPError(
            "upstream_timeout",
            "ERP API timed out",
            True,
        )

    async def get_schedule_operation(
        self,
        correlation_id: str,
    ) -> ScheduleOperationData:
        return ScheduleOperationData.model_validate(
            {
                "correlation_id": correlation_id,
                "status": "RECONCILIATION_REQUIRED",
                "event_id": None,
                "result": {},
                "error": {
                    "code": "upstream_timeout",
                    "status": "RECONCILIATION_REQUIRED",
                    "correlation_id": correlation_id,
                },
            }
        )


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


@pytest.mark.asyncio
async def test_timeout_is_not_retried_and_requires_status_reconciliation() -> None:
    store = ScheduleConfirmationStore(lease_factory=lambda: "l" * 43)
    client = TimeoutClient()
    token = store.put(
        user_id=7,
        action="CREATE",
        category="company",
        event_id=None,
        expected_etag=None,
        proposal=proposal(),
    )

    result = await commit_schedule(
        client,
        store,
        write_enabled=True,
        confirmation_token=token,
        idempotency_key=KEY,
        correlation_id_factory=lambda: "corr-timeout_001",
    )

    assert client.write_calls == 1
    assert result == {
        "status": "RECONCILIATION_REQUIRED",
        "action": "CREATE",
        "event_id": None,
        "correlation_id": "corr-timeout_001",
        "idempotency_key": KEY,
        "replayed": False,
        "write_applied": None,
        "reconciliation_required": True,
        "error_code": "upstream_timeout",
        "confirmation_finalization": "CONSUMED",
    }
    with pytest.raises(ScheduleConfirmationUnavailable):
        store.get(token)


@pytest.mark.asyncio
async def test_uncertain_commit_cannot_replay_the_write_with_same_token() -> None:
    store = ScheduleConfirmationStore(
        lease_factory=lambda: "l" * 43,
    )
    client = TimeoutClient()
    token = store.put(
        user_id=7,
        action="CREATE",
        category="company",
        event_id=None,
        expected_etag=None,
        proposal=proposal(),
    )

    first = await commit_schedule(
        client,
        store,
        write_enabled=True,
        confirmation_token=token,
        idempotency_key=KEY,
        correlation_id_factory=lambda: "corr-timeout_001",
    )
    with pytest.raises(ScheduleConfirmationUnavailable):
        await commit_schedule(
            client,
            store,
            write_enabled=True,
            confirmation_token=token,
            idempotency_key=KEY,
            correlation_id_factory=lambda: "corr-timeout_002",
        )
    status = await get_operation_status(client, first["correlation_id"])

    assert first["correlation_id"] == "corr-timeout_001"
    assert status["status"] == "RECONCILIATION_REQUIRED"
    assert status["correlation_id"] == "corr-timeout_001"
    assert client.write_calls == 1
