"""add project pm employee code

Revision ID: 20260714_0008
Revises: 20260714_0007
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714_0008"
down_revision = "20260714_0007"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("projects")}
    if "pm_employee_code" not in columns:
        op.add_column("projects", sa.Column("pm_employee_code", sa.String(length=20), nullable=True))

    employees = bind.execute(sa.text("SELECT emp_code, name FROM employees WHERE name IS NOT NULL")).mappings().all()
    codes_by_name = {}
    duplicate_names = set()
    for employee in employees:
        name = (employee["name"] or "").strip()
        code = (employee["emp_code"] or "").strip()
        if not name or not code:
            continue
        if name in codes_by_name:
            duplicate_names.add(name)
        else:
            codes_by_name[name] = code

    for name in duplicate_names:
        codes_by_name.pop(name, None)

    projects = bind.execute(
        sa.text("SELECT id, pm_name FROM projects WHERE pm_employee_code IS NULL AND pm_name IS NOT NULL")
    ).mappings().all()
    for project in projects:
        code = codes_by_name.get((project["pm_name"] or "").strip())
        if code:
            bind.execute(
                sa.text("UPDATE projects SET pm_employee_code = :code WHERE id = :id"),
                {"code": code, "id": project["id"]},
            )


def downgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("projects")}
    if "pm_employee_code" in columns:
        op.drop_column("projects", "pm_employee_code")
