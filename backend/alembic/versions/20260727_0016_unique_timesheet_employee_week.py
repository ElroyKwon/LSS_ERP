"""enforce one Timesheet header per employee and week

Revision ID: 20260727_0016
Revises: 20260727_0015
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260727_0016"
down_revision = "20260727_0015"
branch_labels = None
depends_on = None


_DUPLICATE_PREFLIGHT = sa.text(
    """
    SELECT employee_id, week_start, COUNT(*) AS duplicate_count
    FROM timesheets
    GROUP BY employee_id, week_start
    HAVING COUNT(*) > 1
    ORDER BY employee_id, week_start
    LIMIT 20
    """
)


def upgrade():
    duplicates = op.get_bind().execute(_DUPLICATE_PREFLIGHT).fetchall()
    if duplicates:
        details = ", ".join(
            f"employee_id={row[0]} week_start={row[1]} count={row[2]}"
            for row in duplicates
        )
        raise RuntimeError(
            "20260727_0016 blocked: duplicate timesheets exist; "
            f"{details}; resolve duplicates explicitly before retrying; "
            "no rows were changed"
        )
    op.create_unique_constraint(
        "uq_timesheets_employee_week_start",
        "timesheets",
        ["employee_id", "week_start"],
    )


def downgrade():
    op.drop_constraint(
        "uq_timesheets_employee_week_start",
        "timesheets",
        type_="unique",
    )
