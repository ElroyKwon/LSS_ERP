from __future__ import annotations

from statistics import quantiles
from time import perf_counter

import httpx
import pytest

from lss_erp_mcp.erp_client import ERPClient
from tests.contract_server.app import create_contract_app


@pytest.mark.asyncio
async def test_local_adapter_p95_is_within_25ms() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    samples: list[float] = []
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        for _ in range(20):
            await client.get_current_user()
        for _ in range(200):
            started = perf_counter()
            await client.get_current_user()
            samples.append((perf_counter() - started) * 1000)

    p95 = quantiles(samples, n=20)[18]
    assert p95 <= 25, f"local adapter p95 {p95:.3f}ms exceeds 25ms"
