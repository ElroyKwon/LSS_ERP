from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class DocumentSource(Base):
    __tablename__ = "document_sources"
    __table_args__ = (
        UniqueConstraint("provider", "external_item_id", name="uq_document_sources_provider_item"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(30), nullable=False, default="onedrive")
    external_drive_id = Column(String(200))
    external_item_id = Column(String(200), nullable=False)
    parent_external_id = Column(String(200))
    file_name = Column(String(255), nullable=False)
    file_extension = Column(String(20))
    mime_type = Column(String(150))
    file_path = Column(Text, nullable=False)
    web_url = Column(Text)
    size_bytes = Column(Integer)
    content_hash = Column(String(128))
    e_tag = Column(String(200))
    c_tag = Column(String(200))
    last_modified_at = Column(DateTime)
    first_seen_at = Column(DateTime, default=func.now())
    last_seen_at = Column(DateTime, default=func.now())
    sync_status = Column(String(30), default="discovered")
    processed_version = Column(String(200))
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    jobs = relationship("DocumentIngestionJob", back_populates="source")
    extracted_records = relationship("DocumentExtractedRecord", back_populates="source")
    import_errors = relationship("DocumentImportError", back_populates="source")


class DocumentIngestionJob(Base):
    __tablename__ = "document_ingestion_jobs"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("document_sources.id", ondelete="CASCADE"), nullable=False)
    job_type = Column(String(30), nullable=False, default="sync")
    status = Column(String(30), nullable=False, default="pending")
    trigger_type = Column(String(30), default="scheduled")
    parser_type = Column(String(30))
    ai_model = Column(String(100))
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    error_message = Column(Text)
    metrics = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    source = relationship("DocumentSource", back_populates="jobs")
    extracted_records = relationship("DocumentExtractedRecord", back_populates="job")
    import_errors = relationship("DocumentImportError", back_populates="job")


class DocumentExtractedRecord(Base):
    __tablename__ = "document_extracted_records"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("document_sources.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Integer, ForeignKey("document_ingestion_jobs.id", ondelete="SET NULL"))
    document_type = Column(String(50), nullable=False)
    target_entity = Column(String(50))
    target_table = Column(String(100))
    extracted_key = Column(String(200))
    extracted_data = Column(JSON, nullable=False)
    normalized_data = Column(JSON)
    source_refs = Column(JSON)
    confidence = Column(Numeric(5, 4))
    status = Column(String(30), nullable=False, default="staged")
    review_comment = Column(Text)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    imported_table = Column(String(100))
    imported_record_id = Column(String(100))
    imported_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    source = relationship("DocumentSource", back_populates="extracted_records")
    job = relationship("DocumentIngestionJob", back_populates="extracted_records")
    import_errors = relationship("DocumentImportError", back_populates="extracted_record")


class DocumentImportError(Base):
    __tablename__ = "document_import_errors"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("document_sources.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Integer, ForeignKey("document_ingestion_jobs.id", ondelete="SET NULL"))
    extracted_record_id = Column(Integer, ForeignKey("document_extracted_records.id", ondelete="SET NULL"))
    stage = Column(String(50), nullable=False)
    error_code = Column(String(80))
    error_message = Column(Text, nullable=False)
    error_detail = Column(JSON)
    is_resolved = Column(Boolean, default=False)
    resolved_by = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

    source = relationship("DocumentSource", back_populates="import_errors")
    job = relationship("DocumentIngestionJob", back_populates="import_errors")
    extracted_record = relationship("DocumentExtractedRecord", back_populates="import_errors")
