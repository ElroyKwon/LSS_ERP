"""Add document ingestion staging tables

Revision ID: 20260609_0002
Revises: 20260608_0001
Create Date: 2026-06-09 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260609_0002"
down_revision: Union[str, None] = "20260608_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("external_drive_id", sa.String(length=200), nullable=True),
        sa.Column("external_item_id", sa.String(length=200), nullable=False),
        sa.Column("parent_external_id", sa.String(length=200), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_extension", sa.String(length=20), nullable=True),
        sa.Column("mime_type", sa.String(length=150), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("web_url", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("e_tag", sa.String(length=200), nullable=True),
        sa.Column("c_tag", sa.String(length=200), nullable=True),
        sa.Column("last_modified_at", sa.DateTime(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("sync_status", sa.String(length=30), nullable=True),
        sa.Column("processed_version", sa.String(length=200), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_item_id", name="uq_document_sources_provider_item"),
    )
    op.create_index(op.f("ix_document_sources_id"), "document_sources", ["id"], unique=False)
    op.create_index("ix_document_sources_content_hash", "document_sources", ["content_hash"], unique=False)
    op.create_index("ix_document_sources_file_path", "document_sources", ["file_path"], unique=False)
    op.create_index("ix_document_sources_sync_status", "document_sources", ["sync_status"], unique=False)

    op.create_table(
        "document_ingestion_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("trigger_type", sa.String(length=30), nullable=True),
        sa.Column("parser_type", sa.String(length=30), nullable=True),
        sa.Column("ai_model", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["document_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_ingestion_jobs_id"), "document_ingestion_jobs", ["id"], unique=False)
    op.create_index("ix_document_ingestion_jobs_source_status", "document_ingestion_jobs", ["source_id", "status"], unique=False)
    op.create_index("ix_document_ingestion_jobs_status", "document_ingestion_jobs", ["status"], unique=False)

    op.create_table(
        "document_extracted_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("target_entity", sa.String(length=50), nullable=True),
        sa.Column("target_table", sa.String(length=100), nullable=True),
        sa.Column("extracted_key", sa.String(length=200), nullable=True),
        sa.Column("extracted_data", sa.JSON(), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=True),
        sa.Column("source_refs", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("imported_table", sa.String(length=100), nullable=True),
        sa.Column("imported_record_id", sa.String(length=100), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["document_ingestion_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["document_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_extracted_records_id"), "document_extracted_records", ["id"], unique=False)
    op.create_index("ix_document_extracted_records_source_status", "document_extracted_records", ["source_id", "status"], unique=False)
    op.create_index("ix_document_extracted_records_target", "document_extracted_records", ["target_table", "status"], unique=False)
    op.create_index("ix_document_extracted_records_type", "document_extracted_records", ["document_type"], unique=False)

    op.create_table(
        "document_import_errors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("extracted_record_id", sa.Integer(), nullable=True),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("error_detail", sa.JSON(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["extracted_record_id"], ["document_extracted_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["document_ingestion_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["document_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_import_errors_id"), "document_import_errors", ["id"], unique=False)
    op.create_index("ix_document_import_errors_resolved", "document_import_errors", ["is_resolved"], unique=False)
    op.create_index("ix_document_import_errors_source_stage", "document_import_errors", ["source_id", "stage"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_import_errors_source_stage", table_name="document_import_errors")
    op.drop_index("ix_document_import_errors_resolved", table_name="document_import_errors")
    op.drop_index(op.f("ix_document_import_errors_id"), table_name="document_import_errors")
    op.drop_table("document_import_errors")

    op.drop_index("ix_document_extracted_records_type", table_name="document_extracted_records")
    op.drop_index("ix_document_extracted_records_target", table_name="document_extracted_records")
    op.drop_index("ix_document_extracted_records_source_status", table_name="document_extracted_records")
    op.drop_index(op.f("ix_document_extracted_records_id"), table_name="document_extracted_records")
    op.drop_table("document_extracted_records")

    op.drop_index("ix_document_ingestion_jobs_status", table_name="document_ingestion_jobs")
    op.drop_index("ix_document_ingestion_jobs_source_status", table_name="document_ingestion_jobs")
    op.drop_index(op.f("ix_document_ingestion_jobs_id"), table_name="document_ingestion_jobs")
    op.drop_table("document_ingestion_jobs")

    op.drop_index("ix_document_sources_sync_status", table_name="document_sources")
    op.drop_index("ix_document_sources_file_path", table_name="document_sources")
    op.drop_index("ix_document_sources_content_hash", table_name="document_sources")
    op.drop_index(op.f("ix_document_sources_id"), table_name="document_sources")
    op.drop_table("document_sources")
