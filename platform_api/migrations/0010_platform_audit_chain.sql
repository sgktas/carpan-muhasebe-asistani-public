-- Platform sahibi denetim olayları da değişiklik fark edilebilir zincirde tutulur.
-- Olay bağlamı yalnız firma kodu/durum gibi operasyon bilgisidir; finansal veri içermez.
ALTER TABLE carpan.platform_audit_events
    ADD COLUMN IF NOT EXISTS previous_hash CHAR(64),
    ADD COLUMN IF NOT EXISTS event_hash CHAR(64);

DO $$
DECLARE
    event_row RECORD;
    last_hash TEXT := repeat('0', 64);
    current_hash TEXT;
BEGIN
    FOR event_row IN
        SELECT id, actor_user_id, event_type, outcome, event_data, created_at
        FROM carpan.platform_audit_events
        ORDER BY id
    LOOP
        current_hash := encode(digest(
            jsonb_build_object(
                'actor_user_id', event_row.actor_user_id::text,
                'created_at', event_row.created_at,
                'event_data', event_row.event_data,
                'event_type', event_row.event_type,
                'outcome', event_row.outcome,
                'previous_hash', last_hash
            )::text,
            'sha256'
        ), 'hex');
        UPDATE carpan.platform_audit_events
        SET previous_hash = last_hash, event_hash = current_hash
        WHERE id = event_row.id;
        last_hash := current_hash;
    END LOOP;
END;
$$;

ALTER TABLE carpan.platform_audit_events
    ALTER COLUMN previous_hash SET NOT NULL,
    ALTER COLUMN event_hash SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_audit_events_hash
    ON carpan.platform_audit_events(event_hash);
