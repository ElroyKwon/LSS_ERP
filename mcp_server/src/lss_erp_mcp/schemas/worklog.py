from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field

from .common import StrictModel
from .timesheet import ProjectSource

EntryKind = Literal["project", "common", "leave", "non_project"]


class WorklogFact(StrictModel):
    fact_id: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    work_date: date
    entry_kind: EntryKind
    description: str = Field(min_length=1, max_length=300)
    hours: Decimal | None = Field(
        default=None,
        gt=0,
        le=24,
        multiple_of=Decimal("0.25"),
    )
    project_id: int | None = Field(default=None, gt=0)
    project_query: str | None = Field(default=None, min_length=1, max_length=100)
    project_name: str | None = Field(default=None, min_length=1, max_length=200)
    project_source: ProjectSource | None = None
    work_type: str | None = Field(default=None, min_length=1, max_length=200)


class ClarificationOption(StrictModel):
    value: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=300)


class ClarificationQuestion(StrictModel):
    question_id: str = Field(min_length=1, max_length=200)
    fact_id: str | None = Field(default=None, min_length=1, max_length=80)
    code: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=500)
    options: list[ClarificationOption] = Field(default_factory=list, max_length=20)
