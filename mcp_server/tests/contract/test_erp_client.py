from __future__ import annotations

import httpx
import pytest

from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.errors import ERPError
from lss_erp_mcp.schemas.timesheet import CurrentUser
from tests.contract_server.app import create_contract_app


@pytest.mark.asyncio
async def test_get_current_user_against_contract_stub() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        user = await client.get_current_user()
    assert isinstance(user, CurrentUser)
    assert user.employee_id == 25


@pytest.mark.asyncio
async def test_arbitrary_path_is_rejected() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        with pytest.raises(ValueError, match="allowlisted"):
            await client._request("GET", "/api/admin/users")


@pytest.mark.asyncio
async def test_redirect_is_rejected() -> None:
    async def redirect(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            307,
            headers={"Location": "https://other.example.test/api/auth/me"},
            json={"redirect": True},
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(redirect),
    ) as client:
        with pytest.raises(ERPError, match="upstream_redirect_rejected"):
            await client.get_current_user()


@pytest.mark.asyncio
async def test_error_envelope_preserves_code_and_correlation() -> None:
    async def conflict(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "error": {
                    "code": "stale_write",
                    "message": "Current version changed.",
                    "correlation_id": "corr-409",
                    "retryable": False,
                    "details": {"current_version": 4},
                }
            },
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(conflict),
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.get_current_user()

    assert caught.value.code == "stale_write"
    assert caught.value.status_code == 409
    assert caught.value.correlation_id == "corr-409"
    assert caught.value.retryable is False


@pytest.mark.asyncio
async def test_oversized_response_is_stopped() -> None:
    async def oversized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 2049)

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(oversized),
        max_response_bytes=2048,
    ) as client:
        with pytest.raises(ERPError, match="response too large"):
            await client.get_current_user()


@pytest.mark.asyncio
async def test_schema_drift_is_reported_as_invalid_upstream_response() -> None:
    async def drift(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "user_id": 10,
                "employee_id": 25,
                "employee_code": "E0010",
                "display_name": "테스트 사용자",
                "client_id": "lss-erp-mcp-local",
                "resource": "lss-erp-api",
                "scopes": [],
                "unexpected": "field",
            },
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(drift),
    ) as client:
        with pytest.raises(ERPError, match="upstream_invalid_response"):
            await client.get_current_user()
