import hmac
import re
from collections.abc import Mapping

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, relationship
from sqlalchemy.sql import func

from ..database import Base


MCP_SCHEDULE_OPERATION_STATUSES = (
    "IN_PROGRESS",
    "SUCCEEDED",
    "FAILED",
    "RECONCILIATION_REQUIRED",
    "MANUAL_REVIEW",
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,255}$")
_ERROR_CODE_RE = re.compile(r"^[a-z0-9_:-]{1,64}$")
_ETAG_RE = re.compile(r'^"[A-Za-z0-9._:-]{1,253}"$')


class IdempotencyConflictError(ValueError):
    """Raised when an idempotency key is reused for a different request."""


class CorrelationConflictError(ValueError):
    """Raised when a globally unique correlation ID is already bound."""


def _safe_identifier(value, *, max_length=255):
    if isinstance(value, str) and len(value) <= max_length and _IDENTIFIER_RE.fullmatch(value):
        return value
    return None


def _safe_etag(value):
    if isinstance(value, str) and _ETAG_RE.fullmatch(value):
        return value
    return None


def _safe_status(value):
    return value if value in MCP_SCHEDULE_OPERATION_STATUSES else None


def redact_operation_result(value):
    """Keep only bounded, non-sensitive operation result fields."""
    if not isinstance(value, Mapping):
        return None

    redacted = {}
    status = _safe_status(value.get("status"))
    event_id = _safe_identifier(value.get("event_id"))
    correlation_id = _safe_identifier(value.get("correlation_id"), max_length=128)
    etag = _safe_etag(value.get("etag"))
    http_status = value.get("http_status")

    if status is not None:
        redacted["status"] = status
    if event_id is not None:
        redacted["event_id"] = event_id
    if correlation_id is not None:
        redacted["correlation_id"] = correlation_id
    if etag is not None:
        redacted["etag"] = etag
    for name in ("replayed", "write_applied", "reconciliation_required"):
        if isinstance(value.get(name), bool):
            redacted[name] = value[name]
    if isinstance(http_status, int) and not isinstance(http_status, bool) and 100 <= http_status <= 599:
        redacted["http_status"] = http_status
    return redacted


def redact_operation_error(value):
    """Keep stable machine-readable error facts, never free-text diagnostics."""
    if not isinstance(value, Mapping):
        return None

    redacted = {}
    code = value.get("code")
    status = _safe_status(value.get("status"))
    correlation_id = _safe_identifier(value.get("correlation_id"), max_length=128)
    http_status = value.get("http_status")

    if isinstance(code, str) and _ERROR_CODE_RE.fullmatch(code):
        redacted["code"] = code
    if status is not None:
        redacted["status"] = status
    if correlation_id is not None:
        redacted["correlation_id"] = correlation_id
    if isinstance(value.get("retryable"), bool):
        redacted["retryable"] = value["retryable"]
    if isinstance(http_status, int) and not isinstance(http_status, bool) and 100 <= http_status <= 599:
        redacted["http_status"] = http_status
    return redacted


class McpScheduleOperation(Base):
    __tablename__ = "mcp_schedule_operations"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_mcp_schedule_operations_user_idempotency_key",
        ),
        UniqueConstraint("correlation_id", name="uq_mcp_schedule_operations_correlation_id"),
        CheckConstraint(
            "status IN ('IN_PROGRESS', 'SUCCEEDED', 'FAILED', "
            "'RECONCILIATION_REQUIRED', 'MANUAL_REVIEW')",
            name="ck_mcp_schedule_operations_status",
        ),
        Index("idx_mcp_schedule_operations_user_id", "user_id"),
        Index("idx_mcp_schedule_operations_event_id", "event_id"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String(20), nullable=False)
    action = Column(String(20), nullable=False)
    event_id = Column(String(255))
    idempotency_key = Column(String(128), nullable=False)
    correlation_id = Column(String(128), nullable=False)
    request_hash = Column(String(64), nullable=False)
    expected_etag = Column(String(255))
    desired_state_hash = Column(String(64))
    status = Column(String(32), nullable=False)
    result_json = Column(JSON)
    error_json = Column(JSON)
    created_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    # ORM writes refresh this value; direct SQL updates must set updated_at explicitly.
    updated_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
    )

    user = relationship("User", foreign_keys=[user_id])


@event.listens_for(McpScheduleOperation.result_json, "set", retval=True)
def _redact_result_json(_target, value, _oldvalue, _initiator):
    return redact_operation_result(value)


@event.listens_for(McpScheduleOperation.error_json, "set", retval=True)
def _redact_error_json(_target, value, _oldvalue, _initiator):
    return redact_operation_error(value)


@event.listens_for(Session, "before_flush")
def _validate_operation_statuses(session, _flush_context, _instances):
    for operation in session.new.union(session.dirty):
        if isinstance(operation, McpScheduleOperation) and operation.status not in MCP_SCHEDULE_OPERATION_STATUSES:
            raise ValueError("invalid MCP schedule operation status")


def find_replay_operation(session, *, user_id, idempotency_key, request_hash):
    """Return a matching replay or reject a conflicting idempotency-key reuse."""
    operation = (
        session.query(McpScheduleOperation)
        .filter(
            McpScheduleOperation.user_id == user_id,
            McpScheduleOperation.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if operation is None:
        return None
    if not hmac.compare_digest(operation.request_hash, request_hash):
        raise IdempotencyConflictError("idempotency_key is already bound to a different request")
    return operation


def claim_or_replay_operation(session, *, operation):
    """Atomically claim an operation or recover the existing idempotent replay.

    The caller owns the outer transaction. A unique-key collision is contained
    by a savepoint so the session can re-read the winner without rolling back
    surrounding work.
    """
    try:
        with session.begin_nested():
            session.add(operation)
            session.flush()
    except IntegrityError:
        if operation in session:
            session.expunge(operation)
        existing = find_replay_operation(
            session,
            user_id=operation.user_id,
            idempotency_key=operation.idempotency_key,
            request_hash=operation.request_hash,
        )
        if existing is None:
            correlation_existing = (
                session.query(McpScheduleOperation)
                .filter(McpScheduleOperation.correlation_id == operation.correlation_id)
                .one_or_none()
            )
            if correlation_existing is not None:
                raise CorrelationConflictError("correlation_id is already bound") from None
            raise
        return existing, False
    return operation, True
