-- =============================================================================
-- V1__initial_schema.sql
-- Flyway baseline migration for ATS Backend (Java 21 / Spring Boot 3)
-- Consolidates all 33 Alembic migration scripts into a single clean baseline.
-- =============================================================================

-- ─── Helper: auto-update updated_at ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ─── Helper: generate candidate hash ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION generate_candidate_hash(
    p_name TEXT, p_email TEXT, p_phone TEXT
) RETURNS VARCHAR(64) AS $$
BEGIN
    RETURN MD5(LOWER(COALESCE(p_name, '')) || '|' ||
               LOWER(COALESCE(p_email, '')) || '|' ||
               REGEXP_REPLACE(COALESCE(p_phone, ''), '[^0-9]', '', 'g'));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================================================
-- TABLES
-- =============================================================================

-- ─── clients ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clients (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name              VARCHAR(255) NOT NULL,
    industry          VARCHAR(100),
    contact_name      VARCHAR(255),
    contact_email     VARCHAR(255),
    contact_phone     VARCHAR(50),
    address           TEXT,
    website           VARCHAR(500),
    email_domain      VARCHAR(255),
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TRIGGER update_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─── users ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email            VARCHAR(255) NOT NULL UNIQUE,
    hashed_password  VARCHAR(255) NOT NULL,
    full_name        VARCHAR(255),
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    role             VARCHAR(50)  NOT NULL DEFAULT 'client_user',
    client_id        UUID         NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    created_at       TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email     ON users(email);
CREATE INDEX idx_users_client_id ON users(client_id);

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─── password_reset_tokens ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   VARCHAR(128) NOT NULL UNIQUE,
    expires_at   TIMESTAMP    NOT NULL,
    used_at      TIMESTAMP,
    requested_ip VARCHAR(45),
    user_agent   TEXT,
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_prt_user_id    ON password_reset_tokens(user_id);
CREATE INDEX idx_prt_token_hash ON password_reset_tokens(token_hash);

-- ─── candidates ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS candidates (
    id                      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID          REFERENCES clients(id) ON DELETE CASCADE,
    name                    VARCHAR(255)  NOT NULL,
    email                   VARCHAR(255),
    phone                   VARCHAR(50),
    company                 VARCHAR(255),
    location                VARCHAR(255),
    date_of_birth           DATE,
    previous_employment     JSONB,
    key_skill               TEXT,
    resume_file_path        TEXT,
    resume_url              TEXT,
    assigned_user_id        UUID          REFERENCES users(id),
    skills                  JSONB,
    experience              JSONB,
    ctc_current             DECIMAL(12,2),
    ctc_expected            DECIMAL(12,2),
    total_experience_years  DECIMAL(5,2),
    notice_period_days      INTEGER,
    source                  VARCHAR(100)  NOT NULL DEFAULT 'MANUAL',
    linkedin_url            VARCHAR(500),
    selected_client_name    VARCHAR(255),
    status                  VARCHAR(50)   NOT NULL DEFAULT 'ACTIVE',
    is_blacklisted          BOOLEAN       NOT NULL DEFAULT FALSE,
    is_direct_interview     BOOLEAN       NOT NULL DEFAULT FALSE,
    candidate_hash          VARCHAR(64),
    remark                  TEXT,
    other_details           JSONB,
    created_at              TIMESTAMP     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP     NOT NULL DEFAULT NOW(),
    -- FSM invariant: LEFT_COMPANY implies blacklisted
    CONSTRAINT check_left_company_blacklisted
        CHECK (status != 'LEFT_COMPANY' OR is_blacklisted = TRUE)
);

CREATE INDEX idx_candidates_client_id ON candidates(client_id);
CREATE INDEX idx_candidates_hash      ON candidates(candidate_hash);
CREATE INDEX idx_candidates_email     ON candidates(email);
CREATE INDEX idx_candidates_status    ON candidates(status);

CREATE TRIGGER update_candidates_updated_at
    BEFORE UPDATE ON candidates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-generate candidate hash on insert/update
CREATE OR REPLACE FUNCTION update_candidate_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.candidate_hash = generate_candidate_hash(NEW.name, NEW.email, NEW.phone);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_candidate_hash_trigger
    BEFORE INSERT OR UPDATE ON candidates
    FOR EACH ROW EXECUTE FUNCTION update_candidate_hash();

-- ─── jobs ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    id                   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id            UUID          NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    title                VARCHAR(255)  NOT NULL,
    company_name         VARCHAR(255)  NOT NULL,
    posting_date         DATE          NOT NULL DEFAULT CURRENT_DATE,
    closing_date         DATE,
    requirements         TEXT,
    department           VARCHAR(255),
    employment_type      VARCHAR(50)   NOT NULL DEFAULT 'FULL_TIME',
    experience_required  INTEGER,
    salary_lpa           NUMERIC(10,2),
    location             VARCHAR(255),
    openings_count       INTEGER       NOT NULL DEFAULT 1,
    status               VARCHAR(50)   NOT NULL DEFAULT 'OPEN',
    vacant               BOOLEAN       NOT NULL DEFAULT TRUE,
    submitted_by_client  BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMP     NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_jobs_client_id ON jobs(client_id);
CREATE INDEX idx_jobs_status    ON jobs(status);
CREATE INDEX idx_jobs_title     ON jobs(title);

CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─── applications ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS applications (
    id                           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id                    UUID         NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    candidate_id                 UUID         NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    job_id                       UUID         REFERENCES jobs(id),
    job_title                    VARCHAR(255),
    application_date             TIMESTAMP    NOT NULL DEFAULT NOW(),
    source                       VARCHAR(100) NOT NULL DEFAULT 'MANUAL',
    status                       VARCHAR(50)  NOT NULL DEFAULT 'RECEIVED',
    status_updated_at            TIMESTAMP    NOT NULL DEFAULT NOW(),
    flagged_for_review           BOOLEAN      NOT NULL DEFAULT FALSE,
    flag_reason                  TEXT,
    notes                        TEXT,
    applied_by_user_id           UUID         REFERENCES users(id),
    hr_interview_acknowledged    BOOLEAN      NOT NULL DEFAULT FALSE,
    hr_interview_acknowledged_at TIMESTAMP,
    hr_interview_acknowledged_by UUID         REFERENCES users(id),
    hr_interview_ack_note        TEXT,
    deleted_at                   TIMESTAMP,
    created_at                   TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at                   TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_applications_client_id    ON applications(client_id);
CREATE INDEX idx_applications_candidate_id ON applications(candidate_id);
CREATE INDEX idx_applications_job_id       ON applications(job_id);
CREATE INDEX idx_applications_status       ON applications(status);
CREATE INDEX idx_applications_deleted_at   ON applications(deleted_at);

CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Single HIRED application per job constraint (Alembic ab12cd34ef56)
CREATE OR REPLACE FUNCTION enforce_single_hired_per_job()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'HIRED' AND NEW.job_id IS NOT NULL AND NEW.deleted_at IS NULL THEN
        IF EXISTS (
            SELECT 1 FROM applications
            WHERE job_id = NEW.job_id
              AND status = 'HIRED'
              AND deleted_at IS NULL
              AND id != NEW.id
        ) THEN
            RAISE EXCEPTION 'Job already has a hired candidate. Only one HIRED application per job is allowed.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_single_hired_per_job_trigger
    BEFORE INSERT OR UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION enforce_single_hired_per_job();

-- ─── company_employees ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS company_employees (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID         NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    candidate_id    UUID         REFERENCES candidates(id),
    application_id  UUID         REFERENCES applications(id),
    name            VARCHAR(255) NOT NULL,
    email           VARCHAR(255),
    phone           VARCHAR(50),
    role            VARCHAR(255),
    department      VARCHAR(255),
    date_of_joining DATE,
    status          VARCHAR(50)  NOT NULL DEFAULT 'ACTIVE',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    notes           TEXT,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_company_employees_client_id    ON company_employees(client_id);
CREATE INDEX idx_company_employees_candidate_id ON company_employees(candidate_id);

CREATE TRIGGER update_company_employees_updated_at
    BEFORE UPDATE ON company_employees
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─── interview_records ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS interview_records (
    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id   UUID         NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    client_id      UUID         NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    company_id     UUID         NOT NULL REFERENCES clients(id),
    job_id         UUID         REFERENCES jobs(id),
    interviewer_id UUID         NOT NULL REFERENCES users(id),
    interview_date TIMESTAMP    NOT NULL,
    position       VARCHAR(255),
    skills         JSONB,
    notes          TEXT,
    rating         INTEGER      CHECK (rating BETWEEN 1 AND 5),
    deleted_at     TIMESTAMP,
    created_at     TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_interview_records_candidate_id ON interview_records(candidate_id);
CREATE INDEX idx_interview_records_client_id    ON interview_records(client_id);

CREATE TRIGGER update_interview_records_updated_at
    BEFORE UPDATE ON interview_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─── resume_jobs ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resume_jobs (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id        UUID         NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    email_message_id VARCHAR(255) UNIQUE,
    file_name        VARCHAR(255),
    file_path        TEXT,
    status           VARCHAR(50)  NOT NULL DEFAULT 'PENDING',
    error_message    TEXT,
    processed_at     TIMESTAMP,
    created_at       TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_resume_jobs_client_id ON resume_jobs(client_id);
CREATE INDEX idx_resume_jobs_status    ON resume_jobs(status);

-- ─── activity_logs ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS activity_logs (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id   UUID         REFERENCES clients(id),
    user_id     UUID         REFERENCES users(id),
    action_type VARCHAR(50)  NOT NULL,
    entity_id   UUID,
    details     JSONB,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_activity_logs_client_id   ON activity_logs(client_id);
CREATE INDEX idx_activity_logs_entity_id   ON activity_logs(entity_id);
CREATE INDEX idx_activity_logs_created_at  ON activity_logs(created_at);
CREATE INDEX idx_activity_logs_action_type ON activity_logs(action_type);

-- ─── fsm_transition_logs ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fsm_transition_logs (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID         NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    old_status   VARCHAR(50)  NOT NULL,
    new_status   VARCHAR(50)  NOT NULL,
    actor_id     UUID,
    actor_type   VARCHAR(20)  NOT NULL DEFAULT 'SYSTEM',
    reason       TEXT         NOT NULL,
    is_terminal  BOOLEAN      DEFAULT FALSE,
    client_id    UUID         NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fsm_transition_logs_candidate_id ON fsm_transition_logs(candidate_id);
CREATE INDEX idx_fsm_transition_logs_client_id    ON fsm_transition_logs(client_id);
CREATE INDEX idx_fsm_transition_logs_created_at   ON fsm_transition_logs(created_at);

-- ─── security_audit_logs ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS security_audit_logs (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         REFERENCES users(id),
    client_id   UUID         REFERENCES clients(id),
    action      VARCHAR(100) NOT NULL,
    ip_address  VARCHAR(45),
    user_agent  TEXT,
    success     BOOLEAN      NOT NULL DEFAULT TRUE,
    details     JSONB,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_security_audit_logs_user_id   ON security_audit_logs(user_id);
CREATE INDEX idx_security_audit_logs_client_id ON security_audit_logs(client_id);

-- =============================================================================
-- ROW-LEVEL SECURITY (RLS)
-- Matches Python alembic/versions/001_initial_schema_with_rls_policies.py
-- =============================================================================

-- Create role for app connections if not exists
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated_users') THEN
        CREATE ROLE authenticated_users;
    END IF;
END $$;

-- Enable RLS
ALTER TABLE candidates       ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications     ENABLE ROW LEVEL SECURITY;
ALTER TABLE resume_jobs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE fsm_transition_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_logs    ENABLE ROW LEVEL SECURITY;

-- RLS policies — isolation by current_setting('app.current_tenant_id')
CREATE POLICY client_isolation_candidates ON candidates
    FOR ALL TO authenticated_users
    USING (client_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY client_isolation_applications ON applications
    FOR ALL TO authenticated_users
    USING (client_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY client_isolation_resume_jobs ON resume_jobs
    FOR ALL TO authenticated_users
    USING (client_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY client_isolation_company_employees ON company_employees
    FOR ALL TO authenticated_users
    USING (client_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY client_isolation_interview_records ON interview_records
    FOR ALL TO authenticated_users
    USING (client_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY client_isolation_fsm_transition_logs ON fsm_transition_logs
    FOR ALL TO authenticated_users
    USING (client_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY client_isolation_activity_logs ON activity_logs
    FOR ALL TO authenticated_users
    USING (client_id = current_setting('app.current_tenant_id', true)::UUID);

-- =============================================================================
-- FSM TRIGGERS (from Alembic 004_add_fsm_invariant_enforcement.py)
-- =============================================================================

-- Validate candidate status transitions
CREATE OR REPLACE FUNCTION validate_candidate_status_transition()
RETURNS TRIGGER AS $$
BEGIN
    -- Prevent skipping JOINED when transitioning to LEFT_COMPANY from ACTIVE
    IF OLD.status = 'ACTIVE' AND NEW.status = 'LEFT_COMPANY' THEN
        IF NOT EXISTS (
            SELECT 1 FROM fsm_transition_logs
            WHERE candidate_id = NEW.id AND new_status = 'JOINED'
        ) THEN
            RAISE EXCEPTION 'Cannot transition from ACTIVE to LEFT_COMPANY without first transitioning to JOINED';
        END IF;
    END IF;

    -- Enforce terminal state
    IF OLD.status = 'LEFT_COMPANY' AND NEW.status != 'LEFT_COMPANY' THEN
        RAISE EXCEPTION 'LEFT_COMPANY is a terminal state — no further transitions allowed';
    END IF;

    -- Auto-blacklist on LEFT_COMPANY
    IF NEW.status = 'LEFT_COMPANY' THEN
        NEW.is_blacklisted = TRUE;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER candidate_status_transition_trigger
    BEFORE UPDATE ON candidates
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION validate_candidate_status_transition();

-- Log FSM transitions automatically
CREATE OR REPLACE FUNCTION log_fsm_transition()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO fsm_transition_logs (
        candidate_id, old_status, new_status,
        actor_id, actor_type, reason, is_terminal, client_id
    ) VALUES (
        NEW.id,
        OLD.status,
        NEW.status,
        NULLIF(current_setting('app.current_user_id', true), '')::UUID,
        COALESCE(current_setting('app.actor_type', true), 'SYSTEM'),
        COALESCE(current_setting('app.transition_reason', true), 'Status transition'),
        NEW.status = 'LEFT_COMPANY',
        NEW.client_id
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_fsm_transition_trigger
    AFTER UPDATE ON candidates
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION log_fsm_transition();
