from __future__ import annotations

import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_stdio_lists_only_expected_read_tools(
    monkeypatch: pytest.MonkeyPatch,
    contract_server_url: str,
) -> None:
    monkeypatch.setenv("LSS_ERP_ENVIRONMENT", "test")
    monkeypatch.setenv("LSS_ERP_BASE_URL", contract_server_url)
    monkeypatch.setenv("LSS_ERP_ALLOW_ENV_TOKEN", "true")
    monkeypatch.setenv("LSS_ERP_API_TOKEN", "test-token")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "lss_erp_mcp"],
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
    assert {tool.name for tool in result.tools} == {
        "erp_get_current_user",
        "timesheet_get_week",
        "timesheet_search_projects",
    }
