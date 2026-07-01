"""production schema cleanup and current feature tables

Revision ID: 20260701_0004
Revises: 20260701_0003
Create Date: 2026-07-01
"""

from alembic import op


revision = "20260701_0004"
down_revision = "20260701_0003"
branch_labels = None
depends_on = None


def upgrade():
    # Tables from abandoned document-ingestion and legacy contract-budget experiments.
    # They are not referenced by routers or registered ORM models.
    for table_name in (
        "document_import_errors",
        "document_extracted_records",
        "document_ingestion_jobs",
        "document_sources",
        "collections",
        "budget_items",
        "progress_billings",
        "contract_changes",
        "budgets",
        "contracts",
        "sales_pipelines",
        "revenue_forecasts",
        "fund_plans",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")

    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_code VARCHAR(20)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_employee_code ON users (employee_code)")
    op.execute("ALTER TABLE user_registrations ADD COLUMN IF NOT EXISTS employee_code VARCHAR(20)")

    op.execute("ALTER TABLE departments ADD COLUMN IF NOT EXISTS parent_id INTEGER")
    op.execute("ALTER TABLE departments ADD COLUMN IF NOT EXISTS org_year INTEGER")
    op.execute("ALTER TABLE departments ADD COLUMN IF NOT EXISTS dept_type VARCHAR(20)")
    op.execute("ALTER TABLE departments ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0")
    op.execute("ALTER TABLE departments ADD COLUMN IF NOT EXISTS notes TEXT")
    op.execute("ALTER TABLE departments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP")

    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS company_group_code VARCHAR(20)")
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS bank_name VARCHAR(50)")
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS bank_account VARCHAR(50)")
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS bank_holder VARCHAR(50)")
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS receivables_note TEXT")
    op.execute("CREATE INDEX IF NOT EXISTS idx_companies_active_name ON companies (is_active, company_name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_companies_active_code ON companies (is_active, company_code)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_companies_business_no ON companies (business_no)")

    op.execute("ALTER TABLE materials ADD COLUMN IF NOT EXISTS material_company_group_code VARCHAR(20)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_materials_active_code ON materials (is_active, material_code)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_materials_active_name ON materials (is_active, material_name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_materials_active_type_code ON materials (is_active, material_type, material_code)")

    op.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS department_name VARCHAR(100)")
    op.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS job_title VARCHAR(50)")
    op.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS task VARCHAR(100)")
    op.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS wedding_anniversary DATE")
    op.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS home_address VARCHAR(200)")
    op.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS corporate_card_no VARCHAR(50)")

    op.execute("ALTER TABLE timesheet_entries ADD COLUMN IF NOT EXISTS spg VARCHAR(20)")
    op.execute("ALTER TABLE timesheet_entries ADD COLUMN IF NOT EXISTS labor_type VARCHAR(20)")

    op.execute("ALTER TABLE project_plans ADD COLUMN IF NOT EXISTS invoice_plan NUMERIC(18, 2) DEFAULT 0")
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS excel_data_json TEXT")

    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS sales_bill_id INTEGER")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS project_id INTEGER")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS receivable_type VARCHAR(20) DEFAULT 'normal'")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS business_division VARCHAR(100)")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS job_no VARCHAR(30)")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS department VARCHAR(100)")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS client_name VARCHAR(200)")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS project_name VARCHAR(300)")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS sales_manager VARCHAR(100)")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS construction_manager VARCHAR(100)")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS collection_terms VARCHAR(200)")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS customer_class VARCHAR(30) DEFAULT 'general'")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS collection_date DATE")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS note_maturity_date DATE")
    op.execute("ALTER TABLE accounts_receivable ADD COLUMN IF NOT EXISTS note_issuer VARCHAR(200)")

    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS job_no VARCHAR(30)")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS contract_name VARCHAR(300)")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS vendor_name VARCHAR(200)")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS contract_amount_ex_vat NUMERIC(18, 2) DEFAULT 0")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS contract_amount NUMERIC(18, 2) DEFAULT 0")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS purchase_type VARCHAR(30)")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS subcontract_type VARCHAR(30)")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(200)")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS collection_terms VARCHAR(200)")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS related_revenue_no VARCHAR(50)")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS related_revenue NUMERIC(18, 2) DEFAULT 0")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS related_revenue_collection_date DATE")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS related_revenue_collection_method VARCHAR(50)")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS actual_payment_date DATE")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS payment_type VARCHAR(30)")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS cash_paid_amount NUMERIC(18, 2) DEFAULT 0")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS note_issued_amount NUMERIC(18, 2) DEFAULT 0")
    op.execute("ALTER TABLE accounts_payable ADD COLUMN IF NOT EXISTS note_maturity_date DATE")

    op.execute("""
        CREATE TABLE IF NOT EXISTS notices (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_notices_id ON notices (id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS estimate_attachments (
            id SERIAL PRIMARY KEY,
            estimate_id INTEGER NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
            original_name VARCHAR(255) NOT NULL,
            stored_name VARCHAR(255) NOT NULL,
            content_type VARCHAR(120),
            file_size INTEGER DEFAULT 0,
            file_path TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_estimate_attachments_id ON estimate_attachments (id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS project_sales_plan_rows (
            id SERIAL PRIMARY KEY,
            plan_year INTEGER NOT NULL,
            row_key VARCHAR(80) NOT NULL,
            project_id INTEGER REFERENCES projects(id),
            data_json TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_project_sales_plan_rows_year_key ON project_sales_plan_rows (plan_year, row_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_sales_plan_rows_id ON project_sales_plan_rows (id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS project_purchase_plan_rows (
            id SERIAL PRIMARY KEY,
            plan_year INTEGER NOT NULL,
            row_key VARCHAR(80) NOT NULL,
            project_id INTEGER REFERENCES projects(id),
            data_json TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_project_purchase_plan_rows_year_key ON project_purchase_plan_rows (plan_year, row_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_purchase_plan_rows_id ON project_purchase_plan_rows (id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS project_business_categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(80) NOT NULL UNIQUE,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_business_categories_id ON project_business_categories (id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS project_plan_metas (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id),
            plan_year INTEGER NOT NULL,
            data_json TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_project_plan_metas_project_year ON project_plan_metas (project_id, plan_year)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_plan_metas_id ON project_plan_metas (id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS project_plan_weekly_snapshots (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id),
            plan_year INTEGER NOT NULL,
            week_start DATE NOT NULL,
            data_json TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_project_plan_weekly_snapshots_project_year_week ON project_plan_weekly_snapshots (project_id, plan_year, week_start)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_plan_weekly_snapshots_id ON project_plan_weekly_snapshots (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_plan_weekly_snapshots_week_start ON project_plan_weekly_snapshots (week_start)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS sales_management_weekly_rows (
            id SERIAL PRIMARY KEY,
            week_start DATE NOT NULL,
            row_key VARCHAR(80) NOT NULL,
            data_json TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_management_weekly_rows_week_key ON sales_management_weekly_rows (week_start, row_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sales_management_weekly_rows_id ON sales_management_weekly_rows (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sales_management_weekly_rows_week_start ON sales_management_weekly_rows (week_start)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS management_sales_business_plan_rows (
            id SERIAL PRIMARY KEY,
            plan_year INTEGER NOT NULL,
            business_type VARCHAR(100) NOT NULL,
            data_json TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_management_sales_business_plan_rows_year_type ON management_sales_business_plan_rows (plan_year, business_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_management_sales_business_plan_rows_id ON management_sales_business_plan_rows (id)")


def downgrade():
    for table_name in (
        "management_sales_business_plan_rows",
        "sales_management_weekly_rows",
        "project_plan_weekly_snapshots",
        "project_plan_metas",
        "project_business_categories",
        "project_purchase_plan_rows",
        "project_sales_plan_rows",
        "estimate_attachments",
        "notices",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
