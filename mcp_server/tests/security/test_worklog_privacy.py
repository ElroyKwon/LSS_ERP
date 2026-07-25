from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from lss_erp_mcp.confirmation import ConfirmationStore
from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.schemas.worklog import WorklogFact
from lss_erp_mcp.tools.worklog import prepare_from_worklog
from tests.contract_server.app import create_contract_app


SRC = Path(__file__).resolve().parents[2] / "src" / "lss_erp_mcp"


def minimal_fact(index: int) -> dict[str, object]:
    return {
        "fact_id": f"log-{index}",
        "work_date": "2026-07-20",
        "entry_kind": "leave",
        "description": f"연차-{index}",
        "hours": "0.25",
    }


def test_worklog_fact_rejects_raw_content_and_employee_authority() -> None:
    with pytest.raises(ValidationError):
        WorklogFact.model_validate(
            {
                **minimal_fact(1),
                "raw_worklog": "개인 원문",
                "employee_id": 999,
                "status": "승인",
            }
        )


def test_mcp_source_does_not_reference_personal_vault_paths() -> None:
    violations: list[str] = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "_Obsidian" in text or "G:\\\\" in text:
            violations.append(str(path.relative_to(SRC)))
    assert violations == []


@pytest.mark.asyncio
async def test_prepare_rejects_more_than_100_facts_before_http() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        with pytest.raises(ValueError, match="between 1 and 100"):
            await prepare_from_worklog(
                client,
                ConfirmationStore(),
                week_start="2026-07-20",
                facts=[minimal_fact(index) for index in range(101)],
                accepted_question_ids=[],
            )


@pytest.mark.asyncio
async def test_prepare_rejects_more_than_50_accepted_questions_before_http() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        with pytest.raises(ValueError, match="at most 50"):
            await prepare_from_worklog(
                client,
                ConfirmationStore(),
                week_start="2026-07-20",
                facts=[minimal_fact(1)],
                accepted_question_ids=[
                    f"coverage:2026-07-20:below-target-{index}"
                    for index in range(51)
                ],
            )
