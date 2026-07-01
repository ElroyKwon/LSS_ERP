from sqlalchemy import inspect, text


COMPANY_COLUMNS = {
    "company_group_code": "VARCHAR(20)",
    "short_name": "VARCHAR(40)",
    "resident_type": "VARCHAR(20)",
    "resident_no": "VARCHAR(20)",
    "business_type": "VARCHAR(40)",
    "business_item": "VARCHAR(40)",
    "postal_code": "VARCHAR(7)",
    "address_detail1": "VARCHAR(60)",
    "address_detail2": "VARCHAR(100)",
    "fax": "VARCHAR(20)",
    "homepage": "VARCHAR(100)",
    "liquor_code": "VARCHAR(20)",
    "liquor_name": "VARCHAR(100)",
    "country_code": "VARCHAR(20)",
    "project_code": "VARCHAR(30)",
    "project_name": "VARCHAR(100)",
    "company_category_code": "VARCHAR(30)",
    "company_category_name": "VARCHAR(100)",
    "company_grade_code": "VARCHAR(30)",
    "company_grade_name": "VARCHAR(100)",
    "collection_customer_code": "VARCHAR(30)",
    "collection_customer_name": "VARCHAR(100)",
    "region_code": "VARCHAR(30)",
    "region_name": "VARCHAR(100)",
    "external_data_code": "VARCHAR(50)",
    "electronic_tax_invoice_yn": "VARCHAR(1)",
    "single_report_customer_code": "VARCHAR(30)",
    "single_report_customer_name": "VARCHAR(100)",
    "tax_business_no": "VARCHAR(20)",
    "multi_supplier_yn": "VARCHAR(1)",
    "purpose_type": "VARCHAR(30)",
    "transaction_start_date": "DATE",
    "use_yn": "VARCHAR(1)",
    "contract_start_date": "DATE",
    "contract_end_date": "DATE",
    "transaction_status": "VARCHAR(20)",
    "discount_rate": "NUMERIC(8, 4)",
    "contract_amount": "NUMERIC(18, 2)",
    "use_expense_amount": "NUMERIC(18, 2)",
    "payment_terms": "VARCHAR(100)",
    "limit_recovery_days": "INTEGER",
    "payment_bank_code": "VARCHAR(30)",
    "payment_bank_name": "VARCHAR(100)",
    "payment_branch_name": "VARCHAR(100)",
    "payment_account_no": "VARCHAR(50)",
    "payment_account_holder": "VARCHAR(50)",
    "slip_type_code": "VARCHAR(30)",
    "slip_type_name": "VARCHAR(100)",
    "tax_category_code": "VARCHAR(30)",
    "tax_category_name": "VARCHAR(100)",
    "payment_due_day": "INTEGER",
    "manager_department_code": "VARCHAR(30)",
    "manager_department_name": "VARCHAR(100)",
    "manager_position": "VARCHAR(50)",
    "manager_task": "VARCHAR(100)",
    "manager_employee_code": "VARCHAR(30)",
    "manager_employee_name": "VARCHAR(100)",
    "manager_phone": "VARCHAR(20)",
    "manager_extension": "VARCHAR(20)",
    "manager_mobile": "VARCHAR(20)",
    "manager_email": "VARCHAR(150)",
    "manager_notes": "TEXT",
    "receiver_postal_code": "VARCHAR(7)",
    "receiver_address1": "VARCHAR(100)",
    "receiver_address2": "VARCHAR(100)",
    "receiver_phone": "VARCHAR(20)",
    "receiver_fax": "VARCHAR(20)",
    "receiver_notes": "TEXT",
    "bank_name": "VARCHAR(50)",
    "bank_account": "VARCHAR(50)",
    "bank_holder": "VARCHAR(50)",
    "receivables_note": "TEXT",
}


MATERIAL_COLUMNS = {
    "material_company_group_code": "VARCHAR(20)",
    "management_unit": "VARCHAR(20)",
    "conversion_factor": "NUMERIC(18, 6)",
    "procurement_type": "VARCHAR(20)",
    "item_group_code": "VARCHAR(30)",
    "item_group_name": "VARCHAR(100)",
    "lot_use_yn": "VARCHAR(1)",
    "inspection_type": "VARCHAR(20)",
    "lot_quantity": "NUMERIC(18, 2)",
    "drawing_no": "VARCHAR(50)",
    "hs_code": "VARCHAR(30)",
    "width_value": "NUMERIC(18, 6)",
    "width_unit": "VARCHAR(20)",
    "height_value": "NUMERIC(18, 6)",
    "height_unit": "VARCHAR(20)",
    "depth_value": "NUMERIC(18, 6)",
    "depth_unit": "VARCHAR(20)",
    "weight_value": "NUMERIC(18, 6)",
    "weight_unit": "VARCHAR(20)",
    "area_value": "NUMERIC(18, 6)",
    "area_unit": "VARCHAR(20)",
    "set_item_yn": "VARCHAR(1)",
    "use_yn": "VARCHAR(1)",
    "batch_quantity": "NUMERIC(18, 2)",
    "barcode": "VARCHAR(100)",
    "material_quality": "VARCHAR(100)",
    "length_value": "NUMERIC(18, 6)",
    "length_unit": "VARCHAR(20)",
    "density_value": "NUMERIC(18, 6)",
    "tax_type": "VARCHAR(20)",
    "web_order_yn": "VARCHAR(1)",
    "order_notes": "TEXT",
}


EMPLOYEE_COLUMNS = {
    "department_name": "VARCHAR(100)",
    "job_title": "VARCHAR(50)",
    "task": "VARCHAR(100)",
    "wedding_anniversary": "DATE",
    "home_address": "VARCHAR(200)",
    "corporate_card_no": "VARCHAR(50)",
}


USER_COLUMNS = {
    "employee_code": "VARCHAR(20)",
}


USER_REGISTRATION_COLUMNS = {
    "employee_code": "VARCHAR(20)",
}


DEPARTMENT_COLUMNS = {
    "parent_id": "INTEGER",
    "org_year": "INTEGER",
    "dept_type": "VARCHAR(20)",
    "sort_order": "INTEGER DEFAULT 0",
    "notes": "TEXT",
    "updated_at": "TIMESTAMP",
}


TIMESHEET_ENTRY_COLUMNS = {
    "spg": "VARCHAR(20)",
    "labor_type": "VARCHAR(20)",
}


ACCOUNTS_RECEIVABLE_COLUMNS = {
    "sales_bill_id": "INTEGER",
    "project_id": "INTEGER",
    "receivable_type": "VARCHAR(20) DEFAULT '외상매출금'",
    "business_division": "VARCHAR(100)",
    "job_no": "VARCHAR(30)",
    "department": "VARCHAR(100)",
    "client_name": "VARCHAR(200)",
    "project_name": "VARCHAR(300)",
    "sales_manager": "VARCHAR(100)",
    "construction_manager": "VARCHAR(100)",
    "collection_terms": "VARCHAR(200)",
    "customer_class": "VARCHAR(30) DEFAULT '일반'",
    "collection_date": "DATE",
    "note_maturity_date": "DATE",
    "note_issuer": "VARCHAR(200)",
}


ACCOUNTS_PAYABLE_COLUMNS = {
    "job_no": "VARCHAR(30)",
    "contract_name": "VARCHAR(300)",
    "vendor_name": "VARCHAR(200)",
    "contract_amount_ex_vat": "NUMERIC(18, 2) DEFAULT 0",
    "contract_amount": "NUMERIC(18, 2) DEFAULT 0",
    "purchase_type": "VARCHAR(30)",
    "subcontract_type": "VARCHAR(30)",
    "payment_terms": "VARCHAR(200)",
    "collection_terms": "VARCHAR(200)",
    "related_revenue_no": "VARCHAR(50)",
    "related_revenue": "NUMERIC(18, 2) DEFAULT 0",
    "related_revenue_collection_date": "DATE",
    "related_revenue_collection_method": "VARCHAR(50)",
    "actual_payment_date": "DATE",
    "payment_type": "VARCHAR(30)",
    "cash_paid_amount": "NUMERIC(18, 2) DEFAULT 0",
    "note_issued_amount": "NUMERIC(18, 2) DEFAULT 0",
    "note_maturity_date": "DATE",
}

PROJECT_PLAN_COLUMNS = {
    "invoice_plan": "NUMERIC(18, 2) DEFAULT 0",
}

PROJECT_COLUMNS = {
    "excel_data_json": "TEXT",
}

MASTER_INDEXES = {
    "companies": [
        ("idx_companies_active_name", "is_active, company_name"),
        ("idx_companies_active_code", "is_active, company_code"),
        ("idx_companies_business_no", "business_no"),
    ],
    "materials": [
        ("idx_materials_active_code", "is_active, material_code"),
        ("idx_materials_active_name", "is_active, material_name"),
        ("idx_materials_active_type_code", "is_active, material_type, material_code"),
    ],
}


def _ensure_columns(engine, table_name, columns):
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns(table_name)}
    missing = [(name, ddl_type) for name, ddl_type in columns.items() if name not in existing]
    if not missing:
        return

    with engine.begin() as conn:
        for name, ddl_type in missing:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {ddl_type}"))


def _ensure_indexes(engine, index_map):
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table_name, indexes in index_map.items():
            if table_name not in table_names:
                continue
            existing = {idx["name"] for idx in inspector.get_indexes(table_name)}
            for index_name, columns in indexes:
                if index_name in existing:
                    continue
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})"))


def ensure_master_columns(engine):
    _ensure_columns(engine, "users", USER_COLUMNS)
    _ensure_columns(engine, "user_registrations", USER_REGISTRATION_COLUMNS)
    _ensure_columns(engine, "departments", DEPARTMENT_COLUMNS)
    _ensure_columns(engine, "companies", COMPANY_COLUMNS)
    _ensure_columns(engine, "materials", MATERIAL_COLUMNS)
    _ensure_columns(engine, "employees", EMPLOYEE_COLUMNS)
    _ensure_columns(engine, "timesheet_entries", TIMESHEET_ENTRY_COLUMNS)
    _ensure_indexes(engine, MASTER_INDEXES)


def ensure_accounting_columns(engine):
    _ensure_columns(engine, "accounts_receivable", ACCOUNTS_RECEIVABLE_COLUMNS)
    _ensure_columns(engine, "accounts_payable", ACCOUNTS_PAYABLE_COLUMNS)


def ensure_execution_columns(engine):
    _ensure_columns(engine, "projects", PROJECT_COLUMNS)
    _ensure_columns(engine, "project_plans", PROJECT_PLAN_COLUMNS)
