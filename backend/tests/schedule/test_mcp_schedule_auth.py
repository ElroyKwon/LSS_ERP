from datetime import datetime, timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.common import ApiToken, User
from app.utils.auth import create_access_token, get_current_user, hash_api_token

try:
    from app.utils import mcp_schedule_auth
except ImportError:
    mcp_schedule_auth = None


def _scope_auth():
    assert mcp_schedule_auth is not None, "scoped schedule principal does not exist"
    return mcp_schedule_auth


def _make_api_token(db_session, user, scopes, *, expired=False, revoked=False):
    raw_token = f"schedule-scope-token-{user.id}-{db_session.query(ApiToken).count()}"
    row = ApiToken(
        name="MCP schedule test client",
        token_hash=hash_api_token(raw_token),
        token_prefix="lss_erp_test_prefix",
        user_id=user.id,
        scopes=scopes,
        expires_at=(datetime.utcnow() - timedelta(minutes=1)) if expired else None,
        revoked_at=datetime.utcnow() if revoked else None,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return raw_token, row


def _schedule_scope_client(db_session):
    auth = _scope_auth()
    app = FastAPI()

    @app.get("/api/mcp/schedules")
    def list_schedules(principal=Depends(auth.require_schedule_read)):
        return {
            "user_id": principal.user.id,
            "api_token_id": principal.api_token_id,
            "scopes": sorted(principal.scopes),
            "audit_token_prefix": principal.audit_token_prefix,
            "is_mcp_schedule_request": principal.is_mcp_schedule_request,
        }

    @app.get("/api/mcp/schedules/{event_id}")
    def detail_schedule(event_id: str, principal=Depends(auth.require_schedule_read)):
        return {"event_id": event_id, "user_id": principal.user.id}

    @app.post("/api/mcp/schedules/preflight")
    def preflight_schedule(principal=Depends(auth.require_schedule_write)):
        return {"user_id": principal.user.id, "is_mcp_schedule_request": principal.is_mcp_schedule_request}

    @app.post("/api/mcp/schedules/write-context")
    def write_context(principal=Depends(auth.require_schedule_write)):
        return {"api_token_id": principal.api_token_id}

    @app.get("/ui/current-user")
    def ui_current_user(current_user=Depends(get_current_user)):
        return {"user_id": current_user.id}

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_schedule_read_scope_allows_mcp_list_and_detail_only(db_session, ordinary_user):
    token, _ = _make_api_token(db_session, ordinary_user, ["schedule:read"])
    with _schedule_scope_client(db_session) as client:
        assert client.get("/api/mcp/schedules", headers=_bearer(token)).status_code == 200
        assert client.get("/api/mcp/schedules/event-1", headers=_bearer(token)).status_code == 200
        denied = client.post("/api/mcp/schedules/preflight", headers=_bearer(token))

    assert denied.status_code == 403
    assert denied.json()["detail"] == "missing_scope"


def test_schedule_write_scope_allows_preflight_and_write_context_only(db_session, ordinary_user):
    token, _ = _make_api_token(db_session, ordinary_user, ["schedule:write"])
    with _schedule_scope_client(db_session) as client:
        assert client.post("/api/mcp/schedules/preflight", headers=_bearer(token)).status_code == 200
        assert client.post("/api/mcp/schedules/write-context", headers=_bearer(token)).status_code == 200
        denied = client.get("/api/mcp/schedules", headers=_bearer(token))

    assert denied.status_code == 403
    assert denied.json()["detail"] == "missing_scope"


@pytest.mark.parametrize("state", ["expired", "revoked"])
def test_expired_or_revoked_schedule_token_returns_401(db_session, ordinary_user, state):
    token, _ = _make_api_token(
        db_session,
        ordinary_user,
        ["schedule:read"],
        expired=state == "expired",
        revoked=state == "revoked",
    )
    with _schedule_scope_client(db_session) as client:
        response = client.get("/api/mcp/schedules", headers=_bearer(token))

    assert response.status_code == 401


def test_existing_jwt_ui_current_user_behavior_remains_accepted(db_session, ordinary_user):
    jwt_token = create_access_token({"sub": str(ordinary_user.id)})
    with _schedule_scope_client(db_session) as client:
        response = client.get("/ui/current-user", headers=_bearer(jwt_token))

    assert response.status_code == 200
    assert response.json() == {"user_id": ordinary_user.id}


def test_api_token_identity_is_derived_from_token_row_not_request_input(db_session, ordinary_user):
    other_user = User(
        username="mallory",
        employee_code="E002",
        password_hash="not-used-by-scope-tests",
        name="Mallory",
        labor_type="직영",
    )
    db_session.add(other_user)
    db_session.commit()
    token, token_row = _make_api_token(db_session, ordinary_user, ["schedule:read"])

    with _schedule_scope_client(db_session) as client:
        response = client.get(
            f"/api/mcp/schedules?user_id={other_user.id}",
            headers=_bearer(token),
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == ordinary_user.id
    assert response.json()["api_token_id"] == token_row.id
    assert response.json()["audit_token_prefix"] == "lss_erp_test_prefix"
    assert response.json()["is_mcp_schedule_request"] is True


def test_scope_list_is_normalized_and_malformed_values_default_deny(db_session, ordinary_user):
    token, _ = _make_api_token(
        db_session,
        ordinary_user,
        [" schedule:read ", "schedule:read", "schedule:read-extra", 42, ""],
    )
    malformed_token, _ = _make_api_token(db_session, ordinary_user, {"scope": "schedule:read"})

    with _schedule_scope_client(db_session) as client:
        allowed = client.get("/api/mcp/schedules", headers=_bearer(token))
        malformed = client.get("/api/mcp/schedules", headers=_bearer(malformed_token))

    assert allowed.status_code == 200
    assert allowed.json()["scopes"] == ["schedule:read", "schedule:read-extra"]
    assert malformed.status_code == 403
    assert malformed.json()["detail"] == "missing_scope"
