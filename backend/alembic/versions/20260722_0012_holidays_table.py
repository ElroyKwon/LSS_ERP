"""Add holidays table

Revision ID: 20260722_0012
Revises: 20260714_0011
Create Date: 2026-07-22 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260722_0012"
down_revision: Union[str, None] = "20260714_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "holidays",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.String(length=4), nullable=False),
        sa.Column("month", sa.String(length=2), nullable=False),
        sa.Column("day", sa.String(length=2), nullable=False),
        sa.Column("content", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "month", "day", name="uq_holidays_ymd"),
    )
    op.create_index(op.f("ix_holidays_id"), "holidays", ["id"], unique=False)
    op.create_index(op.f("ix_holidays_year"), "holidays", ["year"], unique=False)
    op.create_index(op.f("ix_holidays_month"), "holidays", ["month"], unique=False)
    op.create_index(op.f("ix_holidays_day"), "holidays", ["day"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_holidays_day"), table_name="holidays")
    op.drop_index(op.f("ix_holidays_month"), table_name="holidays")
    op.drop_index(op.f("ix_holidays_year"), table_name="holidays")
    op.drop_index(op.f("ix_holidays_id"), table_name="holidays")
    op.drop_table("holidays")