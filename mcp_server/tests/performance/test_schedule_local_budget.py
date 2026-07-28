from __future__ import annotations

from statistics import quantiles
from time import perf_counter

import httpx
import pytest

from lss_erp_mcp.erp_client import ERPClient
from tests.contract_server.app import create_contract_app
from tests.contract_server.state import ContractState


@pytest.mark.asyncio
async def test_schedule_contract_read_and_status_p95_stays_within_25ms() -> None:
    correlation_id = "corr-budget_001"
    state = ContractState()
    state.schedule_operations[(state.user_id, correlation_id)] = {
        "owner_user_id": state.user_id,
        "correlation_id": correlation_id,
        "status": "IN_PROGRESS",
        "event_id": None,
        "result": {},
        "error": {},
    }
    transport = httpx.ASGITransport(app=create_contract_app(state))
    samples: list[float] = []
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        for _ in range(20):
            await client.list_schedules(category="company")
            await client.get_schedule("abcde123", category="company")
            await client.get_schedule_operation(correlation_id)
        for index in range(120):
            started = perf_counter()
            if index % 3 == 0:
                await client.list_schedules(category="company")
            elif index % 3 == 1:
                await client.get_schedule("abcde123", category="company")
            else:
                await client.get_schedule_operation(correlation_id)
            samples.append((perf_counter() - started) * 1000)

    p95 = quantiles(samples, n=20)[18]
    assert p95 <= 25, f"schedule contract p95 {p95:.3f}ms exceeds 25ms"
