"""add user labor type

Revision ID: 20260714_0010
Revises: 20260714_0009
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714_0010"
down_revision = "20260714_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}

    if "labor_type" not in columns:
        op.add_column(
            "users",
            sa.Column("labor_type", sa.String(length=20), nullable=True, server_default="원가"),
        )

    op.execute(
        """
        UPDATE users
        SET labor_type = '원가'
        WHERE labor_type IS NULL OR labor_type NOT IN ('판관', '원가')
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "labor_type" in columns:
        op.drop_column("users", "labor_type")
