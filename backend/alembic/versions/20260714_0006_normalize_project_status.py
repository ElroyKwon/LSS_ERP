"""normalize legacy project statuses

Revision ID: 20260714_0006
Revises: 20260703_0005
Create Date: 2026-07-14
"""

from alembic import op


revision = "20260714_0006"
down_revision = "20260703_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE projects SET status = '진행중' WHERE status IN ('진행', '진행 중')")
    op.execute("UPDATE projects SET status = '완료' WHERE status IN ('종료', '종료됨', '완료됨')")


def downgrade():
    # Do not reintroduce legacy status labels on downgrade.
    pass
