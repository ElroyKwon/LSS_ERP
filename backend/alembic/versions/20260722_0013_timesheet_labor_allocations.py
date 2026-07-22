"""add timesheet labor allocation table

Revision ID: 20260722_0013
Revises: 20260722_0012
Create Date: 2026-07-22
"""

from alembic import op


revision = "20260722_0013"
down_revision = "20260722_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS timesheet_labor_allocations (
            id SERIAL PRIMARY KEY,
            allocation_year INTEGER NOT NULL,
            allocation_month INTEGER NOT NULL,
            category VARCHAR(20) NOT NULL,
            total_amount NUMERIC(18, 2) DEFAULT 0,
            contract_amount NUMERIC(18, 2) DEFAULT 0,
            other_amount NUMERIC(18, 2) DEFAULT 0,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_timesheet_labor_allocations_month_category
                UNIQUE (allocation_year, allocation_month, category)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_timesheet_labor_allocations_id
            ON timesheet_labor_allocations (id)
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_timesheet_labor_allocations_id")
    op.execute("DROP TABLE IF EXISTS timesheet_labor_allocations")
