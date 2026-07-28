from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import httpx
import pytest

from lss_erp_mcp.erp_client import (
    ALLOWLIST,
    ERPClient,
    build_schedule_event_path,
    build_schedule_operation_path,
)
from lss_erp_mcp.errors import ERPError
from lss_erp_mcp.schemas.schedule import (
    ScheduleAllDayProposal,
    ScheduleListData,
    ScheduleMutationRequest,
    ScheduleOperationData,
    SchedulePreflightRequest,
)


EVENT_ID = "a23456789bcdefg"
CORRELATION_ID = "corr-client-001"
IDEMPOTENCY_KEY = "idem-client-001"
ETAG = '"etag-safe"'


def _envelope(data: dict[str, object]) -> dict[str, object]:
    return {
        "success": True,
        "data": data,
        "error": None,
        "meta": {
            "correlation_id": CORRELATION_ID,
            "timestamp": "2026-07-27T00:00:00Z",
        },
    }


def _mutation_request() -> ScheduleMutationRequest:
    return ScheduleMutationRequest(
        content="Customer visit",
        type="#722ed1",
        category="company",
        is_all_day=True,
        date=date(2026, 8, 3),
        end_date=date(2026, 8, 3),
        schedule_kind="출장",
        timesheet_project_id=123,
        timesheet_project_name="ERP",
        timesheet_project_source="실행",
    )


def _canonical_mutation_body() -> dict[str, object]:
    return {
        **_mutation_request().model_dump(mode="json", exclude_none=True),
        "user_name": "",
    }


def _create_headers() -> dict[str, str]:
    return {
        "Idempotency-Key": IDEMPOTENCY_KEY,
        "X-Correlation-ID": CORRELATION_ID,
        "X-LSS-MCP-Schedule": "1",
    }


def _update_headers() -> dict[str, str]:
    return {**_create_headers(), "If-Match": ETAG}


def test_schedule_allowlist_contains_only_fixed_contract_templates() -> None:
    assert ALLOWLIST == {
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
    assert not any("http://" in path or "https://" in path for _method, path in ALLOWLIST)


@pytest.mark.parametrize(
    "builder,value",
    [
        (build_schedule_event_path, "../admin/users"),
        (build_schedule_event_path, "a23456789?category=refresh"),
        (build_schedule_event_path, "A23456789"),
        (build_schedule_operation_path, "../corr-client-001"),
        (build_schedule_operation_path, "corr-client-001?target=other"),
        (build_schedule_operation_path, "https://evil.example/x"),
    ],
)
def test_dedicated_path_builders_reject_traversal_and_arbitrary_urls(
    builder,
    value: str,
) -> None:
    with pytest.raises(ValueError):
        builder(value)


def test_dedicated_path_builders_return_only_validated_relative_paths() -> None:
    assert build_schedule_event_path(EVENT_ID) == f"/api/mcp/schedules/{EVENT_ID}"
    assert (
        build_schedule_operation_path(CORRELATION_ID)
        == f"/api/mcp/schedules/operations/{CORRELATION_ID}"
    )


@pytest.mark.asyncio
async def test_list_uses_bounded_query_and_object_envelope() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json=_envelope(
                {
                    "items": [
                        {
                            "event_id": EVENT_ID,
                            "category": "company",
                            "is_all_day": True,
                            "schedule_kind": "출장",
                            "start_date": "2026-08-03",
                            "end_date": "2026-08-03",
                        }
                    ],
                    "count": 1,
                }
            ),
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await client.list_schedules(
            category="company",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            limit=10,
        )

    assert isinstance(result, ScheduleListData)
    assert result.count == len(result.items) == 1
    assert seen[0].url.path == "/api/mcp/schedules"
    assert dict(seen[0].url.params) == {
        "category": "company",
        "start_date": "2026-08-01",
        "end_date": "2026-08-31",
        "limit": "10",
    }


@pytest.mark.asyncio
async def test_list_rejects_an_arbitrary_json_list_instead_of_an_envelope() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ERPError, match="expected object"):
            await client.list_schedules()


@pytest.mark.asyncio
async def test_list_rejects_envelope_or_count_drift() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope({"items": [], "count": 1}) | {"unexpected": True},
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ERPError, match="schema mismatch"):
            await client.list_schedules()


@pytest.mark.asyncio
async def test_get_and_preflight_use_only_the_dedicated_routes() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json=_envelope(
                    {
                        "event_id": EVENT_ID,
                        "category": "company",
                        "is_all_day": True,
                        "schedule_kind": "출장",
                        "start_date": "2026-08-03",
                        "end_date": "2026-08-03",
                        "etag": ETAG,
                        "owner_binding": {"state": "BOUND", "write_allowed": True},
                        "eligibility": {"write_allowed": True, "denial_reasons": []},
                    }
                ),
            )
        return httpx.Response(
            200,
            json=_envelope(
                {
                    "action": "DELETE",
                    "category": "company",
                    "event_id": EVENT_ID,
                    "current": {
                        "event_id": EVENT_ID,
                        "category": "company",
                        "is_all_day": True,
                        "schedule_kind": "출장",
                        "start_date": "2026-08-03",
                        "end_date": "2026-08-03",
                    },
                    "desired": None,
                    "owner_binding": {"state": "BOUND", "write_allowed": True},
                    "affected_weeks": ["2026-08-03"],
                    "timesheet_statuses": [],
                    "etag": ETAG,
                    "write_allowed": True,
                    "denial_reasons": [],
                }
            ),
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        detail = await client.get_schedule(EVENT_ID, category="company")
        preflight = await client.preflight_schedule(
            SchedulePreflightRequest(
                action="DELETE",
                category="company",
                event_id=EVENT_ID,
            )
        )

    assert detail.etag == ETAG
    assert preflight.write_allowed is True
    assert [(request.method, request.url.path) for request in seen] == [
        ("GET", f"/api/mcp/schedules/{EVENT_ID}"),
        ("POST", "/api/mcp/schedules/preflight"),
    ]


@pytest.mark.asyncio
async def test_writes_generate_control_headers_and_do_not_accept_header_passthrough() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        response = (
            {"status": "success"}
            if request.method == "DELETE"
            else {"status": "success", "id": EVENT_ID}
        )
        return httpx.Response(200, json=response)

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        created = await client.create_schedule(
            _mutation_request(),
            idempotency_key=IDEMPOTENCY_KEY,
            correlation_id=CORRELATION_ID,
        )
        updated = await client.update_schedule(
            EVENT_ID,
            _mutation_request(),
            etag=ETAG,
            idempotency_key="idem-client-002",
            correlation_id="corr-client-002",
        )
        deleted = await client.delete_schedule(
            EVENT_ID,
            category="company",
            etag=ETAG,
            idempotency_key="idem-client-003",
            correlation_id="corr-client-003",
        )

    assert created.event_id == updated.event_id == EVENT_ID
    assert deleted.status == "success"
    assert [(item.method, item.url.path) for item in seen] == [
        ("POST", "/api/schedules"),
        ("PUT", f"/api/schedules/{EVENT_ID}"),
        ("DELETE", f"/api/schedules/{EVENT_ID}"),
    ]
    for request in seen:
        assert request.headers["X-LSS-MCP-Schedule"] == "1"
        assert request.headers["Idempotency-Key"].startswith("idem-client-")
        assert request.headers["X-Correlation-ID"].startswith("corr-client-")
        assert "X-User-ID" not in request.headers
    assert "If-Match" not in seen[0].headers
    assert seen[1].headers["If-Match"] == ETAG
    assert seen[2].headers["If-Match"] == ETAG
    for request in seen[:2]:
        body = json.loads(request.content)
        assert body["user_name"] == ""
        assert "user_id" not in body
        assert "employee_id" not in body

    with pytest.raises(TypeError):
        await client.create_schedule(  # type: ignore[call-arg]
            _mutation_request(),
            idempotency_key=IDEMPOTENCY_KEY,
            correlation_id=CORRELATION_ID,
            headers={"X-User-ID": "999"},
        )


@pytest.mark.asyncio
async def test_direct_create_request_cannot_bypass_headers_body_or_kwargs() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"status": "success", "id": EVENT_ID})

    body = _canonical_mutation_body()
    headers = _create_headers()
    bad_kwargs = [
        {"json": body, "headers": headers | {"Authorization": "Bearer other"}},
        {"json": body, "headers": headers | {"X-User-ID": "999"}},
        {"json": body, "headers": headers | {"X-Custom": "unsafe"}},
        *[
            {
                "json": body,
                "headers": {
                    name: value
                    for name, value in headers.items()
                    if name != missing
                },
            }
            for missing in headers
        ],
        {"json": body, "headers": headers | {"X-LSS-MCP-Schedule": "0"}},
        {"json": body | {"user_id": 999}, "headers": headers},
        {"json": body | {"employee_id": 999}, "headers": headers},
        {"json": body | {"user_name": "Mallory"}, "headers": headers},
        {"json": body | {"extra": "unsafe"}, "headers": headers},
        {"json": body, "headers": headers, "params": {"category": "company"}},
        {"data": json.dumps(body), "headers": headers},
        {"headers": headers},
    ]

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        for kwargs in bad_kwargs:
            with pytest.raises(ValueError):
                await client._request("POST", "/api/schedules", **kwargs)

    assert calls == 0


@pytest.mark.asyncio
async def test_direct_update_request_cannot_bypass_headers_body_or_kwargs() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"status": "success", "id": EVENT_ID})

    body = _canonical_mutation_body()
    headers = _update_headers()
    path = f"/api/schedules/{EVENT_ID}"
    bad_kwargs = [
        {"json": body, "headers": headers | {"Authorization": "Bearer other"}},
        {"json": body, "headers": headers | {"X-User-ID": "999"}},
        {"json": body, "headers": headers | {"X-Custom": "unsafe"}},
        *[
            {
                "json": body,
                "headers": {
                    name: value
                    for name, value in headers.items()
                    if name != missing
                },
            }
            for missing in headers
        ],
        {"json": body, "headers": headers | {"If-Match": "*"}},
        {"json": body | {"user_id": 999}, "headers": headers},
        {"json": body | {"employee_id": 999}, "headers": headers},
        {"json": body | {"user_name": "Mallory"}, "headers": headers},
        {"json": body | {"extra": "unsafe"}, "headers": headers},
        {"json": body, "headers": headers, "params": {"category": "company"}},
        {"content": json.dumps(body), "headers": headers},
    ]

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        for kwargs in bad_kwargs:
            with pytest.raises(ValueError):
                await client._request("PUT", path, **kwargs)

    assert calls == 0


@pytest.mark.asyncio
async def test_direct_delete_request_cannot_bypass_headers_query_or_kwargs() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"status": "success"})

    headers = _update_headers()
    path = f"/api/schedules/{EVENT_ID}"
    valid_params = {"category": "company"}
    bad_kwargs = [
        {"params": valid_params, "headers": headers | {"Authorization": "Bearer other"}},
        {"params": valid_params, "headers": headers | {"X-User-ID": "999"}},
        {"params": valid_params, "headers": headers | {"X-Custom": "unsafe"}},
        *[
            {
                "params": valid_params,
                "headers": {
                    name: value
                    for name, value in headers.items()
                    if name != missing
                },
            }
            for missing in headers
        ],
        {"params": valid_params, "headers": headers | {"If-Match": "*"}},
        {"params": {"category": "other"}, "headers": headers},
        {"params": valid_params | {"target": "other"}, "headers": headers},
        {"params": valid_params, "headers": headers, "json": {"user_id": 999}},
        {"headers": headers},
    ]

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        for kwargs in bad_kwargs:
            with pytest.raises(ValueError):
                await client._request("DELETE", path, **kwargs)

    assert calls == 0


@pytest.mark.asyncio
async def test_direct_schedule_reads_and_preflight_enforce_exact_kwargs() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    attempts = [
        ("GET", "/api/mcp/schedules", {"params": {"category": "company", "limit": "10"}}),
        ("GET", "/api/mcp/schedules", {"json": {"category": "company"}}),
        (
            "GET",
            f"/api/mcp/schedules/{EVENT_ID}",
            {"params": {"category": "company", "target": "other"}},
        ),
        (
            "GET",
            f"/api/mcp/schedules/{EVENT_ID}",
            {"params": {"category": "company"}, "headers": {"X-Custom": "unsafe"}},
        ),
        (
            "POST",
            "/api/mcp/schedules/preflight",
            {
                "json": {
                    "action": "CREATE",
                    "category": "company",
                    "event_id": EVENT_ID,
                    "desired": {
                        "is_all_day": True,
                        "date": "2026-08-03",
                        "end_date": "2026-08-03",
                    },
                }
            },
        ),
        (
            "POST",
            "/api/mcp/schedules/preflight",
            {
                "json": {
                    "action": "DELETE",
                    "category": "company",
                    "event_id": EVENT_ID,
                },
                "headers": {"X-Custom": "unsafe"},
            },
        ),
        (
            "GET",
            f"/api/mcp/schedules/operations/{CORRELATION_ID}",
            {"params": {"target": "other"}},
        ),
    ]

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        for method, path, kwargs in attempts:
            with pytest.raises(ValueError):
                await client._request(method, path, **kwargs)

    assert calls == 0


@pytest.mark.asyncio
async def test_write_identifier_and_etag_inputs_are_validated_before_transport() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"status": "success", "id": EVENT_ID})

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ValueError, match="idempotency"):
            await client.create_schedule(
                _mutation_request(),
                idempotency_key="../reuse",
                correlation_id=CORRELATION_ID,
            )
        with pytest.raises(ValueError, match="correlation"):
            await client.create_schedule(
                _mutation_request(),
                idempotency_key=IDEMPOTENCY_KEY,
                correlation_id="../corr",
            )
        with pytest.raises(ValueError, match="correlation"):
            await client.create_schedule(
                _mutation_request(),
                idempotency_key=IDEMPOTENCY_KEY,
                correlation_id="corr.client-001",
            )
        with pytest.raises(ValueError, match="etag"):
            await client.update_schedule(
                EVENT_ID,
                _mutation_request(),
                etag="*",
                idempotency_key=IDEMPOTENCY_KEY,
                correlation_id=CORRELATION_ID,
            )

    assert calls == 0


@pytest.mark.asyncio
async def test_operation_status_uses_a_typed_correlation_path_and_response() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json=_envelope(
                {
                    "correlation_id": CORRELATION_ID,
                    "status": "SUCCEEDED",
                    "event_id": EVENT_ID,
                    "result": {
                        "status": "SUCCEEDED",
                        "event_id": EVENT_ID,
                        "correlation_id": CORRELATION_ID,
                        "etag": ETAG,
                        "write_applied": True,
                    },
                    "error": {},
                }
            ),
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await client.get_schedule_operation(CORRELATION_ID)

    assert isinstance(result, ScheduleOperationData)
    assert result.status == "SUCCEEDED"
    assert seen[0].url.path == f"/api/mcp/schedules/operations/{CORRELATION_ID}"


@pytest.mark.asyncio
async def test_schedule_error_preserves_stable_detail_code_and_correlation_header() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={"detail": "timesheet_locked"},
            headers={"X-Correlation-ID": CORRELATION_ID},
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.update_schedule(
                EVENT_ID,
                _mutation_request(),
                etag=ETAG,
                idempotency_key=IDEMPOTENCY_KEY,
                correlation_id=CORRELATION_ID,
            )

    assert caught.value.code == "timesheet_locked"
    assert caught.value.correlation_id == CORRELATION_ID
    assert caught.value.status_code == 409
    assert caught.value.retryable is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,value",
    [
        ("header", "corr.with.dot"),
        ("header", "../corr-client-001"),
        ("body", "corr.with.dot"),
        ("body", "../corr-client-001"),
    ],
)
async def test_schedule_error_rejects_noncanonical_correlation_ids(
    source: str,
    value: str,
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        if source == "header":
            return httpx.Response(
                409,
                json={"detail": "timesheet_locked"},
                headers={"X-Correlation-ID": value},
            )
        return httpx.Response(
            409,
            json={
                "error": {
                    "code": "timesheet_locked",
                    "message": "must not cross",
                    "correlation_id": value,
                    "details": {},
                }
            },
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.get_schedule(EVENT_ID, category="company")

    assert caught.value.code == "timesheet_locked"
    assert caught.value.correlation_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "upstream_code,expected_code",
    [
        ("timesheet_locked", "timesheet_locked"),
        ("BAD CODE", "http_409"),
    ],
)
async def test_schedule_error_uses_canonical_code_and_redacts_free_text(
    upstream_code: str,
    expected_code: str,
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "error": {
                    "code": upstream_code,
                    "message": "sensitive upstream explanation",
                    "correlation_id": CORRELATION_ID,
                    "details": {"private": "must not cross"},
                }
            },
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.get_schedule(EVENT_ID, category="company")

    assert caught.value.code == expected_code
    assert caught.value.message == "ERP API rejected the request"
    assert caught.value.correlation_id == CORRELATION_ID
    assert caught.value.details == {}


@pytest.mark.asyncio
async def test_dynamic_paths_and_queries_remain_rejected_by_low_level_request() -> None:
    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={})),
    ) as client:
        for path in [
            f"/api/mcp/schedules/{EVENT_ID}?category=company",
            "/api/mcp/schedules/../admin/users",
            "https://evil.example/api/mcp/schedules",
        ]:
            with pytest.raises(ValueError, match="allowlisted"):
                await client._request("GET", path)
        with pytest.raises(ValueError, match="query"):
            await client._request(
                "GET",
                "/api/mcp/schedules",
                params={"target": "other"},
            )


def _all_day_item(
    *,
    event_id: str = EVENT_ID,
    category: str = "company",
    start_date: str = "2026-08-03",
    end_date: str = "2026-08-03",
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "category": category,
        "is_all_day": True,
        "schedule_kind": "출장",
        "start_date": start_date,
        "end_date": end_date,
    }


def _detail_data(
    *,
    event_id: str = EVENT_ID,
    category: str = "company",
    start_date: str = "2026-08-03",
    end_date: str = "2026-08-03",
) -> dict[str, object]:
    return {
        **_all_day_item(
            event_id=event_id,
            category=category,
            start_date=start_date,
            end_date=end_date,
        ),
        "etag": ETAG,
        "owner_binding": {"state": "BOUND", "write_allowed": True},
        "eligibility": {"write_allowed": True, "denial_reasons": []},
    }


def _preflight_update_data() -> dict[str, object]:
    return {
        "action": "UPDATE",
        "category": "company",
        "event_id": EVENT_ID,
        "current": _all_day_item(),
        "desired": {
            "is_all_day": True,
            "start_date": "2026-08-10",
            "end_date": "2026-08-10",
        },
        "owner_binding": {"state": "BOUND", "write_allowed": True},
        "affected_weeks": ["2026-08-03", "2026-08-10"],
        "timesheet_statuses": [],
        "etag": ETAG,
        "write_allowed": True,
        "denial_reasons": [],
    }


def _preflight_update_request() -> SchedulePreflightRequest:
    return SchedulePreflightRequest(
        action="UPDATE",
        category="company",
        event_id=EVENT_ID,
        desired=ScheduleAllDayProposal(
            date=date(2026, 8, 10),
            end_date=date(2026, 8, 10),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "category",
        "before_start",
        "after_end",
        "outside_both",
        "over_limit",
    ],
)
async def test_list_rejects_response_not_bound_to_requested_window(case: str) -> None:
    items = [_all_day_item()]
    kwargs: dict[str, object] = {"category": "company", "limit": 10}
    if case == "category":
        items[0]["category"] = "refresh"
    elif case == "before_start":
        kwargs["start_date"] = date(2026, 8, 3)
        items[0]["start_date"] = "2026-08-02"
        items[0]["end_date"] = "2026-08-02"
    elif case == "after_end":
        kwargs["end_date"] = date(2026, 8, 3)
        items[0]["start_date"] = "2026-08-04"
        items[0]["end_date"] = "2026-08-04"
    elif case == "outside_both":
        kwargs["start_date"] = date(2026, 8, 3)
        kwargs["end_date"] = date(2026, 8, 5)
        items[0]["start_date"] = "2026-08-06"
        items[0]["end_date"] = "2026-08-06"
    else:
        kwargs["limit"] = 1
        items.append(_all_day_item(event_id="b23456789bcdefg"))

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope({"items": items, "count": len(items)}),
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.list_schedules(**kwargs)

    assert caught.value.code == "upstream_invalid_response"


@pytest.mark.asyncio
async def test_list_accepts_a_long_legacy_item_when_its_start_is_in_bounds() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope(
                {
                    "items": [
                        _all_day_item(
                            start_date="2026-01-01",
                            end_date="2026-03-31",
                        )
                    ],
                    "count": 1,
                }
            ),
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await client.list_schedules(
            category="company",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

    assert result.items[0].end_date == date(2026, 3, 31)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["event_id", "category"])
async def test_detail_rejects_response_for_a_different_target(case: str) -> None:
    detail = _detail_data()
    detail[case] = (
        "b23456789bcdefg" if case == "event_id" else "refresh"
    )

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(detail))

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.get_schedule(EVENT_ID, category="company")

    assert caught.value.code == "upstream_invalid_response"


@pytest.mark.asyncio
async def test_detail_accepts_a_long_legacy_schedule() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_envelope(
                _detail_data(
                    start_date="2026-01-01",
                    end_date="2026-03-31",
                )
            ),
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await client.get_schedule(EVENT_ID, category="company")

    assert result.end_date == date(2026, 3, 31)


@pytest.mark.asyncio
async def test_update_rejects_a_result_for_a_different_event() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "success", "id": "b23456789bcdefg"},
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.update_schedule(
                EVENT_ID,
                _mutation_request(),
                etag=ETAG,
                idempotency_key=IDEMPOTENCY_KEY,
                correlation_id=CORRELATION_ID,
            )

    assert caught.value.code == "upstream_invalid_response"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "action",
        "category",
        "event_id",
        "current_event",
        "current_category",
        "desired",
    ],
)
async def test_preflight_rejects_response_not_bound_to_request(case: str) -> None:
    data = _preflight_update_data()
    if case == "action":
        data["action"] = "DELETE"
        data["desired"] = None
    elif case == "category":
        data["category"] = "refresh"
        data["current"] = _all_day_item(category="refresh")
    elif case == "event_id":
        data["event_id"] = "b23456789bcdefg"
        data["current"] = _all_day_item(event_id="b23456789bcdefg")
    elif case == "current_event":
        data["current"] = _all_day_item(event_id="b23456789bcdefg")
    elif case == "current_category":
        data["current"] = _all_day_item(category="refresh")
    else:
        data["desired"] = {
            "is_all_day": True,
            "start_date": "2026-08-11",
            "end_date": "2026-08-11",
        }

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(data))

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.preflight_schedule(_preflight_update_request())

    assert caught.value.code == "upstream_invalid_response"


@pytest.mark.asyncio
async def test_preflight_accepts_long_legacy_current_and_unbounded_week_evidence() -> None:
    data = _preflight_update_data()
    data["current"] = _all_day_item(
        start_date="2026-01-01",
        end_date="2026-04-30",
    )
    week_start = date(2025, 12, 29)
    data["affected_weeks"] = [
        (week_start + timedelta(days=7 * offset)).isoformat()
        for offset in range(18)
    ]
    data["timesheet_statuses"] = [
        {
            "week_start": (week_start + timedelta(days=7 * offset)).isoformat(),
            "status": "작성중",
        }
        for offset in range(15)
    ]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(data))

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await client.preflight_schedule(_preflight_update_request())

    assert len(result.affected_weeks) == 18
    assert len(result.timesheet_statuses) == 15


def _operation_status_data(status: str = "SUCCEEDED") -> dict[str, object]:
    if status == "IN_PROGRESS":
        result: dict[str, object] = {}
        error: dict[str, object] = {}
    elif status == "SUCCEEDED":
        result = {
            "status": "SUCCEEDED",
            "event_id": EVENT_ID,
            "correlation_id": CORRELATION_ID,
            "etag": ETAG,
            "write_applied": True,
        }
        error = {}
    else:
        result = {}
        error = {
            "code": "operation_failed",
            "status": status,
            "correlation_id": CORRELATION_ID,
            "http_status": 409,
        }
    return {
        "correlation_id": CORRELATION_ID,
        "status": status,
        "event_id": EVENT_ID,
        "result": result,
        "error": error,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        "IN_PROGRESS",
        "SUCCEEDED",
        "FAILED",
        "RECONCILIATION_REQUIRED",
        "MANUAL_REVIEW",
    ],
)
async def test_operation_status_accepts_each_backend_state(
    status: str,
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(_operation_status_data(status)))

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await client.get_schedule_operation(CORRELATION_ID)

    assert result.status == status


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["top_correlation", "meta_correlation"])
async def test_operation_status_rejects_response_for_other_correlation(
    case: str,
) -> None:
    data = _operation_status_data()
    payload = _envelope(data)
    if case == "top_correlation":
        data["correlation_id"] = "corr-other_001"
        payload["meta"]["correlation_id"] = "corr-other_001"
    else:
        payload["meta"]["correlation_id"] = "corr-other_001"

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.get_schedule_operation(CORRELATION_ID)

    assert caught.value.code == "upstream_invalid_response"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "in_progress_result",
        "success_empty_result",
        "success_error",
        "success_event",
        "success_status",
        "success_correlation",
        "success_missing_correlation",
        "success_missing_write_applied",
        "success_write_not_applied",
        "success_reconciliation_required",
        "terminal_result",
        "terminal_empty_error",
        "terminal_error_status",
        "terminal_error_correlation",
    ],
)
async def test_operation_status_nested_mismatch_is_safe_schema_drift(
    case: str,
) -> None:
    if case == "in_progress_result":
        data = _operation_status_data("IN_PROGRESS")
        data["result"] = {"status": "IN_PROGRESS"}
    elif case.startswith("success"):
        data = _operation_status_data("SUCCEEDED")
        if case == "success_empty_result":
            data["result"] = {}
        elif case == "success_error":
            data["error"] = {
                "code": "operation_failed",
                "status": "FAILED",
                "correlation_id": CORRELATION_ID,
            }
        else:
            result = dict(data["result"])
            if case == "success_missing_correlation":
                result.pop("correlation_id")
            elif case == "success_missing_write_applied":
                result.pop("write_applied")
            else:
                field, value = {
                    "success_event": ("event_id", "b23456789bcdefg"),
                    "success_status": ("status", "FAILED"),
                    "success_correlation": (
                        "correlation_id",
                        "corr-other_001",
                    ),
                    "success_write_not_applied": ("write_applied", False),
                    "success_reconciliation_required": (
                        "reconciliation_required",
                        True,
                    ),
                }[case]
                result[field] = value
            data["result"] = result
    else:
        data = _operation_status_data("FAILED")
        if case == "terminal_result":
            data["result"] = {
                "status": "FAILED",
                "event_id": EVENT_ID,
            }
        elif case == "terminal_empty_error":
            data["error"] = {}
        else:
            error = dict(data["error"])
            field, value = {
                "terminal_error_status": ("status", "MANUAL_REVIEW"),
                "terminal_error_correlation": (
                    "correlation_id",
                    "corr-other_001",
                ),
            }[case]
            error[field] = value
            data["error"] = error

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(data))

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ERPError) as caught:
            await client.get_schedule_operation(CORRELATION_ID)

    assert caught.value.code == "upstream_invalid_response"
    assert caught.value.correlation_id is None
    assert caught.value.details == {}
