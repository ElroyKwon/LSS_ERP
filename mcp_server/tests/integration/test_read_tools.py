from __future__ import annotations

import httpx
import pytest

from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.tools.identity import get_current_user
from lss_erp_mcp.tools.timesheets import get_week, search_projects
from tests.contract_server.app import create_contract_app


@pytest.mark.asyncio
async def test_read_tools_use_contract_stub() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        user = await get_current_user(client)
        week = await get_week(client, "2026-07-20")
        projects = await search_projects(client, "MCP", 20)
    assert user["employee_id"] == 25
    assert week["status"] == "작성중"
    assert projects["items"][0]["project_id"] == 123


@pytest.mark.asyncio
async def test_get_week_rejects_non_iso_date_before_http() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        with pytest.raises(ValueError):
            await get_week(client, "2026/07/20")
