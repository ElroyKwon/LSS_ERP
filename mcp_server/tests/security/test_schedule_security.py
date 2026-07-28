from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.errors import ERPError
from tests.contract_server.app import create_contract_app
from tests.contract_server.state import ContractState


EVENT_ID = "abcde123"
SECRET = "schedule-secret-canary-value"


@pytest.mark.asyncio
async def test_schedule_read_surfaces_redact_content_and_owner_metadata() -> None:
    state = ContractState()
    state.schedules[EVENT_ID]["content"] = SECRET
    state.schedules[EVENT_ID]["owner_metadata"] = {
        "private_extended_property": SECRET,
    }
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        responses = [
            await client.get("/api/mcp/schedules"),
            await client.get(
                f"/api/mcp/schedules/{EVENT_ID}",
                params={"category": "company"},
            ),
            await client.post(
                "/api/mcp/schedules/preflight",
                json={
                    "action": "DELETE",
                    "category": "company",
                    "event_id": EVENT_ID,
                },
            ),
        ]

    serialized = json.dumps(
        [response.json() for response in responses],
        ensure_ascii=False,
    )
    assert all(response.status_code == 200 for response in responses)
    assert SECRET not in serialized
    assert "owner_metadata" not in serialized
    assert "content" not in serialized


@pytest.mark.asyncio
async def test_schedule_validation_error_does_not_echo_rejected_secret() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/schedules",
            json={
                "content": SECRET,
                "type": "#123456",
                "category": "company",
                "is_all_day": True,
                "date": "2026-07-28",
                "end_date": "2026-07-28",
                "user_name": "",
                "unexpected_secret": SECRET,
            },
            headers={
                "Idempotency-Key": "schedule-secret-001",
                "X-Correlation-ID": "corr-secret_001",
                "X-LSS-MCP-Schedule": "1",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert SECRET not in response.text
    assert "input_value" not in response.text


@pytest.mark.asyncio
async def test_oversized_schedule_response_is_rejected_by_client_bound() -> None:
    state = ContractState()
    template = dict(state.schedules[EVENT_ID])
    state.schedules = {
        f"{index:08x}": {
            **template,
            "event_id": f"{index:08x}",
            "schedule_kind": "x" * 100,
        }
        for index in range(40)
    }
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
        max_response_bytes=1024,
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.list_schedules(category="company", limit=100)

    assert caught.value.code == "upstream_invalid_response"
    assert "too large" in caught.value.message


@pytest.mark.asyncio
async def test_operation_status_allowlist_drops_secret_and_owner_metadata() -> None:
    state = ContractState()
    correlation_id = "corr-redact_001"
    state.schedule_operations[(state.user_id, correlation_id)] = {
        "owner_user_id": state.user_id,
        "correlation_id": correlation_id,
        "status": "MANUAL_REVIEW",
        "event_id": EVENT_ID,
        "result": {
            "content": SECRET,
            "authorization": f"Bearer {SECRET}",
            "status": f"{SECRET}/invalid",
            "event_id": f"{SECRET}/invalid",
            "correlation_id": f"{SECRET}/invalid",
            "etag": f"{SECRET}/invalid",
            "replayed": SECRET,
            "write_applied": 1,
            "reconciliation_required": None,
            "http_status": True,
        },
        "error": {
            "code": "conflicting_evidence",
            "status": "MANUAL_REVIEW",
            "correlation_id": correlation_id,
            "http_status": 409,
            "retryable": SECRET,
            "message": SECRET,
            "details": {"credential_path": SECRET},
        },
        "private_owner": SECRET,
    }
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/api/mcp/schedules/operations/{correlation_id}"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert set(payload) == {
        "correlation_id",
        "status",
        "event_id",
        "result",
        "error",
    }
    assert payload["result"] == {}
    assert payload["error"] == {
        "code": "conflicting_evidence",
        "status": "MANUAL_REVIEW",
        "correlation_id": correlation_id,
        "http_status": 409,
    }
    assert SECRET not in response.text
    assert "owner_user_id" not in response.text


@pytest.mark.asyncio
async def test_operation_status_drops_invalid_values_in_allowed_fields() -> None:
    state = ContractState()
    correlation_id = "corr-redact_002"
    state.schedule_operations[(state.user_id, correlation_id)] = {
        "owner_user_id": state.user_id,
        "correlation_id": correlation_id,
        "status": "MANUAL_REVIEW",
        "event_id": EVENT_ID,
        "result": {
            "status": f"{SECRET}/invalid",
            "event_id": f"{SECRET}/invalid",
            "correlation_id": f"{SECRET}/invalid",
            "etag": f"{SECRET}/invalid",
            "replayed": 1,
            "write_applied": SECRET,
            "reconciliation_required": SECRET,
            "http_status": True,
        },
        "error": {
            "code": f"{SECRET}/invalid",
            "status": f"{SECRET}/invalid",
            "correlation_id": f"{SECRET}/invalid",
            "retryable": SECRET,
            "http_status": True,
        },
    }
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/api/mcp/schedules/operations/{correlation_id}"
        )

    assert response.status_code == 200
    assert response.json()["data"]["result"] == {}
    assert response.json()["data"]["error"] == {}
    assert SECRET not in response.text


def test_schedule_contract_stub_has_no_runtime_or_personal_path_dependency() -> None:
    root = Path(__file__).parents[1] / "contract_server"
    source = "\n".join(
        (root / name).read_text(encoding="utf-8")
        for name in ("app.py", "state.py")
    ).casefold()
    forbidden = {
        "sqlalchemy",
        "googleapiclient",
        "google.oauth",
        "database_url",
        "secret_key",
        ("g:" + "\\"),
        ("d:" + "\\_onedrive"),
    }

    assert all(marker not in source for marker in forbidden)
