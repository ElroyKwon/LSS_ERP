import os
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.common import User
from app.utils.auth import hash_password
from app.utils.permissions import validate_role


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def main() -> int:
    username = _env("LSS_ERP_ADMIN_USERNAME", "admin")
    password = _env("LSS_ERP_ADMIN_PASSWORD")
    name = _env("LSS_ERP_ADMIN_NAME", "시스템관리자")
    email = _env("LSS_ERP_ADMIN_EMAIL")
    employee_code = _env("LSS_ERP_ADMIN_EMPLOYEE_CODE")
    role = validate_role(_env("LSS_ERP_ADMIN_ROLE", "system_admin"))

    if not username:
        print("LSS_ERP_ADMIN_USERNAME is required.", file=sys.stderr)
        return 2
    if not password:
        print("LSS_ERP_ADMIN_PASSWORD is required.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.name = name or user.name
            user.email = email or user.email
            user.role = role
            user.is_active = True
            if employee_code:
                user.employee_code = employee_code
            user.password_hash = hash_password(password)
            action = "updated"
        else:
            user = User(
                username=username,
                employee_code=employee_code or None,
                password_hash=hash_password(password),
                name=name,
                email=email or None,
                role=role,
                is_active=True,
            )
            db.add(user)
            action = "created"
        db.commit()
        print(f"Admin user {action}: {username}")
        return 0
    except SQLAlchemyError as exc:
        db.rollback()
        print(f"Failed to create admin user: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
