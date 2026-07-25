from __future__ import annotations

import json
from datetime import date
from typing import TypeVar
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ValidationError

from .errors import ERPError
from .schemas.timesheet import (
    CurrentUser,
    DraftWriteRequest,
    DraftWriteResult,
    ProjectSearch,
    TimesheetWeek,
)


ALLOWLIST = {
    ("GET", "/api/auth/me"),
    ("GET", "/api/timesheets/week"),
    ("GET", "/api/timesheets/projects"),
    ("POST", "/api/timesheets/mcp-draft"),
}

ModelT = TypeVar("ModelT", bound=BaseModel)


def _validate_response(model: type[ModelT], payload: dict[str, object]) -> ModelT:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise ERPError(
            "upstream_invalid_response",
            "ERP API response schema mismatch",
            False,
        ) from exc


class ERPClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        transport: httpx.AsyncBaseTransport | None = None,
        connect_timeout_seconds: float = 2,
        read_timeout_seconds: float = 10,
        write_timeout_seconds: float = 10,
        pool_timeout_seconds: float = 2,
        max_response_bytes: int = 65536,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("base_url must be a credential-free HTTP origin")
        if not token.strip():
            raise ValueError("ERP API token must not be empty")
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")

        self._max_response_bytes = max_response_bytes
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
            timeout=httpx.Timeout(
                connect=connect_timeout_seconds,
                read=read_timeout_seconds,
                write=write_timeout_seconds,
                pool=pool_timeout_seconds,
            ),
            transport=transport,
        )

    async def __aenter__(self) -> "ERPClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: object,
    ) -> dict[str, object]:
        key = (method.upper(), path)
        if key not in ALLOWLIST:
            raise ValueError(f"REST path is not allowlisted: {key}")

        request = self._client.build_request(method, path, **kwargs)
        try:
            response = await self._client.send(request, stream=True)
        except httpx.TimeoutException as exc:
            raise ERPError("upstream_timeout", "ERP API timed out", True) from exc
        except httpx.RequestError as exc:
            raise ERPError(
                "upstream_unavailable",
                "ERP API request failed",
                True,
            ) from exc

        try:
            if response.is_redirect:
                raise ERPError(
                    "upstream_redirect_rejected",
                    "ERP API redirect was rejected",
                    False,
                    response.status_code,
                )

            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > self._max_response_bytes:
                    raise ERPError(
                        "upstream_invalid_response",
                        "response too large",
                        False,
                        response.status_code,
                    )

            try:
                payload = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ERPError(
                    "upstream_invalid_response",
                    "invalid JSON",
                    False,
                    response.status_code,
                ) from exc

            if not isinstance(payload, dict):
                raise ERPError(
                    "upstream_invalid_response",
                    "expected object",
                    False,
                    response.status_code,
                )

            if response.is_error:
                detail = payload.get("error") or payload.get("detail") or {}
                if not isinstance(detail, dict):
                    detail = {}
                code = detail.get("code")
                message = detail.get("message")
                correlation_id = detail.get("correlation_id")
                details = detail.get("details")
                declared_retryable = detail.get("retryable")
                retryable = (
                    declared_retryable
                    if isinstance(declared_retryable, bool)
                    else response.status_code in {429, 502, 503, 504}
                )
                raise ERPError(
                    code if isinstance(code, str) else f"http_{response.status_code}",
                    message
                    if isinstance(message, str)
                    else "ERP API rejected the request",
                    retryable,
                    response.status_code,
                    correlation_id if isinstance(correlation_id, str) else None,
                    details if isinstance(details, dict) else {},
                )
            return payload
        finally:
            await response.aclose()

    async def get_current_user(self) -> CurrentUser:
        data = await self._request("GET", "/api/auth/me")
        return _validate_response(CurrentUser, data)

    async def get_week(self, week_start: date) -> TimesheetWeek:
        data = await self._request(
            "GET",
            "/api/timesheets/week",
            params={"week_start": week_start.isoformat()},
        )
        return _validate_response(TimesheetWeek, data)

    async def search_projects(self, query: str, limit: int = 20) -> ProjectSearch:
        data = await self._request(
            "GET",
            "/api/timesheets/projects",
            params={"q": query, "limit": limit},
        )
        return _validate_response(ProjectSearch, data)

    async def save_draft(
        self,
        request: DraftWriteRequest,
        *,
        idempotency_key: UUID,
        correlation_id: UUID,
    ) -> DraftWriteResult:
        data = await self._request(
            "POST",
            "/api/timesheets/mcp-draft",
            json=request.model_dump(mode="json"),
            headers={
                "Idempotency-Key": str(idempotency_key),
                "X-Correlation-ID": str(correlation_id),
            },
        )
        return _validate_response(DraftWriteResult, data)
