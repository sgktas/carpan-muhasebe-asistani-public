-- Merkezi lisans zorlaması kontrollü açılır. Varsayılan, mevcut yerel çalışma
-- akışını değiştirmez; firma bazında açıkça etkinleştirildiğinde uygulanır.
ALTER TABLE carpan.licenses
    ADD COLUMN IF NOT EXISTS enforce_central BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS offline_grace_hours INTEGER NOT NULL DEFAULT 168,
    ADD CONSTRAINT licenses_offline_grace_hours_valid
        CHECK (offline_grace_hours BETWEEN 0 AND 720);
