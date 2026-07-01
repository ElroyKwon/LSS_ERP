from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt

from ..config import settings
from ..database import SessionLocal
from ..models.common import User
from .permissions import can_access, is_public_api, resolve_api_permission


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


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


async def enforce_api_permissions(request: Request, call_next):
    path = request.url.path
    if request.method.upper() == "OPTIONS" or not path.startswith("/api/") or is_public_api(path):
        return await call_next(request)

    permission = resolve_api_permission(request.method, path)
    if permission is None:
        return await call_next(request)

    user = _current_user_from_request(request)
    if not user:
        return _error(status.HTTP_401_UNAUTHORIZED, "인증 정보가 유효하지 않습니다.")

    if not can_access(user.role, permission.menu_path, permission.action):
        return _error(status.HTTP_403_FORBIDDEN, "해당 기능을 사용할 권한이 없습니다.")

    return await call_next(request)
