from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
import base64
import hmac
import re

from ..config import settings
from ..database import SessionLocal
from ..models.common import User
from ..models.execution import Project
from ..models.master import Employee
from .permissions import can_access, is_public_api, resolve_api_permission


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


def _basic_auth_error() -> JSONResponse:
    response = JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "API 문서 접근 권한이 필요합니다."},
    )
    response.headers["WWW-Authenticate"] = 'Basic realm="LSS ERP API Docs"'
    return response


def _is_docs_path(path: str) -> bool:
    return path in {"/api/docs", "/api/redoc", "/api/openapi.json", "/api/docs/oauth2-redirect"}


def _has_valid_docs_basic_auth(request: Request) -> bool:
    if not settings.API_DOCS_USERNAME and not settings.API_DOCS_PASSWORD:
        return True

    auth_header = request.headers.get("Authorization", "")
    scheme, _, encoded = auth_header.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return False
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return False

    username, separator, password = decoded.partition(":")
    if not separator:
        return False
    return (
        hmac.compare_digest(username, settings.API_DOCS_USERNAME)
        and hmac.compare_digest(password, settings.API_DOCS_PASSWORD)
    )


def _current_user_from_request(request: Request) -> User | None:
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    finally:
        db.close()


def _is_project_pm_update_allowed(request: Request, user: User) -> bool:
    if request.method.upper() != "PUT":
        return False
    match = re.fullmatch(r"/api/projects/(\d+)", request.url.path)
    if not match:
        return False

    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == int(match.group(1))).first()
        employee_code = (user.employee_code or "").strip()
        if not project or not employee_code:
            return False
        if project.pm_employee_code:
            return project.pm_employee_code == employee_code

        if not project.pm_name:
            return False
        matches = db.query(Employee).filter(Employee.name == project.pm_name).all()
        return len(matches) == 1 and matches[0].emp_code == employee_code
    finally:
        db.close()


async def enforce_api_permissions(request: Request, call_next):
    path = request.url.path
    if _is_docs_path(path) and not _has_valid_docs_basic_auth(request):
        return _basic_auth_error()
    if request.method.upper() == "OPTIONS" or not path.startswith("/api/") or is_public_api(path):
        return await call_next(request)

    permission = resolve_api_permission(request.method, path)
    if permission is None:
        return await call_next(request)

    user = _current_user_from_request(request)
    if not user:
        return _error(status.HTTP_401_UNAUTHORIZED, "인증 정보가 유효하지 않습니다.")

    if not can_access(user.role, permission.menu_path, permission.action):
        if permission.menu_path == "/execution/projects" and _is_project_pm_update_allowed(request, user):
            return await call_next(request)
        return _error(status.HTTP_403_FORBIDDEN, "해당 기능을 사용할 권한이 없습니다.")

    return await call_next(request)
