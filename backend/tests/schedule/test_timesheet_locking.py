import importlib.util
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import UniqueConstraint, event, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.models.master import Employee
from app.models.timesheet import Timesheet
from app.routers import timesheet as timesheet_router


def _employee(db_session, ordinary_user):
    return db_session.query(Employee).filter(
        Employee.emp_code == ordinary_user.employee_code,
    ).one()


def _timesheet(db_session, ordinary_user, *, status="작성중"):
    employee = _employee(db_session, ordinary_user)
    row = Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 8, 3),
        week_end=date(2026, 8, 9),
        status=status,
        created_by=ordinary_user.id,
    )
    db_session.add(row)
    db_session.commit()
    return row


def _track_for_update_order(db_session):
    ordering = []

    def track(orm_execute_state):
        statement = orm_execute_state.statement
        if getattr(statement, "_for_update_arg", None) is None:
            return
        sql = " ".join(
            str(statement.compile(dialect=postgresql.dialect())).lower().split()
        )
        if " from employees " in f" {sql} ":
            ordering.append("employee")
        elif " from timesheets " in f" {sql} ":
            ordering.append("timesheet")

    event.listen(db_session, "do_orm_execute", track)
    return ordering, track


def test_timesheet_model_enforces_unique_employee_week_start(
    db_session, ordinary_user,
):
    constraint = next(
        item
        for item in Timesheet.__table__.constraints
        if isinstance(item, UniqueConstraint)
        and item.name == "uq_timesheets_employee_week_start"
    )
    assert [column.name for column in constraint.columns] == [
        "employee_id",
        "week_start",
    ]

    employee = _employee(db_session, ordinary_user)
    db_session.add(Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 8, 3),
        week_end=date(2026, 8, 9),
        status="작성중",
    ))
    db_session.commit()
    db_session.add(Timesheet(
        employee_id=employee.id,
        week_start=date(2026, 8, 3),
        week_end=date(2026, 8, 9),
        status="작성중",
    ))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_0016_migration_fails_closed_on_duplicates_and_adds_named_unique_constraint(
    monkeypatch,
):
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260727_0016_unique_timesheet_employee_week.py"
    )
    spec = importlib.util.spec_from_file_location("timesheet_unique_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "20260727_0016"
    assert migration.down_revision == "20260727_0015"

    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    created = []
    dropped = []
    executed_sql = []
    duplicate_rows = [(7, date(2026, 8, 3), 2)]

    def get_bind():
        return SimpleNamespace(
            execute=lambda statement: (
                executed_sql.append(str(statement)),
                _Result(duplicate_rows),
            )[1],
        )

    monkeypatch.setattr(
        migration,
        "op",
        SimpleNamespace(
            get_bind=get_bind,
            create_unique_constraint=lambda *args, **kwargs: created.append((args, kwargs)),
            drop_constraint=lambda *args, **kwargs: dropped.append((args, kwargs)),
        ),
    )

    with pytest.raises(RuntimeError, match="employee_id=7.*2026-08-03.*resolve duplicates"):
        migration.upgrade()
    assert created == []
    assert "GROUP BY employee_id, week_start" in executed_sql[0]
    assert "HAVING COUNT(*) > 1" in executed_sql[0]

    duplicate_rows.clear()
    migration.upgrade()
    assert created == [
        (
            ("uq_timesheets_employee_week_start", "timesheets", ["employee_id", "week_start"]),
            {},
        )
    ]

    migration.downgrade()
    assert dropped == [
        (
            ("uq_timesheets_employee_week_start", "timesheets"),
            {"type_": "unique"},
        )
    ]


def test_shared_lock_queries_use_employee_then_deterministic_timesheet_for_update(
    db_session, ordinary_user,
):
    from app.services import timesheet_locking

    employee = _employee(db_session, ordinary_user)
    employee_sql = str(
        timesheet_locking.build_employee_lock_query(
            db_session,
            employee_id=employee.id,
        ).statement.compile(dialect=postgresql.dialect())
    )
    timesheet_sql = str(
        timesheet_locking.build_timesheet_lock_query(
            db_session,
            employee_id=employee.id,
            weeks=[date(2026, 8, 10), date(2026, 8, 3)],
        ).statement.compile(dialect=postgresql.dialect())
    )

    assert "employees.id" in employee_sql
    assert employee_sql.rstrip().endswith("FOR UPDATE")
    assert "timesheets.employee_id" in timesheet_sql
    assert "timesheets.week_start IN" in timesheet_sql
    assert "ORDER BY timesheets.week_start ASC, timesheets.id ASC" in timesheet_sql
    assert timesheet_sql.rstrip().endswith("FOR UPDATE")


def test_save_timesheet_locks_employee_before_missing_week_query_and_preserves_response(
    db_session, ordinary_user,
):
    employee = _employee(db_session, ordinary_user)
    ordering, listener = _track_for_update_order(db_session)
    try:
        result = timesheet_router.save_timesheet(
            timesheet_router.TimesheetCreate(
                employee_id=employee.id,
                week_start=date(2026, 8, 3),
                entries=[],
                notes="locked save",
            ),
            db=db_session,
            current=ordinary_user,
        )
    finally:
        event.remove(db_session, "do_orm_execute", listener)

    assert ordering[:2] == ["employee", "timesheet"]
    assert result["employee_id"] == employee.id
    assert result["week_start"] == "2026-08-03"
    assert result["status"] == "작성중"


@pytest.mark.parametrize(
    ("action", "starting_status", "expected_status", "expected_message"),
    [
        ("submit", "작성중", "제출", "제출되었습니다."),
        ("approve", "제출", "승인", "승인되었습니다."),
        ("reject", "제출", "반려", "반려되었습니다."),
    ],
)
def test_timesheet_state_writers_lock_employee_then_reread_timesheet_and_preserve_response(
    db_session,
    ordinary_user,
    action,
    starting_status,
    expected_status,
    expected_message,
):
    row = _timesheet(db_session, ordinary_user, status=starting_status)
    ordering, listener = _track_for_update_order(db_session)
    try:
        if action == "submit":
            result = timesheet_router.submit_timesheet(
                row.id,
                db=db_session,
                current=ordinary_user,
            )
        elif action == "approve":
            result = timesheet_router.approve_timesheet(
                row.id,
                db=db_session,
                current=ordinary_user,
            )
        else:
            result = timesheet_router.reject_timesheet(
                row.id,
                timesheet_router.RejectIn(reason="needs correction"),
                db=db_session,
                current=ordinary_user,
            )
    finally:
        event.remove(db_session, "do_orm_execute", listener)

    assert ordering[:2] == ["employee", "timesheet"]
    assert result == {"message": expected_message}
    db_session.refresh(row)
    assert row.status == expected_status


def test_submit_timesheet_rechecks_state_after_employee_lock(
    db_session, ordinary_user,
):
    row = _timesheet(db_session, ordinary_user, status="작성중")
    injected = False

    def change_state_when_employee_locks(orm_execute_state):
        nonlocal injected
        statement = orm_execute_state.statement
        if injected or getattr(statement, "_for_update_arg", None) is None:
            return
        sql = " ".join(
            str(statement.compile(dialect=postgresql.dialect())).lower().split()
        )
        if " from employees " not in f" {sql} ":
            return
        injected = True
        orm_execute_state.session.connection().execute(
            update(Timesheet)
            .where(Timesheet.id == row.id)
            .values(status="제출")
        )

    event.listen(db_session, "do_orm_execute", change_state_when_employee_locks)
    try:
        with pytest.raises(HTTPException) as exc_info:
            timesheet_router.submit_timesheet(
                row.id,
                db=db_session,
                current=ordinary_user,
            )
    finally:
        event.remove(db_session, "do_orm_execute", change_state_when_employee_locks)
        db_session.rollback()

    assert injected is True
    assert exc_info.value.status_code == 400
