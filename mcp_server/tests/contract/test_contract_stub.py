from __future__ import annotations

from datetime import date

import httpx
import pytest
from pydantic import ValidationError

from lss_erp_mcp.schemas.timesheet import CurrentUser, DraftWriteRequest
from tests.contract_server.app import create_contract_app
from tests.contract_server.state import ContractState


def draft_body(*, expected_version: int = 3, hours: float = 7.5) -> dict:
    return {
        "week_start": "2026-07-20",
        "expected_version": expected_version,
        "entries": [
            {
                "work_date": "2026-07-20",
                "project_id": 123,
                "hours": hours,
                "work_type": "개발",
                "description": "MCP 계약 테스트",
            }
        ],
    }


def write_headers(*, key: str = "idem-001") -> dict[str, str]:
    return {
        "Idempotency-Key": key,
        "X-Correlation-ID": "corr-001",
    }


def test_schema_rejects_extra_identity_fields() -> None:
    with pytest.raises(ValidationError):
        CurrentUser(
            user_id=10,
            employee_id=25,
            employee_code="E0010",
            display_name="테스트 사용자",
            client_id="lss-erp-mcp-local",
            resource="lss-erp-api",
            scopes=["mcp:discover"],
            raw_token="must-not-be-accepted",
        )


def test_draft_request_requires_monday_and_quarter_hour() -> None:
    with pytest.raises(ValidationError, match="Monday"):
        DraftWriteRequest(
            week_start=date(2026, 7, 21),
            expected_version=3,
            entries=[],
        )
    with pytest.raises(ValidationError, match="multiple"):
        DraftWriteRequest.model_validate(draft_body(hours=7.1))


@pytest.mark.asyncio
async def test_stub_returns_strict_identity_contract() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/auth/me")

    assert response.status_code == 200
    identity = CurrentUser.model_validate(response.json())
    assert identity.employee_id == 25
    assert "raw_token" not in response.json()


@pytest.mark.asyncio
async def test_stub_commit_and_same_key_replay_write_once() -> None:
    state = ContractState()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        first = await client.post(
            "/api/timesheets/mcp-draft",
            json=draft_body(),
            headers=write_headers(),
        )
        replay = await client.post(
            "/api/timesheets/mcp-draft",
            json=draft_body(),
            headers=write_headers(),
        )

    assert first.status_code == 200
    assert first.json()["idempotency_replayed"] is False
    assert replay.status_code == 200
    assert replay.json()["idempotency_replayed"] is True
    assert state.post_count == 1


@pytest.mark.asyncio
async def test_stub_returns_error_envelope_for_stale_write() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/timesheets/mcp-draft",
            json=draft_body(expected_version=2),
            headers=write_headers(),
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "stale_write",
            "message": "Current version changed.",
            "correlation_id": "corr-001",
            "retryable": False,
            "details": {"expected_version": 2, "current_version": 3},
        }
    }


@pytest.mark.asyncio
async def test_stub_returns_error_envelope_for_validation_failure() -> None:
    body = draft_body()
    body["week_start"] = "2026-07-21"
    transport = httpx.ASGITransport(app=create_contract_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/timesheets/mcp-draft",
            json=body,
            headers=write_headers(),
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_failed"
    assert payload["error"]["correlation_id"] == "corr-001"
    assert payload["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_contract_server_fixture_serves_a_real_loopback_socket(
    contract_server_url: str,
) -> None:
    async with httpx.AsyncClient(base_url=contract_server_url) as client:
        response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["employee_code"] == "E0010"
