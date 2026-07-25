from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from lss_erp_mcp.confirmation import ConfirmationStore
from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.tools.timesheets import prepare_draft
from tests.contract_server.app import create_contract_app
from tests.contract_server.state import ContractState


def proposed_entry(
    *,
    project_id: int = 123,
    hours: float = 7.5,
    description: str = "MCP 개발",
) -> dict[str, object]:
    return {
        "work_date": "2026-07-20",
        "project_id": project_id,
        "hours": hours,
        "work_type": "개발",
        "description": description,
    }


async def run_prepare(
    state: ContractState,
    entries: list[dict[str, object]],
) -> dict[str, object]:
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        return await prepare_draft(
            client,
            ConfirmationStore(),
            week_start="2026-07-20",
            entries=entries,
        )


@pytest.mark.asyncio
async def test_prepare_success_returns_diff_and_never_posts() -> None:
    state = ContractState()

    result = await run_prepare(state, [proposed_entry()])

    assert result["mode"] == "replace"
    assert result["daily_totals"] == {"2026-07-20": "7.5"}
    assert result["weekly_total_hours"] == "7.5"
    assert result["can_commit"] is True
    assert isinstance(result["confirmation_token"], str)
    assert result["unresolved_project_ids"] == []
    assert state.post_count == 0


@pytest.mark.asyncio
async def test_complete_replacement_prepare_accepts_common_entry_without_project_id() -> None:
    state = ContractState()
    common_entry = {
        "work_date": "2026-07-20",
        "project_id": None,
        "project_name": "교육",
        "project_source": "공통",
        "spg": None,
        "hours": "8",
        "work_type": "공통 > 교육",
        "description": "사내 교육",
    }

    result = await run_prepare(state, [common_entry])

    assert result["can_commit"] is True
    assert result["unresolved_project_ids"] == []
    assert state.post_count == 0


@pytest.mark.asyncio
async def test_prepare_unresolved_project_never_posts() -> None:
    state = ContractState()

    result = await run_prepare(state, [proposed_entry(project_id=999)])

    assert result["can_commit"] is False
    assert result["confirmation_token"] is None
    assert result["unresolved_project_ids"] == [999]
    assert state.post_count == 0


@pytest.mark.asyncio
async def test_prepare_daily_total_warning_never_posts() -> None:
    state = ContractState()
    entries = [
        proposed_entry(hours=13, description="오전"),
        proposed_entry(hours=13, description="오후"),
    ]

    result = await run_prepare(state, entries)

    assert result["can_commit"] is False
    assert result["warnings"] == ["2026-07-20 exceeds 24 hours"]
    assert state.post_count == 0


@pytest.mark.asyncio
async def test_prepare_duplicate_entry_warning_never_posts() -> None:
    state = ContractState()
    duplicated = proposed_entry()

    result = await run_prepare(state, [duplicated, dict(duplicated)])

    assert result["can_commit"] is False
    assert any("duplicate proposed entry" in item for item in result["warnings"])
    assert state.post_count == 0


@pytest.mark.asyncio
async def test_prepare_non_draft_status_never_posts() -> None:
    state = ContractState(status="승인")

    result = await run_prepare(state, [proposed_entry()])

    assert result["can_commit"] is False
    assert result["current_status"] == "승인"
    assert state.post_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entries",
    [
        [],
        [proposed_entry(description=f"entry-{index}") for index in range(51)],
        [
            {
                **proposed_entry(),
                "work_date": "2026-07-27",
            }
        ],
    ],
)
async def test_prepare_rejects_empty_unbounded_or_out_of_week_entries(
    entries: list[dict[str, object]],
) -> None:
    state = ContractState()

    with pytest.raises(ValidationError):
        await run_prepare(state, entries)

    assert state.post_count == 0
