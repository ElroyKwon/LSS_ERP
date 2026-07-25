from __future__ import annotations

import httpx
import pytest

from lss_erp_mcp.confirmation import ConfirmationStore
from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.tools.worklog import prepare_from_worklog
from tests.contract_server.app import create_contract_app
from tests.contract_server.state import ContractState


def existing_entry(
    *,
    work_date: str = "2026-07-20",
    description: str = "기존 업무",
) -> dict[str, object]:
    return {
        "entry_id": 1,
        "work_date": work_date,
        "project_id": 123,
        "project_name": "MCP 개발",
        "project_source": "실행",
        "spg": "에너지",
        "hours": "8",
        "work_type": "실행 > 업무지원",
        "description": description,
    }


def project_fact(
    *,
    fact_id: str = "log-1",
    work_date: str = "2026-07-21",
    hours: str | None = "8",
    project_query: str = "MCP",
    work_type: str | None = "실행 > 업무지원",
) -> dict[str, object]:
    return {
        "fact_id": fact_id,
        "work_date": work_date,
        "entry_kind": "project",
        "description": "신규 업무",
        "hours": hours,
        "project_query": project_query,
        "work_type": work_type,
    }


def weekday_gap_acceptances(*dates: str) -> list[str]:
    return [f"coverage:{work_date}:below-target" for work_date in dates]


async def run_prepare(
    state: ContractState,
    facts: list[dict[str, object]],
    accepted_question_ids: list[str] | None = None,
) -> dict[str, object]:
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        return await prepare_from_worklog(
            client,
            ConfirmationStore(),
            week_start="2026-07-20",
            facts=facts,
            accepted_question_ids=accepted_question_ids or [],
        )


@pytest.mark.asyncio
async def test_prepare_merges_unique_project_and_preserves_existing_row() -> None:
    state = ContractState(entries=[existing_entry()])

    result = await run_prepare(
        state,
        [project_fact()],
        weekday_gap_acceptances("2026-07-22", "2026-07-23", "2026-07-24"),
    )

    assert result["mode"] == "merge"
    assert result["preserved_entry_count"] == 1
    assert result["daily_totals"]["2026-07-20"] == "8"
    assert result["daily_totals"]["2026-07-21"] == "8"
    assert result["weekly_total_hours"] == "16"
    assert result["clarification_questions"] == []
    assert result["can_commit"] is True
    assert isinstance(result["confirmation_token"], str)
    assert state.post_count == 0


@pytest.mark.asyncio
async def test_prepare_returns_ambiguous_project_candidates_without_post() -> None:
    state = ContractState(
        projects=[
            {
                "project_id": 123,
                "project_code": "P-1",
                "project_name": "MCP 개발",
                "project_source": "실행",
                "spg": "에너지",
                "active": True,
            },
            {
                "project_id": 456,
                "project_code": "P-2",
                "project_name": "MCP 고도화",
                "project_source": "실행",
                "spg": "에너지",
                "active": True,
            },
        ]
    )

    result = await run_prepare(state, [project_fact(project_query="MCP")])

    question = result["clarification_questions"][0]
    assert question["code"] == "project_ambiguous"
    assert len(question["options"]) == 2
    assert result["can_commit"] is False
    assert result["confirmation_token"] is None
    assert state.post_count == 0


@pytest.mark.asyncio
async def test_prepare_does_not_guess_missing_hours_or_work_type() -> None:
    state = ContractState()

    result = await run_prepare(
        state,
        [project_fact(hours=None, work_type=None)],
    )

    codes = {item["code"] for item in result["clarification_questions"]}
    assert "missing_hours" in codes
    assert "missing_work_type" in codes
    assert result["can_commit"] is False
    assert state.post_count == 0


@pytest.mark.asyncio
async def test_prepare_normalizes_leave_without_project_search_input() -> None:
    state = ContractState()
    fact = {
        "fact_id": "leave-1",
        "work_date": "2026-07-20",
        "entry_kind": "leave",
        "description": "연차",
        "hours": "8",
    }

    result = await run_prepare(
        state,
        [fact],
        weekday_gap_acceptances(
            "2026-07-21",
            "2026-07-22",
            "2026-07-23",
            "2026-07-24",
        ),
    )

    entry = result["proposal_entries"][0]
    assert entry["project_id"] is None
    assert entry["project_name"] == "연차"
    assert entry["project_source"] == "공통"
    assert entry["work_type"] == "공통 > 연차"
    assert result["can_commit"] is True


@pytest.mark.asyncio
async def test_prepare_requires_common_name() -> None:
    state = ContractState()
    fact = {
        "fact_id": "common-1",
        "work_date": "2026-07-20",
        "entry_kind": "common",
        "description": "내부 업무",
        "hours": "8",
        "work_type": "공통 > 기타",
    }

    result = await run_prepare(state, [fact])

    assert {
        item["code"] for item in result["clarification_questions"]
    } >= {"missing_common_name"}
    assert result["can_commit"] is False


@pytest.mark.asyncio
async def test_prepare_rejects_unknown_or_noncoverage_acceptance() -> None:
    state = ContractState()

    with pytest.raises(ValueError, match="unknown or non-coverage"):
        await run_prepare(
            state,
            [project_fact(hours=None)],
            ["fact:log-1:missing-hours"],
        )
