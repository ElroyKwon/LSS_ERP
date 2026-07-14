"""add project cost detail columns

Revision ID: 20260714_0007
Revises: 20260714_0006
Create Date: 2026-07-14
"""

from alembic import op
from sqlalchemy import text
import json


revision = "20260714_0007"
down_revision = "20260714_0006"
branch_labels = None
depends_on = None


PROJECT_COST_COLUMNS = (
    "contract_material_cost",
    "contract_labor_cost",
    "sales_domestic_material_cost",
    "sales_overseas_material_cost",
    "sales_outsourcing_cost",
    "sales_labor_cost",
    "sales_expense_cost",
    "sales_indirect_cost",
)
PROJECT_REQ_MARKER = "\n---프로젝트리스트요구사항---\n"


def upgrade():
    for column in PROJECT_COST_COLUMNS:
        op.execute(f"ALTER TABLE projects ADD COLUMN IF NOT EXISTS {column} NUMERIC(18, 2) DEFAULT 0")

    bind = op.get_bind()
    rows = bind.execute(text("SELECT id, notes FROM projects WHERE notes LIKE :marker"), {"marker": f"%{PROJECT_REQ_MARKER}%"}).fetchall()
    for project_id, notes in rows:
        try:
            raw_json = (notes or "").split(PROJECT_REQ_MARKER, 1)[1]
            meta = json.loads(raw_json)
        except Exception:
            continue

        values = {column: meta.get(column) for column in PROJECT_COST_COLUMNS if meta.get(column) is not None}
        if not values:
            continue

        assignments = ", ".join(f"{column} = :{column}" for column in values)
        bind.execute(
            text(f"UPDATE projects SET {assignments} WHERE id = :project_id"),
            {**values, "project_id": project_id},
        )


def downgrade():
    for column in reversed(PROJECT_COST_COLUMNS):
        op.execute(f"ALTER TABLE projects DROP COLUMN IF EXISTS {column}")
