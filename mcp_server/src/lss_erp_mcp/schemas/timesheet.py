from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from .common import StrictModel


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
    project_id: int
    hours: Decimal = Field(gt=0, le=24, multiple_of=Decimal("0.25"))
    work_type: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=300)


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
    project_id: int
    project_code: str
    project_name: str
    active: bool


class ProjectSearch(StrictModel):
    items: list[ProjectItem]
    truncated: bool


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
