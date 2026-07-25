from __future__ import annotations

from lss_erp_mcp.tools.timesheets import build_diff, entry_key


def entry(
    *,
    work_date: str,
    project_id: int,
    hours: str,
    description: str = "개발",
) -> dict[str, object]:
    return {
        "work_date": work_date,
        "project_id": project_id,
        "hours": hours,
        "work_type": "개발",
        "description": description,
    }


def test_build_diff_is_deterministic_and_separates_changes() -> None:
    current = [
        entry(work_date="2026-07-21", project_id=2, hours="4.00"),
        entry(work_date="2026-07-20", project_id=1, hours="7.00"),
    ]
    proposed = [
        entry(work_date="2026-07-22", project_id=3, hours="2.00"),
        entry(work_date="2026-07-20", project_id=1, hours="7.50"),
    ]

    result = build_diff(current, proposed)

    assert [entry_key(item) for item in result["added"]] == [
        entry_key(proposed[0])
    ]
    assert result["changed"] == [{"before": current[1], "after": proposed[1]}]
    assert [entry_key(item) for item in result["removed"]] == [
        entry_key(current[0])
    ]
