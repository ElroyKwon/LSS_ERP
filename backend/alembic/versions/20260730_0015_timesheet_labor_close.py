"""add timesheet labor calculated columns and monthly close

Revision ID: 20260730_0015
Revises: 20260724_0014
Create Date: 2026-07-30
"""

from alembic import op


revision = "20260730_0015"
down_revision = "20260724_0014"
branch_labels = None
depends_on = None


def upgrade():
    for column_name in (
        "contract_ratio_amount",
        "contract_actual_amount",
        "contract_diff_amount",
        "other_ratio_amount",
        "other_actual_amount",
        "other_diff_amount",
    ):
        op.execute(f"""
            ALTER TABLE timesheet_labor_allocations
            ADD COLUMN IF NOT EXISTS {column_name} NUMERIC(18, 2) DEFAULT 0
        """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS timesheet_monthly_closes (
            id SERIAL PRIMARY KEY,
            close_year INTEGER NOT NULL,
            close_month INTEGER NOT NULL,
            is_closed BOOLEAN NOT NULL DEFAULT TRUE,
            closed_by INTEGER REFERENCES users(id),
            closed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_timesheet_monthly_closes_month
                UNIQUE (close_year, close_month)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_timesheet_monthly_closes_id
            ON timesheet_monthly_closes (id)
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_timesheet_monthly_closes_id")
    op.execute("DROP TABLE IF EXISTS timesheet_monthly_closes")
    for column_name in (
        "other_diff_amount",
        "other_actual_amount",
        "other_ratio_amount",
        "contract_diff_amount",
        "contract_actual_amount",
        "contract_ratio_amount",
    ):
        op.execute(f"ALTER TABLE timesheet_labor_allocations DROP COLUMN IF EXISTS {column_name}")
