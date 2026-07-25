from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import StrictModel

ProjectSource = Literal["실행", "영업", "공통"]


class CurrentUser(StrictModel):
    user_id: int
    employee_id: int
    employee_code: str
    display_name: str
    client_id: str
    resource: str
    scopes: list[str]


class DraftEntry(StrictModel):
    work_date: date
    project_id: int | None = Field(default=None, gt=0)
    project_name: str | None = Field(default=None, min_length=1, max_length=200)
    project_source: ProjectSource = "실행"
    spg: str | None = Field(default=None, min_length=1, max_length=100)
    hours: Decimal = Field(gt=0, le=24, multiple_of=Decimal("0.25"))
    work_type: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def require_project_identity(self) -> "DraftEntry":
        if self.project_source == "실행" and self.project_id is None:
            raise ValueError("execution entry project_id is required")
        if self.project_source != "실행" and self.project_id is not None:
            raise ValueError("non-execution entry project_id must be omitted")
        if self.project_source in {"영업", "공통"} and not self.project_name:
            raise ValueError("non-execution entry project_name is required")
        return self


class PersistedEntry(DraftEntry):
    entry_id: int


class TimesheetWeek(StrictModel):
    timesheet_id: int | None
    week_start: date
    week_end: date
    status: str
    version: int
    entries: list[PersistedEntry]


class ProjectItem(StrictModel):
    project_id: int | None = Field(default=None, gt=0)
    project_code: str
    project_name: str
    project_source: ProjectSource = "실행"
    spg: str | None = None
    active: bool

    @model_validator(mode="after")
    def require_source_identity(self) -> "ProjectItem":
        if self.project_source == "실행" and self.project_id is None:
            raise ValueError("execution project candidate project_id is required")
        if self.project_source != "실행" and self.project_id is not None:
            raise ValueError(
                "non-execution project candidate project_id must be omitted"
            )
        return self


class ProjectSearch(StrictModel):
    items: list[ProjectItem]
    truncated: bool


class DailyTarget(StrictModel):
    work_date: date
    target_hours: Decimal = Field(ge=0, le=24)
    reason: str = Field(min_length=1, max_length=100)


class TimesheetEntryContext(StrictModel):
    week_start: date
    week_end: date
    labor_type: Literal["원가", "판관"]
    project_sources: list[ProjectSource] = Field(min_length=1, max_length=3)
    work_types: list[str] = Field(min_length=1, max_length=100)
    daily_targets: list[DailyTarget] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def require_exact_week_shape(self) -> "TimesheetEntryContext":
        expected_end = self.week_start + timedelta(days=6)
        if self.week_start.weekday() != 0 or self.week_end != expected_end:
            raise ValueError("entry context must describe one Monday-to-Sunday week")
        expected_dates = [
            self.week_start + timedelta(days=offset) for offset in range(7)
        ]
        if [target.work_date for target in self.daily_targets] != expected_dates:
            raise ValueError("daily_targets must contain the seven ordered week dates")
        if set(self.project_sources) != {"실행", "영업", "공통"}:
            raise ValueError(
                "project_sources must contain 실행, 영업, and 공통 exactly once"
            )
        if len(set(self.work_types)) != len(self.work_types):
            raise ValueError("work_types must not contain duplicates")
        return self


class DraftWriteRequest(StrictModel):
    week_start: date
    expected_version: int
    entries: list[DraftEntry] = Field(min_length=1, max_length=50)

    @field_validator("week_start")
    @classmethod
    def require_monday(cls, value: date) -> date:
        if value.weekday() != 0:
            raise ValueError("week_start must be Monday")
        return value

    @model_validator(mode="after")
    def require_entries_in_week(self) -> "DraftWriteRequest":
        week_end = self.week_start + timedelta(days=6)
        if any(
            entry.work_date < self.week_start or entry.work_date > week_end
            for entry in self.entries
        ):
            raise ValueError("entry work_date must be within the requested week")
        return self


class DraftWriteResult(StrictModel):
    timesheet_id: int
    week_start: date
    status: str
    version: int
    correlation_id: str
    idempotency_replayed: bool
