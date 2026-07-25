from __future__ import annotations

from datetime import date

import httpx
import pytest

from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.errors import ERPError
from lss_erp_mcp.tools.timesheets import get_entry_context
from tests.contract_server.app import create_contract_app


@pytest.mark.asyncio
async def test_entry_context_is_bound_to_requested_week() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        context = await client.get_entry_context(date(2026, 7, 20))

    assert context.week_start == date(2026, 7, 20)
    assert context.labor_type == "원가"
    assert len(context.daily_targets) == 7
    assert "공통 > 연차" in context.work_types
    assert context.model_dump().get("employee_id") is None


@pytest.mark.asyncio
async def test_entry_context_tool_returns_json_without_employee_selector() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        result = await get_entry_context(client, "2026-07-20")

    assert result["week_start"] == "2026-07-20"
    assert result["daily_targets"][0]["target_hours"] == "8"
    assert "employee_id" not in result


@pytest.mark.asyncio
async def test_context_response_for_another_week_is_rejected() -> None:
    async def mismatched_context(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "week_start": "2026-07-27",
                "week_end": "2026-08-02",
                "labor_type": "원가",
                "project_sources": ["실행", "영업", "공통"],
                "work_types": ["공통 > 연차"],
                "daily_targets": [
                    {
                        "work_date": f"2026-07-{day:02d}",
                        "target_hours": "8",
                        "reason": "normal",
                    }
                    for day in range(27, 32)
                ]
                + [
                    {
                        "work_date": "2026-08-01",
                        "target_hours": "0",
                        "reason": "weekend",
                    },
                    {
                        "work_date": "2026-08-02",
                        "target_hours": "0",
                        "reason": "weekend",
                    },
                ],
            },
        )
    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(mismatched_context),
    ) as client:
        with pytest.raises(ERPError, match="context week mismatch"):
            await client.get_entry_context(date(2026, 7, 20))
