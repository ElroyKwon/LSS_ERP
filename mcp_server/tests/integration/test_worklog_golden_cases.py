from __future__ import annotations

import httpx
import pytest

from lss_erp_mcp.confirmation import ConfirmationStore
from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.tools.worklog import prepare_from_worklog
from tests.contract_server.app import create_contract_app
from tests.contract_server.state import ContractState


WEEKDAY_GAPS_AFTER_MONDAY = [
    f"coverage:2026-07-{day:02d}:below-target" for day in range(21, 25)
]


async def prepare(
    fact: dict[str, object],
    *,
    accepted_question_ids: list[str] | None = None,
) -> dict[str, object]:
    state = ContractState()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        result = await prepare_from_worklog(
            client,
            ConfirmationStore(),
            week_start="2026-07-20",
            facts=[fact],
            accepted_question_ids=accepted_question_ids or [],
        )
    assert state.post_count == 0
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entry_kind", "project_name", "work_type"),
    [
        ("common", "교육", "공통 > 교육"),
        ("non_project", "내부 관리", "공통 > 기타"),
    ],
)
async def test_common_and_non_project_golden_cases(
    entry_kind: str,
    project_name: str,
    work_type: str,
) -> None:
    result = await prepare(
        {
            "fact_id": f"{entry_kind}-1",
            "work_date": "2026-07-20",
            "entry_kind": entry_kind,
            "description": project_name,
            "hours": "8",
            "project_name": project_name,
            "work_type": work_type,
        },
        accepted_question_ids=WEEKDAY_GAPS_AFTER_MONDAY,
    )

    entry = result["proposal_entries"][0]
    assert entry["project_id"] is None
    assert entry["project_name"] == project_name
    assert entry["project_source"] == "공통"
    assert entry["work_type"] == work_type
    assert result["can_commit"] is True


@pytest.mark.asyncio
async def test_coverage_question_ids_are_deterministic() -> None:
    fact = {
        "fact_id": "leave-1",
        "work_date": "2026-07-20",
        "entry_kind": "leave",
        "description": "연차",
        "hours": "8",
    }

    first = await prepare(fact)
    second = await prepare(fact)

    assert [
        item["question_id"] for item in first["clarification_questions"]
    ] == [
        item["question_id"] for item in second["clarification_questions"]
    ]
    assert first["confirmation_token"] is None
    assert second["confirmation_token"] is None


@pytest.mark.asyncio
async def test_explicit_coverage_acceptance_unlocks_only_the_same_proposal() -> None:
    fact = {
        "fact_id": "leave-1",
        "work_date": "2026-07-20",
        "entry_kind": "leave",
        "description": "연차",
        "hours": "8",
    }

    result = await prepare(
        fact,
        accepted_question_ids=WEEKDAY_GAPS_AFTER_MONDAY,
    )

    assert result["clarification_questions"] == []
    assert result["can_commit"] is True
    assert isinstance(result["confirmation_token"], str)
