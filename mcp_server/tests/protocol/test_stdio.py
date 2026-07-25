from __future__ import annotations

import os
import sys
from uuid import uuid4

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
    tools = {tool.name: tool for tool in result.tools}
    assert set(tools) == {
        "erp_get_current_user",
        "timesheet_commit_draft",
        "timesheet_get_entry_context",
        "timesheet_get_week",
        "timesheet_prepare_draft",
        "timesheet_prepare_from_worklog",
        "timesheet_search_projects",
    }
    worklog_tool = tools["timesheet_prepare_from_worklog"]
    assert worklog_tool.annotations is not None
    assert worklog_tool.annotations.readOnlyHint is True
    assert worklog_tool.annotations.destructiveHint is False
    assert worklog_tool.annotations.idempotentHint is True
    assert worklog_tool.annotations.openWorldHint is False
    assert "구조화" in (worklog_tool.description or "")
    assert "추측" in (worklog_tool.description or "")

    replace_tool = tools["timesheet_prepare_draft"]
    assert "전체 교체" in (replace_tool.description or "")

    commit_tool = tools["timesheet_commit_draft"]
    assert commit_tool.annotations is not None
    assert commit_tool.annotations.readOnlyHint is False
    assert commit_tool.annotations.destructiveHint is True
    assert commit_tool.annotations.idempotentHint is True


@pytest.mark.asyncio
async def test_stdio_write_tool_fails_closed_by_default(
    monkeypatch: pytest.MonkeyPatch,
    contract_server_url: str,
) -> None:
    monkeypatch.setenv("LSS_ERP_ENVIRONMENT", "test")
    monkeypatch.setenv("LSS_ERP_BASE_URL", contract_server_url)
    monkeypatch.setenv("LSS_ERP_ALLOW_ENV_TOKEN", "true")
    monkeypatch.setenv("LSS_ERP_API_TOKEN", "test-token")
    monkeypatch.delenv("LSS_ERP_CANARY_WRITE", raising=False)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "lss_erp_mcp"],
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "timesheet_commit_draft",
                {
                    "confirmation_token": "not-used",
                    "idempotency_key": str(uuid4()),
                },
            )

    assert result.isError is True
    assert "disabled" in result.content[0].text
