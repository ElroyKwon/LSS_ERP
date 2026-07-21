"""expand timesheet work type length

Revision ID: 20260714_0011
Revises: 20260714_0010
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714_0011"
down_revision = "20260714_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.alter_column(
        "timesheet_entries",
        "work_type",
        existing_type=sa.String(length=50),
        type_=sa.String(length=200),
        existing_nullable=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.alter_column(
        "timesheet_entries",
        "work_type",
        existing_type=sa.String(length=200),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
