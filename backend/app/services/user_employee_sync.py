from sqlalchemy.orm import Session

from ..models.common import Department, User
from ..models.master import Employee


def user_employee_code(user_id: int) -> str:
    return f"USER-{user_id}"


def effective_employee_code(user: User) -> str:
    return (user.employee_code or "").strip() or user_employee_code(user.id)


def sync_employee_for_user(db: Session, user: User) -> Employee:
    if not user.id:
        db.flush()

    department = None
    if user.department_id:
        department = db.query(Department).filter(Department.id == user.department_id).first()

    employee = (
        db.query(Employee)
        .filter(Employee.emp_code == effective_employee_code(user))
        .first()
    )
    if not employee:
        employee = (
            db.query(Employee)
            .filter(Employee.emp_code == user_employee_code(user.id))
            .first()
        )
    if not employee:
        employee = Employee(emp_code=effective_employee_code(user))
        db.add(employee)
    employee.emp_code = effective_employee_code(user)

    employee.name = user.name
    employee.email = user.email
    employee.phone = user.phone
    employee.position = user.position
    employee.department_id = user.department_id
    employee.department_name = department.name if department else None
    employee.is_active = bool(user.is_active)
    return employee


def deactivate_employee_for_user(db: Session, user: User) -> None:
    if not user.id:
        return
    employee = (
        db.query(Employee)
        .filter(Employee.emp_code.in_([effective_employee_code(user), user_employee_code(user.id)]))
        .first()
    )
    if employee:
        employee.is_active = False
