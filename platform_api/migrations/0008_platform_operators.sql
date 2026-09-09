-- Platform sahibi, firma yöneticisinden ayrı tutulur. Bu kayıtlar yalnız
-- merkezi API'nin sahip bağlantısıyla okunur; normal firma uygulama rolüne
-- bu tablolar için izin verilmez.
CREATE TABLE IF NOT EXISTS carpan.platform_operators (
    user_id UUID PRIMARY KEY REFERENCES carpan.users(id),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS carpan.platform_audit_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_user_id UUID REFERENCES carpan.users(id),
    event_type VARCHAR(80) NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT platform_audit_events_outcome_valid CHECK (outcome IN ('SUCCESS', 'FAILED', 'BLOCKED'))
);

CREATE INDEX IF NOT EXISTS idx_platform_audit_events_created
    ON carpan.platform_audit_events(created_at DESC, id DESC);

ALTER TABLE carpan.platform_operators ENABLE ROW LEVEL SECURITY;
ALTER TABLE carpan.platform_audit_events ENABLE ROW LEVEL SECURITY;
