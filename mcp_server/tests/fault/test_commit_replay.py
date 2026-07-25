from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from lss_erp_mcp.confirmation import (
    ConfirmationStore,
    ConfirmationUnavailable,
)
from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.errors import ERPError
from lss_erp_mcp.tools.timesheets import commit_draft, prepare_draft
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


class TimeoutAfterFirstCommit(httpx.AsyncBaseTransport):
    def __init__(self, app) -> None:
        self.inner = httpx.ASGITransport(app=app)
        self.fired = False

    async def handle_async_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        response = await self.inner.handle_async_request(request)
        if request.method == "POST" and not self.fired:
            self.fired = True
            await response.aread()
            await response.aclose()
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                stream=TimeoutBodyStream(request),
                request=request,
            )
        return response

    async def aclose(self) -> None:
        await self.inner.aclose()


class TimeoutBodyStream(httpx.AsyncByteStream):
    def __init__(self, request: httpx.Request) -> None:
        self.request = request

    async def __aiter__(self):
        yield b"{"
        raise httpx.ReadTimeout(
            "response body lost after commit",
            request=self.request,
        )


async def prepare(
    client: ERPClient,
    store: ConfirmationStore,
    *,
    proposed: dict | None = None,
) -> str:
    result = await prepare_draft(
        client,
        store,
        week_start="2026-07-20",
        entries=[proposed or entry()],
    )
    token = result["confirmation_token"]
    assert isinstance(token, str)
    return token


@pytest.mark.asyncio
async def test_missing_confirmation_never_posts() -> None:
    state = ContractState()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        with pytest.raises(ConfirmationUnavailable):
            await commit_draft(
                client,
                ConfirmationStore(),
                confirmation_token="missing",
                idempotency_key=str(uuid4()),
            )
    assert state.post_count == 0


@pytest.mark.asyncio
async def test_expired_confirmation_never_posts() -> None:
    now = datetime(2026, 7, 25, tzinfo=UTC)
    state = ContractState()
    store = ConfirmationStore(ttl=timedelta(minutes=1), clock=lambda: now)
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        token = await prepare(client, store)
        store.clock = lambda: now + timedelta(minutes=2)
        with pytest.raises(ConfirmationUnavailable):
            await commit_draft(
                client,
                store,
                confirmation_token=token,
                idempotency_key=str(uuid4()),
            )
    assert state.post_count == 0


@pytest.mark.asyncio
async def test_different_user_never_posts() -> None:
    state = ContractState()
    store = ConfirmationStore()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        token = await prepare(client, store)
        state.user_id = 11
        with pytest.raises(PermissionError, match="user mismatch"):
            await commit_draft(
                client,
                store,
                confirmation_token=token,
                idempotency_key=str(uuid4()),
            )
    assert state.post_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("stale", "stale_write"),
        ("approved", "timesheet_not_draft"),
    ],
)
async def test_stale_or_protected_state_never_commits(
    mutation: str,
    expected_code: str,
) -> None:
    state = ContractState()
    store = ConfirmationStore()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        token = await prepare(client, store)
        if mutation == "stale":
            state.version += 1
        else:
            state.status = "승인"
        with pytest.raises(ERPError) as caught:
            await commit_draft(
                client,
                store,
                confirmation_token=token,
                idempotency_key=str(uuid4()),
            )
        assert caught.value.code == expected_code
        assert state.post_count == 0
        assert store.get(token).user_id == 10
        with pytest.raises(ConfirmationUnavailable, match="idempotency"):
            await commit_draft(
                client,
                store,
                confirmation_token=token,
                idempotency_key=str(uuid4()),
            )
    assert state.post_count == 0


@pytest.mark.asyncio
async def test_response_loss_retries_same_key_and_writes_once() -> None:
    state = ContractState()
    store = ConfirmationStore()
    transport = TimeoutAfterFirstCommit(create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        token = await prepare(client, store)
        result = await commit_draft(
            client,
            store,
            confirmation_token=token,
            idempotency_key=str(uuid4()),
        )

    assert result["verified"] is True
    assert result["reconciled_after_timeout"] is True
    assert result["idempotency_replayed"] is False
    assert state.post_count == 1


@pytest.mark.asyncio
async def test_unexpected_version_jump_is_not_reported_as_success() -> None:
    state = ContractState(version_increment=2)
    store = ConfirmationStore()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        token = await prepare(client, store)
        with pytest.raises(RuntimeError, match="verification_failed"):
            await commit_draft(
                client,
                store,
                confirmation_token=token,
                idempotency_key=str(uuid4()),
            )

    assert state.post_count == 1
    assert store.get(token).user_id == 10


@pytest.mark.asyncio
async def test_concurrent_confirmation_reuse_allows_only_one_commit() -> None:
    state = ContractState()
    store = ConfirmationStore()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        token = await prepare(client, store)
        results = await asyncio.gather(
            commit_draft(
                client,
                store,
                confirmation_token=token,
                idempotency_key=str(uuid4()),
            ),
            commit_draft(
                client,
                store,
                confirmation_token=token,
                idempotency_key=str(uuid4()),
            ),
            return_exceptions=True,
        )

    assert sum(isinstance(item, dict) for item in results) == 1
    assert sum(
        isinstance(item, ConfirmationUnavailable) for item in results
    ) == 1
    assert state.post_count == 1


@pytest.mark.asyncio
async def test_same_key_with_changed_body_is_rejected() -> None:
    state = ContractState()
    store = ConfirmationStore()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    key = str(uuid4())
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        first_token = await prepare(client, store)
        await commit_draft(
            client,
            store,
            confirmation_token=first_token,
            idempotency_key=key,
        )
        second_token = await prepare(
            client,
            store,
            proposed=entry(hours=6.0),
        )
        with pytest.raises(ERPError) as caught:
            await commit_draft(
                client,
                store,
                confirmation_token=second_token,
                idempotency_key=key,
            )

    assert caught.value.code == "idempotency_conflict"
    assert state.post_count == 1


@pytest.mark.asyncio
async def test_post_write_readback_mismatch_is_not_reported_as_success() -> None:
    state = ContractState()
    store = ConfirmationStore()
    transport = httpx.ASGITransport(app=create_contract_app(state))
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        token = await prepare(client, store)
        state.readback_entries_override = []
        with pytest.raises(RuntimeError, match="verification_failed"):
            await commit_draft(
                client,
                store,
                confirmation_token=token,
                idempotency_key=str(uuid4()),
            )

    assert state.post_count == 1
    assert store.get(token).user_id == 10
