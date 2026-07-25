from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from lss_erp_mcp.schemas.timesheet import (
    DailyTarget,
    DraftEntry,
    ProjectItem,
    TimesheetEntryContext,
)
from lss_erp_mcp.schemas.worklog import WorklogFact


def daily_targets(week_start: date) -> list[DailyTarget]:
    return [
        DailyTarget(
            work_date=week_start + timedelta(days=offset),
            target_hours=Decimal("8") if offset < 5 else Decimal("0"),
            reason="normal" if offset < 5 else "weekend",
        )
        for offset in range(7)
    ]


def test_leave_fact_needs_no_project_query() -> None:
    fact = WorklogFact(
        fact_id="log-1",
        work_date=date(2026, 7, 20),
        entry_kind="leave",
        hours=Decimal("8"),
        description="연차",
    )

    assert fact.entry_kind == "leave"
    assert fact.project_id is None
    assert fact.project_query is None


def test_fact_rejects_path_like_fact_id() -> None:
    with pytest.raises(ValidationError, match="fact_id"):
        WorklogFact(
            fact_id=r"G:\vault\worklog.md",
            work_date=date(2026, 7, 20),
            entry_kind="project",
            description="개발",
        )


def test_fact_rejects_authority_or_raw_text_fields() -> None:
    with pytest.raises(ValidationError):
        WorklogFact.model_validate(
            {
                "fact_id": "log-1",
                "work_date": "2026-07-20",
                "entry_kind": "project",
                "description": "개발",
                "employee_id": 999,
                "raw_worklog": "원문",
            }
        )


def test_expanded_entry_rejects_projectless_execution_row() -> None:
    with pytest.raises(ValidationError, match="project_id"):
        DraftEntry(
            work_date=date(2026, 7, 20),
            project_source="실행",
            project_name="MCP 개발",
            hours=Decimal("8"),
            work_type="실행 > 업무지원",
            description="개발",
        )


def test_expanded_entry_rejects_nameless_common_row() -> None:
    with pytest.raises(ValidationError, match="project_name"):
        DraftEntry(
            work_date=date(2026, 7, 20),
            project_source="공통",
            hours=Decimal("8"),
            work_type="공통 > 기타",
            description="내부 업무",
        )


def test_entry_context_requires_exact_requested_week_shape() -> None:
    week_start = date(2026, 7, 20)
    context = TimesheetEntryContext(
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        labor_type="원가",
        project_sources=["실행", "영업", "공통"],
        work_types=["공통 > 연차", "공통 > 기타", "실행 > 업무지원"],
        daily_targets=daily_targets(week_start),
    )

    assert context.daily_targets[0].target_hours == Decimal("8")
    assert context.daily_targets[-1].target_hours == Decimal("0")


def test_entry_context_rejects_missing_day() -> None:
    week_start = date(2026, 7, 20)
    with pytest.raises(ValidationError, match="daily_targets"):
        TimesheetEntryContext(
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            labor_type="원가",
            project_sources=["실행", "영업", "공통"],
            work_types=["공통 > 연차"],
            daily_targets=daily_targets(week_start)[:-1],
        )


def test_project_candidate_requires_identity_matching_source() -> None:
    with pytest.raises(ValidationError, match="project_id"):
        ProjectItem(
            project_id=None,
            project_code="P-1",
            project_name="실행 프로젝트",
            project_source="실행",
            active=True,
        )


def test_entry_context_requires_all_three_project_sources() -> None:
    week_start = date(2026, 7, 20)
    with pytest.raises(ValidationError, match="project_sources"):
        TimesheetEntryContext(
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            labor_type="원가",
            project_sources=["실행", "공통"],
            work_types=["공통 > 연차"],
            daily_targets=daily_targets(week_start),
        )
