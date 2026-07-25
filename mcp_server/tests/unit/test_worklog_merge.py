from __future__ import annotations

from decimal import Decimal

from lss_erp_mcp.tools.worklog import (
    calculate_totals,
    merge_entries,
    semantic_entry_key,
)


def draft_entry(
    *,
    work_date: str = "2026-07-20",
    project_id: int | None = 123,
    project_name: str = "MCP 개발",
    project_source: str = "실행",
    hours: str = "4",
    description: str = "개발",
) -> dict[str, object]:
    return {
        "work_date": work_date,
        "project_id": project_id,
        "project_name": project_name,
        "project_source": project_source,
        "spg": "에너지" if project_source == "실행" else None,
        "hours": hours,
        "work_type": (
            "실행 > 업무지원"
            if project_source == "실행"
            else "공통 > 기타"
        ),
        "description": description,
    }


def test_merge_preserves_unrelated_existing_rows() -> None:
    current = [
        {
            "entry_id": 1,
            **draft_entry(
                work_date="2026-07-20",
                project_id=123,
                description="기존 업무",
            ),
        }
    ]
    incoming = [
        draft_entry(
            work_date="2026-07-21",
            project_id=456,
            project_name="신규 프로젝트",
            description="신규 업무",
        )
    ]

    merged, preserved = merge_entries(current, incoming)

    assert len(merged) == 2
    assert preserved == 1
    assert all("entry_id" not in entry for entry in merged)


def test_merge_replaces_only_same_semantic_row() -> None:
    current = [draft_entry(hours="4")]
    incoming = [draft_entry(hours="8")]

    merged, preserved = merge_entries(current, incoming)

    assert merged[0]["hours"] == "8"
    assert preserved == 0


def test_merge_never_collapses_duplicate_existing_rows() -> None:
    current = [
        {"entry_id": 1, **draft_entry(hours="4")},
        {"entry_id": 2, **draft_entry(hours="4")},
    ]
    incoming = [
        draft_entry(
            work_date="2026-07-21",
            project_id=456,
            project_name="신규 프로젝트",
            description="신규 업무",
        )
    ]

    merged, preserved = merge_entries(current, incoming)

    assert len(merged) == 3
    assert preserved == 2


def test_semantic_key_distinguishes_projectless_names() -> None:
    common = draft_entry(
        project_id=None,
        project_name="교육",
        project_source="공통",
    )
    leave = {
        **common,
        "project_name": "연차",
        "work_type": "공통 > 연차",
    }

    assert semantic_entry_key(common) != semantic_entry_key(leave)


def test_calculate_totals_returns_daily_and_weekly_decimal_totals() -> None:
    entries = [
        draft_entry(work_date="2026-07-20", hours="4"),
        draft_entry(
            work_date="2026-07-20",
            hours="3.5",
            description="검토",
        ),
        draft_entry(work_date="2026-07-21", hours="8"),
    ]

    daily, weekly = calculate_totals(entries)

    assert daily == {
        "2026-07-20": Decimal("7.5"),
        "2026-07-21": Decimal("8"),
    }
    assert weekly == Decimal("15.5")
