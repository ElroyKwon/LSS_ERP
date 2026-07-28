"""Scoped, bounded MCP schedule read and preflight endpoints."""

from __future__ import annotations

import re
import uuid
from datetime import date, date as Date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.common import CalendarSchedule
from ..models.mcp_schedule import McpScheduleOperation, redact_operation_error, redact_operation_result
from ..services.mcp_schedule_control import (
    owner_binding,
    current_google_event,
    normalize_kst_datetime,
    preflight_schedule,
    safe_google_etag,
    schedule_projection,
    verified_schedule_projection,
)
from ..utils.mcp_schedule_auth import McpSchedulePrincipal, require_schedule_read, require_schedule_write
from .schedule import get_calendar_config_and_service


router = APIRouter(prefix="/api/mcp/schedules", tags=["MCP Schedules"])

_EVENT_ID_RE = re.compile(r"^[0-9a-v]{8,255}$")
_CORRELATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_MAX_LIST_RANGE_DAYS = 31
# Proposals use the same 31-day date-difference bound as the list endpoint.
# For all-day proposals this permits 32 inclusive calendar dates.
MAX_PROPOSAL_RANGE_DAYS = _MAX_LIST_RANGE_DAYS


class ScheduleDesiredState(BaseModel):
    is_all_day: bool = True
    date: Date | None = None
    end_date: Date | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    # Accepted only to validate an MCP proposal; it is never reflected back.
    content: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_exact_time_shape_and_range(self):
        if self.is_all_day:
            if self.date is None or self.end_date is None:
                raise ValueError("all-day proposals require date and end_date")
            if self.start_time is not None or self.end_time is not None:
                raise ValueError("all-day proposals forbid start_time and end_time")
            if self.end_date < self.date:
                raise ValueError("end_date must not precede date")
            if (self.end_date - self.date).days > MAX_PROPOSAL_RANGE_DAYS:
                raise ValueError("proposal date range exceeds 31 days")
            return self

        if self.start_time is None or self.end_time is None:
            raise ValueError("timed proposals require start_time and end_time")
        if self.date is not None or self.end_date is not None:
            raise ValueError("timed proposals forbid date and end_date")
        start_is_aware = self.start_time.tzinfo is not None and self.start_time.utcoffset() is not None
        end_is_aware = self.end_time.tzinfo is not None and self.end_time.utcoffset() is not None
        if start_is_aware != end_is_aware:
            raise ValueError("timed proposal datetimes must use matching timezone awareness")
        start_time = normalize_kst_datetime(self.start_time)
        end_time = normalize_kst_datetime(self.end_time)
        if end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        if end_time - start_time > timedelta(days=MAX_PROPOSAL_RANGE_DAYS):
            raise ValueError("proposal time range exceeds 31 days")
        self.start_time = start_time
        self.end_time = end_time
        return self


class SchedulePreflightRequest(BaseModel):
    action: Literal["CREATE", "UPDATE", "DELETE"]
    category: Literal["company", "refresh"]
    event_id: str | None = None
    desired: ScheduleDesiredState | None = None

    @field_validator("event_id")
    @classmethod
    def valid_event_id(cls, value: str | None):
        if value is not None and not _EVENT_ID_RE.fullmatch(value):
            raise ValueError("invalid event_id")
        return value

    @model_validator(mode="after")
    def action_requires_correct_fields(self):
        if self.action in {"UPDATE", "DELETE"} and self.event_id is None:
            raise ValueError("event_id is required")
        if self.action in {"CREATE", "UPDATE"} and self.desired is None:
            raise ValueError("desired is required")
        if self.action == "DELETE" and self.desired is not None:
            raise ValueError("delete preflight must not include desired")
        return self


def _envelope(data: dict, *, correlation_id: str | None = None) -> dict:
    return {
        "success": True,
        "data": data,
        "error": None,
        "meta": {
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    }


def _validated_event_id(event_id: str) -> str:
    if not _EVENT_ID_RE.fullmatch(event_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_event_id")
    return event_id


def _list_range(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date:
        if end_date < start_date or (end_date - start_date).days > _MAX_LIST_RANGE_DAYS:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_date_range")


@router.get("")
def list_mcp_schedules(
    category: Literal["company", "refresh"] = Query("company"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    principal: McpSchedulePrincipal = Depends(require_schedule_read),
    db: Session = Depends(get_db),
):
    _list_range(start_date, end_date)
    query = db.query(CalendarSchedule).filter(
        CalendarSchedule.category == category,
    )
    if start_date:
        query = query.filter(CalendarSchedule.date >= start_date)
    if end_date:
        query = query.filter(CalendarSchedule.date <= end_date)
    rows = query.order_by(CalendarSchedule.date.asc(), CalendarSchedule.id.asc()).limit(limit).all()
    items = []
    for row in rows:
        projection = schedule_projection(row)
        item = {
            "event_id": projection["event_id"],
            "category": projection["category"],
            "is_all_day": projection["is_all_day"],
            "schedule_kind": projection["schedule_kind"],
        }
        if projection["is_all_day"]:
            item["start_date"] = projection["start_date"]
            item["end_date"] = projection["end_date"]
        else:
            item["start_time"] = projection["start_time"]
            item["end_time"] = projection["end_time"]
        items.append(item)
    return _envelope({"items": items, "count": len(items)})


@router.get("/operations/{correlation_id}")
def get_mcp_schedule_operation(
    correlation_id: str,
    principal: McpSchedulePrincipal = Depends(require_schedule_write),
    db: Session = Depends(get_db),
):
    if not _CORRELATION_ID_RE.fullmatch(correlation_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_correlation_id")
    operation = (
        db.query(McpScheduleOperation)
        .filter(
            McpScheduleOperation.correlation_id == correlation_id,
            McpScheduleOperation.user_id == principal.user.id,
        )
        .one_or_none()
    )
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="operation_not_found")
    data = {
        "correlation_id": operation.correlation_id,
        "status": operation.status,
        "event_id": operation.event_id,
        "result": redact_operation_result(operation.result_json) or {},
        "error": redact_operation_error(operation.error_json) or {},
    }
    return _envelope(data, correlation_id=operation.correlation_id)


@router.get("/{event_id}")
def get_mcp_schedule_detail(
    event_id: str,
    category: Literal["company", "refresh"] = Query("company"),
    principal: McpSchedulePrincipal = Depends(require_schedule_read),
    db: Session = Depends(get_db),
):
    event_id = _validated_event_id(event_id)
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
    event = current_google_event(get_calendar_config_and_service, category, event_id)
    binding = owner_binding(event, row, principal.user.id)
    denial_reasons = [] if binding.write_allowed else [
        "legacy_owner_unbound" if binding.state == "LEGACY_OWNER_UNBOUND" else "owner_mismatch",
    ]
    projection = verified_schedule_projection(event, row)
    return _envelope({
        **projection,
        "etag": safe_google_etag(event),
        "owner_binding": binding.as_dict(),
        "eligibility": {
            "write_allowed": binding.write_allowed,
            "denial_reasons": denial_reasons,
        },
    })


@router.post("/preflight")
def preflight_mcp_schedule(
    payload: SchedulePreflightRequest,
    principal: McpSchedulePrincipal = Depends(require_schedule_write),
    db: Session = Depends(get_db),
):
    result = preflight_schedule(
        db,
        user=principal.user,
        action=payload.action,
        category=payload.category,
        event_id=payload.event_id,
        desired=payload.desired,
        get_calendar_service=get_calendar_config_and_service,
    )
    return _envelope(result)
