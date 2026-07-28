"""add MCP schedule operation journal

Revision ID: 20260727_0015
Revises: 20260724_0014
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260727_0015"
down_revision = "20260724_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mcp_schedule_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("event_id", sa.String(length=255)),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("expected_etag", sa.String(length=255)),
        sa.Column("desired_state_hash", sa.String(length=64)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_json", sa.JSON()),
        sa.Column("error_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_mcp_schedule_operations_user_idempotency_key",
        ),
        sa.UniqueConstraint("correlation_id", name="uq_mcp_schedule_operations_correlation_id"),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS', 'SUCCEEDED', 'FAILED', "
            "'RECONCILIATION_REQUIRED', 'MANUAL_REVIEW')",
            name="ck_mcp_schedule_operations_status",
        ),
    )
    op.create_index(
        "idx_mcp_schedule_operations_user_id",
        "mcp_schedule_operations",
        ["user_id"],
    )
    op.create_index(
        "idx_mcp_schedule_operations_event_id",
        "mcp_schedule_operations",
        ["event_id"],
    )


def downgrade():
    op.drop_index("idx_mcp_schedule_operations_event_id", table_name="mcp_schedule_operations")
    op.drop_index("idx_mcp_schedule_operations_user_id", table_name="mcp_schedule_operations")
    op.drop_table("mcp_schedule_operations")
