from datetime import date

from sqlalchemy.dialects import postgresql

from app.models.common import CalendarSchedule
from app.models.master import Employee
from app.models.mcp_schedule import McpScheduleOperation
from app.routers import schedule
from app.services import mcp_schedule_control


def test_mcp_timesheet_lock_query_uses_postgresql_for_update_and_deterministic_order(
    db_session, ordinary_user,
):
    employee = db_session.query(Employee).filter(
        Employee.emp_code == ordinary_user.employee_code,
    ).one()

    query = mcp_schedule_control.build_mcp_timesheet_lock_query(
        db_session,
        employee_id=employee.id,
        weeks=[date(2026, 8, 10), date(2026, 8, 3)],
    )
    sql = str(query.statement.compile(dialect=postgresql.dialect()))

    assert "timesheets.employee_id" in sql
    assert "timesheets.week_start IN" in sql
    assert "ORDER BY timesheets.week_start ASC, timesheets.id ASC" in sql
    assert sql.rstrip().endswith("FOR UPDATE")


def test_mcp_delete_readback_404_needs_matching_local_and_journal_evidence(
    db_session, ordinary_user,
):
    row = CalendarSchedule(
        google_event_id="a23456789bcdefg", category="company", content="x",
        type="#722ed1", user_name="Alice", created_by=ordinary_user.id,
    )
    operation = McpScheduleOperation(
        user_id=ordinary_user.id, category="company", action="DELETE", event_id=row.google_event_id,
        idempotency_key="delete-evidence-001", correlation_id="corr-delete-evidence-001", request_hash="a" * 64,
        status="IN_PROGRESS",
    )
    db_session.add_all([row, operation])
    db_session.commit()

    result = schedule._mcp_delete_readback_state(db_session, operation, row.google_event_id, "company", google_missing=True)

    assert result == "RECONCILIATION_REQUIRED"


def test_mcp_delete_readback_404_with_absent_local_row_and_in_progress_journal_is_success(
    db_session, ordinary_user,
):
    operation = McpScheduleOperation(
        user_id=ordinary_user.id, category="company", action="DELETE",
        event_id="a23456789bcdefg", idempotency_key="delete-evidence-002",
        correlation_id="corr-delete-evidence-002", request_hash="c" * 64,
        status="IN_PROGRESS",
    )
    db_session.add(operation)
    db_session.commit()

    result = schedule._mcp_delete_readback_state(
        db_session, operation, operation.event_id, "company", google_missing=True,
    )

    assert result == "SUCCEEDED"


def test_mcp_delete_readback_404_rejects_mismatched_journal_evidence(
    db_session, ordinary_user,
):
    operation = McpScheduleOperation(
        user_id=ordinary_user.id, category="refresh", action="DELETE",
        event_id="different-event", idempotency_key="delete-evidence-003",
        correlation_id="corr-delete-evidence-003", request_hash="d" * 64,
        status="IN_PROGRESS",
    )
    db_session.add(operation)
    db_session.commit()

    result = schedule._mcp_delete_readback_state(
        db_session, operation, "a23456789bcdefg", "company", google_missing=True,
    )

    assert result == "RECONCILIATION_REQUIRED"


def test_mcp_delete_conflicting_readback_evidence_requires_manual_review(db_session, ordinary_user):
    operation = McpScheduleOperation(
        user_id=ordinary_user.id, category="company", action="DELETE", event_id="a23456789bcdefg",
        idempotency_key="delete-conflict-001", correlation_id="corr-delete-conflict-001", request_hash="b" * 64,
        status="IN_PROGRESS",
    )
    db_session.add(operation)
    db_session.commit()

    result = schedule._mcp_delete_readback_state(db_session, operation, "a23456789bcdefg", "company", google_missing=False)

    assert result == "MANUAL_REVIEW"
