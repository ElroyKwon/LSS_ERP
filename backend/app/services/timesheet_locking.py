"""Shared PostgreSQL lock order for every timesheet-mutating transaction."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Iterable, Mapping

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models.common import CalendarSchedule
from ..models.master import Employee
from ..models.timesheet import Timesheet, TimesheetEntry


class ScheduleTimesheetScopeUnstable(RuntimeError):
    """The affected Employee namespace changed across bounded lock attempts."""


def _week_starts(range_start: date, range_end: date) -> set[date]:
    cursor = range_start - timedelta(days=range_start.weekday())
    last = range_end - timedelta(days=range_end.weekday())
    values: set[date] = set()
    while cursor <= last:
        values.add(cursor)
        cursor += timedelta(days=7)
    return values


def _calendar_schedule_weeks(row: CalendarSchedule | None) -> set[date]:
    if row is None:
        return set()
    if not row.is_all_day and row.start_time:
        range_start = row.start_time.date()
        range_end = (row.end_time or row.start_time).date()
    elif row.date:
        range_start = row.date
        range_end = row.end_date or row.date
    else:
        return set()
    return _week_starts(range_start, range_end)


def _discover_schedule_timesheet_scope(
    db: Session,
    *,
    event_id: str | None,
    category: str,
    employee_id: int | None,
) -> dict[int, set[date]]:
    """Re-read current local and linked scope; callers decide lock stability."""
    weeks_by_employee: dict[int, set[date]] = {}
    if not event_id:
        return weeks_by_employee

    row = (
        db.query(CalendarSchedule)
        .filter(
            CalendarSchedule.google_event_id == event_id,
            CalendarSchedule.category == category,
        )
        .populate_existing()
        .one_or_none()
    )
    current_weeks = _calendar_schedule_weeks(row)
    if current_weeks and employee_id is not None:
        weeks_by_employee.setdefault(employee_id, set()).update(current_weeks)

    linked_rows = (
        db.query(Timesheet.employee_id, Timesheet.week_start)
        .join(TimesheetEntry, TimesheetEntry.timesheet_id == Timesheet.id)
        .filter(
            TimesheetEntry.schedule_event_id == event_id,
            TimesheetEntry.schedule_category == category,
        )
        .all()
    )
    for linked_employee_id, week_start in linked_rows:
        weeks_by_employee.setdefault(linked_employee_id, set()).add(week_start)
    return weeks_by_employee


def _with_desired_weeks(
    scope: Mapping[int, Iterable[date]],
    *,
    employee_id: int | None,
    desired_weeks: Iterable[date],
) -> dict[int, set[date]]:
    merged = {
        scope_employee_id: set(weeks)
        for scope_employee_id, weeks in scope.items()
    }
    desired = set(desired_weeks)
    if desired and employee_id is not None:
        merged.setdefault(employee_id, set()).update(desired)
    return merged


def lock_revalidated_schedule_timesheet_scope(
    db: Session,
    *,
    event_id: str | None,
    category: str,
    employee_id: int | None,
    desired_weeks: Iterable[date],
    on_restart: Callable[[], None] | None = None,
    max_attempts: int = 3,
) -> list[Timesheet]:
    """Lock parents, re-read actual scope, then lock children without TOCTOU."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    seed_scope = _discover_schedule_timesheet_scope(
        db,
        event_id=event_id,
        category=category,
        employee_id=employee_id,
    )
    parent_ids = set(seed_scope)
    if employee_id is not None:
        parent_ids.add(employee_id)

    for _attempt in range(max_attempts):
        lock_employee_namespaces(db, employee_ids=parent_ids)
        current_scope = _discover_schedule_timesheet_scope(
            db,
            event_id=event_id,
            category=category,
            employee_id=employee_id,
        )
        stable_scope = _with_desired_weeks(
            current_scope,
            employee_id=employee_id,
            desired_weeks=desired_weeks,
        )
        discovered_ids = set(stable_scope)
        if discovered_ids.issubset(parent_ids):
            return lock_timesheet_scopes(
                db,
                weeks_by_employee=stable_scope,
            )

        parent_ids.update(discovered_ids)
        db.rollback()
        if on_restart is not None:
            on_restart()

    raise ScheduleTimesheetScopeUnstable(
        "schedule timesheet scope changed across all lock attempts"
    )


def build_employee_lock_query(db: Session, *, employee_id: int):
    """Build the always-existing namespace lock acquired before child rows."""
    return (
        db.query(Employee)
        .filter(Employee.id == employee_id)
        .with_for_update()
    )


def build_timesheet_lock_query(
    db: Session,
    *,
    employee_id: int,
    weeks: Iterable[date],
):
    """Build the deterministic child-row lock query for affected weeks."""
    week_values = sorted(set(weeks))
    return (
        db.query(Timesheet)
        .filter(
            Timesheet.employee_id == employee_id,
            Timesheet.week_start.in_(week_values),
        )
        .order_by(Timesheet.week_start.asc(), Timesheet.id.asc())
        .with_for_update()
        .populate_existing()
    )


def lock_employee_namespace(db: Session, *, employee_id: int) -> Employee | None:
    """Acquire the parent namespace row before any Timesheet row lock."""
    return build_employee_lock_query(
        db,
        employee_id=employee_id,
    ).one_or_none()


def lock_employee_namespaces(
    db: Session,
    *,
    employee_ids: Iterable[int],
) -> list[Employee]:
    """Lock every parent in global Employee.id order before any child row."""
    id_values = sorted(set(employee_ids))
    if not id_values:
        return []
    return (
        db.query(Employee)
        .filter(Employee.id.in_(id_values))
        .order_by(Employee.id.asc())
        .with_for_update()
        .populate_existing()
        .all()
    )


def lock_timesheet_rows(
    db: Session,
    *,
    employee_id: int,
    weeks: Iterable[date],
) -> list[Timesheet]:
    """Acquire existing affected child rows after the Employee parent lock."""
    return build_timesheet_lock_query(
        db,
        employee_id=employee_id,
        weeks=weeks,
    ).all()


def lock_timesheet_scopes(
    db: Session,
    *,
    weeks_by_employee: Mapping[int, Iterable[date]],
) -> list[Timesheet]:
    """Lock all affected children globally by week_start then Timesheet.id."""
    conditions = [
        and_(
            Timesheet.employee_id == employee_id,
            Timesheet.week_start.in_(sorted(set(weeks))),
        )
        for employee_id, weeks in sorted(weeks_by_employee.items())
        if weeks
    ]
    if not conditions:
        return []
    return (
        db.query(Timesheet)
        .filter(or_(*conditions))
        .order_by(Timesheet.week_start.asc(), Timesheet.id.asc())
        .with_for_update()
        .populate_existing()
        .all()
    )


def lock_employee_then_timesheets(
    db: Session,
    *,
    employee_id: int,
    weeks: Iterable[date],
) -> tuple[Employee | None, list[Timesheet]]:
    """Apply the global Employee -> Timesheet lock order, including empty weeks."""
    employee = lock_employee_namespace(db, employee_id=employee_id)
    if employee is None:
        return None, []
    rows = lock_timesheet_rows(
        db,
        employee_id=employee_id,
        weeks=weeks,
    )
    return employee, rows


def lock_timesheet_by_id(db: Session, *, timesheet_id: int) -> Timesheet | None:
    """Resolve the namespace, lock Employee, then re-read and lock the row."""
    employee_id = (
        db.query(Timesheet.employee_id)
        .filter(Timesheet.id == timesheet_id)
        .scalar()
    )
    if employee_id is None:
        return None
    if lock_employee_namespace(db, employee_id=employee_id) is None:
        return None
    return (
        db.query(Timesheet)
        .filter(
            Timesheet.id == timesheet_id,
            Timesheet.employee_id == employee_id,
        )
        .order_by(Timesheet.week_start.asc(), Timesheet.id.asc())
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
