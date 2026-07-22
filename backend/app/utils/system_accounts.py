import os

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.common import User
from ..models.master import Employee


def system_account_usernames() -> set[str]:
    configured_admin = os.getenv("LSS_ERP_ADMIN_USERNAME", "admin").strip().lower()
    names = {"admin"}
    if configured_admin:
        names.add(configured_admin)
    return names


def is_system_account_username(username: str | None) -> bool:
    return (username or "").strip().lower() in system_account_usernames()


def system_account_employee_codes(db: Session) -> set[str]:
    usernames = system_account_usernames()
    users = db.query(User).filter(func.lower(User.username).in_(usernames)).all()
    codes = set()
    for user in users:
        employee_code = (user.employee_code or "").strip() or f"USER-{user.id}"
        if employee_code:
            codes.add(employee_code)
    return codes


def exclude_system_account_employees(query, db: Session):
    codes = system_account_employee_codes(db)
    if not codes:
        return query
    return query.filter(~Employee.emp_code.in_(codes))


def is_system_account_employee(db: Session, employee_id: int | None) -> bool:
    if not employee_id:
        return False
    codes = system_account_employee_codes(db)
    if not codes:
        return False
    return db.query(Employee.id).filter(
        Employee.id == employee_id,
        Employee.emp_code.in_(codes),
    ).first() is not None
