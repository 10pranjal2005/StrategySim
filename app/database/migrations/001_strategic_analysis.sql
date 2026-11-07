
-- =========================================================
-- STRATEGYSIM
-- MIGRATION: 001 - STRATEGIC ANALYSIS
-- PURPOSE:
--   Add SWOT, PESTLE and analytical evidence linking.
--
-- IMPORTANT:
--   1. Existing tables are not modified.
--   2. Existing records are not deleted or updated.
--   3. All new tables use CREATE TABLE IF NOT EXISTS.
--   4. Evidence links are validated by backend services.
-- =========================================================


-- =========================================================
-- 1. SWOT ASSESSMENTS
-- =========================================================

CREATE TABLE IF NOT EXISTS swot_assessments (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    company_id INTEGER NOT NULL,

    assessment_name TEXT NOT NULL,

    assessment_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    summary TEXT,

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
-- 2. SWOT FACTORS
-- =========================================================

CREATE TABLE IF NOT EXISTS swot_factors (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    assessment_id INTEGER NOT NULL,

    factor_type TEXT NOT NULL
        CHECK (
            factor_type IN (
                'Strength',
                'Weakness',
                'Opportunity',
                'Threat'
            )
        ),

    factor_name TEXT NOT NULL,

    description TEXT,

    strategic_importance INTEGER
        CHECK (
            strategic_importance IS NULL
            OR strategic_importance BETWEEN 1 AND 5
        ),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (assessment_id)
        REFERENCES swot_assessments(id)
        ON DELETE CASCADE

);


-- =========================================================
-- 3. PESTLE ASSESSMENTS
-- =========================================================

CREATE TABLE IF NOT EXISTS pestle_assessments (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    company_id INTEGER NOT NULL,

    assessment_name TEXT NOT NULL,

    assessment_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    summary TEXT,

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
-- 4. PESTLE FACTORS
-- =========================================================

CREATE TABLE IF NOT EXISTS pestle_factors (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    assessment_id INTEGER NOT NULL,

    category TEXT NOT NULL
        CHECK (
            category IN (
                'Political',
                'Economic',
                'Social',
                'Technological',
                'Legal',
                'Environmental'
            )
        ),

    factor_name TEXT NOT NULL,

    description TEXT,

    impact INTEGER NOT NULL
        CHECK (impact BETWEEN 1 AND 5),

    likelihood INTEGER NOT NULL
        CHECK (likelihood BETWEEN 1 AND 5),

    response_strategy TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (assessment_id)
        REFERENCES pestle_assessments(id)
        ON DELETE CASCADE

);


-- =========================================================
-- 5. STRATEGIC ANALYSIS EVIDENCE LINKS
-- =========================================================

CREATE TABLE IF NOT EXISTS strategic_analysis_evidence (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    evidence_id INTEGER NOT NULL,

    analysis_type TEXT NOT NULL
        CHECK (
            analysis_type IN (
                'SWOT',
                'PESTLE',
                'FIVE_FORCES',
                'VALUE_CHAIN'
            )
        ),

    analysis_record_id INTEGER NOT NULL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (evidence_id)
        REFERENCES evidence(id)
        ON DELETE CASCADE,

    UNIQUE (
        evidence_id,
        analysis_type,
        analysis_record_id
    )

);


-- =========================================================
-- 6. INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_swot_assessments_company
ON swot_assessments(company_id);


CREATE INDEX IF NOT EXISTS idx_swot_factors_assessment
ON swot_factors(assessment_id);


CREATE INDEX IF NOT EXISTS idx_swot_factors_type
ON swot_factors(factor_type);


CREATE INDEX IF NOT EXISTS idx_pestle_assessments_company
ON pestle_assessments(company_id);


CREATE INDEX IF NOT EXISTS idx_pestle_factors_assessment
ON pestle_factors(assessment_id);


CREATE INDEX IF NOT EXISTS idx_pestle_factors_category
ON pestle_factors(category);


CREATE INDEX IF NOT EXISTS idx_strategic_analysis_evidence_record
ON strategic_analysis_evidence(
    analysis_type,
    analysis_record_id
);


CREATE INDEX IF NOT EXISTS idx_strategic_analysis_evidence_evidence
ON strategic_analysis_evidence(evidence_id);


-- =========================================================
-- END OF MIGRATION 001
-- =========================================================
