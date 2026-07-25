from __future__ import annotations

from statistics import quantiles
from time import perf_counter

import httpx
import pytest

from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.tools.worklog import merge_entries
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


def test_merge_100_worklog_rows_stays_within_25ms() -> None:
    incoming = [
        {
            "work_date": f"2026-07-{20 + index % 7:02d}",
            "project_id": 1000 + index,
            "project_name": f"프로젝트-{index}",
            "project_source": "실행",
            "spg": "에너지",
            "hours": "0.25",
            "work_type": "실행 > 업무지원",
            "description": f"업무-{index}",
        }
        for index in range(100)
    ]
    started = perf_counter()

    merged, preserved = merge_entries([], incoming)

    elapsed_ms = (perf_counter() - started) * 1000
    assert len(merged) == 100
    assert preserved == 0
    assert elapsed_ms <= 25, f"merge took {elapsed_ms:.3f}ms"
