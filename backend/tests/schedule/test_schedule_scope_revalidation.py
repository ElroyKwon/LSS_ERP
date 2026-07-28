from datetime import date

import pytest

from app.services import timesheet_locking


class _FakeSession:
    def __init__(self):
        self.rollback_calls = 0

    def rollback(self):
        self.rollback_calls += 1


def _scope(employee_id, week):
    return {employee_id: {week}}


@pytest.mark.parametrize("action", ["UPDATE", "DELETE"])
def test_scope_requery_after_parent_lock_uses_current_linked_week_not_stale_seed(
    monkeypatch,
    action,
):
    stale_week = date(2026, 8, 3)
    current_week = date(2026, 8, 10)
    desired_week = date(2026, 8, 17)
    discoveries = iter([
        _scope(1, stale_week),
        _scope(1, current_week),
    ])
    parent_locks = []
    child_locks = []
    db = _FakeSession()

    monkeypatch.setattr(
        timesheet_locking,
        "_discover_schedule_timesheet_scope",
        lambda *_args, **_kwargs: next(discoveries),
        raising=False,
    )
    monkeypatch.setattr(
        timesheet_locking,
        "lock_employee_namespaces",
        lambda _db, *, employee_ids: parent_locks.append(sorted(employee_ids)) or [],
    )
    monkeypatch.setattr(
        timesheet_locking,
        "lock_timesheet_scopes",
        lambda _db, *, weeks_by_employee: child_locks.append({
            employee_id: set(weeks)
            for employee_id, weeks in weeks_by_employee.items()
        }) or [],
    )

    timesheet_locking.lock_revalidated_schedule_timesheet_scope(
        db,
        event_id="event-scope-drift",
        category="company",
        employee_id=1,
        desired_weeks=[desired_week] if action == "UPDATE" else [],
    )

    assert parent_locks == [[1]]
    assert child_locks == [{
        1: (
            {current_week, desired_week}
            if action == "UPDATE"
            else {current_week}
        ),
    }]
    assert stale_week not in child_locks[0][1]
    assert db.rollback_calls == 0


def test_new_employee_after_parent_lock_rolls_back_and_restarts_before_child_lock(
    monkeypatch,
):
    stale_week = date(2026, 8, 3)
    current_week = date(2026, 8, 10)
    discoveries = iter([
        _scope(1, stale_week),
        _scope(2, current_week),
        _scope(2, current_week),
    ])
    parent_locks = []
    child_locks = []
    restart_calls = []
    db = _FakeSession()

    monkeypatch.setattr(
        timesheet_locking,
        "_discover_schedule_timesheet_scope",
        lambda *_args, **_kwargs: next(discoveries),
        raising=False,
    )
    monkeypatch.setattr(
        timesheet_locking,
        "lock_employee_namespaces",
        lambda _db, *, employee_ids: parent_locks.append(sorted(employee_ids)) or [
            object() for _ in employee_ids
        ],
    )
    monkeypatch.setattr(
        timesheet_locking,
        "lock_timesheet_scopes",
        lambda _db, *, weeks_by_employee: child_locks.append({
            employee_id: set(weeks)
            for employee_id, weeks in weeks_by_employee.items()
        }) or [],
    )

    timesheet_locking.lock_revalidated_schedule_timesheet_scope(
        db,
        event_id="event-new-parent",
        category="company",
        employee_id=1,
        desired_weeks=[],
        on_restart=lambda: restart_calls.append("rebound"),
    )

    assert parent_locks == [[1], [1, 2]]
    assert db.rollback_calls == 1
    assert restart_calls == ["rebound"]
    assert child_locks == [{2: {current_week}}]


def test_persistent_new_employee_churn_is_bounded_and_never_locks_children(
    monkeypatch,
):
    discoveries = iter([
        _scope(1, date(2026, 8, 3)),
        _scope(2, date(2026, 8, 10)),
        _scope(3, date(2026, 8, 17)),
        _scope(4, date(2026, 8, 24)),
    ])
    parent_locks = []
    child_locks = []
    restart_calls = []
    db = _FakeSession()

    monkeypatch.setattr(
        timesheet_locking,
        "_discover_schedule_timesheet_scope",
        lambda *_args, **_kwargs: next(discoveries),
        raising=False,
    )
    monkeypatch.setattr(
        timesheet_locking,
        "lock_employee_namespaces",
        lambda _db, *, employee_ids: parent_locks.append(sorted(employee_ids)) or [
            object() for _ in employee_ids
        ],
    )
    monkeypatch.setattr(
        timesheet_locking,
        "lock_timesheet_scopes",
        lambda _db, *, weeks_by_employee: child_locks.append(weeks_by_employee) or [],
    )

    with pytest.raises(timesheet_locking.ScheduleTimesheetScopeUnstable):
        timesheet_locking.lock_revalidated_schedule_timesheet_scope(
            db,
            event_id="event-persistent-churn",
            category="company",
            employee_id=1,
            desired_weeks=[],
            on_restart=lambda: restart_calls.append("rebound"),
            max_attempts=3,
        )

    assert parent_locks == [[1], [1, 2], [1, 2, 3]]
    assert db.rollback_calls == 3
    assert restart_calls == ["rebound", "rebound", "rebound"]
    assert child_locks == []
