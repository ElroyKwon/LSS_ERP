from __future__ import annotations

import os
import sys
from uuid import uuid4

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_stdio_lists_expected_timesheet_and_schedule_tools(
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
        "schedule_commit",
        "schedule_get",
        "schedule_list",
        "schedule_operation_status",
        "schedule_prepare_create",
        "schedule_prepare_delete",
        "schedule_prepare_update",
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

    for name in {
        "schedule_list",
        "schedule_get",
        "schedule_prepare_create",
        "schedule_prepare_update",
        "schedule_prepare_delete",
        "schedule_operation_status",
    }:
        annotations = tools[name].annotations
        assert annotations is not None
        assert annotations.readOnlyHint is True
        assert annotations.destructiveHint is False
        assert annotations.idempotentHint is True
        assert annotations.openWorldHint is False

    schedule_commit_tool = tools["schedule_commit"]
    assert schedule_commit_tool.annotations is not None
    assert schedule_commit_tool.annotations.readOnlyHint is False
    assert schedule_commit_tool.annotations.destructiveHint is True
    assert schedule_commit_tool.annotations.idempotentHint is True
    assert schedule_commit_tool.annotations.openWorldHint is False
    expected_schedule_inputs = {
        "schedule_list": {"category", "start_date", "end_date", "limit"},
        "schedule_get": {"event_id", "category"},
        "schedule_prepare_create": {"proposal"},
        "schedule_prepare_update": {"event_id", "proposal"},
        "schedule_prepare_delete": {"event_id", "category"},
        "schedule_commit": {"confirmation_token", "idempotency_key"},
        "schedule_operation_status": {"correlation_id"},
    }
    for name, expected_properties in expected_schedule_inputs.items():
        assert set(tools[name].inputSchema["properties"]) == expected_properties
        assert tools[name].inputSchema["additionalProperties"] is False


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


@pytest.mark.asyncio
async def test_stdio_schedule_write_tool_has_an_independent_fail_closed_gate(
    monkeypatch: pytest.MonkeyPatch,
    contract_server_url: str,
) -> None:
    monkeypatch.setenv("LSS_ERP_ENVIRONMENT", "test")
    monkeypatch.setenv("LSS_ERP_BASE_URL", contract_server_url)
    monkeypatch.setenv("LSS_ERP_ALLOW_ENV_TOKEN", "true")
    monkeypatch.setenv("LSS_ERP_API_TOKEN", "test-token")
    monkeypatch.setenv("LSS_ERP_CANARY_WRITE", "true")
    monkeypatch.delenv("LSS_ERP_SCHEDULE_CANARY_WRITE", raising=False)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "lss_erp_mcp"],
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "schedule_commit",
                {
                    "confirmation_token": "not-used",
                    "idempotency_key": str(uuid4()),
                },
            )

    assert result.isError is True
    assert "schedule commit tool is disabled" in result.content[0].text


@pytest.mark.asyncio
async def test_stdio_redacts_schedule_argument_validation_values(
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
            result = await session.call_tool(
                "schedule_prepare_create",
                {
                    "proposal": {
                        "content": "SECRET_OWNER",
                        "type": "bad-color",
                        "category": "company",
                        "is_all_day": True,
                        "date": "2026-07-28",
                        "end_date": "2026-07-28",
                    }
                },
            )

    assert result.isError is True
    text = result.content[0].text
    assert "invalid_tool_arguments" in text
    assert "bad-color" not in text
    assert "SECRET_OWNER" not in text
    assert "input_value" not in text


@pytest.mark.asyncio
async def test_stdio_rejects_and_redacts_unknown_top_level_tool_arguments(
    monkeypatch: pytest.MonkeyPatch,
    contract_server_url: str,
) -> None:
    monkeypatch.setenv("LSS_ERP_ENVIRONMENT", "test")
    monkeypatch.setenv("LSS_ERP_BASE_URL", contract_server_url)
    monkeypatch.setenv("LSS_ERP_ALLOW_ENV_TOKEN", "true")
    monkeypatch.setenv("LSS_ERP_API_TOKEN", "test-token")
    monkeypatch.delenv("LSS_ERP_SCHEDULE_CANARY_WRITE", raising=False)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "lss_erp_mcp"],
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "schedule_commit",
                {
                    "confirmation_token": "not-used",
                    "idempotency_key": "schedule-operation-001",
                    "user_name": "SECRET_OWNER",
                },
            )

    assert result.isError is True
    text = result.content[0].text
    assert "invalid_tool_arguments" in text
    assert "schedule commit tool is disabled" not in text
    assert "user_name" not in text
    assert "SECRET_OWNER" not in text
