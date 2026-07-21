import bcrypt
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from .permissions import is_system_admin, normalize_role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
api_token_scheme = HTTPBearer(
    scheme_name="ApiTokenBearer",
    description="관리자가 발급한 장기 API 토큰을 입력합니다.",
    auto_error=False,
)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_api_token_value() -> str:
    return f"lss_erp_{secrets.token_urlsafe(32)}"


def hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 유효하지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _get_user_from_api_token(token: str, db: Session):
    from ..models.common import ApiToken, User

    row = db.query(ApiToken).filter(ApiToken.token_hash == hash_api_token(token)).first()
    if not row or row.revoked_at is not None:
        return None
    if row.expires_at is not None and row.expires_at < datetime.utcnow():
        return None

    user = db.query(User).filter(User.id == row.user_id, User.is_active == True).first()
    if user is None:
        return None

    row.last_used_at = datetime.utcnow()
    db.commit()
    return user


def get_current_user(
    oauth_token: Optional[str] = Depends(oauth2_scheme),
    api_credentials: Optional[HTTPAuthorizationCredentials] = Depends(api_token_scheme),
    db: Session = Depends(get_db),
):
    from ..models.common import User

    token = oauth_token or (api_credentials.credentials if api_credentials else None)
    if not token:
        raise _credentials_exception()

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise _credentials_exception()
    except JWTError:
        user = _get_user_from_api_token(token, db)
        if user is None:
            raise _credentials_exception()
        return user

    user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    if user is None:
        raise _credentials_exception()
    return user


def require_admin(current_user=Depends(get_current_user)):
    if not is_system_admin(current_user.role):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return current_user


def require_manager(current_user=Depends(get_current_user)):
    if normalize_role(current_user.role) not in ("system_admin", "sales_manager"):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return current_user
