
-- =========================================================
-- STRATEGYSIM DATABASE SCHEMA
-- Database: SQLite
-- Version: 1.0
-- =========================================================

PRAGMA foreign_keys = ON;


-- =========================================================
-- 1. USER MANAGEMENT
-- =========================================================

CREATE TABLE IF NOT EXISTS users (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    full_name TEXT NOT NULL,

    email TEXT NOT NULL UNIQUE COLLATE NOCASE,

    password_hash TEXT NOT NULL,

    role TEXT NOT NULL DEFAULT 'Viewer'
        CHECK (role IN ('Administrator', 'Analyst', 'Viewer')),

    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),

    last_login_at TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

);


-- =========================================================
-- 2. INDUSTRY MANAGEMENT
-- =========================================================

CREATE TABLE IF NOT EXISTS industries (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    sector TEXT,

    description TEXT,

    geography TEXT DEFAULT 'India',

    industry_type TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(name, geography)

);


-- =========================================================
-- 3. COMPANY MANAGEMENT
-- =========================================================

CREATE TABLE IF NOT EXISTS companies (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    industry_id INTEGER NOT NULL,

    name TEXT NOT NULL,

    company_type TEXT NOT NULL DEFAULT 'Target'
        CHECK (company_type IN ('Target', 'Competitor', 'Other')),

    description TEXT,

    headquarters TEXT,

    website TEXT,

    annual_revenue REAL,

    employee_count INTEGER,

    market_share REAL,

    founded_year INTEGER,

    is_demo INTEGER NOT NULL DEFAULT 0
        CHECK (is_demo IN (0, 1)),

    created_by INTEGER,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (industry_id)
        REFERENCES industries(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE SET NULL

);


-- =========================================================
-- 4. COMPETITOR RELATIONSHIPS
-- =========================================================

CREATE TABLE IF NOT EXISTS competitor_relationships (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    company_id INTEGER NOT NULL,

    competitor_id INTEGER NOT NULL,

    competitive_strength INTEGER
        CHECK (
            competitive_strength IS NULL
            OR competitive_strength BETWEEN 1 AND 5
        ),

    notes TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON DELETE CASCADE,

    FOREIGN KEY (competitor_id)
        REFERENCES companies(id)
        ON DELETE CASCADE,

    CHECK (company_id != competitor_id),

    UNIQUE(company_id, competitor_id)

);


-- =========================================================
-- 5. PORTER'S FIVE FORCES ASSESSMENTS
-- =========================================================

CREATE TABLE IF NOT EXISTS five_forces_assessments (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    company_id INTEGER NOT NULL,

    assessment_name TEXT NOT NULL,

    assessment_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    buyer_power_score REAL,

    supplier_power_score REAL,

    competitive_rivalry_score REAL,

    threat_of_substitution_score REAL,

    threat_of_new_entrants_score REAL,

    overall_score REAL,

    summary TEXT,

    created_by INTEGER,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON DELETE CASCADE,

    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE SET NULL

);


-- =========================================================
-- 6. FIVE FORCES INDICATORS
-- =========================================================

CREATE TABLE IF NOT EXISTS five_forces_indicators (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    assessment_id INTEGER NOT NULL,

    force_name TEXT NOT NULL
        CHECK (
            force_name IN (
                'Buyer Power',
                'Supplier Power',
                'Competitive Rivalry',
                'Threat of Substitution',
                'Threat of New Entrants'
            )
        ),

    indicator_name TEXT NOT NULL,

    score INTEGER NOT NULL
        CHECK (score BETWEEN 1 AND 5),

    weight REAL NOT NULL DEFAULT 1
        CHECK (weight > 0),

    explanation TEXT,

    evidence_id INTEGER,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (assessment_id)
        REFERENCES five_forces_assessments(id)
        ON DELETE CASCADE

);


-- =========================================================
-- 7. VALUE CHAIN ASSESSMENTS
-- =========================================================

CREATE TABLE IF NOT EXISTS value_chain_assessments (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    company_id INTEGER NOT NULL,

    assessment_name TEXT NOT NULL,

    assessment_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    summary TEXT,

    created_by INTEGER,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON DELETE CASCADE,

    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE SET NULL

);


-- =========================================================
-- 8. VALUE CHAIN ACTIVITIES
-- =========================================================

CREATE TABLE IF NOT EXISTS value_chain_activities (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    assessment_id INTEGER NOT NULL,

    activity_category TEXT NOT NULL
        CHECK (
            activity_category IN ('Primary', 'Support')
        ),

    activity_name TEXT NOT NULL,

    description TEXT,

    cost_contribution REAL,

    strategic_importance INTEGER
        CHECK (
            strategic_importance IS NULL
            OR strategic_importance BETWEEN 1 AND 5
        ),

    competitive_advantage TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (assessment_id)
        REFERENCES value_chain_assessments(id)
        ON DELETE CASCADE

);


-- =========================================================
-- 9. SUPPLIER MANAGEMENT
-- =========================================================

CREATE TABLE IF NOT EXISTS suppliers (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    supplier_code TEXT UNIQUE,

    parent_supplier_id INTEGER,

    country TEXT,

    headquarters TEXT,

    supplier_type TEXT,

    tier_level INTEGER NOT NULL DEFAULT 1
        CHECK (tier_level >= 1),

    risk_level TEXT DEFAULT 'Medium'
        CHECK (risk_level IN ('Low', 'Medium', 'High', 'Critical')),

    financial_dependency_score REAL,

    operational_risk_score REAL,

    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),

    description TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (parent_supplier_id)
        REFERENCES suppliers(id)
        ON DELETE SET NULL

);


-- =========================================================
-- 10. COMPONENT MANAGEMENT
-- =========================================================

CREATE TABLE IF NOT EXISTS components (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    component_code TEXT UNIQUE,

    category TEXT,

    description TEXT,

    criticality TEXT DEFAULT 'Medium'
        CHECK (criticality IN ('Low', 'Medium', 'High', 'Critical')),

    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

);


-- =========================================================
-- 11. SUPPLIER COMPONENT RELATIONSHIPS
-- =========================================================

CREATE TABLE IF NOT EXISTS supplier_components (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    supplier_id INTEGER NOT NULL,

    component_id INTEGER NOT NULL,

    unit_cost REAL,

    lead_time_days INTEGER,

    dependency_share_percent REAL
        CHECK (
            dependency_share_percent IS NULL
            OR dependency_share_percent BETWEEN 0 AND 100
        ),

    is_alternative INTEGER NOT NULL DEFAULT 0
        CHECK (is_alternative IN (0, 1)),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (supplier_id)
        REFERENCES suppliers(id)
        ON DELETE CASCADE,

    FOREIGN KEY (component_id)
        REFERENCES components(id)
        ON DELETE CASCADE,

    UNIQUE(supplier_id, component_id)

);


-- =========================================================
-- 12. PROCUREMENT RECORDS
-- =========================================================

CREATE TABLE IF NOT EXISTS procurement_records (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    company_id INTEGER NOT NULL,

    supplier_id INTEGER NOT NULL,

    component_id INTEGER NOT NULL,

    annual_spend REAL NOT NULL DEFAULT 0
        CHECK (annual_spend >= 0),

    spend_share_percent REAL
        CHECK (
            spend_share_percent IS NULL
            OR spend_share_percent BETWEEN 0 AND 100
        ),

    quantity REAL,

    unit_cost REAL,

    contract_start_date TEXT,

    contract_end_date TEXT,

    contract_status TEXT DEFAULT 'Active'
        CHECK (
            contract_status IN (
                'Active',
                'Expired',
                'Pending',
                'Terminated'
            )
        ),

    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON DELETE CASCADE,

    FOREIGN KEY (supplier_id)
        REFERENCES suppliers(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (component_id)
        REFERENCES components(id)
        ON DELETE RESTRICT

);


-- =========================================================
-- 13. SUPPLIER FACILITIES
-- =========================================================

CREATE TABLE IF NOT EXISTS facilities (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    supplier_id INTEGER NOT NULL,

    facility_name TEXT NOT NULL,

    facility_type TEXT,

    country TEXT,

    city TEXT,

    capacity_description TEXT,

    operational_status TEXT DEFAULT 'Active'
        CHECK (
            operational_status IN (
                'Active',
                'Inactive',
                'Disrupted'
            )
        ),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (supplier_id)
        REFERENCES suppliers(id)
        ON DELETE CASCADE

);


-- =========================================================
-- 14. SUPPLIER DEPENDENCY GRAPH RELATIONSHIPS
-- =========================================================

CREATE TABLE IF NOT EXISTS supplier_relationships (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_supplier_id INTEGER NOT NULL,

    target_supplier_id INTEGER NOT NULL,

    relationship_type TEXT NOT NULL,

    dependency_strength REAL
        CHECK (
            dependency_strength IS NULL
            OR dependency_strength BETWEEN 0 AND 100
        ),

    description TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (source_supplier_id)
        REFERENCES suppliers(id)
        ON DELETE CASCADE,

    FOREIGN KEY (target_supplier_id)
        REFERENCES suppliers(id)
        ON DELETE CASCADE,

    CHECK (source_supplier_id != target_supplier_id),

    UNIQUE(
        source_supplier_id,
        target_supplier_id,
        relationship_type
    )

);


-- =========================================================
-- 15. WHAT-IF SCENARIOS
-- =========================================================

CREATE TABLE IF NOT EXISTS scenarios (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    company_id INTEGER NOT NULL,

    scenario_name TEXT NOT NULL,

    scenario_type TEXT NOT NULL,

    description TEXT,

    parameters_json TEXT NOT NULL DEFAULT '{}',

    baseline_metrics_json TEXT,

    status TEXT NOT NULL DEFAULT 'Draft'
        CHECK (
            status IN (
                'Draft',
                'Simulated',
                'Archived'
            )
        ),

    created_by INTEGER,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON DELETE CASCADE,

    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE SET NULL

);


-- =========================================================
-- 16. SCENARIO RESULTS
-- =========================================================

CREATE TABLE IF NOT EXISTS scenario_results (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    scenario_id INTEGER NOT NULL,

    result_name TEXT NOT NULL,

    baseline_value REAL,

    simulated_value REAL,

    change_value REAL,

    change_percent REAL,

    interpretation TEXT,

    result_data_json TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (scenario_id)
        REFERENCES scenarios(id)
        ON DELETE CASCADE

);


-- =========================================================
-- 17. DECISION MATRICES
-- =========================================================

CREATE TABLE IF NOT EXISTS decision_matrices (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    company_id INTEGER NOT NULL,

    matrix_name TEXT NOT NULL,

    objective TEXT,

    description TEXT,

    created_by INTEGER,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON DELETE CASCADE,

    FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE SET NULL

);


-- =========================================================
-- 18. DECISION CRITERIA
-- =========================================================

CREATE TABLE IF NOT EXISTS decision_criteria (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    matrix_id INTEGER NOT NULL,

    criterion_name TEXT NOT NULL,

    weight REAL NOT NULL
        CHECK (weight >= 0),

    description TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (matrix_id)
        REFERENCES decision_matrices(id)
        ON DELETE CASCADE

);


-- =========================================================
-- 19. DECISION OPTIONS
-- =========================================================

CREATE TABLE IF NOT EXISTS decision_options (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    matrix_id INTEGER NOT NULL,

    option_name TEXT NOT NULL,

    description TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (matrix_id)
        REFERENCES decision_matrices(id)
        ON DELETE CASCADE

);


-- =========================================================
-- 20. DECISION SCORES
-- =========================================================

CREATE TABLE IF NOT EXISTS decision_scores (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    option_id INTEGER NOT NULL,

    criterion_id INTEGER NOT NULL,

    score REAL NOT NULL
        CHECK (score BETWEEN 1 AND 5),

    weighted_score REAL,

    justification TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (option_id)
        REFERENCES decision_options(id)
        ON DELETE CASCADE,

    FOREIGN KEY (criterion_id)
        REFERENCES decision_criteria(id)
        ON DELETE CASCADE,

    UNIQUE(option_id, criterion_id)

);


-- =========================================================
-- 21. EVIDENCE AND DATA PROVENANCE
-- =========================================================

CREATE TABLE IF NOT EXISTS evidence (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,

    description TEXT,

    source_type TEXT NOT NULL DEFAULT 'Manual'
        CHECK (
            source_type IN (
                'Manual',
                'CSV Import',
                'External Source',
                'Internal Research',
                'Document'
            )
        ),

    source_name TEXT,

    source_url TEXT,

    file_path TEXT,

    entity_type TEXT,

    entity_id INTEGER,

    reliability_score INTEGER
        CHECK (
            reliability_score IS NULL
            OR reliability_score BETWEEN 1 AND 5
        ),

    uploaded_by INTEGER,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (uploaded_by)
        REFERENCES users(id)
        ON DELETE SET NULL

);


-- =========================================================
-- 22. AUDIT LOGS
-- =========================================================

CREATE TABLE IF NOT EXISTS audit_logs (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER,

    action TEXT NOT NULL,

    entity_type TEXT,

    entity_id INTEGER,

    description TEXT,

    ip_address TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL

);


-- =========================================================
-- 23. DATABASE INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_companies_industry
ON companies(industry_id);

CREATE INDEX IF NOT EXISTS idx_companies_type
ON companies(company_type);

CREATE INDEX IF NOT EXISTS idx_competitors_company
ON competitor_relationships(company_id);

CREATE INDEX IF NOT EXISTS idx_five_forces_company
ON five_forces_assessments(company_id);

CREATE INDEX IF NOT EXISTS idx_five_forces_indicators_assessment
ON five_forces_indicators(assessment_id);

CREATE INDEX IF NOT EXISTS idx_value_chain_company
ON value_chain_assessments(company_id);

CREATE INDEX IF NOT EXISTS idx_value_chain_activities_assessment
ON value_chain_activities(assessment_id);

CREATE INDEX IF NOT EXISTS idx_suppliers_parent
ON suppliers(parent_supplier_id);

CREATE INDEX IF NOT EXISTS idx_supplier_components_supplier
ON supplier_components(supplier_id);

CREATE INDEX IF NOT EXISTS idx_supplier_components_component
ON supplier_components(component_id);

CREATE INDEX IF NOT EXISTS idx_procurement_company
ON procurement_records(company_id);

CREATE INDEX IF NOT EXISTS idx_procurement_supplier
ON procurement_records(supplier_id);

CREATE INDEX IF NOT EXISTS idx_procurement_component
ON procurement_records(component_id);

CREATE INDEX IF NOT EXISTS idx_supplier_relationship_source
ON supplier_relationships(source_supplier_id);

CREATE INDEX IF NOT EXISTS idx_supplier_relationship_target
ON supplier_relationships(target_supplier_id);

CREATE INDEX IF NOT EXISTS idx_scenarios_company
ON scenarios(company_id);

CREATE INDEX IF NOT EXISTS idx_scenario_results_scenario
ON scenario_results(scenario_id);

CREATE INDEX IF NOT EXISTS idx_decision_matrices_company
ON decision_matrices(company_id);

CREATE INDEX IF NOT EXISTS idx_decision_criteria_matrix
ON decision_criteria(matrix_id);

CREATE INDEX IF NOT EXISTS idx_decision_options_matrix
ON decision_options(matrix_id);

CREATE INDEX IF NOT EXISTS idx_decision_scores_option
ON decision_scores(option_id);

CREATE INDEX IF NOT EXISTS idx_evidence_entity
ON evidence(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user
ON audit_logs(user_id);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created
ON audit_logs(created_at);


-- =========================================================
-- END OF STRATEGYSIM DATABASE SCHEMA
-- =========================================================
