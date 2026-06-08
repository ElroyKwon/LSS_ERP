-- ============================================================
-- LSS ERP 데이터베이스 초기화 스크립트
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 0. 공통 시스템
-- ============================================================

CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150),
    phone VARCHAR(20),
    department_id INT REFERENCES departments(id),
    position VARCHAR(50),
    role VARCHAR(30) NOT NULL DEFAULT 'user',  -- admin, manager, user
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    username VARCHAR(50),
    action VARCHAR(20) NOT NULL,  -- CREATE, UPDATE, DELETE, VIEW
    table_name VARCHAR(100),
    record_id VARCHAR(50),
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- 1. 기준정보 (Master Data)
-- ============================================================

CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    company_code VARCHAR(20) UNIQUE NOT NULL,
    company_name VARCHAR(200) NOT NULL,
    company_type VARCHAR(20) NOT NULL,  -- client(발주처), vendor(협력사), both
    business_no VARCHAR(20),
    ceo_name VARCHAR(50),
    address TEXT,
    phone VARCHAR(20),
    email VARCHAR(150),
    bank_name VARCHAR(50),
    bank_account VARCHAR(50),
    bank_holder VARCHAR(50),
    credit_limit NUMERIC(18,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sites (
    id SERIAL PRIMARY KEY,
    site_code VARCHAR(20) UNIQUE NOT NULL,
    job_no VARCHAR(20) UNIQUE,
    site_name VARCHAR(200) NOT NULL,
    client_id INT REFERENCES companies(id),
    contract_type VARCHAR(20),  -- lump_sum(총액), unit_price(단가), actual_cost(실비)
    site_manager_id INT REFERENCES users(id),
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'active',  -- active, completed, suspended
    location TEXT,
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE cost_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    parent_id INT REFERENCES cost_codes(id),
    level INT DEFAULT 1,
    cost_type VARCHAR(20),  -- material, labor, subcontract, expense, equipment
    account_code VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE account_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    parent_id INT REFERENCES account_codes(id),
    account_type VARCHAR(20),  -- asset, liability, equity, revenue, expense
    is_vat BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE materials (
    id SERIAL PRIMARY KEY,
    material_code VARCHAR(30) UNIQUE NOT NULL,
    material_name VARCHAR(200) NOT NULL,
    spec VARCHAR(200),
    unit VARCHAR(20),
    material_type VARCHAR(20),  -- domestic(내자재), import(외자재), sauter
    cost_code_id INT REFERENCES cost_codes(id),
    standard_price NUMERIC(18,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE unit_prices (
    id SERIAL PRIMARY KEY,
    material_id INT REFERENCES materials(id),
    vendor_id INT REFERENCES companies(id),
    price NUMERIC(18,2) NOT NULL,
    unit VARCHAR(20),
    apply_year INT NOT NULL,
    apply_from DATE,
    apply_to DATE,
    price_type VARCHAR(20) DEFAULT 'standard',  -- standard, contract
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    emp_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(50) NOT NULL,
    department_id INT REFERENCES departments(id),
    position VARCHAR(50),
    emp_type VARCHAR(20) DEFAULT 'regular',  -- regular(정규직), daily(일용직), contract(계약직)
    hire_date DATE,
    resign_date DATE,
    birth_date DATE,
    phone VARCHAR(20),
    email VARCHAR(150),
    bank_name VARCHAR(50),
    bank_account VARCHAR(50),
    daily_wage NUMERIC(12,2) DEFAULT 0,
    monthly_salary NUMERIC(12,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE overhead_rates (
    id SERIAL PRIMARY KEY,
    rate_year INT NOT NULL,
    labor_rate NUMERIC(8,4),      -- 임율 (원/시간 또는 원/인일)
    overhead_rate NUMERIC(8,4),   -- 판관비율 (%)
    profit_rate NUMERIC(8,4),     -- 이익률 (%)
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- 2. 영업·수주
-- ============================================================

CREATE TABLE estimates (
    id SERIAL PRIMARY KEY,
    estimate_no VARCHAR(30) UNIQUE NOT NULL,
    site_id INT REFERENCES sites(id),
    client_id INT REFERENCES companies(id),
    title VARCHAR(300) NOT NULL,
    estimate_type VARCHAR(20) DEFAULT 'bas',  -- bas, other
    total_amount NUMERIC(18,2) DEFAULT 0,
    labor_amount NUMERIC(18,2) DEFAULT 0,
    material_amount NUMERIC(18,2) DEFAULT 0,
    subcontract_amount NUMERIC(18,2) DEFAULT 0,
    expense_amount NUMERIC(18,2) DEFAULT 0,
    overhead_amount NUMERIC(18,2) DEFAULT 0,
    profit_amount NUMERIC(18,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, submitted, approved, converted
    estimated_by INT REFERENCES users(id),
    estimate_date DATE,
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE estimate_items (
    id SERIAL PRIMARY KEY,
    estimate_id INT REFERENCES estimates(id) ON DELETE CASCADE,
    cost_code_id INT REFERENCES cost_codes(id),
    item_name VARCHAR(200) NOT NULL,
    spec VARCHAR(200),
    unit VARCHAR(20),
    quantity NUMERIC(14,4) DEFAULT 0,
    unit_price NUMERIC(18,2) DEFAULT 0,
    amount NUMERIC(18,2) DEFAULT 0,
    sort_order INT DEFAULT 0,
    notes TEXT
);

CREATE TABLE contracts (
    id SERIAL PRIMARY KEY,
    contract_no VARCHAR(30) UNIQUE NOT NULL,
    site_id INT REFERENCES sites(id),
    estimate_id INT REFERENCES estimates(id),
    client_id INT REFERENCES companies(id),
    contract_name VARCHAR(300) NOT NULL,
    contract_type VARCHAR(20) NOT NULL,  -- lump_sum, unit_price, actual_cost
    revenue_type VARCHAR(20) DEFAULT 'general',  -- general(일반), progress(진행율)
    original_amount NUMERIC(18,2) DEFAULT 0,
    current_amount NUMERIC(18,2) DEFAULT 0,
    original_cost NUMERIC(18,2) DEFAULT 0,
    current_cost NUMERIC(18,2) DEFAULT 0,
    contract_date DATE,
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'active',  -- active, changed, completed, cancelled
    sales_manager_id INT REFERENCES users(id),
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE contract_changes (
    id SERIAL PRIMARY KEY,
    contract_id INT REFERENCES contracts(id),
    change_no INT NOT NULL,
    change_date DATE NOT NULL,
    amount_before NUMERIC(18,2),
    amount_change NUMERIC(18,2) DEFAULT 0,
    amount_after NUMERIC(18,2),
    cost_before NUMERIC(18,2),
    cost_change NUMERIC(18,2) DEFAULT 0,
    cost_after NUMERIC(18,2),
    end_date_before DATE,
    end_date_after DATE,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, approved
    approved_by INT REFERENCES users(id),
    approved_at TIMESTAMP,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE progress_billings (
    id SERIAL PRIMARY KEY,
    billing_no VARCHAR(30) UNIQUE NOT NULL,
    contract_id INT REFERENCES contracts(id),
    site_id INT REFERENCES sites(id),
    billing_seq INT NOT NULL,
    billing_date DATE NOT NULL,
    progress_rate NUMERIC(6,2) DEFAULT 0,  -- 기성율 (%)
    billing_amount NUMERIC(18,2) DEFAULT 0,
    vat_amount NUMERIC(18,2) DEFAULT 0,
    total_amount NUMERIC(18,2) DEFAULT 0,
    cumulative_amount NUMERIC(18,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, submitted, approved, invoiced
    invoice_no VARCHAR(50),
    invoice_date DATE,
    due_date DATE,
    notes TEXT,
    approved_by INT REFERENCES users(id),
    approved_at TIMESTAMP,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE collections (
    id SERIAL PRIMARY KEY,
    collection_no VARCHAR(30) UNIQUE NOT NULL,
    billing_id INT REFERENCES progress_billings(id),
    contract_id INT REFERENCES contracts(id),
    site_id INT REFERENCES sites(id),
    client_id INT REFERENCES companies(id),
    collected_date DATE NOT NULL,
    collected_amount NUMERIC(18,2) NOT NULL,
    bank_name VARCHAR(50),
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- 3. 구매·투입
-- ============================================================

CREATE TABLE purchase_requests (
    id SERIAL PRIMARY KEY,
    request_no VARCHAR(30) UNIQUE NOT NULL,
    site_id INT REFERENCES sites(id),
    request_type VARCHAR(20) NOT NULL,  -- material(내자재), import(외자재), subcontract(외주)
    request_date DATE NOT NULL,
    required_date DATE,
    total_amount NUMERIC(18,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, approved, ordered
    notes TEXT,
    requested_by INT REFERENCES users(id),
    approved_by INT REFERENCES users(id),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE purchase_request_items (
    id SERIAL PRIMARY KEY,
    request_id INT REFERENCES purchase_requests(id) ON DELETE CASCADE,
    material_id INT REFERENCES materials(id),
    item_name VARCHAR(200) NOT NULL,
    spec VARCHAR(200),
    unit VARCHAR(20),
    quantity NUMERIC(14,4) DEFAULT 0,
    unit_price NUMERIC(18,2) DEFAULT 0,
    amount NUMERIC(18,2) DEFAULT 0,
    cost_code_id INT REFERENCES cost_codes(id),
    notes TEXT
);

CREATE TABLE purchase_orders (
    id SERIAL PRIMARY KEY,
    order_no VARCHAR(30) UNIQUE NOT NULL,
    site_id INT REFERENCES sites(id),
    vendor_id INT REFERENCES companies(id),
    request_id INT REFERENCES purchase_requests(id),
    order_type VARCHAR(20) NOT NULL,  -- material, import, subcontract, equipment
    order_date DATE NOT NULL,
    delivery_date DATE,
    total_amount NUMERIC(18,2) DEFAULT 0,
    vat_amount NUMERIC(18,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, confirmed, partial, completed, cancelled
    notes TEXT,
    approved_by INT REFERENCES users(id),
    approved_at TIMESTAMP,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE purchase_order_items (
    id SERIAL PRIMARY KEY,
    order_id INT REFERENCES purchase_orders(id) ON DELETE CASCADE,
    material_id INT REFERENCES materials(id),
    item_name VARCHAR(200) NOT NULL,
    spec VARCHAR(200),
    unit VARCHAR(20),
    ordered_qty NUMERIC(14,4) DEFAULT 0,
    received_qty NUMERIC(14,4) DEFAULT 0,
    unit_price NUMERIC(18,2) DEFAULT 0,
    amount NUMERIC(18,2) DEFAULT 0,
    cost_code_id INT REFERENCES cost_codes(id),
    notes TEXT
);

CREATE TABLE receipts (
    id SERIAL PRIMARY KEY,
    receipt_no VARCHAR(30) UNIQUE NOT NULL,
    order_id INT REFERENCES purchase_orders(id),
    site_id INT REFERENCES sites(id),
    vendor_id INT REFERENCES companies(id),
    receipt_date DATE NOT NULL,
    invoice_no VARCHAR(50),
    total_amount NUMERIC(18,2) DEFAULT 0,
    vat_amount NUMERIC(18,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, inspected, approved, rejected
    inspector_id INT REFERENCES users(id),
    inspected_at TIMESTAMP,
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE receipt_items (
    id SERIAL PRIMARY KEY,
    receipt_id INT REFERENCES receipts(id) ON DELETE CASCADE,
    order_item_id INT REFERENCES purchase_order_items(id),
    material_id INT REFERENCES materials(id),
    item_name VARCHAR(200) NOT NULL,
    unit VARCHAR(20),
    received_qty NUMERIC(14,4) DEFAULT 0,
    returned_qty NUMERIC(14,4) DEFAULT 0,
    unit_price NUMERIC(18,2) DEFAULT 0,
    amount NUMERIC(18,2) DEFAULT 0,
    cost_code_id INT REFERENCES cost_codes(id)
);

CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    site_id INT REFERENCES sites(id),
    material_id INT REFERENCES materials(id),
    current_qty NUMERIC(14,4) DEFAULT 0,
    reserved_qty NUMERIC(14,4) DEFAULT 0,
    available_qty NUMERIC(14,4) DEFAULT 0,
    avg_unit_price NUMERIC(18,2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(site_id, material_id)
);

CREATE TABLE inventory_transactions (
    id SERIAL PRIMARY KEY,
    site_id INT REFERENCES sites(id),
    material_id INT REFERENCES materials(id),
    transaction_type VARCHAR(20) NOT NULL,  -- in(입고), out(출고), return(반납), transfer(이동)
    quantity NUMERIC(14,4) NOT NULL,
    unit_price NUMERIC(18,2) DEFAULT 0,
    amount NUMERIC(18,2) DEFAULT 0,
    ref_type VARCHAR(50),  -- receipt, issue, etc.
    ref_id INT,
    cost_code_id INT REFERENCES cost_codes(id),
    transaction_date DATE NOT NULL,
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE subcontracts (
    id SERIAL PRIMARY KEY,
    subcontract_no VARCHAR(30) UNIQUE NOT NULL,
    site_id INT REFERENCES sites(id),
    vendor_id INT REFERENCES companies(id),
    contract_name VARCHAR(200) NOT NULL,
    cost_code_id INT REFERENCES cost_codes(id),
    contract_amount NUMERIC(18,2) DEFAULT 0,
    advance_payment NUMERIC(18,2) DEFAULT 0,
    retention_rate NUMERIC(6,2) DEFAULT 0,  -- 하자보증금율
    start_date DATE,
    end_date DATE,
    payment_terms TEXT,
    status VARCHAR(20) DEFAULT 'active',  -- active, completed, cancelled
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE subcontract_billings (
    id SERIAL PRIMARY KEY,
    billing_no VARCHAR(30) UNIQUE NOT NULL,
    subcontract_id INT REFERENCES subcontracts(id),
    site_id INT REFERENCES sites(id),
    billing_seq INT NOT NULL,
    billing_date DATE NOT NULL,
    progress_rate NUMERIC(6,2) DEFAULT 0,
    billing_amount NUMERIC(18,2) DEFAULT 0,
    vat_amount NUMERIC(18,2) DEFAULT 0,
    total_amount NUMERIC(18,2) DEFAULT 0,
    cumulative_amount NUMERIC(18,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, approved, paid
    approved_by INT REFERENCES users(id),
    approved_at TIMESTAMP,
    paid_at TIMESTAMP,
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE labor_inputs (
    id SERIAL PRIMARY KEY,
    site_id INT REFERENCES sites(id),
    employee_id INT REFERENCES employees(id),
    cost_code_id INT REFERENCES cost_codes(id),
    work_date DATE NOT NULL,
    work_days NUMERIC(4,1) DEFAULT 1,
    daily_wage NUMERIC(12,2) DEFAULT 0,
    amount NUMERIC(14,2) DEFAULT 0,
    insurance_amount NUMERIC(12,2) DEFAULT 0,
    net_amount NUMERIC(14,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, confirmed
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE expenses (
    id SERIAL PRIMARY KEY,
    expense_no VARCHAR(30) UNIQUE NOT NULL,
    site_id INT REFERENCES sites(id),
    cost_code_id INT REFERENCES cost_codes(id),
    expense_date DATE NOT NULL,
    expense_type VARCHAR(50),  -- travel, meal, supplies, etc.
    description VARCHAR(300),
    amount NUMERIC(14,2) DEFAULT 0,
    vat_amount NUMERIC(12,2) DEFAULT 0,
    vendor_id INT REFERENCES companies(id),
    receipt_no VARCHAR(50),
    status VARCHAR(20) DEFAULT 'draft',  -- draft, approved, paid
    approved_by INT REFERENCES users(id),
    approved_at TIMESTAMP,
    notes TEXT,
    requested_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- 4. 예산·원가분석
-- ============================================================

CREATE TABLE budgets (
    id SERIAL PRIMARY KEY,
    contract_id INT REFERENCES contracts(id),
    site_id INT REFERENCES sites(id),
    version INT DEFAULT 1,
    budget_name VARCHAR(100),
    total_amount NUMERIC(18,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',  -- draft, active, superseded
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE budget_items (
    id SERIAL PRIMARY KEY,
    budget_id INT REFERENCES budgets(id) ON DELETE CASCADE,
    cost_code_id INT REFERENCES cost_codes(id),
    cost_type VARCHAR(20),  -- material, labor, subcontract, expense, equipment
    item_name VARCHAR(200),
    budgeted_amount NUMERIC(18,2) DEFAULT 0,
    execution_amount NUMERIC(18,2) DEFAULT 0,
    actual_amount NUMERIC(18,2) DEFAULT 0,
    notes TEXT
);

CREATE TABLE cost_inputs (
    id SERIAL PRIMARY KEY,
    site_id INT REFERENCES sites(id),
    cost_code_id INT REFERENCES cost_codes(id),
    cost_type VARCHAR(20) NOT NULL,  -- material, labor, subcontract, expense, equipment
    input_date DATE NOT NULL,
    amount NUMERIC(18,2) DEFAULT 0,
    ref_type VARCHAR(50),  -- receipt, labor_input, subcontract_billing, expense
    ref_id INT,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- 5. 회계
-- ============================================================

CREATE TABLE journal_entries (
    id SERIAL PRIMARY KEY,
    entry_no VARCHAR(30) UNIQUE NOT NULL,
    entry_date DATE NOT NULL,
    entry_type VARCHAR(20) DEFAULT 'general',  -- general, auto, closing
    description TEXT,
    total_debit NUMERIC(18,2) DEFAULT 0,
    total_credit NUMERIC(18,2) DEFAULT 0,
    site_id INT REFERENCES sites(id),
    status VARCHAR(20) DEFAULT 'draft',  -- draft, approved, cancelled
    ref_type VARCHAR(50),  -- billing, receipt, labor, expense, etc.
    ref_id INT,
    approved_by INT REFERENCES users(id),
    approved_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE journal_lines (
    id SERIAL PRIMARY KEY,
    entry_id INT REFERENCES journal_entries(id) ON DELETE CASCADE,
    line_no INT NOT NULL,
    account_id INT REFERENCES account_codes(id),
    debit_amount NUMERIC(18,2) DEFAULT 0,
    credit_amount NUMERIC(18,2) DEFAULT 0,
    site_id INT REFERENCES sites(id),
    cost_code_id INT REFERENCES cost_codes(id),
    vendor_id INT REFERENCES companies(id),
    description VARCHAR(300),
    tax_invoice_no VARCHAR(50)
);

CREATE TABLE accounts_receivable (
    id SERIAL PRIMARY KEY,
    billing_id INT REFERENCES progress_billings(id),
    site_id INT REFERENCES sites(id),
    client_id INT REFERENCES companies(id),
    issue_date DATE NOT NULL,
    due_date DATE,
    billing_amount NUMERIC(18,2) DEFAULT 0,
    collected_amount NUMERIC(18,2) DEFAULT 0,
    outstanding_amount NUMERIC(18,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'outstanding',  -- outstanding, partial, collected, overdue
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE accounts_payable (
    id SERIAL PRIMARY KEY,
    site_id INT REFERENCES sites(id),
    vendor_id INT REFERENCES companies(id),
    ref_type VARCHAR(50),  -- receipt, subcontract_billing, expense
    ref_id INT,
    issue_date DATE NOT NULL,
    due_date DATE,
    invoice_no VARCHAR(50),
    total_amount NUMERIC(18,2) DEFAULT 0,
    paid_amount NUMERIC(18,2) DEFAULT 0,
    outstanding_amount NUMERIC(18,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'outstanding',  -- outstanding, partial, paid
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    payment_no VARCHAR(30) UNIQUE NOT NULL,
    vendor_id INT REFERENCES companies(id),
    site_id INT REFERENCES sites(id),
    payment_date DATE NOT NULL,
    payment_amount NUMERIC(18,2) NOT NULL,
    payment_method VARCHAR(20) DEFAULT 'transfer',  -- transfer, check, cash
    bank_name VARCHAR(50),
    notes TEXT,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, approved, completed
    approved_by INT REFERENCES users(id),
    approved_at TIMESTAMP,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE payment_items (
    id SERIAL PRIMARY KEY,
    payment_id INT REFERENCES payments(id) ON DELETE CASCADE,
    payable_id INT REFERENCES accounts_payable(id),
    applied_amount NUMERIC(18,2) DEFAULT 0
);

CREATE TABLE period_closings (
    id SERIAL PRIMARY KEY,
    close_year INT NOT NULL,
    close_month INT NOT NULL,
    status VARCHAR(20) DEFAULT 'open',  -- open, closed
    closed_by INT REFERENCES users(id),
    closed_at TIMESTAMP,
    notes TEXT,
    UNIQUE(close_year, close_month)
);

-- ============================================================
-- 6. 경영예측
-- ============================================================

CREATE TABLE revenue_forecasts (
    id SERIAL PRIMARY KEY,
    site_id INT REFERENCES sites(id),
    forecast_year INT NOT NULL,
    forecast_month INT NOT NULL,
    forecast_amount NUMERIC(18,2) DEFAULT 0,
    actual_amount NUMERIC(18,2) DEFAULT 0,
    achievement_rate NUMERIC(8,4) DEFAULT 0,
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(site_id, forecast_year, forecast_month)
);

CREATE TABLE sales_pipelines (
    id SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(200) NOT NULL,
    client_id INT REFERENCES companies(id),
    expected_amount NUMERIC(18,2) DEFAULT 0,
    probability INT DEFAULT 50,  -- 0-100%
    weighted_amount NUMERIC(18,2) DEFAULT 0,
    expected_date DATE,
    sales_manager_id INT REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'active',  -- active, won, lost
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE fund_plans (
    id SERIAL PRIMARY KEY,
    plan_year INT NOT NULL,
    plan_month INT NOT NULL,
    planned_income NUMERIC(18,2) DEFAULT 0,
    planned_expense NUMERIC(18,2) DEFAULT 0,
    planned_balance NUMERIC(18,2) DEFAULT 0,
    actual_income NUMERIC(18,2) DEFAULT 0,
    actual_expense NUMERIC(18,2) DEFAULT 0,
    actual_balance NUMERIC(18,2) DEFAULT 0,
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(plan_year, plan_month)
);

-- ============================================================
-- 인덱스
-- ============================================================

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);
CREATE INDEX idx_sites_client ON sites(client_id);
CREATE INDEX idx_sites_status ON sites(status);
CREATE INDEX idx_contracts_site ON contracts(site_id);
CREATE INDEX idx_contracts_client ON contracts(client_id);
CREATE INDEX idx_progress_billings_contract ON progress_billings(contract_id);
CREATE INDEX idx_progress_billings_site ON progress_billings(site_id);
CREATE INDEX idx_purchase_orders_site ON purchase_orders(site_id);
CREATE INDEX idx_purchase_orders_vendor ON purchase_orders(vendor_id);
CREATE INDEX idx_receipts_order ON receipts(order_id);
CREATE INDEX idx_inventory_site_material ON inventory(site_id, material_id);
CREATE INDEX idx_journal_entries_date ON journal_entries(entry_date);
CREATE INDEX idx_journal_entries_site ON journal_entries(site_id);
CREATE INDEX idx_journal_lines_entry ON journal_lines(entry_id);
CREATE INDEX idx_ar_site ON accounts_receivable(site_id);
CREATE INDEX idx_ap_vendor ON accounts_payable(vendor_id);
CREATE INDEX idx_cost_inputs_site ON cost_inputs(site_id);

-- ============================================================
-- 기초 데이터 삽입
-- ============================================================

INSERT INTO departments (code, name) VALUES
('MGMT', '경영지원팀'),
('SALES', '영업팀'),
('DESIGN', '설계팀'),
('EXEC', '실행팀'),
('PURCHASE', '구매팀'),
('FINANCE', '자금팀');

INSERT INTO users (username, password_hash, name, email, department_id, position, role) VALUES
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/RK.s5uMxy', '시스템관리자', 'admin@lss.com', 1, '관리자', 'admin');

INSERT INTO account_codes (code, name, account_type, is_vat) VALUES
('1100', '현금', 'asset', FALSE),
('1200', '보통예금', 'asset', FALSE),
('1310', '공사미수금', 'asset', FALSE),
('1400', '재고자산', 'asset', FALSE),
('2100', '외상매입금', 'liability', FALSE),
('2200', '미지급금', 'liability', FALSE),
('4000', '공사수입', 'revenue', TRUE),
('5100', '재료비', 'expense', TRUE),
('5200', '노무비', 'expense', FALSE),
('5300', '외주비', 'expense', TRUE),
('5400', '경비', 'expense', TRUE),
('5500', '일반관리비', 'expense', FALSE);

INSERT INTO cost_codes (code, name, level, cost_type) VALUES
('100', '직접공사비', 1, NULL),
('110', '재료비', 2, 'material'),
('120', '노무비', 2, 'labor'),
('130', '외주비', 2, 'subcontract'),
('140', '경비', 2, 'expense'),
('200', '간접공사비', 1, NULL),
('210', '현장관리비', 2, 'expense'),
('220', '안전관리비', 2, 'expense');
