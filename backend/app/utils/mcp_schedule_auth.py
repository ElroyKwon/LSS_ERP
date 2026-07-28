"""Scoped API-token dependencies for the additive MCP schedule surface."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import FrozenSet

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..database import get_db
from .auth import api_token_scheme, hash_api_token


SCHEDULE_READ_SCOPE = "schedule:read"
SCHEDULE_WRITE_SCOPE = "schedule:write"


def _utc_now_naive() -> datetime:
    """Match the existing naive UTC database columns without utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class McpSchedulePrincipal:
    """Validated API-token identity and scopes for MCP schedule operations."""

    user: object
    api_token_id: int
    scopes: FrozenSet[str]
    audit_token_prefix: str
    is_mcp_schedule_request: bool


def normalize_api_token_scopes(raw_scopes: object) -> FrozenSet[str]:
    """Return a safe, exact-match scope set; malformed JSON fails closed."""
    if not isinstance(raw_scopes, (list, tuple)):
        return frozenset()

    return frozenset(
        scope.strip()
        for scope in raw_scopes
        if isinstance(scope, str) and scope.strip()
    )


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid_api_token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _is_mcp_schedule_request(request: Request) -> bool:
    return (
        request.url.path.startswith("/api/mcp/schedules")
        or request.headers.get("X-LSS-MCP-Schedule") == "1"
    )


def resolve_mcp_schedule_principal(request: Request, db: Session) -> McpSchedulePrincipal:
    """Validate an explicit legacy-create marker against an API token only."""
    if request.headers.get("X-LSS-MCP-Schedule") != "1":
        raise _credentials_exception()
    scheme, _, raw_token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not raw_token or raw_token.strip() != raw_token:
        raise _credentials_exception()

    from ..models.common import ApiToken, User

    token_row = db.query(ApiToken).filter(
        ApiToken.token_hash == hash_api_token(raw_token),
    ).first()
    if token_row is None or token_row.revoked_at is not None:
        raise _credentials_exception()
    if token_row.expires_at is not None and token_row.expires_at < _utc_now_naive():
        raise _credentials_exception()
    user = db.query(User).filter(User.id == token_row.user_id, User.is_active == True).first()
    if user is None:
        raise _credentials_exception()
    return McpSchedulePrincipal(
        user=user,
        api_token_id=token_row.id,
        scopes=normalize_api_token_scopes(token_row.scopes),
        audit_token_prefix=(token_row.token_prefix or "")[:20],
        is_mcp_schedule_request=True,
    )


def get_mcp_schedule_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(api_token_scheme),
    db: Session = Depends(get_db),
) -> McpSchedulePrincipal:
    """Resolve an active API token without trusting any request identity fields."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _credentials_exception()

    from ..models.common import ApiToken, User

    token_row = db.query(ApiToken).filter(
        ApiToken.token_hash == hash_api_token(credentials.credentials),
    ).first()
    if token_row is None or token_row.revoked_at is not None:
        raise _credentials_exception()
    if token_row.expires_at is not None and token_row.expires_at < _utc_now_naive():
        raise _credentials_exception()

    user = db.query(User).filter(
        User.id == token_row.user_id,
        User.is_active == True,
    ).first()
    if user is None:
        raise _credentials_exception()

    return McpSchedulePrincipal(
        user=user,
        api_token_id=token_row.id,
        scopes=normalize_api_token_scopes(token_row.scopes),
        audit_token_prefix=(token_row.token_prefix or "")[:20],
        is_mcp_schedule_request=_is_mcp_schedule_request(request),
    )


def _require_scope(principal: McpSchedulePrincipal, required_scope: str) -> McpSchedulePrincipal:
    if required_scope not in principal.scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="missing_scope")
    return principal


def require_schedule_read(
    principal: McpSchedulePrincipal = Depends(get_mcp_schedule_principal),
) -> McpSchedulePrincipal:
    return _require_scope(principal, SCHEDULE_READ_SCOPE)


def require_schedule_write(
    principal: McpSchedulePrincipal = Depends(get_mcp_schedule_principal),
) -> McpSchedulePrincipal:
    return _require_scope(principal, SCHEDULE_WRITE_SCOPE)
