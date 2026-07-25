from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from lss_erp_mcp.confirmation import (
    ConfirmationStore,
    ConfirmationUnavailable,
)
from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.tools.timesheets import commit_draft, prepare_draft
from lss_erp_mcp.tools.worklog import prepare_from_worklog
from tests.contract_server.app import create_contract_app
from tests.contract_server.state import ContractState


def entry(*, hours: float = 7.5, description: str = "MCP API 계약 검토") -> dict:
    return {
        "work_date": "2026-07-20",
        "project_id": 123,
        "hours": hours,
        "work_type": "개발",
        "description": description,
    }


@pytest.mark.asyncio
async def test_commit_writes_once_verifies_and_consumes_confirmation() -> None:
    state = ContractState()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    store = ConfirmationStore()
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        prepared = await prepare_draft(
            client,
            store,
            week_start="2026-07-20",
            entries=[entry()],
        )
        token = prepared["confirmation_token"]
        result = await commit_draft(
            client,
            store,
            confirmation_token=token,
            idempotency_key=str(uuid4()),
        )

    assert result["verified"] is True
    assert state.post_count == 1
    with pytest.raises(ConfirmationUnavailable):
        store.get(token)


@pytest.mark.asyncio
async def test_worklog_confirmation_commits_expanded_leave_without_local_metadata() -> None:
    state = ContractState()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    store = ConfirmationStore()
    fact = {
        "fact_id": "leave-1",
        "work_date": "2026-07-20",
        "entry_kind": "leave",
        "description": "연차",
        "hours": "8",
    }
    accepted_question_ids = [
        f"coverage:2026-07-{day:02d}:below-target"
        for day in range(21, 25)
    ]
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        prepared = await prepare_from_worklog(
            client,
            store,
            week_start="2026-07-20",
            facts=[fact],
            accepted_question_ids=accepted_question_ids,
        )
        result = await commit_draft(
            client,
            store,
            confirmation_token=prepared["confirmation_token"],
            idempotency_key=str(uuid4()),
        )

    assert result["verified"] is True
    assert state.post_count == 1
    assert state.entries == [
        {
            "entry_id": 1,
            "work_date": "2026-07-20",
            "project_id": None,
            "project_name": "연차",
            "project_source": "공통",
            "spg": None,
            "hours": "8",
            "work_type": "공통 > 연차",
            "description": "연차",
        }
    ]
    assert "fact_id" not in state.entries[0]
    assert "accepted_question_ids" not in state.entries[0]
