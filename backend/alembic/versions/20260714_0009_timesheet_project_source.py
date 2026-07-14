"""add timesheet project source

Revision ID: 20260714_0009
Revises: 20260714_0008
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714_0009"
down_revision = "20260714_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("timesheet_entries")}

    if "project_source" not in columns:
        op.add_column(
            "timesheet_entries",
            sa.Column("project_source", sa.String(length=20), nullable=True, server_default="공통"),
        )

    op.execute(
        """
        UPDATE timesheet_entries
        SET project_source = CASE
            WHEN project_id IS NOT NULL THEN '실행'
            WHEN project_source IS NULL OR project_source = '' THEN '공통'
            ELSE project_source
        END
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("timesheet_entries")}
    if "project_source" in columns:
        op.drop_column("timesheet_entries", "project_source")
