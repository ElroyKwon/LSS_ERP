"""opinion listening tables

Revision ID: 20260701_0003
Revises: 20260609_0002
Create Date: 2026-07-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20260701_0003"
down_revision = "20260609_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "opinion_posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answered_by", sa.Integer(), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["answered_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opinion_posts_id"), "opinion_posts", ["id"], unique=False)

    op.create_table(
        "opinion_notification_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("notify_on_new_post", sa.Boolean(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_opinion_notification_settings_id"),
        "opinion_notification_settings",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_opinion_notification_settings_user_id"),
        "opinion_notification_settings",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "opinion_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("opinion_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["opinion_id"], ["opinion_posts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opinion_attachments_id"), "opinion_attachments", ["id"], unique=False)
    op.create_index(
        op.f("ix_opinion_attachments_opinion_id"),
        "opinion_attachments",
        ["opinion_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_opinion_attachments_opinion_id"), table_name="opinion_attachments")
    op.drop_index(op.f("ix_opinion_attachments_id"), table_name="opinion_attachments")
    op.drop_table("opinion_attachments")

    op.drop_index(op.f("ix_opinion_notification_settings_user_id"), table_name="opinion_notification_settings")
    op.drop_index(op.f("ix_opinion_notification_settings_id"), table_name="opinion_notification_settings")
    op.drop_table("opinion_notification_settings")

    op.drop_index(op.f("ix_opinion_posts_id"), table_name="opinion_posts")
    op.drop_table("opinion_posts")
