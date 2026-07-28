from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import TypeVar
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ValidationError

from .errors import ERPError
from .schemas.schedule import (
    ScheduleDeleteResult,
    ScheduleDetail,
    ScheduleEnvelope,
    ScheduleListData,
    ScheduleListRequest,
    ScheduleMutationRequest,
    ScheduleOperationData,
    SchedulePreflightData,
    SchedulePreflightRequest,
    ScheduleUpsertResult,
)
from .schemas.timesheet import (
    CurrentUser,
    DraftWriteRequest,
    DraftWriteResult,
    ProjectSearch,
    TimesheetEntryContext,
    TimesheetWeek,
)


ALLOWLIST = {
    ("GET", "/api/auth/me"),
    ("GET", "/api/timesheets/week"),
    ("GET", "/api/timesheets/entry-context"),
    ("GET", "/api/timesheets/projects"),
    ("POST", "/api/timesheets/mcp-draft"),
    ("GET", "/api/mcp/schedules"),
    ("GET", "/api/mcp/schedules/{event_id}"),
    ("POST", "/api/mcp/schedules/preflight"),
    ("GET", "/api/mcp/schedules/operations/{correlation_id}"),
    ("POST", "/api/schedules"),
    ("PUT", "/api/schedules/{event_id}"),
    ("DELETE", "/api/schedules/{event_id}"),
}

ModelT = TypeVar("ModelT", bound=BaseModel)
_EVENT_ID_RE = re.compile(r"^[0-9a-v]{8,255}$")
_CORRELATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_ETAG_RE = re.compile(r'^"[A-Za-z0-9._:-]{1,253}"$')
_ERROR_CODE_RE = re.compile(r"^[a-z0-9_:-]{1,64}$")
_QUERY_ALLOWLIST = {
    ("GET", "/api/auth/me"): frozenset(),
    ("GET", "/api/timesheets/week"): frozenset({"week_start"}),
    ("GET", "/api/timesheets/entry-context"): frozenset({"week_start"}),
    ("GET", "/api/timesheets/projects"): frozenset({"q", "limit"}),
    ("POST", "/api/timesheets/mcp-draft"): frozenset(),
    ("GET", "/api/mcp/schedules"): frozenset(
        {"category", "start_date", "end_date", "limit"}
    ),
    ("GET", "/api/mcp/schedules/{event_id}"): frozenset({"category"}),
    ("POST", "/api/mcp/schedules/preflight"): frozenset(),
    ("GET", "/api/mcp/schedules/operations/{correlation_id}"): frozenset(),
    ("POST", "/api/schedules"): frozenset(),
    ("PUT", "/api/schedules/{event_id}"): frozenset(),
    ("DELETE", "/api/schedules/{event_id}"): frozenset({"category"}),
}
_SCHEDULE_ROUTE_TEMPLATES = frozenset(
    {
        ("GET", "/api/mcp/schedules"),
        ("GET", "/api/mcp/schedules/{event_id}"),
        ("POST", "/api/mcp/schedules/preflight"),
        ("GET", "/api/mcp/schedules/operations/{correlation_id}"),
        ("POST", "/api/schedules"),
        ("PUT", "/api/schedules/{event_id}"),
        ("DELETE", "/api/schedules/{event_id}"),
    }
)


def _validate_response(model: type[ModelT], payload: dict[str, object]) -> ModelT:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise ERPError(
            "upstream_invalid_response",
            "ERP API response schema mismatch",
            False,
        ) from exc


def _validated_identifier(
    value: str,
    *,
    pattern: re.Pattern[str],
    name: str,
) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"invalid schedule {name}")
    return value


def build_schedule_event_path(event_id: str) -> str:
    """Build the MCP detail path from one validated Google event ID."""
    value = _validated_identifier(event_id, pattern=_EVENT_ID_RE, name="event_id")
    return f"/api/mcp/schedules/{value}"


def _build_schedule_mutation_path(event_id: str) -> str:
    value = _validated_identifier(event_id, pattern=_EVENT_ID_RE, name="event_id")
    return f"/api/schedules/{value}"


def build_schedule_operation_path(correlation_id: str) -> str:
    """Build the operation-status path from one validated correlation ID."""
    value = _validated_identifier(
        correlation_id,
        pattern=_CORRELATION_ID_RE,
        name="correlation_id",
    )
    return f"/api/mcp/schedules/operations/{value}"


def _allowlisted_route_template(method: str, path: str) -> tuple[str, str] | None:
    key = (method.upper(), path)
    if key in ALLOWLIST:
        return key
    try:
        if method.upper() == "GET" and path.startswith(
            "/api/mcp/schedules/operations/"
        ):
            correlation_id = path.removeprefix(
                "/api/mcp/schedules/operations/"
            )
            if path == build_schedule_operation_path(correlation_id):
                return ("GET", "/api/mcp/schedules/operations/{correlation_id}")
        if method.upper() == "GET" and path.startswith("/api/mcp/schedules/"):
            event_id = path.removeprefix("/api/mcp/schedules/")
            if path == build_schedule_event_path(event_id):
                return ("GET", "/api/mcp/schedules/{event_id}")
        if method.upper() in {"PUT", "DELETE"} and path.startswith(
            "/api/schedules/"
        ):
            event_id = path.removeprefix("/api/schedules/")
            if path == _build_schedule_mutation_path(event_id):
                return (method.upper(), "/api/schedules/{event_id}")
    except ValueError:
        return None
    return None


def _schedule_write_headers(
    *,
    idempotency_key: str,
    correlation_id: str,
    etag: str | None = None,
) -> dict[str, str]:
    key = _validated_identifier(
        idempotency_key,
        pattern=_OPERATION_ID_RE,
        name="idempotency_key",
    )
    correlation = _validated_identifier(
        correlation_id,
        # The operation-status route is intentionally narrower than the
        # idempotency header. Only issue correlation IDs that can be queried.
        pattern=_CORRELATION_ID_RE,
        name="correlation_id",
    )
    headers = {
        "Idempotency-Key": key,
        "X-Correlation-ID": correlation,
        "X-LSS-MCP-Schedule": "1",
    }
    if etag is not None:
        headers["If-Match"] = _validated_identifier(
            etag,
            pattern=_ETAG_RE,
            name="etag",
        )
    return headers


def _schedule_body(request: ScheduleMutationRequest) -> dict[str, object]:
    # The legacy endpoint requires user_name, but MCP authority comes only from
    # its bearer token. Supplying a fixed empty presentation value prevents a
    # caller-selected owner identity from crossing this boundary.
    return {
        **request.model_dump(mode="json", exclude_none=True),
        "user_name": "",
    }


def _require_exact_kwargs(
    kwargs: dict[str, object],
    expected: set[str],
) -> None:
    if set(kwargs) != expected:
        raise ValueError("schedule REST kwargs do not match the typed contract")


def _require_dict(value: object, *, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"schedule {name} must be an object")
    return value


def _validate_schedule_headers(
    value: object,
    *,
    require_etag: bool,
) -> None:
    headers = _require_dict(value, name="headers")
    expected_names = {
        "Idempotency-Key",
        "X-Correlation-ID",
        "X-LSS-MCP-Schedule",
    }
    if require_etag:
        expected_names.add("If-Match")
    if set(headers) != expected_names:
        raise ValueError("schedule control headers do not match the typed contract")
    if not all(isinstance(item, str) for item in headers.values()):
        raise ValueError("schedule control header values must be strings")
    canonical = _schedule_write_headers(
        idempotency_key=headers["Idempotency-Key"],
        correlation_id=headers["X-Correlation-ID"],
        etag=headers.get("If-Match") if require_etag else None,
    )
    if headers != canonical:
        raise ValueError("schedule control headers are not canonical")


def _validate_schedule_mutation_body(value: object) -> None:
    body = _require_dict(value, name="JSON body")
    if body.get("user_name") != "":
        raise ValueError("schedule user_name must be the generated empty value")
    model_input = dict(body)
    model_input.pop("user_name")
    try:
        request = ScheduleMutationRequest.model_validate(model_input)
    except ValidationError as exc:
        raise ValueError("schedule mutation body is invalid") from exc
    if body != _schedule_body(request):
        raise ValueError("schedule mutation body is not canonical")


def _validate_schedule_list_query(value: object) -> None:
    params = _require_dict(value, name="query")
    try:
        request = ScheduleListRequest.model_validate(params)
    except ValidationError as exc:
        raise ValueError("schedule list query is invalid") from exc
    if params != request.model_dump(mode="json", exclude_none=True):
        raise ValueError("schedule list query is not canonical")


def _validate_schedule_category_query(value: object) -> None:
    params = _require_dict(value, name="query")
    if set(params) != {"category"} or params["category"] not in {
        "company",
        "refresh",
    }:
        raise ValueError("schedule category query is invalid")


def _validate_schedule_preflight_body(value: object) -> None:
    body = _require_dict(value, name="JSON body")
    try:
        request = SchedulePreflightRequest.model_validate(body)
    except ValidationError as exc:
        raise ValueError("schedule preflight body is invalid") from exc
    if body != request.model_dump(mode="json", exclude_none=True):
        raise ValueError("schedule preflight body is not canonical")


def _validate_schedule_route_request(
    route_template: tuple[str, str],
    kwargs: dict[str, object],
) -> None:
    """Enforce schedule authority and shape below every public client method."""
    if route_template == ("GET", "/api/mcp/schedules"):
        _require_exact_kwargs(kwargs, {"params"})
        _validate_schedule_list_query(kwargs["params"])
        return
    if route_template == ("GET", "/api/mcp/schedules/{event_id}"):
        _require_exact_kwargs(kwargs, {"params"})
        _validate_schedule_category_query(kwargs["params"])
        return
    if route_template == ("POST", "/api/mcp/schedules/preflight"):
        _require_exact_kwargs(kwargs, {"json"})
        _validate_schedule_preflight_body(kwargs["json"])
        return
    if route_template == (
        "GET",
        "/api/mcp/schedules/operations/{correlation_id}",
    ):
        _require_exact_kwargs(kwargs, set())
        return
    if route_template == ("POST", "/api/schedules"):
        _require_exact_kwargs(kwargs, {"json", "headers"})
        _validate_schedule_headers(kwargs["headers"], require_etag=False)
        _validate_schedule_mutation_body(kwargs["json"])
        return
    if route_template == ("PUT", "/api/schedules/{event_id}"):
        _require_exact_kwargs(kwargs, {"json", "headers"})
        _validate_schedule_headers(kwargs["headers"], require_etag=True)
        _validate_schedule_mutation_body(kwargs["json"])
        return
    if route_template == ("DELETE", "/api/schedules/{event_id}"):
        _require_exact_kwargs(kwargs, {"params", "headers"})
        _validate_schedule_headers(kwargs["headers"], require_etag=True)
        _validate_schedule_category_query(kwargs["params"])
        return
    raise ValueError("schedule REST route policy is missing")


DataT = TypeVar("DataT")


def _validate_envelope_data(
    model: type[DataT],
    payload: dict[str, object],
) -> DataT:
    envelope = _validate_response(ScheduleEnvelope[model], payload)
    return envelope.data


def _upstream_binding_error() -> ERPError:
    return ERPError(
        "upstream_invalid_response",
        "ERP API response schema mismatch",
        False,
    )


def _schedule_item_start_date(item: object) -> date:
    if getattr(item, "is_all_day", None) is True:
        return getattr(item, "start_date")
    return getattr(item, "start_time").date()


def _proposal_matches_projection(
    request: SchedulePreflightRequest,
    result: SchedulePreflightData,
) -> bool:
    proposal = request.desired
    projection = result.desired
    if proposal is None or projection is None:
        return proposal is None and projection is None
    if proposal.is_all_day is not projection.is_all_day:
        return False
    if proposal.is_all_day:
        return (
            proposal.date == projection.start_date
            and proposal.end_date == projection.end_date
        )
    return (
        proposal.start_time == projection.start_time
        and proposal.end_time == projection.end_time
    )


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
        route_template = _allowlisted_route_template(method, path)
        if route_template is None:
            raise ValueError(f"REST path is not allowlisted: {key}")
        if route_template in _SCHEDULE_ROUTE_TEMPLATES:
            _validate_schedule_route_request(route_template, kwargs)
        else:
            params = kwargs.get("params")
            if params is not None:
                if not isinstance(params, dict):
                    raise ValueError(
                        "REST query parameters must use a bounded mapping"
                    )
                allowed_query = _QUERY_ALLOWLIST[route_template]
                if not set(params).issubset(allowed_query):
                    raise ValueError("REST query parameter is not allowlisted")

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
                raw_detail = payload.get("error") or payload.get("detail") or {}
                detail = raw_detail if isinstance(raw_detail, dict) else {}
                schedule_route = route_template in _SCHEDULE_ROUTE_TEMPLATES
                if schedule_route:
                    raw_code = detail.get("code")
                    code = (
                        raw_code
                        if isinstance(raw_code, str)
                        and _ERROR_CODE_RE.fullmatch(raw_code)
                        else None
                    )
                    if (
                        code is None
                        and isinstance(raw_detail, str)
                        and _ERROR_CODE_RE.fullmatch(raw_detail)
                    ):
                        code = raw_detail
                    raw_correlation = detail.get("correlation_id")
                    correlation_id = (
                        raw_correlation
                        if isinstance(raw_correlation, str)
                        and _CORRELATION_ID_RE.fullmatch(raw_correlation)
                        else None
                    )
                    response_correlation = response.headers.get(
                        "X-Correlation-ID"
                    )
                    if (
                        correlation_id is None
                        and response_correlation is not None
                        and _CORRELATION_ID_RE.fullmatch(response_correlation)
                    ):
                        correlation_id = response_correlation
                    message = None
                    details: object = {}
                else:
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
        except ERPError:
            raise
        except httpx.TimeoutException as exc:
            raise ERPError(
                "upstream_timeout",
                "ERP API timed out",
                True,
                response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise ERPError(
                "upstream_unavailable",
                "ERP API response failed",
                True,
                response.status_code,
            ) from exc
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
        result = _validate_response(TimesheetWeek, data)
        if (
            result.week_start != week_start
            or result.week_end != week_start + timedelta(days=6)
        ):
            raise ERPError(
                "upstream_invalid_response",
                "ERP API week mismatch",
                False,
            )
        return result

    async def get_entry_context(self, week_start: date) -> TimesheetEntryContext:
        data = await self._request(
            "GET",
            "/api/timesheets/entry-context",
            params={"week_start": week_start.isoformat()},
        )
        result = _validate_response(TimesheetEntryContext, data)
        if (
            result.week_start != week_start
            or result.week_end != week_start + timedelta(days=6)
        ):
            raise ERPError(
                "upstream_invalid_response",
                "ERP API context week mismatch",
                False,
            )
        return result

    async def search_projects(self, query: str, limit: int = 20) -> ProjectSearch:
        if len(query) > 100:
            raise ValueError("project query must not exceed 100 characters")
        if not 1 <= limit <= 50:
            raise ValueError("project limit must be between 1 and 50")
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

    async def list_schedules(
        self,
        *,
        category: str = "company",
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
    ) -> ScheduleListData:
        request = ScheduleListRequest(
            category=category,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        data = await self._request(
            "GET",
            "/api/mcp/schedules",
            params=request.model_dump(mode="json", exclude_none=True),
        )
        result = _validate_envelope_data(ScheduleListData, data)
        if result.count > request.limit:
            raise _upstream_binding_error()
        for item in result.items:
            item_start = _schedule_item_start_date(item)
            if item.category != request.category:
                raise _upstream_binding_error()
            if request.start_date is not None and item_start < request.start_date:
                raise _upstream_binding_error()
            if request.end_date is not None and item_start > request.end_date:
                raise _upstream_binding_error()
        return result

    async def get_schedule(
        self,
        event_id: str,
        *,
        category: str = "company",
    ) -> ScheduleDetail:
        request = ScheduleListRequest(category=category)
        data = await self._request(
            "GET",
            build_schedule_event_path(event_id),
            params={"category": request.category},
        )
        result = _validate_envelope_data(ScheduleDetail, data)
        if result.event_id != event_id or result.category != request.category:
            raise _upstream_binding_error()
        return result

    async def preflight_schedule(
        self,
        request: SchedulePreflightRequest,
    ) -> SchedulePreflightData:
        data = await self._request(
            "POST",
            "/api/mcp/schedules/preflight",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        result = _validate_envelope_data(SchedulePreflightData, data)
        if (
            result.action != request.action
            or result.category != request.category
            or result.event_id != request.event_id
            or not _proposal_matches_projection(request, result)
        ):
            raise _upstream_binding_error()
        return result

    async def create_schedule(
        self,
        request: ScheduleMutationRequest,
        *,
        idempotency_key: str,
        correlation_id: str,
    ) -> ScheduleUpsertResult:
        data = await self._request(
            "POST",
            "/api/schedules",
            json=_schedule_body(request),
            headers=_schedule_write_headers(
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            ),
        )
        return _validate_response(ScheduleUpsertResult, data)

    async def update_schedule(
        self,
        event_id: str,
        request: ScheduleMutationRequest,
        *,
        etag: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ScheduleUpsertResult:
        data = await self._request(
            "PUT",
            _build_schedule_mutation_path(event_id),
            json=_schedule_body(request),
            headers=_schedule_write_headers(
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                etag=etag,
            ),
        )
        result = _validate_response(ScheduleUpsertResult, data)
        if result.event_id != event_id:
            raise _upstream_binding_error()
        return result

    async def delete_schedule(
        self,
        event_id: str,
        *,
        category: str,
        etag: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ScheduleDeleteResult:
        request = ScheduleListRequest(category=category)
        data = await self._request(
            "DELETE",
            _build_schedule_mutation_path(event_id),
            params={"category": request.category},
            headers=_schedule_write_headers(
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                etag=etag,
            ),
        )
        return _validate_response(ScheduleDeleteResult, data)

    async def get_schedule_operation(
        self,
        correlation_id: str,
    ) -> ScheduleOperationData:
        data = await self._request(
            "GET",
            build_schedule_operation_path(correlation_id),
        )
        envelope = _validate_response(
            ScheduleEnvelope[ScheduleOperationData],
            data,
        )
        result = envelope.data
        if (
            result.correlation_id != correlation_id
            or envelope.meta.correlation_id != result.correlation_id
        ):
            raise _upstream_binding_error()
        return result
