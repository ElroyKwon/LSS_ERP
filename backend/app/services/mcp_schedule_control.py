"""Controls for the additive MCP schedule API.

This module intentionally does not reuse or reproduce the legacy schedule
create/update/delete orchestration. It provides read-only preparation plus
small journal and concurrency hooks around the existing router operations.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from fastapi import HTTPException, status
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from ..models.common import CalendarSchedule
from ..models.master import Employee
from ..models.mcp_schedule import (
    CorrelationConflictError,
    IdempotencyConflictError,
    McpScheduleOperation,
    claim_or_replay_operation,
)
from ..models.timesheet import Timesheet
from ..utils.mcp_schedule_auth import (
    McpSchedulePrincipal,
    SCHEDULE_WRITE_SCOPE,
    resolve_mcp_schedule_principal,
)
from .timesheet_locking import (
    ScheduleTimesheetScopeUnstable,
    build_timesheet_lock_query as build_shared_timesheet_lock_query,
    lock_revalidated_schedule_timesheet_scope,
)


SCHEDULE_CATEGORIES = frozenset({"company", "refresh"})
WRITABLE_TIMESHEET_STATUS = "작성중"
# The schedule contract targets modern ERP dates. Korea Standard Time has a
# fixed UTC+09:00 offset for that range, avoiding a platform tzdata dependency.
KST = timezone(timedelta(hours=9), name="Asia/Seoul")
_OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_ETAG_RE = re.compile(r'^"[A-Za-z0-9._:-]{1,253}"$')


def _require_schedule_write_enabled() -> None:
    """Fail closed unless the backend write Gate is explicitly enabled."""
    if os.getenv("MCP_SCHEDULE_WRITE_ENABLED") != "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="write_disabled",
        )


@dataclass
class McpCreateHook:
    principal: McpSchedulePrincipal
    operation: McpScheduleOperation
    event_id: str
    request_hash: str
    correlation_id: str
    employee_id: int
    affected_weeks: tuple[date, ...]
    desired_weeks: tuple[date, ...] = ()
    replay_succeeded: bool = False
    reconcile_observed: bool = False

    def apply_to_event(self, event: dict[str, Any]) -> None:
        event["id"] = self.event_id
        event["extendedProperties"] = {"private": _expected_private(self)}


@dataclass
class McpMutationHook:
    """Durable, marker-only control state for one update or delete."""

    principal: McpSchedulePrincipal
    operation: McpScheduleOperation
    event_id: str
    expected_etag: str
    existing_event: dict[str, Any]
    request_hash: str
    correlation_id: str
    employee_id: int
    action: str
    affected_weeks: tuple[date, ...]
    desired_weeks: tuple[date, ...] = ()
    replay_succeeded: bool = False

    def apply_to_update_event(self, event: dict[str, Any]) -> None:
        extended = self.existing_event.get("extendedProperties")
        extended_copy = dict(extended) if isinstance(extended, dict) else {}
        private = dict(_event_private_properties(self.existing_event))
        private.update({
            "lss_owner_user_id": str(self.principal.user.id),
            "lss_owner_employee_id": str(self.employee_id),
            "lss_event_version": "1",
            "lss_correlation_id": self.correlation_id,
            "lss_request_hash": self.request_hash,
        })
        extended_copy["private"] = private
        event["extendedProperties"] = extended_copy


def _required_header(request: object, name: str, detail: str) -> str:
    value = getattr(request, "headers", {}).get(name)
    if not isinstance(value, str) or not _OPERATION_ID_RE.fullmatch(value):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    return value


def _if_match_header(request: object) -> str:
    value = getattr(request, "headers", {}).get("If-Match")
    if not isinstance(value, str) or not _ETAG_RE.fullmatch(value):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="stale_event")
    return value


def _parse_create_desired(payload: object) -> object:
    is_all_day = bool(getattr(payload, "is_all_day", True))
    try:
        if is_all_day:
            start = date.fromisoformat(str(getattr(payload, "date", "")))
            end = date.fromisoformat(str(getattr(payload, "end_date", None) or getattr(payload, "date", "")))
            if end < start:
                raise ValueError("reversed all-day schedule")
            return type("CreateDesired", (), {"is_all_day": True, "date": start, "end_date": end, "start_time": None, "end_time": None})()
        start = datetime.fromisoformat(str(getattr(payload, "start_time", "")).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(getattr(payload, "end_time", "")).replace("Z", "+00:00"))
        normalized_start = normalize_kst_datetime(start)
        normalized_end = normalize_kst_datetime(end)
        if normalized_end <= normalized_start:
            raise ValueError("reversed timed schedule")
        return type("CreateDesired", (), {"is_all_day": False, "date": None, "end_date": None, "start_time": normalized_start, "end_time": normalized_end})()
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_schedule_time") from None


def canonical_mcp_create_effect(effect_snapshot: object, principal: McpSchedulePrincipal) -> dict[str, Any]:
    """Hash the schedule router's actual legacy effect, never a parallel model."""
    if not isinstance(effect_snapshot, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_schedule_effect")
    calendar = effect_snapshot.get("calendar")
    if not isinstance(calendar, dict) or calendar.get("category") not in SCHEDULE_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_category")
    return {
        "version": 1,
        "owner_user_id": principal.user.id,
        "owner_employee_code": getattr(principal.user, "employee_code", None),
        "effect": effect_snapshot,
    }


def _hash_canonical(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _canonical_mutation_input(desired: object) -> dict[str, Any] | None:
    """Bind idempotency to every submitted update field without storing prose."""
    if desired is None:
        return None
    model_dump = getattr(desired, "model_dump", None)
    if callable(model_dump):
        value = model_dump(mode="json")
    elif isinstance(desired, dict):
        value = desired
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_schedule_effect",
        )
    if not isinstance(value, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_schedule_effect",
        )
    return value


def deterministic_mcp_create_event_id(*, user_id: int, employee_id: int, category: str, idempotency_key: str, request_hash: str) -> str:
    material = f"v1|{user_id}|{employee_id}|{category}|{idempotency_key}|{request_hash}".encode("utf-8")
    return base64.b32hexencode(hashlib.sha256(material).digest()).decode("ascii").lower().rstrip("=")


def _result_for(operation: McpScheduleOperation) -> dict[str, Any]:
    return {"status": "SUCCEEDED", "event_id": operation.event_id, "correlation_id": operation.correlation_id, "write_applied": True}


def _mutation_result_for(operation: McpScheduleOperation, etag: str | None) -> dict[str, Any]:
    result = _result_for(operation)
    if etag and _ETAG_RE.fullmatch(etag):
        result["etag"] = etag
    return result


def _stored_mutation_error(operation: McpScheduleOperation) -> HTTPException:
    error = operation.error_json if isinstance(operation.error_json, dict) else {}
    operation_status = operation.status
    code = error.get("code")
    if not isinstance(code, str):
        code = "manual_review" if operation_status == "MANUAL_REVIEW" else "reconciliation_required"
    detail = "manual_review" if operation_status == "MANUAL_REVIEW" else code
    http_status = error.get("http_status")
    if not isinstance(http_status, int) or not 400 <= http_status <= 599:
        http_status = status.HTTP_409_CONFLICT
    return HTTPException(
        status_code=http_status,
        detail=detail,
        headers={"X-Correlation-ID": operation.correlation_id},
    )


def _expected_private(hook: McpCreateHook) -> dict[str, str]:
    return {
        "lss_owner_user_id": str(hook.principal.user.id),
        "lss_owner_employee_id": str(hook.employee_id),
        "lss_event_version": "1",
        "lss_correlation_id": hook.correlation_id,
        "lss_request_hash": hook.request_hash,
    }


def is_expected_mcp_create_event(hook: McpCreateHook, event: object) -> bool:
    return (
        isinstance(event, dict)
        and event.get("id") == hook.event_id
        and _event_private_properties(event) == _expected_private(hook)
    )


@dataclass(frozen=True)
class OwnerBinding:
    state: str
    write_allowed: bool

    def as_dict(self) -> dict[str, Any]:
        return {"state": self.state, "write_allowed": self.write_allowed}


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def date_text(value: date | None) -> str | None:
    return value.isoformat() if value else None


def datetime_text(value: datetime | None) -> str | None:
    return normalize_kst_datetime(value).isoformat() if value else None


def normalize_kst_datetime(value: datetime) -> datetime:
    """Treat naive schedule times as KST and convert aware values to KST."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def schedule_projection(row: CalendarSchedule | None) -> dict[str, Any] | None:
    """Return a bounded schedule state without user-entered free text."""
    if row is None:
        return None
    projection = {
        "event_id": row.google_event_id,
        "category": row.category,
        "is_all_day": bool(row.is_all_day),
        "schedule_kind": row.schedule_kind,
    }
    if row.is_all_day:
        projection["start_date"] = date_text(row.date)
        projection["end_date"] = date_text(row.end_date or row.date)
    else:
        projection["start_time"] = datetime_text(row.start_time)
        projection["end_time"] = datetime_text(row.end_time)
    return projection


def google_temporal_projection(event: object) -> dict[str, Any]:
    """Normalize Google event time fields without exposing event free text."""
    if not isinstance(event, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="upstream_invalid_response",
        )
    start = event.get("start")
    end = event.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="upstream_invalid_response",
        )

    start_date_value = start.get("date")
    end_date_value = end.get("date")
    if isinstance(start_date_value, str) and isinstance(end_date_value, str):
        try:
            start_date = date.fromisoformat(start_date_value)
            exclusive_end_date = date.fromisoformat(end_date_value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="upstream_invalid_response",
            ) from None
        if exclusive_end_date <= start_date:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="upstream_invalid_response",
            )
        return {
            "is_all_day": True,
            "start_date": start_date.isoformat(),
            "end_date": (exclusive_end_date - timedelta(days=1)).isoformat(),
        }

    start_time_value = start.get("dateTime")
    end_time_value = end.get("dateTime")
    if isinstance(start_time_value, str) and isinstance(end_time_value, str):
        try:
            start_time = datetime.fromisoformat(start_time_value.replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(end_time_value.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="upstream_invalid_response",
            ) from None
        normalized_start = normalize_kst_datetime(start_time)
        normalized_end = normalize_kst_datetime(end_time)
        if normalized_end <= normalized_start:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="upstream_invalid_response",
            )
        return {
            "is_all_day": False,
            "start_time": normalized_start.isoformat(),
            "end_time": normalized_end.isoformat(),
        }

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="upstream_invalid_response",
    )


def verified_schedule_projection(
    event: object,
    row: CalendarSchedule | None,
) -> dict[str, Any] | None:
    """Fail closed when Google and the local schedule time projection diverge."""
    projection = schedule_projection(row)
    if projection is None:
        return None
    google_projection = google_temporal_projection(event)
    if projection["is_all_day"]:
        local_temporal = {
            "is_all_day": True,
            "start_date": projection.get("start_date"),
            "end_date": projection.get("end_date"),
        }
    else:
        local_temporal = {
            "is_all_day": False,
            "start_time": projection.get("start_time"),
            "end_time": projection.get("end_time"),
        }
    if local_temporal != google_projection:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="schedule_state_drift",
        )
    return projection


def desired_projection(desired: object) -> dict[str, Any] | None:
    if desired is None:
        return None
    is_all_day = bool(getattr(desired, "is_all_day", True))
    if not is_all_day:
        return {
            "is_all_day": False,
            "start_time": datetime_text(getattr(desired, "start_time", None)),
            "end_time": datetime_text(getattr(desired, "end_time", None)),
        }
    start_date = getattr(desired, "date", None)
    end_date = getattr(desired, "end_date", None)
    return {
        "is_all_day": is_all_day,
        "start_date": date_text(start_date),
        "end_date": date_text(end_date),
    }


def _event_private_properties(event: object) -> dict[str, object]:
    if not isinstance(event, dict):
        return {}
    extended = event.get("extendedProperties")
    if not isinstance(extended, dict):
        return {}
    private = extended.get("private")
    return private if isinstance(private, dict) else {}


def owner_binding(event: object, row: CalendarSchedule | None, principal_user_id: int) -> OwnerBinding:
    """Check immutable Google ownership and local creator binding exactly.

    A summary prefix is presentation text and is intentionally not consulted.
    """
    owner_value = _event_private_properties(event).get("lss_owner_user_id")
    if owner_value is None:
        return OwnerBinding("LEGACY_OWNER_UNBOUND", False)
    if str(owner_value) != str(principal_user_id):
        return OwnerBinding("OWNER_MISMATCH", False)
    if row is None or row.created_by != principal_user_id:
        return OwnerBinding("OWNER_MISMATCH", False)
    return OwnerBinding("BOUND", True)


def safe_google_etag(event: object) -> str | None:
    if not isinstance(event, dict):
        return None
    etag = event.get("etag")
    if not isinstance(etag, str) or len(etag) > 255:
        return None
    return etag


def google_event(service: object, calendar_id: str, event_id: str) -> dict[str, Any]:
    try:
        result = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    except HttpError as exc:
        if getattr(getattr(exc, "resp", None), "status", None) == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="schedule_not_found") from None
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="upstream_unavailable") from None
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="upstream_unavailable") from None
    if not isinstance(result, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="upstream_invalid_response")
    return result


def current_google_event(get_calendar_service, category: str, event_id: str) -> dict[str, Any]:
    """Resolve calendar configuration and read one event without leaking internals."""
    try:
        service, calendar_id = get_calendar_service(category)
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="upstream_unavailable") from None
    return google_event(service, calendar_id, event_id)


def affected_weeks(
    row: CalendarSchedule | None,
    desired: object,
) -> list[date]:
    ranges: list[tuple[date, date]] = []
    if row:
        if not row.is_all_day and row.start_time:
            current_start = normalize_kst_datetime(row.start_time)
            current_end = normalize_kst_datetime(row.end_time or row.start_time)
            ranges.append((current_start.date(), current_end.date()))
        elif row.date:
            ranges.append((row.date, row.end_date or row.date))
    if desired is not None:
        if not bool(getattr(desired, "is_all_day", True)):
            start_time = getattr(desired, "start_time", None)
            end_time = getattr(desired, "end_time", None)
            if start_time and end_time:
                ranges.append((
                    normalize_kst_datetime(start_time).date(),
                    normalize_kst_datetime(end_time).date(),
                ))
        else:
            start = getattr(desired, "date", None)
            end = getattr(desired, "end_date", None)
            if start and end:
                ranges.append((start, end))

    weeks: set[date] = set()
    for range_start, range_end in ranges:
        cursor = week_start(range_start)
        last = week_start(range_end)
        while cursor <= last:
            weeks.add(cursor)
            cursor += timedelta(days=7)
    return sorted(weeks)


def relevant_timesheet_statuses(
    db: Session,
    *,
    user: object,
    weeks: Iterable[date],
) -> tuple[list[dict[str, str]], bool]:
    employee_code = getattr(user, "employee_code", None)
    if not employee_code:
        return [], False
    employee = db.query(Employee).filter(Employee.emp_code == employee_code).one_or_none()
    if employee is None:
        return [], False
    week_values = list(weeks)
    if not week_values:
        return [], True
    rows = (
        db.query(Timesheet)
        .filter(Timesheet.employee_id == employee.id, Timesheet.week_start.in_(week_values))
        .order_by(Timesheet.week_start.asc(), Timesheet.id.asc())
        .all()
    )
    return [
        {"week_start": row.week_start.isoformat(), "status": row.status or ""}
        for row in rows
    ], True


def build_mcp_timesheet_lock_query(
    db: Session,
    *,
    employee_id: int,
    weeks: Iterable[date],
):
    """Build the deterministic PostgreSQL row-lock query for MCP mutations."""
    return build_shared_timesheet_lock_query(
        db,
        employee_id=employee_id,
        weeks=weeks,
    )


def lock_mcp_timesheet_rows(
    db: Session,
    hook: McpCreateHook | McpMutationHook,
) -> list[Timesheet]:
    """Lock and revalidate headers per docs/mcp/SCHEDULE-MUTATION-LOCKING.md."""
    operation_id = hook.operation.id
    allowed_operation_statuses = (
        {"IN_PROGRESS", "RECONCILIATION_REQUIRED"}
        if isinstance(hook, McpCreateHook)
        else {"IN_PROGRESS"}
    )

    def rebind_operation() -> None:
        operation = (
            db.query(McpScheduleOperation)
            .filter(McpScheduleOperation.id == operation_id)
            .populate_existing()
            .one_or_none()
        )
        if (
            operation is None
            or operation.status not in allowed_operation_statuses
        ):
            raise ScheduleTimesheetScopeUnstable(
                "MCP operation changed during schedule scope restart"
            )
        hook.operation = operation

    try:
        rows = lock_revalidated_schedule_timesheet_scope(
            db,
            event_id=hook.event_id if isinstance(hook, McpMutationHook) else None,
            category=hook.operation.category,
            employee_id=hook.employee_id,
            desired_weeks=hook.desired_weeks,
            on_restart=rebind_operation,
        )
    except ScheduleTimesheetScopeUnstable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="timesheet_scope_unstable",
            headers={"X-Correlation-ID": hook.correlation_id},
        ) from None
    if any((row.status or "") != WRITABLE_TIMESHEET_STATUS for row in rows):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="timesheet_locked",
            headers={"X-Correlation-ID": hook.correlation_id},
        )
    return rows


def preflight_schedule(
    db: Session,
    *,
    user: object,
    action: str,
    category: str,
    event_id: str | None,
    desired: object,
    get_calendar_service,
) -> dict[str, Any]:
    """Calculate only; this function never flushes, commits, or writes upstream."""
    row = None
    event: dict[str, Any] | None = None
    binding = OwnerBinding("NOT_APPLICABLE", True)
    if event_id:
        row = (
            db.query(CalendarSchedule)
            .filter(
                CalendarSchedule.google_event_id == event_id,
                CalendarSchedule.category == category,
                CalendarSchedule.created_by == user.id,
            )
            .one_or_none()
        )
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="schedule_not_found")
        event = current_google_event(get_calendar_service, category, event_id)
        binding = owner_binding(event, row, user.id)
        current = verified_schedule_projection(event, row)
    else:
        current = None

    weeks = affected_weeks(row, desired)
    timesheet_statuses, employee_found = relevant_timesheet_statuses(db, user=user, weeks=weeks)
    denial_reasons: list[str] = []
    if binding.state == "LEGACY_OWNER_UNBOUND":
        denial_reasons.append("legacy_owner_unbound")
    elif binding.state == "OWNER_MISMATCH":
        denial_reasons.append("owner_mismatch")
    if not employee_found:
        denial_reasons.append("employee_not_found")
    if any(item["status"] != WRITABLE_TIMESHEET_STATUS for item in timesheet_statuses):
        denial_reasons.append("timesheet_locked")

    return {
        "action": action,
        "category": category,
        "event_id": event_id,
        "current": current,
        "desired": desired_projection(desired),
        "owner_binding": binding.as_dict(),
        "affected_weeks": [value.isoformat() for value in weeks],
        "timesheet_statuses": timesheet_statuses,
        "etag": safe_google_etag(event),
        "write_allowed": not denial_reasons,
        "denial_reasons": denial_reasons,
    }


def _strict_local_owner_row(db: Session, *, event_id: str, category: str, user_id: int) -> CalendarSchedule:
    row = (
        db.query(CalendarSchedule)
        .filter(
            CalendarSchedule.google_event_id == event_id,
            CalendarSchedule.category == category,
        )
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="schedule_not_found")
    if row.created_by != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_mismatch")
    return row


def begin_mcp_mutation(
    db: Session,
    *,
    request: object,
    current_user: object,
    action: str,
    category: str,
    event_id: str,
    desired: object,
    service: object,
    calendar_id: str,
) -> McpMutationHook | None:
    """Claim one strict MCP update/delete before its Google side effect."""
    if getattr(request, "headers", {}).get("X-LSS-MCP-Schedule") != "1":
        return None
    if action not in {"UPDATE", "DELETE"} or category not in SCHEDULE_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_category")
    principal = resolve_mcp_schedule_principal(request, db)
    if getattr(current_user, "id", None) != principal.user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_token")
    if SCHEDULE_WRITE_SCOPE not in principal.scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="missing_scope")
    _require_schedule_write_enabled()
    idempotency_key = _required_header(request, "Idempotency-Key", "invalid_idempotency_key")
    correlation_id = _required_header(request, "X-Correlation-ID", "invalid_correlation_id")
    expected_etag = _if_match_header(request)
    normalized_desired = _parse_create_desired(desired) if desired is not None else None
    desired_input = _canonical_mutation_input(desired)

    employee_code = getattr(principal.user, "employee_code", None)
    employee = db.query(Employee).filter(Employee.emp_code == employee_code).one_or_none() if employee_code else None
    if employee is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="employee_not_found")
    employee_id = employee.id
    desired_state = desired_projection(normalized_desired)
    canonical = {
        "version": 1,
        "action": action,
        "category": category,
        "event_id": event_id,
        "owner_user_id": principal.user.id,
        "owner_employee_id": employee_id,
        "expected_etag": expected_etag,
        "desired": desired_state,
        "desired_input": desired_input,
    }
    request_hash = _hash_canonical(canonical)
    desired_state_hash = _hash_canonical({
        "action": action,
        "desired": desired_state,
        "desired_input": desired_input,
        "expected_etag": expected_etag,
    })
    candidate = McpScheduleOperation(
        user_id=principal.user.id, category=category, action=action, event_id=event_id,
        idempotency_key=idempotency_key, correlation_id=correlation_id, request_hash=request_hash,
        expected_etag=expected_etag, desired_state_hash=desired_state_hash, status="IN_PROGRESS",
    )
    try:
        operation, claimed = claim_or_replay_operation(db, operation=candidate)
    except CorrelationConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="correlation_id_conflict") from None
    except IdempotencyConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="idempotency_conflict") from None

    if not claimed:
        hook = McpMutationHook(
            principal, operation, event_id, expected_etag, {}, request_hash,
            operation.correlation_id, employee_id, action, (), (),
        )
        if operation.status == "SUCCEEDED":
            hook.replay_succeeded = True
            return hook
        raise _stored_mutation_error(operation)

    # Resolve immutable owner/etag evidence before making the claim durable.
    # Mutable timesheet status is revalidated under a row lock afterwards.
    row = _strict_local_owner_row(db, event_id=event_id, category=category, user_id=principal.user.id)
    existing_event = google_event(service, calendar_id, event_id)
    binding = owner_binding(existing_event, row, principal.user.id)
    if binding.state == "LEGACY_OWNER_UNBOUND":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="legacy_owner_unbound")
    if not binding.write_allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_mismatch")
    if expected_etag != safe_google_etag(existing_event):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="stale_event")

    hook = McpMutationHook(
        principal, operation, event_id, expected_etag, existing_event, request_hash,
        operation.correlation_id, employee_id, action,
        tuple(affected_weeks(row, normalized_desired)),
        tuple(affected_weeks(None, normalized_desired)),
    )
    db.commit()
    return hook


def attach_if_match(request: object, expected_etag: str) -> None:
    """Use the Google request object's header map without rebuilding the request."""
    headers = getattr(request, "headers", None)
    if headers is None:
        headers = {}
        setattr(request, "headers", headers)
    headers["If-Match"] = expected_etag


def complete_mcp_mutation(hook: McpMutationHook, *, etag: str | None = None) -> None:
    hook.operation.status = "SUCCEEDED"
    hook.operation.result_json = _mutation_result_for(hook.operation, etag)
    hook.operation.error_json = None


def record_mcp_mutation_failure(
    db: Session,
    hook: McpMutationHook | None,
    *,
    operation_status: str,
    code: str,
    http_status: int,
) -> None:
    if hook is None:
        return
    try:
        operation = db.query(McpScheduleOperation).filter(
            McpScheduleOperation.user_id == hook.principal.user.id,
            McpScheduleOperation.idempotency_key == hook.operation.idempotency_key,
        ).one_or_none()
        if operation is None:
            return
        operation.status = operation_status
        operation.result_json = None
        operation.error_json = {
            "code": code, "status": operation_status, "correlation_id": hook.correlation_id,
            "http_status": http_status,
        }
        db.commit()
    except Exception:
        db.rollback()


def begin_mcp_create(
    db: Session,
    *,
    request: object,
    current_user: object,
    payload: object,
    effect_snapshot: dict[str, Any] | None,
    service: object,
    calendar_id: str,
) -> McpCreateHook | None:
    """Claim/replay an explicit MCP create without changing ordinary UI flow."""
    if getattr(request, "headers", {}).get("X-LSS-MCP-Schedule") != "1":
        return None
    principal = resolve_mcp_schedule_principal(request, db)
    if getattr(current_user, "id", None) != principal.user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_token")
    if SCHEDULE_WRITE_SCOPE not in principal.scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="missing_scope")
    _require_schedule_write_enabled()
    idempotency_key = _required_header(request, "Idempotency-Key", "invalid_idempotency_key")
    correlation_id = _required_header(request, "X-Correlation-ID", "invalid_correlation_id")
    desired = _parse_create_desired(payload)
    canonical = canonical_mcp_create_effect(effect_snapshot, principal)
    request_hash = _hash_canonical(canonical)
    employee_code = getattr(principal.user, "employee_code", None)
    employee = db.query(Employee).filter(Employee.emp_code == employee_code).one_or_none() if employee_code else None
    if employee is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="employee_not_found")
    event_id = deterministic_mcp_create_event_id(
        user_id=principal.user.id, employee_id=employee.id, category=effect_snapshot["calendar"]["category"],
        idempotency_key=idempotency_key, request_hash=request_hash,
    )
    candidate = McpScheduleOperation(
        user_id=principal.user.id, category=effect_snapshot["calendar"]["category"], action="CREATE", event_id=event_id,
        idempotency_key=idempotency_key, correlation_id=correlation_id, request_hash=request_hash,
        status="IN_PROGRESS",
    )
    try:
        operation, claimed = claim_or_replay_operation(db, operation=candidate)
    except CorrelationConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="correlation_id_conflict") from None
    except IdempotencyConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="idempotency_conflict") from None
    hook = McpCreateHook(
        principal,
        operation,
        operation.event_id or event_id,
        request_hash,
        operation.correlation_id,
        employee.id,
        tuple(affected_weeks(None, desired)),
        tuple(affected_weeks(None, desired)),
    )
    if claimed:
        # This boundary is deliberately before every external side effect.
        # A process loss after Google accepts the deterministic event can then
        # be recovered by a fresh request/session rather than duplicated.
        db.commit()
        return hook
    if operation.status == "SUCCEEDED":
        hook.replay_succeeded = True
        return hook
    if operation.status not in {"IN_PROGRESS", "RECONCILIATION_REQUIRED"}:
        raise _stored_mutation_error(operation)
    recovery_status = operation.status
    try:
        # This is the single bounded, read-only observation allowed for
        # deterministic CREATE recovery; it never retries the insert.
        observed = service.events().get(calendarId=calendar_id, eventId=hook.event_id).execute()
    except Exception:
        if recovery_status == "RECONCILIATION_REQUIRED":
            raise _stored_mutation_error(operation) from None
        operation.status = "RECONCILIATION_REQUIRED"
        operation.error_json = {"code": "reconciliation_required", "status": "RECONCILIATION_REQUIRED", "correlation_id": hook.correlation_id, "http_status": 409}
        db.commit()
        raise _stored_mutation_error(operation) from None
    if not is_expected_mcp_create_event(hook, observed):
        operation.status = "MANUAL_REVIEW"
        operation.error_json = {"code": "conflicting_evidence", "status": "MANUAL_REVIEW", "correlation_id": hook.correlation_id, "http_status": 409}
        db.commit()
        raise _stored_mutation_error(operation)
    hook.reconcile_observed = True
    # End replay/readback work before the router starts the lock-holding
    # mutation transaction.
    db.commit()
    return hook


def complete_mcp_create(hook: McpCreateHook) -> None:
    hook.operation.event_id = hook.event_id
    hook.operation.status = "SUCCEEDED"
    hook.operation.result_json = _result_for(hook.operation)
    hook.operation.error_json = None


def record_mcp_create_failure(
    db: Session,
    hook: McpCreateHook | None,
    *,
    operation_status: str,
    code: str,
    http_status: int,
) -> None:
    """Persist a bounded failure fact after the legacy transaction rolls back."""
    if hook is None:
        return
    try:
        operation = db.query(McpScheduleOperation).filter(
            McpScheduleOperation.user_id == hook.principal.user.id,
            McpScheduleOperation.idempotency_key == hook.operation.idempotency_key,
        ).one_or_none()
        if operation is None:
            operation = McpScheduleOperation(
                user_id=hook.principal.user.id,
                category=hook.operation.category,
                action="CREATE",
                event_id=hook.event_id,
                idempotency_key=hook.operation.idempotency_key,
                correlation_id=hook.correlation_id,
                request_hash=hook.request_hash,
                status=operation_status,
            )
            db.add(operation)
        else:
            operation.event_id = hook.event_id
            operation.status = operation_status
        operation.result_json = None
        operation.error_json = {
            "code": code,
            "status": operation_status,
            "correlation_id": hook.correlation_id,
            "http_status": http_status,
        }
        db.commit()
    except Exception:
        db.rollback()
