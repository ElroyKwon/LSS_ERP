from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from lss_erp_mcp.schemas.common import ErrorDetail, ErrorEnvelope
from lss_erp_mcp.schemas.schedule import (
    ScheduleMutationRequest,
    SchedulePreflightRequest,
)
from lss_erp_mcp.schemas.timesheet import DraftWriteRequest

from .state import ContractState

WORK_TYPES = [
    "공통 > 연차",
    "공통 > 교육",
    "공통 > 행사",
    "공통 > 기타",
    "영업 > 설계",
    "영업 > SHOP작업",
    "영업 > 견적",
    "영업 > 제안서",
    "영업 > 미팅",
    "영업 > 기타",
    "실행 > 현장관리",
    "실행 > 시운전",
    "실행 > 안전관리",
    "실행 > 유지보수",
    "실행 > 업무지원",
    "실행 > 하자처리(유상)",
    "실행 > 하자처리(무상)",
    "실행 > 기타",
    "경영지원 > 구매",
    "경영지원 > 총무",
    "경영지원 > 인사",
    "경영지원 > 회계",
    "경영지원 > 자금",
    "경영지원 > 공시",
    "경영지원 > 기타",
]
_SCHEDULE_READ_CORRELATION = "stub-read_001"
_DRAFT_STATUS = "작성중"
_OPERATION_STATUSES = {
    "IN_PROGRESS",
    "SUCCEEDED",
    "FAILED",
    "RECONCILIATION_REQUIRED",
    "MANUAL_REVIEW",
}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,255}$")
_ERROR_CODE_RE = re.compile(r"^[a-z0-9_:-]{1,64}$")
_ETAG_RE = re.compile(r'^"[A-Za-z0-9._:-]{1,253}"$')


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    correlation_id: str,
    retryable: bool = False,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=code,
            message=message,
            correlation_id=correlation_id,
            retryable=retryable,
            details=details or {},
        )
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


def _schedule_envelope(
    data: dict[str, object],
    *,
    correlation_id: str = _SCHEDULE_READ_CORRELATION,
) -> dict[str, object]:
    return {
        "success": True,
        "data": data,
        "error": None,
        "meta": {
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    }


def _schedule_scope_error(
    state: ContractState,
    scope: str,
    correlation_id: str,
) -> JSONResponse | None:
    if scope in state.scopes:
        return None
    return _error_response(
        status_code=403,
        code="missing_scope",
        message="The API token does not grant the required schedule scope.",
        correlation_id=correlation_id,
    )


def _schedule_item(event: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {
        "event_id": event["event_id"],
        "category": event["category"],
        "is_all_day": event["is_all_day"],
        "schedule_kind": event.get("schedule_kind"),
    }
    if event["is_all_day"] is True:
        result["start_date"] = event["date"]
        result["end_date"] = event["end_date"]
    else:
        result["start_time"] = event["start_time"]
        result["end_time"] = event["end_time"]
    return result


def _owner_evidence(state: ContractState) -> tuple[dict[str, object], list[str]]:
    reason_by_state = {
        "BOUND": None,
        "LEGACY_OWNER_UNBOUND": "legacy_owner_unbound",
        "OWNER_MISMATCH": "owner_mismatch",
    }
    reason = reason_by_state[state.schedule_owner_state]
    reasons = [] if reason is None else [reason]
    return (
        {
            "state": state.schedule_owner_state,
            "write_allowed": state.schedule_owner_state == "BOUND",
        },
        reasons,
    )


def _schedule_detail(
    state: ContractState,
    event: dict[str, object],
) -> dict[str, object]:
    owner, reasons = _owner_evidence(state)
    return {
        **_schedule_item(event),
        "etag": event["etag"],
        "owner_binding": owner,
        "eligibility": {
            "write_allowed": not reasons,
            "denial_reasons": reasons,
        },
    }


def _proposal_projection(proposal: object) -> dict[str, object] | None:
    if proposal is None:
        return None
    if proposal.is_all_day:
        return {
            "is_all_day": True,
            "start_date": proposal.date.isoformat(),
            "end_date": proposal.end_date.isoformat(),
        }
    return {
        "is_all_day": False,
        "start_time": proposal.start_time.isoformat(),
        "end_time": proposal.end_time.isoformat(),
    }


def _item_start_date(event: dict[str, object]) -> date:
    raw = event["date"] if event["is_all_day"] is True else event["start_time"]
    return date.fromisoformat(str(raw)[:10])


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _preflight_weeks(
    request: SchedulePreflightRequest,
    event: dict[str, object] | None,
) -> list[date]:
    values: list[date] = []
    if event is not None:
        values.append(_item_start_date(event))
    if request.desired is not None:
        if request.desired.is_all_day:
            values.append(request.desired.date)
        else:
            values.append(request.desired.start_time.date())
    return sorted({_week_start(value) for value in values})


def _mutation_validation_error(
    correlation_id: str,
    exc: ValidationError | None = None,
) -> JSONResponse:
    issues = []
    if exc is not None:
        issues = [
            {"location": list(error["loc"]), "type": error["type"]}
            for error in exc.errors()
        ]
    return _error_response(
        status_code=422,
        code="validation_failed",
        message="Request validation failed.",
        correlation_id=correlation_id,
        details={"issues": issues},
    )


def _parse_schedule_mutation(
    body: dict[str, object],
    correlation_id: str,
) -> tuple[ScheduleMutationRequest | None, JSONResponse | None]:
    if body.get("user_name") != "":
        return None, _mutation_validation_error(correlation_id)
    model_input = dict(body)
    model_input.pop("user_name", None)
    try:
        return ScheduleMutationRequest.model_validate(model_input), None
    except ValidationError as exc:
        return None, _mutation_validation_error(correlation_id, exc)


def _schedule_request_hash(
    *,
    action: str,
    event_id: str | None,
    payload: dict[str, object],
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "action": action,
                "event_id": event_id,
                "payload": payload,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _schedule_replay(
    state: ContractState,
    *,
    idempotency_key: str,
    request_hash: str,
    correlation_id: str,
) -> dict[str, object] | JSONResponse | None:
    existing = state.schedule_idempotency.get(
        (state.user_id, idempotency_key)
    )
    if existing is None:
        return None
    old_hash, status_code, response = existing
    if old_hash != request_hash:
        return _error_response(
            status_code=409,
            code="idempotency_conflict",
            message="Idempotency key was used with a different request.",
            correlation_id=correlation_id,
        )
    if status_code == 200:
        return dict(response)
    return JSONResponse(status_code=status_code, content=response)


def _operation_projection(operation: dict[str, object]) -> dict[str, object]:
    raw_result = operation.get("result")
    raw_error = operation.get("error")
    result = raw_result if isinstance(raw_result, dict) else {}
    error = raw_error if isinstance(raw_error, dict) else {}
    safe_result: dict[str, object] = {}
    if result.get("status") in _OPERATION_STATUSES:
        safe_result["status"] = result["status"]
    result_event = result.get("event_id")
    if (
        isinstance(result_event, str)
        and len(result_event) <= 255
        and _IDENTIFIER_RE.fullmatch(result_event)
    ):
        safe_result["event_id"] = result_event
    result_correlation = result.get("correlation_id")
    if (
        isinstance(result_correlation, str)
        and len(result_correlation) <= 128
        and _IDENTIFIER_RE.fullmatch(result_correlation)
    ):
        safe_result["correlation_id"] = result_correlation
    result_etag = result.get("etag")
    if isinstance(result_etag, str) and _ETAG_RE.fullmatch(result_etag):
        safe_result["etag"] = result_etag
    for name in ("replayed", "write_applied", "reconciliation_required"):
        if isinstance(result.get(name), bool):
            safe_result[name] = result[name]
    result_http = result.get("http_status")
    if (
        isinstance(result_http, int)
        and not isinstance(result_http, bool)
        and 100 <= result_http <= 599
    ):
        safe_result["http_status"] = result_http

    safe_error: dict[str, object] = {}
    error_code = error.get("code")
    if isinstance(error_code, str) and _ERROR_CODE_RE.fullmatch(error_code):
        safe_error["code"] = error_code
    if error.get("status") in _OPERATION_STATUSES:
        safe_error["status"] = error["status"]
    error_correlation = error.get("correlation_id")
    if (
        isinstance(error_correlation, str)
        and len(error_correlation) <= 128
        and _IDENTIFIER_RE.fullmatch(error_correlation)
    ):
        safe_error["correlation_id"] = error_correlation
    if isinstance(error.get("retryable"), bool):
        safe_error["retryable"] = error["retryable"]
    error_http = error.get("http_status")
    if (
        isinstance(error_http, int)
        and not isinstance(error_http, bool)
        and 100 <= error_http <= 599
    ):
        safe_error["http_status"] = error_http
    return {
        "correlation_id": operation["correlation_id"],
        "status": operation["status"],
        "event_id": operation.get("event_id"),
        "result": safe_result,
        "error": safe_error,
    }


def _write_revalidation_error(
    state: ContractState,
    *,
    correlation_id: str,
    require_owner: bool,
) -> JSONResponse | None:
    code = None
    status_code = 409
    if require_owner and state.schedule_owner_state == "LEGACY_OWNER_UNBOUND":
        code = "legacy_owner_unbound"
        status_code = 403
    elif require_owner and state.schedule_owner_state != "BOUND":
        code = "owner_mismatch"
        status_code = 403
    elif state.schedule_timesheet_status != _DRAFT_STATUS:
        code = "timesheet_locked"
    if code is None:
        return None
    return _error_response(
        status_code=status_code,
        code=code,
        message="Schedule mutation was denied by current authority evidence.",
        correlation_id=correlation_id,
    )


def _store_schedule_error(
    state: ContractState,
    *,
    idempotency_key: str,
    request_hash: str,
    correlation_id: str,
    event_id: str | None,
    response: JSONResponse,
) -> None:
    payload = json.loads(response.body)
    state.schedule_idempotency[(state.user_id, idempotency_key)] = (
        request_hash,
        response.status_code,
        payload,
    )
    error = payload.get("error", {})
    code = error.get("code", "operation_failed")
    state.schedule_operations[(state.user_id, correlation_id)] = {
        "owner_user_id": state.user_id,
        "correlation_id": correlation_id,
        "status": "FAILED",
        "event_id": event_id,
        "result": {},
        "error": {
            "code": code,
            "status": "FAILED",
            "correlation_id": correlation_id,
            "http_status": response.status_code,
        },
    }


def _operation_success(
    correlation_id: str,
    event_id: str,
    *,
    etag: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "SUCCEEDED",
        "event_id": event_id,
        "correlation_id": correlation_id,
        "write_applied": True,
    }
    if etag is not None:
        result["etag"] = etag
    return {
        "correlation_id": correlation_id,
        "status": "SUCCEEDED",
        "event_id": event_id,
        "result": result,
        "error": {},
    }


def _operation_failure(
    correlation_id: str,
    event_id: str | None,
    status: str,
    code: str,
    *,
    http_status: int,
) -> dict[str, object]:
    return {
        "correlation_id": correlation_id,
        "status": status,
        "event_id": event_id,
        "result": {},
        "error": {
            "code": code,
            "status": status,
            "correlation_id": correlation_id,
            "retryable": False,
            "http_status": http_status,
        },
    }


def create_contract_app(state: ContractState | None = None) -> FastAPI:
    app = FastAPI()
    app.state.contract = state or ContractState()

    @app.middleware("http")
    async def forced_error(request: Request, call_next):
        current = app.state.contract
        if current.forced_error_status is not None:
            return _error_response(
                status_code=current.forced_error_status,
                code=current.forced_error_code,
                message="Forced contract error.",
                correlation_id=(
                    request.headers.get("X-Correlation-ID")
                    or "forced-correlation"
                ),
                retryable=current.forced_error_retryable,
            )
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        details = {
            "issues": [
                {"location": list(error["loc"]), "type": error["type"]}
                for error in exc.errors()
            ]
        }
        return _error_response(
            status_code=422,
            code="validation_failed",
            message="Request validation failed.",
            correlation_id=correlation_id,
            details=details,
        )

    @app.get("/api/auth/me")
    def me() -> dict[str, object]:
        current = app.state.contract
        return {
            "user_id": current.user_id,
            "employee_id": current.employee_id,
            "employee_code": current.employee_code,
            "display_name": "테스트 사용자",
            "client_id": "lss-erp-mcp-local",
            "resource": "lss-erp-api",
            "scopes": sorted(current.scopes),
        }

    @app.get("/api/timesheets/week", response_model=None)
    def week(
        week_start: date = Query(...),
    ) -> dict[str, object] | JSONResponse:
        current = app.state.contract
        if week_start != current.week_start:
            return _error_response(
                status_code=404,
                code="timesheet_not_found",
                message="Timesheet week was not found.",
                correlation_id=str(uuid4()),
            )
        return {
            "timesheet_id": 100,
            "week_start": str(current.week_start),
            "week_end": str(current.week_start + timedelta(days=6)),
            "status": current.status,
            "version": current.version,
            "entries": (
                current.entries
                if current.readback_entries_override is None
                else current.readback_entries_override
            ),
        }

    @app.get("/api/timesheets/entry-context")
    def entry_context(
        week_start: date = Query(...),
    ) -> dict[str, object]:
        current = app.state.contract
        return {
            "week_start": str(week_start),
            "week_end": str(week_start + timedelta(days=6)),
            "labor_type": current.labor_type,
            "project_sources": ["실행", "영업", "공통"],
            "work_types": WORK_TYPES,
            "daily_targets": [
                {
                    "work_date": str(week_start + timedelta(days=offset)),
                    "target_hours": "8" if offset < 5 else "0",
                    "reason": "normal" if offset < 5 else "weekend",
                }
                for offset in range(7)
            ],
        }

    @app.get("/api/timesheets/projects")
    def projects(q: str = "", limit: int = Query(default=20, ge=1, le=50)) -> dict:
        items = list(app.state.contract.projects)
        if q:
            lowered = q.casefold()
            items = [
                item
                for item in items
                if lowered == str(item["project_id"])
                or lowered in item["project_code"].casefold()
                or lowered in item["project_name"].casefold()
            ]
        return {"items": items[:limit], "truncated": len(items) > limit}

    @app.post("/api/timesheets/mcp-draft", response_model=None)
    def save(
        body: DraftWriteRequest,
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
        correlation_id: str = Header(alias="X-Correlation-ID", min_length=1),
    ) -> dict[str, object] | JSONResponse:
        current = app.state.contract
        request_hash = hashlib.sha256(
            json.dumps(
                body.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        existing = current.idempotency.get(idempotency_key)
        if existing:
            old_hash, result = existing
            if old_hash != request_hash:
                return _error_response(
                    status_code=409,
                    code="idempotency_conflict",
                    message="Idempotency key was used with a different request.",
                    correlation_id=correlation_id,
                )
            return {**result, "idempotency_replayed": True}
        if current.status != "작성중":
            return _error_response(
                status_code=409,
                code="timesheet_not_draft",
                message="Timesheet is not editable.",
                correlation_id=correlation_id,
                details={"status": current.status},
            )
        if body.expected_version != current.version:
            return _error_response(
                status_code=409,
                code="stale_write",
                message="Current version changed.",
                correlation_id=correlation_id,
                details={
                    "expected_version": body.expected_version,
                    "current_version": current.version,
                },
            )

        current.post_count += 1
        current.version += current.version_increment
        current.entries = [
            {"entry_id": index + 1, **entry.model_dump(mode="json")}
            for index, entry in enumerate(body.entries)
        ]
        result: dict[str, object] = {
            "timesheet_id": 100,
            "week_start": str(current.week_start),
            "status": current.status,
            "version": current.version,
            "correlation_id": correlation_id,
            "idempotency_replayed": False,
        }
        current.idempotency[idempotency_key] = (request_hash, result)
        return result

    @app.get("/api/mcp/schedules", response_model=None)
    def schedule_list(
        category: str = Query(default="company"),
        start_date: date | None = Query(default=None),
        end_date: date | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> dict[str, object] | JSONResponse:
        current = app.state.contract
        denied = _schedule_scope_error(
            current,
            "schedule:read",
            _SCHEDULE_READ_CORRELATION,
        )
        if denied is not None:
            return denied
        if category not in {"company", "refresh"}:
            return _mutation_validation_error(_SCHEDULE_READ_CORRELATION)
        items = []
        for event in current.schedules.values():
            event_date = _item_start_date(event)
            if (
                event["category"] != category
                or event.get("owner_user_id") != current.user_id
            ):
                continue
            if start_date is not None and event_date < start_date:
                continue
            if end_date is not None and event_date > end_date:
                continue
            items.append(_schedule_item(event))
        items = items[:limit]
        return _schedule_envelope(
            {
                "items": items,
                "count": len(items),
            }
        )

    @app.get(
        "/api/mcp/schedules/operations/{correlation_id}",
        response_model=None,
    )
    def schedule_operation(
        correlation_id: str,
    ) -> dict[str, object] | JSONResponse:
        current = app.state.contract
        denied = _schedule_scope_error(
            current,
            "schedule:write",
            correlation_id,
        )
        if denied is not None:
            return denied
        operation = current.schedule_operations.get(
            (current.user_id, correlation_id)
        )
        if operation is None:
            return _error_response(
                status_code=404,
                code="operation_not_found",
                message="Schedule operation was not found.",
                correlation_id=correlation_id,
            )
        return _schedule_envelope(
            _operation_projection(operation),
            correlation_id=correlation_id,
        )

    @app.get("/api/mcp/schedules/{event_id}", response_model=None)
    def schedule_detail(
        event_id: str,
        category: str = Query(default="company"),
    ) -> dict[str, object] | JSONResponse:
        current = app.state.contract
        denied = _schedule_scope_error(
            current,
            "schedule:read",
            _SCHEDULE_READ_CORRELATION,
        )
        if denied is not None:
            return denied
        event = current.schedules.get(event_id)
        if (
            event is None
            or event["category"] != category
            or event.get("owner_user_id") != current.user_id
        ):
            return _error_response(
                status_code=404,
                code="schedule_not_found",
                message="Schedule was not found.",
                correlation_id=_SCHEDULE_READ_CORRELATION,
            )
        return _schedule_envelope(_schedule_detail(current, event))

    @app.post("/api/mcp/schedules/preflight", response_model=None)
    def schedule_preflight(
        body: SchedulePreflightRequest,
    ) -> dict[str, object] | JSONResponse:
        current = app.state.contract
        denied = _schedule_scope_error(
            current,
            "schedule:write",
            _SCHEDULE_READ_CORRELATION,
        )
        if denied is not None:
            return denied

        event = None
        if body.event_id is not None:
            event = current.schedules.get(body.event_id)
            if (
                event is None
                or event["category"] != body.category
                or event.get("owner_user_id") != current.user_id
            ):
                return _error_response(
                    status_code=404,
                    code="schedule_not_found",
                    message="Schedule was not found.",
                    correlation_id=_SCHEDULE_READ_CORRELATION,
                )

        if body.action == "CREATE":
            owner = {
                "state": "NOT_APPLICABLE",
                "write_allowed": True,
            }
            owner_reasons: list[str] = []
        else:
            owner, owner_reasons = _owner_evidence(current)

        weeks = _preflight_weeks(body, event)
        statuses = [
            {
                "week_start": week.isoformat(),
                "status": current.schedule_timesheet_status,
            }
            for week in weeks
        ]
        denial_reasons = list(owner_reasons)
        if current.schedule_timesheet_status != _DRAFT_STATUS:
            denial_reasons.append("timesheet_locked")

        return _schedule_envelope(
            {
                "action": body.action,
                "category": body.category,
                "event_id": body.event_id,
                "current": None if event is None else _schedule_item(event),
                "desired": _proposal_projection(body.desired),
                "owner_binding": owner,
                "affected_weeks": [week.isoformat() for week in weeks],
                "timesheet_statuses": statuses,
                "etag": None if event is None else event["etag"],
                "write_allowed": not denial_reasons,
                "denial_reasons": denial_reasons,
            }
        )

    @app.post("/api/schedules", response_model=None)
    def schedule_create(
        body: dict[str, object],
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=8),
        correlation_id: str = Header(alias="X-Correlation-ID", min_length=8),
        schedule_header: str = Header(alias="X-LSS-MCP-Schedule"),
    ) -> dict[str, object] | JSONResponse:
        current = app.state.contract
        denied = _schedule_scope_error(
            current,
            "schedule:write",
            correlation_id,
        )
        if denied is not None:
            return denied
        if schedule_header != "1":
            return _mutation_validation_error(correlation_id)
        mutation, invalid = _parse_schedule_mutation(body, correlation_id)
        if invalid is not None or mutation is None:
            return invalid or _mutation_validation_error(correlation_id)
        payload = mutation.model_dump(mode="json", exclude_none=True)
        request_hash = _schedule_request_hash(
            action="CREATE",
            event_id=None,
            payload=payload,
        )
        replay = _schedule_replay(
            current,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            correlation_id=correlation_id,
        )
        if replay is not None:
            return replay

        event_id = hashlib.sha256(
            f"{current.user_id}\0{idempotency_key}".encode("utf-8")
        ).hexdigest()[:16]
        denied_mutation = _write_revalidation_error(
            current,
            correlation_id=correlation_id,
            require_owner=False,
        )
        if denied_mutation is not None:
            _store_schedule_error(
                current,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                correlation_id=correlation_id,
                event_id=event_id,
                response=denied_mutation,
            )
            return denied_mutation
        event = {
            "event_id": event_id,
            **payload,
            "etag": '"etag-1"',
            "owner_user_id": current.user_id,
        }
        current.schedules[event_id] = event
        current.schedule_write_count += 1
        response: dict[str, object] = {
            "status": "success",
            "id": event_id,
        }
        current.schedule_idempotency[(current.user_id, idempotency_key)] = (
            request_hash,
            200,
            response,
        )
        current.schedule_operations[(current.user_id, correlation_id)] = {
            "owner_user_id": current.user_id,
            **_operation_success(
                correlation_id,
                event_id,
                etag=str(event["etag"]),
            ),
        }
        if current.schedule_faults.get("CREATE") == "response_loss":
            return _error_response(
                status_code=504,
                code="response_lost_after_apply",
                message="The observable create response was lost.",
                correlation_id=correlation_id,
                retryable=True,
            )
        return response

    @app.put("/api/schedules/{event_id}", response_model=None)
    def schedule_update(
        event_id: str,
        body: dict[str, object],
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=8),
        correlation_id: str = Header(alias="X-Correlation-ID", min_length=8),
        schedule_header: str = Header(alias="X-LSS-MCP-Schedule"),
        etag: str = Header(alias="If-Match"),
    ) -> dict[str, object] | JSONResponse:
        current = app.state.contract
        denied = _schedule_scope_error(
            current,
            "schedule:write",
            correlation_id,
        )
        if denied is not None:
            return denied
        if schedule_header != "1":
            return _mutation_validation_error(correlation_id)
        mutation, invalid = _parse_schedule_mutation(body, correlation_id)
        if invalid is not None or mutation is None:
            return invalid or _mutation_validation_error(correlation_id)
        payload = mutation.model_dump(mode="json", exclude_none=True)
        request_hash = _schedule_request_hash(
            action="UPDATE",
            event_id=event_id,
            payload={**payload, "expected_etag": etag},
        )
        replay = _schedule_replay(
            current,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            correlation_id=correlation_id,
        )
        if replay is not None:
            return replay
        event = current.schedules.get(event_id)
        if (
            event is None
            or event.get("owner_user_id") != current.user_id
        ):
            return _error_response(
                status_code=409,
                code="stale_event",
                message="Schedule state changed.",
                correlation_id=correlation_id,
            )
        denied_mutation = _write_revalidation_error(
            current,
            correlation_id=correlation_id,
            require_owner=True,
        )
        if denied_mutation is not None:
            # The real backend resolves immutable owner evidence before the
            # operation claim is committed. Owner denial therefore rolls the
            # claim back and may be retried after evidence is corrected.
            # Mutable timesheet denial happens after the durable claim and is
            # replayed exactly.
            if current.schedule_owner_state == "BOUND":
                _store_schedule_error(
                    current,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    correlation_id=correlation_id,
                    event_id=event_id,
                    response=denied_mutation,
                )
            return denied_mutation
        if event["etag"] != etag:
            return _error_response(
                status_code=409,
                code="stale_event",
                message="Schedule etag changed.",
                correlation_id=correlation_id,
            )

        new_etag = '"etag-2"'
        current.schedules[event_id] = {
            "event_id": event_id,
            **payload,
            "etag": new_etag,
            "owner_user_id": current.user_id,
        }
        current.schedule_write_count += 1
        response = {"status": "success", "id": event_id}
        fault = current.schedule_faults.get("UPDATE")
        if fault == "partial_failure":
            current.schedule_operations[(current.user_id, correlation_id)] = {
                "owner_user_id": current.user_id,
                **_operation_failure(
                    correlation_id,
                    event_id,
                    "RECONCILIATION_REQUIRED",
                    "reconciliation_required",
                    http_status=502,
                ),
            }
            fault_response = _error_response(
                status_code=502,
                code="reconciliation_required",
                message="Update outcome requires reconciliation.",
                correlation_id=correlation_id,
                retryable=False,
            )
            current.schedule_idempotency[
                (current.user_id, idempotency_key)
            ] = (
                request_hash,
                502,
                json.loads(fault_response.body),
            )
            return fault_response
        current.schedule_idempotency[(current.user_id, idempotency_key)] = (
            request_hash,
            200,
            response,
        )
        current.schedule_operations[(current.user_id, correlation_id)] = {
            "owner_user_id": current.user_id,
            **_operation_success(
                correlation_id,
                event_id,
                etag=new_etag,
            ),
        }
        return response

    @app.delete("/api/schedules/{event_id}", response_model=None)
    def schedule_delete(
        event_id: str,
        category: str = Query(...),
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=8),
        correlation_id: str = Header(alias="X-Correlation-ID", min_length=8),
        schedule_header: str = Header(alias="X-LSS-MCP-Schedule"),
        etag: str = Header(alias="If-Match"),
    ) -> dict[str, object] | JSONResponse:
        current = app.state.contract
        denied = _schedule_scope_error(
            current,
            "schedule:write",
            correlation_id,
        )
        if denied is not None:
            return denied
        if schedule_header != "1":
            return _mutation_validation_error(correlation_id)
        payload = {"category": category, "etag": etag}
        request_hash = _schedule_request_hash(
            action="DELETE",
            event_id=event_id,
            payload=payload,
        )
        replay = _schedule_replay(
            current,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            correlation_id=correlation_id,
        )
        if replay is not None:
            return replay
        event = current.schedules.get(event_id)
        if (
            event is None
            or event["category"] != category
            or event.get("owner_user_id") != current.user_id
        ):
            return _error_response(
                status_code=409,
                code="stale_event",
                message="Schedule state changed.",
                correlation_id=correlation_id,
            )
        denied_mutation = _write_revalidation_error(
            current,
            correlation_id=correlation_id,
            require_owner=True,
        )
        if denied_mutation is not None:
            if current.schedule_owner_state == "BOUND":
                _store_schedule_error(
                    current,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    correlation_id=correlation_id,
                    event_id=event_id,
                    response=denied_mutation,
                )
            return denied_mutation
        if event["etag"] != etag:
            return _error_response(
                status_code=409,
                code="stale_event",
                message="Schedule etag changed.",
                correlation_id=correlation_id,
            )

        del current.schedules[event_id]
        current.schedule_write_count += 1
        response = {"status": "success"}
        fault = current.schedule_faults.get("DELETE")
        if fault == "manual_review":
            current.schedule_operations[(current.user_id, correlation_id)] = {
                "owner_user_id": current.user_id,
                **_operation_failure(
                    correlation_id,
                    event_id,
                    "MANUAL_REVIEW",
                    "conflicting_evidence",
                    http_status=502,
                ),
            }
            fault_response = _error_response(
                status_code=502,
                code="manual_review",
                message="Delete outcome requires manual review.",
                correlation_id=correlation_id,
                retryable=False,
            )
            current.schedule_idempotency[
                (current.user_id, idempotency_key)
            ] = (
                request_hash,
                502,
                json.loads(fault_response.body),
            )
            return fault_response
        current.schedule_idempotency[(current.user_id, idempotency_key)] = (
            request_hash,
            200,
            response,
        )
        current.schedule_operations[(current.user_id, correlation_id)] = {
            "owner_user_id": current.user_id,
            **_operation_success(
                correlation_id,
                event_id,
            ),
        }
        return response

    return app
