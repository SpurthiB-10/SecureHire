-- =====================================================================
-- SecureHire AI — PostgreSQL Schema
-- Normalized OLTP schema for users, companies, job postings, ML
-- predictions, skills, community reporting, and trust scoring.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------
-- USERS
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255),
    role            VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin', 'recruiter')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_role ON users (role);

-- ---------------------------------------------------------------------
-- COMPANIES  (registry of employers referenced by postings)
-- ---------------------------------------------------------------------
CREATE TABLE companies (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(255) NOT NULL,
    normalized_name     VARCHAR(255) NOT NULL,   -- lower/trim/std for dedup joins
    website             VARCHAR(512),
    domain              VARCHAR(255),
    domain_age_days     INTEGER,                 -- mocked/real WHOIS lookup
    industry            VARCHAR(120),
    hq_location         VARCHAR(255),
    has_verified_domain BOOLEAN NOT NULL DEFAULT FALSE,
    trust_score         NUMERIC(5,2) NOT NULL DEFAULT 50.00 CHECK (trust_score BETWEEN 0 AND 100),
    posting_count       INTEGER NOT NULL DEFAULT 0,
    fraud_report_count  INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (normalized_name)
);
CREATE INDEX idx_companies_normalized_name ON companies (normalized_name);
CREATE INDEX idx_companies_trust_score ON companies (trust_score);

-- ---------------------------------------------------------------------
-- TRUSTED_COMPANIES (admin-curated allow-list / verification registry)
-- ---------------------------------------------------------------------
CREATE TABLE trusted_companies (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    verified_by     UUID REFERENCES users(id),
    verification_note VARCHAR(512),
    verified_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id)
);

-- ---------------------------------------------------------------------
-- JOB_POSTINGS
-- ---------------------------------------------------------------------
CREATE TABLE job_postings (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submitted_by        UUID REFERENCES users(id) ON DELETE SET NULL,
    company_id          UUID REFERENCES companies(id) ON DELETE SET NULL,
    title               VARCHAR(255) NOT NULL,
    raw_text            TEXT NOT NULL,
    location             VARCHAR(255),
    normalized_location VARCHAR(255),
    employment_type     VARCHAR(50),             -- full-time / internship / contract
    salary_min          NUMERIC(12,2),
    salary_max          NUMERIC(12,2),
    salary_currency     VARCHAR(10) DEFAULT 'INR',
    contact_email       VARCHAR(255),
    source              VARCHAR(120),             -- e.g. 'user_upload', 'linkedin', 'dataset'
    source_url          VARCHAR(512),
    posted_at           TIMESTAMPTZ,
    last_updated_at     TIMESTAMPTZ,
    duplicate_of        UUID REFERENCES job_postings(id),
    text_hash           VARCHAR(64) NOT NULL,     -- sha256 for cache/duplicate lookup
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_job_postings_company ON job_postings (company_id);
CREATE INDEX idx_job_postings_text_hash ON job_postings (text_hash);
CREATE INDEX idx_job_postings_location ON job_postings (normalized_location);
CREATE INDEX idx_job_postings_created_at ON job_postings (created_at);

-- ---------------------------------------------------------------------
-- JOB_FEATURES  (engineered feature snapshot per posting, used by ML)
-- ---------------------------------------------------------------------
-- NOTE: this table is currently defined but never populated anywhere in
-- the application (the actual per-prediction feature snapshot is
-- persisted via fraud_predictions.top_features JSONB instead). Column
-- names are kept in sync with ml/feature_engineering.py's
-- RedFlagFeatures for when/if this table is wired up.
-- NOTE: this table is now genuinely populated on every /jobs/analyze
-- call (backend/app/services/analysis_service.py) — the full raw,
-- unscaled red-flag feature snapshot for that prediction. Kept 1:1 with
-- ml/feature_engineering.py's RedFlagFeatures dataclass.
CREATE TABLE job_features (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id                      UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    has_free_email_domain       BOOLEAN,
    salary_is_suspicious        BOOLEAN,
    urgent_language_score       NUMERIC(5,2),
    company_name_missing        BOOLEAN,
    experience_mismatch_score   NUMERIC(5,2),
    promo_phrase_count          INTEGER,
    skill_role_mismatch_score   NUMERIC(5,2),
    location_inconsistency      BOOLEAN,
    description_length          INTEGER,
    exclamation_count           INTEGER,
    salary_spread_ratio         NUMERIC(10,2),
    has_registration_fee_mention BOOLEAN,
    requests_informal_contact   BOOLEAN,
    tfidf_vector_ref            VARCHAR(255),     -- pointer to stored sparse vector (optional, unused today)
    embedding_ref               VARCHAR(255),     -- pointer to stored SBERT embedding (optional, unused today)
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id)
);

-- ---------------------------------------------------------------------
-- FRAUD_PREDICTIONS (model output + explainability per posting)
-- ---------------------------------------------------------------------
CREATE TABLE fraud_predictions (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id            UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    model_version     VARCHAR(50) NOT NULL,
    fraud_probability NUMERIC(5,2) NOT NULL CHECK (fraud_probability BETWEEN 0 AND 100),
    risk_category     VARCHAR(10) NOT NULL CHECK (risk_category IN ('Low', 'Medium', 'High')),
    top_features      JSONB,           -- [{feature, weight, direction}]
    confidence        NUMERIC(5,2),
    explanation_text  TEXT,
    predicted_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_fraud_predictions_job ON fraud_predictions (job_id);
CREATE INDEX idx_fraud_predictions_risk ON fraud_predictions (risk_category);

-- ---------------------------------------------------------------------
-- EXTRACTED_SKILLS
-- ---------------------------------------------------------------------
CREATE TABLE extracted_skills (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id        UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    skill_name    VARCHAR(120) NOT NULL,
    normalized_skill VARCHAR(120) NOT NULL,
    is_required   BOOLEAN NOT NULL DEFAULT TRUE,
    demand_level  VARCHAR(10) CHECK (demand_level IN ('Low', 'Medium', 'High')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_extracted_skills_job ON extracted_skills (job_id);
CREATE INDEX idx_extracted_skills_norm ON extracted_skills (normalized_skill);

-- ---------------------------------------------------------------------
-- USER_SKILLS (skill tracker for job-fit analysis)
-- ---------------------------------------------------------------------
CREATE TABLE user_skills (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_name  VARCHAR(120) NOT NULL,
    proficiency VARCHAR(20) CHECK (proficiency IN ('Beginner', 'Intermediate', 'Advanced')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, skill_name)
);

-- ---------------------------------------------------------------------
-- REPORTS (community fraud reporting)
-- ---------------------------------------------------------------------
CREATE TABLE reports (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id       UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    reported_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    reason       VARCHAR(120) NOT NULL,
    evidence_url VARCHAR(512),
    status       VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed', 'dismissed', 'confirmed')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reports_job ON reports (job_id);
CREATE INDEX idx_reports_status ON reports (status);

-- ---------------------------------------------------------------------
-- COMMENTS (discussion / evidence thread on a posting)
-- ---------------------------------------------------------------------
-- ---------------------------------------------------------------------
-- USER_SAVED_JOBS
-- ---------------------------------------------------------------------
CREATE TABLE user_saved_jobs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id      UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    saved_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, job_id)
);
CREATE INDEX idx_user_saved_jobs_user ON user_saved_jobs (user_id);

-- =====================================================================
-- Convenience view: latest prediction per job (used by dashboard/feed)
-- =====================================================================
CREATE VIEW v_job_latest_prediction AS
SELECT DISTINCT ON (jp.job_id)
    jp.job_id, jp.fraud_probability, jp.risk_category, jp.confidence, jp.predicted_at
FROM fraud_predictions jp
ORDER BY jp.job_id, jp.predicted_at DESC;

-- =====================================================================
-- WAREHOUSE / DATA ENGINEERING LAYER
-- =====================================================================
-- Architectural note: `job_postings` and `fraud_predictions` (above)
-- already ARE the primary source-of-record tables for postings and ML
-- results — there is no separate "fraud_analysis" table here, because
-- creating one would just be a duplicate of fraud_predictions with a
-- different name. Instead, the two genuinely NEW concepts this layer
-- introduces (Gemini company intelligence, and ETL pipeline run
-- tracking) get their own tables below, and `v_warehouse_job_fact`
-- (further below) is the flat, analytics-friendly denormalized view
-- that a "job_postings warehouse table" would otherwise have been.

-- ---------------------------------------------------------------------
-- COMPANY_INTELLIGENCE — Gemini-generated company verification results
-- ---------------------------------------------------------------------
CREATE TABLE company_intelligence (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id                  UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    company_summary         TEXT,
    industry                VARCHAR(120),
    headquarters            VARCHAR(255),
    website_status          VARCHAR(30),   -- e.g. 'verified', 'not_found', 'unknown', 'suspicious'
    online_presence         VARCHAR(30),   -- e.g. 'strong', 'moderate', 'weak', 'unknown'
    recruiter_email_status  VARCHAR(30),   -- e.g. 'corporate_domain', 'free_email', 'unknown'
    verification_score      NUMERIC(5,2) CHECK (verification_score BETWEEN 0 AND 100),
    key_findings            JSONB,          -- list of short finding strings
    evidence                JSONB,          -- list of {claim, source/reasoning} objects
    recommendation          TEXT,
    llm_provider            VARCHAR(50) NOT NULL DEFAULT 'gemini',
    llm_model               VARCHAR(80),
    status                  VARCHAR(20) NOT NULL DEFAULT 'ok',  -- 'ok' | 'unavailable' | 'error'
    generated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_company_intelligence_job ON company_intelligence (job_id);

-- ---------------------------------------------------------------------
-- PIPELINE_METRICS — one row per ETL pipeline run (ingest_jobs ->
-- clean_jobs -> enrich_jobs -> build_warehouse), for the Pipeline
-- Health dashboard and for reproducibility record-keeping.
-- ---------------------------------------------------------------------
CREATE TABLE pipeline_metrics (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id                      VARCHAR(64) NOT NULL UNIQUE,
    extraction_mode             VARCHAR(20) NOT NULL DEFAULT 'full',  -- 'full' | 'incremental'
    since_timestamp             TIMESTAMPTZ,  -- the --since cutoff, only set for incremental runs
    rows_ingested               INTEGER NOT NULL DEFAULT 0,   -- rows returned by ingest_jobs.py's extract query
    rows_cleaned                INTEGER NOT NULL DEFAULT 0,   -- rows after clean_jobs.py's dedup/normalize
    rows_enriched                INTEGER NOT NULL DEFAULT 0,   -- rows after enrich_jobs.py's derived-field step
    rows_loaded                  INTEGER NOT NULL DEFAULT 0,   -- rows written to the final warehouse snapshot
    duplicates_removed          INTEGER NOT NULL DEFAULT 0,
    fraud_rows_detected         INTEGER NOT NULL DEFAULT 0,
    data_quality_passed         BOOLEAN,       -- NULL if checks weren't run (shouldn't happen going forward)
    data_quality_issues         JSONB,         -- see pipelines/data_quality.py's DataQualityReport.to_dict()
    pipeline_duration_seconds   NUMERIC(10,3),
    status                      VARCHAR(20) NOT NULL DEFAULT 'success',  -- 'success' | 'failed'
    error_message               TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pipeline_metrics_created_at ON pipeline_metrics (created_at);

-- ---------------------------------------------------------------------
-- Warehouse fact view: the flat, denormalized, analytics-ready join of
-- job_postings + latest fraud_predictions + companies + latest
-- company_intelligence. This is what the dashboard's aggregation
-- endpoints query — a real "warehouse table" without duplicating data
-- that already has a source of record above.
-- ---------------------------------------------------------------------
CREATE VIEW v_warehouse_job_fact AS
SELECT
    jp.id                           AS job_id,
    jp.title,
    jp.normalized_location,
    jp.employment_type,
    jp.salary_min,
    jp.salary_max,
    jp.contact_email,
    jp.created_at                   AS job_created_at,
    c.id                            AS company_id,
    c.name                          AS company_name,
    c.trust_score                   AS company_trust_score,
    c.domain                        AS company_domain,
    fp.fraud_probability,
    fp.risk_category,
    fp.confidence                   AS fraud_confidence,
    fp.model_version,
    ci.verification_score           AS company_verification_score,
    ci.website_status,
    ci.online_presence,
    ci.recruiter_email_status,
    ci.recommendation               AS company_recommendation
FROM job_postings jp
LEFT JOIN companies c ON c.id = jp.company_id
LEFT JOIN LATERAL (
    SELECT * FROM fraud_predictions fp2
    WHERE fp2.job_id = jp.id ORDER BY fp2.predicted_at DESC LIMIT 1
) fp ON true
LEFT JOIN LATERAL (
    SELECT * FROM company_intelligence ci2
    WHERE ci2.job_id = jp.id ORDER BY ci2.generated_at DESC LIMIT 1
) ci ON true;

