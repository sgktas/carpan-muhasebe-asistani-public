CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS carpan;

CREATE TABLE IF NOT EXISTS carpan.schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS carpan.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(40) NOT NULL,
    name VARCHAR(160) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT companies_code_unique UNIQUE (code),
    CONSTRAINT companies_status_valid CHECK (status IN ('ACTIVE', 'SUSPENDED', 'ARCHIVED'))
);

CREATE TABLE IF NOT EXISTS carpan.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(80) NOT NULL,
    display_name VARCHAR(160) NOT NULL,
    password_hash TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT users_username_unique UNIQUE (username),
    CONSTRAINT users_status_valid CHECK (status IN ('ACTIVE', 'SUSPENDED', 'INVITED')),
    CONSTRAINT users_failed_attempts_valid CHECK (failed_attempts >= 0)
);

CREATE TABLE IF NOT EXISTS carpan.company_memberships (
    company_id UUID NOT NULL REFERENCES carpan.companies(id),
    user_id UUID NOT NULL REFERENCES carpan.users(id),
    role VARCHAR(30) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, user_id),
    CONSTRAINT company_memberships_role_valid CHECK (
        role IN ('ADMIN', 'OPERATOR', 'APPROVER', 'AUDITOR')
    )
);

CREATE TABLE IF NOT EXISTS carpan.licenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES carpan.companies(id),
    plan_code VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'TRIAL',
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    module_entitlements JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT licenses_status_valid CHECK (status IN ('TRIAL', 'ACTIVE', 'PAST_DUE', 'SUSPENDED', 'CANCELLED'))
);

CREATE TABLE IF NOT EXISTS carpan.device_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES carpan.companies(id),
    user_id UUID NOT NULL REFERENCES carpan.users(id),
    device_fingerprint_hash CHAR(64) NOT NULL,
    device_label VARCHAR(160),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT device_registrations_unique UNIQUE (company_id, device_fingerprint_hash),
    CONSTRAINT device_registrations_status_valid CHECK (status IN ('ACTIVE', 'REVOKED'))
);

CREATE TABLE IF NOT EXISTS carpan.refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES carpan.companies(id),
    user_id UUID NOT NULL REFERENCES carpan.users(id),
    device_registration_id UUID REFERENCES carpan.device_registrations(id),
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS carpan.audit_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES carpan.companies(id),
    actor_user_id UUID REFERENCES carpan.users(id),
    event_type VARCHAR(80) NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    previous_hash CHAR(64) NOT NULL,
    event_hash CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT audit_events_outcome_valid CHECK (outcome IN ('SUCCESS', 'FAILED', 'BLOCKED'))
);

CREATE INDEX IF NOT EXISTS idx_company_memberships_user
    ON carpan.company_memberships(user_id, active);
CREATE INDEX IF NOT EXISTS idx_licenses_company_status
    ON carpan.licenses(company_id, status);
CREATE INDEX IF NOT EXISTS idx_devices_company_user
    ON carpan.device_registrations(company_id, user_id, status);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user
    ON carpan.refresh_tokens(company_id, user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_audit_events_company_created
    ON carpan.audit_events(company_id, created_at DESC, id DESC);

ALTER TABLE carpan.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE carpan.company_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE carpan.licenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE carpan.device_registrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE carpan.refresh_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE carpan.audit_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY companies_tenant_scope ON carpan.companies
    USING (id = NULLIF(current_setting('app.company_id', true), '')::uuid)
    WITH CHECK (id = NULLIF(current_setting('app.company_id', true), '')::uuid);

CREATE POLICY memberships_tenant_scope ON carpan.company_memberships
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid)
    WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);

CREATE POLICY licenses_tenant_scope ON carpan.licenses
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid)
    WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);

CREATE POLICY devices_tenant_scope ON carpan.device_registrations
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid)
    WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);

CREATE POLICY refresh_tokens_tenant_scope ON carpan.refresh_tokens
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid)
    WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);

CREATE POLICY audit_events_tenant_scope ON carpan.audit_events
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid)
    WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);
