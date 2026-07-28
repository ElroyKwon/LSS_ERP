"""Strict standalone-MCP schemas for the bounded schedule REST contract."""

from __future__ import annotations

from datetime import date as Date, datetime as DateTime, timedelta
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from .common import StrictModel


ScheduleCategory = Literal["company", "refresh"]
ScheduleOperation = Literal["CREATE", "UPDATE", "DELETE"]
ScheduleOperationStatus = Literal[
    "IN_PROGRESS",
    "SUCCEEDED",
    "FAILED",
    "RECONCILIATION_REQUIRED",
    "MANUAL_REVIEW",
]
OwnerBindingState = Literal[
    "BOUND",
    "LEGACY_OWNER_UNBOUND",
    "OWNER_MISMATCH",
    "NOT_APPLICABLE",
]
ScheduleDenialReason = Literal[
    "legacy_owner_unbound",
    "owner_mismatch",
    "employee_not_found",
    "timesheet_locked",
]
EventId = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9a-v]+$", min_length=8, max_length=255),
]
CorrelationId = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_-]+$", min_length=8, max_length=128),
]
IdempotencyKey = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9._:-]+$", min_length=8, max_length=128),
]
ETag = Annotated[
    str,
    StringConstraints(pattern=r'^"[A-Za-z0-9._:-]{1,253}"$', max_length=255),
]
ScheduleConfirmationToken = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_-]+$", min_length=32, max_length=256),
]

MAX_SCHEDULE_RANGE_DAYS = 31
MAX_SCHEDULE_LIST_LIMIT = 100


def _validate_date_range(start: Date, end: Date) -> None:
    if end < start or (end - start).days > MAX_SCHEDULE_RANGE_DAYS:
        raise ValueError("schedule date range must be ordered and at most 31 days")


def _require_aware(value: DateTime) -> DateTime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("schedule datetimes must be timezone-aware")
    return value


def _require_exact_bool(value: object) -> object:
    if type(value) is not bool:
        raise ValueError("value must be a JSON boolean")
    return value


class ScheduleListRequest(StrictModel):
    category: ScheduleCategory = "company"
    start_date: Date | None = None
    end_date: Date | None = None
    limit: StrictInt = Field(default=50, ge=1, le=MAX_SCHEDULE_LIST_LIMIT)

    @model_validator(mode="after")
    def validate_bounded_range(self) -> "ScheduleListRequest":
        # The backend deliberately supports either one-sided bound. Ordering
        # and the 31-day maximum apply only when both bounds are supplied.
        if self.start_date is not None and self.end_date is not None:
            _validate_date_range(self.start_date, self.end_date)
        return self


class ScheduleAllDayProposal(StrictModel):
    is_all_day: Literal[True] = True
    date: Date
    end_date: Date
    content: str | None = Field(default=None, min_length=1, max_length=2000)

    @field_validator("is_all_day", mode="before")
    @classmethod
    def require_boolean_discriminator(cls, value: object) -> object:
        return _require_exact_bool(value)

    @model_validator(mode="after")
    def validate_bounded_range(self) -> "ScheduleAllDayProposal":
        _validate_date_range(self.date, self.end_date)
        return self


class ScheduleTimedProposal(StrictModel):
    is_all_day: Literal[False]
    start_time: DateTime
    end_time: DateTime
    content: str | None = Field(default=None, min_length=1, max_length=2000)

    @field_validator("is_all_day", mode="before")
    @classmethod
    def require_boolean_discriminator(cls, value: object) -> object:
        return _require_exact_bool(value)

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, value: DateTime) -> DateTime:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_bounded_range(self) -> "ScheduleTimedProposal":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.end_time - self.start_time > timedelta(days=MAX_SCHEDULE_RANGE_DAYS):
            raise ValueError("schedule time range must be at most 31 days")
        return self


ScheduleProposal = ScheduleAllDayProposal | ScheduleTimedProposal


class SchedulePreflightRequest(StrictModel):
    action: ScheduleOperation
    category: ScheduleCategory
    event_id: EventId | None = None
    desired: ScheduleProposal | None = None

    @model_validator(mode="after")
    def validate_action_shape(self) -> "SchedulePreflightRequest":
        if self.action == "CREATE" and self.event_id is not None:
            raise ValueError("event_id must be omitted for create")
        if self.action in {"UPDATE", "DELETE"} and self.event_id is None:
            raise ValueError("event_id is required for update and delete")
        if self.action in {"CREATE", "UPDATE"} and self.desired is None:
            raise ValueError("desired is required for create and update")
        if self.action == "DELETE" and self.desired is not None:
            raise ValueError("desired must be omitted for delete")
        return self


class ScheduleMutationRequest(StrictModel):
    """Legacy schedule body without caller-controlled owner identity."""

    content: str = Field(min_length=1, max_length=2000)
    type: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    category: ScheduleCategory
    is_all_day: StrictBool
    date: Date | None = None
    end_date: Date | None = None
    start_time: DateTime | None = None
    end_time: DateTime | None = None
    schedule_kind: str | None = Field(default=None, min_length=1, max_length=100)
    timesheet_project_id: StrictInt | None = Field(default=None, gt=0)
    timesheet_project_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    timesheet_project_source: Literal["실행", "영업", "공통"] | None = None

    @model_validator(mode="after")
    def validate_exact_time_shape(self) -> "ScheduleMutationRequest":
        if self.is_all_day:
            if self.date is None or self.end_date is None:
                raise ValueError("all-day mutation requires date and end_date")
            if self.start_time is not None or self.end_time is not None:
                raise ValueError("all-day mutation forbids timed fields")
            _validate_date_range(self.date, self.end_date)
            return self
        if self.start_time is None or self.end_time is None:
            raise ValueError("timed mutation requires start_time and end_time")
        if self.date is not None or self.end_date is not None:
            raise ValueError("timed mutation forbids date fields")
        _require_aware(self.start_time)
        _require_aware(self.end_time)
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.end_time - self.start_time > timedelta(days=MAX_SCHEDULE_RANGE_DAYS):
            raise ValueError("schedule time range must be at most 31 days")
        return self


class ScheduleAllDayItem(StrictModel):
    event_id: EventId
    category: ScheduleCategory
    is_all_day: Literal[True]
    schedule_kind: str | None = Field(default=None, max_length=100)
    start_date: Date
    end_date: Date

    @field_validator("is_all_day", mode="before")
    @classmethod
    def require_boolean_discriminator(cls, value: object) -> object:
        return _require_exact_bool(value)

    @model_validator(mode="after")
    def validate_ordered_range(self) -> "ScheduleAllDayItem":
        if self.end_date < self.start_date:
            raise ValueError("schedule response end_date precedes start_date")
        return self


class ScheduleTimedItem(StrictModel):
    event_id: EventId
    category: ScheduleCategory
    is_all_day: Literal[False]
    schedule_kind: str | None = Field(default=None, max_length=100)
    start_time: DateTime
    end_time: DateTime

    @field_validator("is_all_day", mode="before")
    @classmethod
    def require_boolean_discriminator(cls, value: object) -> object:
        return _require_exact_bool(value)

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, value: DateTime) -> DateTime:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_ordered_range(self) -> "ScheduleTimedItem":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


ScheduleItem = ScheduleAllDayItem | ScheduleTimedItem


class ScheduleListData(StrictModel):
    items: list[ScheduleItem] = Field(max_length=MAX_SCHEDULE_LIST_LIMIT)
    count: StrictInt = Field(ge=0, le=MAX_SCHEDULE_LIST_LIMIT)

    @model_validator(mode="after")
    def count_matches_items(self) -> "ScheduleListData":
        if self.count != len(self.items):
            raise ValueError("schedule count must match items")
        return self


class OwnerBinding(StrictModel):
    state: OwnerBindingState
    write_allowed: StrictBool

    @model_validator(mode="after")
    def validate_state_authority(self) -> "OwnerBinding":
        expected = self.state in {"BOUND", "NOT_APPLICABLE"}
        if self.write_allowed is not expected:
            raise ValueError("owner binding authority contradicts its state")
        return self


class ScheduleEligibility(StrictModel):
    write_allowed: StrictBool
    denial_reasons: list[ScheduleDenialReason] = Field(max_length=4)

    @field_validator("denial_reasons")
    @classmethod
    def require_unique_reasons(
        cls,
        value: list[ScheduleDenialReason],
    ) -> list[ScheduleDenialReason]:
        if len(value) != len(set(value)):
            raise ValueError("denial reasons must be unique")
        return value

    @model_validator(mode="after")
    def validate_write_authority(self) -> "ScheduleEligibility":
        if self.write_allowed is not (not self.denial_reasons):
            raise ValueError("eligibility authority contradicts denial reasons")
        return self


def _validate_detail_authority(
    owner_binding: OwnerBinding,
    eligibility: ScheduleEligibility,
) -> None:
    if owner_binding.state == "NOT_APPLICABLE":
        raise ValueError("detail owner binding cannot be NOT_APPLICABLE")
    expected_reasons: list[ScheduleDenialReason]
    if owner_binding.state == "LEGACY_OWNER_UNBOUND":
        expected_reasons = ["legacy_owner_unbound"]
    elif owner_binding.state == "OWNER_MISMATCH":
        expected_reasons = ["owner_mismatch"]
    else:
        expected_reasons = []
    if (
        eligibility.write_allowed is not owner_binding.write_allowed
        or eligibility.denial_reasons != expected_reasons
    ):
        raise ValueError("detail eligibility contradicts owner binding")


class ScheduleAllDayDetail(ScheduleAllDayItem):
    etag: ETag
    owner_binding: OwnerBinding
    eligibility: ScheduleEligibility

    @model_validator(mode="after")
    def validate_authority(self) -> "ScheduleAllDayDetail":
        _validate_detail_authority(self.owner_binding, self.eligibility)
        return self


class ScheduleTimedDetail(ScheduleTimedItem):
    etag: ETag
    owner_binding: OwnerBinding
    eligibility: ScheduleEligibility

    @model_validator(mode="after")
    def validate_authority(self) -> "ScheduleTimedDetail":
        _validate_detail_authority(self.owner_binding, self.eligibility)
        return self


ScheduleDetail = ScheduleAllDayDetail | ScheduleTimedDetail


class ScheduleAllDayProjection(StrictModel):
    is_all_day: Literal[True]
    start_date: Date
    end_date: Date

    @field_validator("is_all_day", mode="before")
    @classmethod
    def require_boolean_discriminator(cls, value: object) -> object:
        return _require_exact_bool(value)

    @model_validator(mode="after")
    def validate_ordered_range(self) -> "ScheduleAllDayProjection":
        if self.end_date < self.start_date:
            raise ValueError("schedule response end_date precedes start_date")
        return self


class ScheduleTimedProjection(StrictModel):
    is_all_day: Literal[False]
    start_time: DateTime
    end_time: DateTime

    @field_validator("is_all_day", mode="before")
    @classmethod
    def require_boolean_discriminator(cls, value: object) -> object:
        return _require_exact_bool(value)

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, value: DateTime) -> DateTime:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_ordered_range(self) -> "ScheduleTimedProjection":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


ScheduleProjection = ScheduleAllDayProjection | ScheduleTimedProjection


class TimesheetStatus(StrictModel):
    week_start: Date
    status: str = Field(min_length=1, max_length=32)


class SchedulePreflightData(StrictModel):
    action: ScheduleOperation
    category: ScheduleCategory
    event_id: EventId | None
    current: ScheduleItem | None
    desired: ScheduleProjection | None
    owner_binding: OwnerBinding
    # Legacy schedules may span many weeks. max_response_bytes is the response
    # bound; the backend does not guarantee a fixed count for these evidence
    # collections.
    affected_weeks: list[Date]
    timesheet_statuses: list[TimesheetStatus]
    etag: ETag | None
    write_allowed: StrictBool
    denial_reasons: list[ScheduleDenialReason] = Field(max_length=4)

    @field_validator("denial_reasons")
    @classmethod
    def require_unique_reasons(
        cls,
        value: list[ScheduleDenialReason],
    ) -> list[ScheduleDenialReason]:
        if len(value) != len(set(value)):
            raise ValueError("denial reasons must be unique")
        return value

    @model_validator(mode="after")
    def validate_action_and_current_binding(self) -> "SchedulePreflightData":
        if self.action == "CREATE":
            if self.owner_binding.state != "NOT_APPLICABLE":
                raise ValueError(
                    "CREATE preflight owner binding must be NOT_APPLICABLE"
                )
        elif self.owner_binding.state == "NOT_APPLICABLE":
            raise ValueError(
                "mutation preflight owner binding cannot be NOT_APPLICABLE"
            )

        owner_reason_by_state: dict[
            OwnerBindingState,
            ScheduleDenialReason | None,
        ] = {
            "BOUND": None,
            "NOT_APPLICABLE": None,
            "LEGACY_OWNER_UNBOUND": "legacy_owner_unbound",
            "OWNER_MISMATCH": "owner_mismatch",
        }
        expected_owner_reason = owner_reason_by_state[self.owner_binding.state]
        actual_owner_reasons = {
            reason
            for reason in self.denial_reasons
            if reason in {"legacy_owner_unbound", "owner_mismatch"}
        }
        expected_owner_reasons = (
            {expected_owner_reason} if expected_owner_reason is not None else set()
        )
        if actual_owner_reasons != expected_owner_reasons:
            raise ValueError("preflight owner denial evidence is inconsistent")

        has_locked_timesheet = any(
            item.status != "작성중" for item in self.timesheet_statuses
        )
        if (
            ("timesheet_locked" in self.denial_reasons)
            is not has_locked_timesheet
        ):
            raise ValueError("preflight timesheet lock evidence is inconsistent")
        if self.write_allowed is not (not self.denial_reasons):
            raise ValueError("preflight authority contradicts denial reasons")

        if self.action == "CREATE":
            if (
                self.event_id is not None
                or self.current is not None
                or self.etag is not None
                or self.desired is None
            ):
                raise ValueError("CREATE preflight response shape is invalid")
            return self

        if (
            self.event_id is None
            or self.current is None
            or self.etag is None
        ):
            raise ValueError("mutation preflight current evidence is incomplete")
        if (
            self.current.event_id != self.event_id
            or self.current.category != self.category
        ):
            raise ValueError("preflight current item does not match its target")
        if self.action == "UPDATE" and self.desired is None:
            raise ValueError("UPDATE preflight desired state is missing")
        if self.action == "DELETE" and self.desired is not None:
            raise ValueError("DELETE preflight desired state must be absent")
        return self


class ScheduleOperationResult(StrictModel):
    status: ScheduleOperationStatus | None = None
    event_id: EventId | None = None
    correlation_id: CorrelationId | None = None
    etag: ETag | None = None
    replayed: StrictBool | None = None
    write_applied: StrictBool | None = None
    reconciliation_required: StrictBool | None = None
    http_status: StrictInt | None = Field(default=None, ge=100, le=599)


class ScheduleOperationError(StrictModel):
    code: str | None = Field(default=None, pattern=r"^[a-z0-9_:-]{1,64}$")
    status: ScheduleOperationStatus | None = None
    correlation_id: CorrelationId | None = None
    retryable: StrictBool | None = None
    http_status: StrictInt | None = Field(default=None, ge=100, le=599)


class ScheduleOperationData(StrictModel):
    correlation_id: CorrelationId
    status: ScheduleOperationStatus
    event_id: EventId | None
    result: ScheduleOperationResult
    error: ScheduleOperationError

    @model_validator(mode="after")
    def validate_status_evidence(self) -> "ScheduleOperationData":
        result_present = bool(self.result.model_fields_set)
        error_present = bool(self.error.model_fields_set)

        if self.result.correlation_id is not None and (
            self.result.correlation_id != self.correlation_id
        ):
            raise ValueError("operation result correlation mismatch")
        if self.result.event_id is not None and (
            self.result.event_id != self.event_id
        ):
            raise ValueError("operation result event mismatch")
        if self.result.status is not None and self.result.status != self.status:
            raise ValueError("operation result status mismatch")
        if self.error.correlation_id is not None and (
            self.error.correlation_id != self.correlation_id
        ):
            raise ValueError("operation error correlation mismatch")
        if self.error.status is not None and self.error.status != self.status:
            raise ValueError("operation error status mismatch")

        if self.status == "IN_PROGRESS":
            if result_present or error_present:
                raise ValueError("IN_PROGRESS operation must have empty evidence")
            return self
        if self.status == "SUCCEEDED":
            if (
                error_present
                or not result_present
                or self.event_id is None
                or self.result.status != "SUCCEEDED"
                or self.result.event_id != self.event_id
                or self.result.correlation_id != self.correlation_id
                or self.result.write_applied is not True
                or self.result.reconciliation_required is True
            ):
                raise ValueError("SUCCEEDED operation evidence is invalid")
            return self
        if (
            result_present
            or not error_present
            or self.error.code is None
            or self.error.status != self.status
            or self.error.correlation_id != self.correlation_id
        ):
            raise ValueError("terminal operation failure evidence is invalid")
        return self


class ScheduleUpsertResult(StrictModel):
    status: Literal["success"]
    event_id: EventId = Field(alias="id")


class ScheduleDeleteResult(StrictModel):
    status: Literal["success"]


class ScheduleEnvelopeMeta(StrictModel):
    correlation_id: CorrelationId
    timestamp: DateTime

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: DateTime) -> DateTime:
        return _require_aware(value)


DataT = TypeVar("DataT")


class ScheduleEnvelope(StrictModel, Generic[DataT]):
    success: Literal[True]
    data: DataT
    error: None
    meta: ScheduleEnvelopeMeta

    @field_validator("success", mode="before")
    @classmethod
    def require_boolean_success(cls, value: object) -> object:
        return _require_exact_bool(value)
