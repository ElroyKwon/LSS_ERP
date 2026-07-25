from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from uuid import uuid4

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from lss_erp_mcp.schemas.common import ErrorDetail, ErrorEnvelope
from lss_erp_mcp.schemas.timesheet import DraftWriteRequest

from .state import ContractState


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


def create_contract_app(state: ContractState | None = None) -> FastAPI:
    app = FastAPI()
    app.state.contract = state or ContractState()

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

    @app.get("/api/timesheets/week")
    def week(week_start: date = Query(...)) -> dict[str, object]:
        current = app.state.contract
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

    @app.get("/api/timesheets/projects")
    def projects(q: str = "", limit: int = Query(default=20, ge=1, le=50)) -> dict:
        items = [
            {
                "project_id": 123,
                "project_code": "P-2026-001",
                "project_name": "MCP 개발",
                "active": True,
            }
        ]
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
        current.version += 1
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

    return app
