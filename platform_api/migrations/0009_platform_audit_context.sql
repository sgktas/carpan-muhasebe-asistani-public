-- Platform sahibinin firma/lisans kararlarında hedefi denetlenebilir tutar.
-- Bu tabloya müşteri, banka, IBAN, Excel veya finansal hareket verisi girmez.
ALTER TABLE carpan.platform_audit_events
    ADD COLUMN IF NOT EXISTS event_data JSONB NOT NULL DEFAULT '{}'::jsonb;
