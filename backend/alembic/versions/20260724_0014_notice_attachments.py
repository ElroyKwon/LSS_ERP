"""add notice attachments

Revision ID: 20260724_0014
Revises: 20260722_0013
Create Date: 2026-07-24
"""

from alembic import op


revision = "20260724_0014"
down_revision = "20260722_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS notice_attachments (
            id SERIAL PRIMARY KEY,
            notice_id INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
            original_name VARCHAR(255) NOT NULL,
            stored_name VARCHAR(255) NOT NULL,
            content_type VARCHAR(100),
            file_size INTEGER DEFAULT 0,
            file_path VARCHAR(500) NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_notice_attachments_id
            ON notice_attachments (id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_notice_attachments_notice_id
            ON notice_attachments (notice_id)
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_notice_attachments_notice_id")
    op.execute("DROP INDEX IF EXISTS ix_notice_attachments_id")
    op.execute("DROP TABLE IF EXISTS notice_attachments")
