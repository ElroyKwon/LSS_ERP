"""add registration notification settings

Revision ID: 20260703_0005
Revises: 20260701_0004
Create Date: 2026-07-03
"""

from alembic import op


revision = "20260703_0005"
down_revision = "20260701_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE opinion_notification_settings "
        "ADD COLUMN IF NOT EXISTS notify_on_registration BOOLEAN DEFAULT TRUE"
    )
    op.execute(
        "UPDATE opinion_notification_settings "
        "SET notify_on_registration = TRUE "
        "WHERE notify_on_registration IS NULL"
    )


def downgrade():
    op.execute("ALTER TABLE opinion_notification_settings DROP COLUMN IF EXISTS notify_on_registration")
