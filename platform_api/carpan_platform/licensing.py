from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Iterable
from uuid import UUID

from carpan_platform.config import Settings
from carpan_platform.database import tenant_transaction


USABLE_LICENSE_STATUSES = frozenset({"TRIAL", "ACTIVE"})


@dataclass(frozen=True)
class LicenseSnapshot:
    plan_code: str
    status: str
    expires_at: datetime | None
    enabled_modules: tuple[str, ...]
    enforcement_required: bool = False
    offline_grace_hours: int = 168

    def is_usable(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return self.status in USABLE_LICENSE_STATUSES and (
            self.expires_at is None or self.expires_at >= current
        )


def normalize_module_entitlements(value: object) -> tuple[str, ...]:
    """Merkezi lisans verisini dar ve öngörülebilir bir sözleşmeye çevirir."""
    if not isinstance(value, list):
        return ()
    return tuple(
        sorted(
            {
                item.strip()
                for item in value
                if isinstance(item, str) and item.strip()
            }
        )
    )


def installation_hash(installation_id: str) -> str:
    """Ham cihaz bilgisi yerine, yerel kurulumun rastgele kimliğini saklar."""
    value = str(installation_id).strip()
    if len(value) < 16 or len(value) > 200:
        raise ValueError("Kurulum kimliği geçersiz.")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class LicensingRepository:
    """Lisans ve kurulum aktivasyonları için firma kapsamlı merkezi erişim."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def current_license(self, company_id: UUID) -> LicenseSnapshot | None:
        with tenant_transaction(self.settings, company_id) as connection:
            row = connection.execute(
                """
                SELECT plan_code, status, expires_at, module_entitlements,
                       enforce_central, offline_grace_hours
                FROM carpan.licenses
                WHERE company_id = %s
                ORDER BY
                    CASE status WHEN 'ACTIVE' THEN 0 WHEN 'TRIAL' THEN 1 ELSE 2 END,
                    created_at DESC
                LIMIT 1
                """,
                (company_id,),
            ).fetchone()
        if row is None:
            return None
        return LicenseSnapshot(
            plan_code=str(row["plan_code"]),
            status=str(row["status"]),
            expires_at=row["expires_at"],
            enabled_modules=normalize_module_entitlements(row["module_entitlements"]),
            enforcement_required=bool(row["enforce_central"]),
            offline_grace_hours=int(row["offline_grace_hours"]),
        )

    def activate_installation(
        self,
        *,
        company_id: UUID,
        user_id: UUID,
        installation_id: str,
        device_label: str | None,
        refresh_token_hash: str | None = None,
    ) -> None:
        """Kurulum kaydını günceller; donanım veya kişisel veri toplamaz."""
        safe_label = " ".join(str(device_label or "").split())[:160] or None
        fingerprint_hash = installation_hash(installation_id)
        with tenant_transaction(self.settings, company_id) as connection:
            row = connection.execute(
                """
                INSERT INTO carpan.device_registrations(
                    company_id, user_id, device_fingerprint_hash, device_label
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (company_id, device_fingerprint_hash)
                DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    device_label = COALESCE(EXCLUDED.device_label, carpan.device_registrations.device_label),
                    status = 'ACTIVE',
                    last_seen_at = now()
                RETURNING id
                """,
                (company_id, user_id, fingerprint_hash, safe_label),
            ).fetchone()
            # Oturum, cihaz kaydından sonra oluştuğu için ilk girişte henüz
            # bağlanmamış olur. Ham anahtarı asla saklamadan yalnız özetini
            # eşleştiririz; böylece iptal edilen cihazın yenileme oturumları da
            # anında geçersiz olur.
            if refresh_token_hash:
                connection.execute(
                    """
                    UPDATE carpan.refresh_tokens
                    SET device_registration_id = %s
                    WHERE company_id = %s AND user_id = %s
                      AND token_hash = %s AND revoked_at IS NULL
                    """,
                    (row["id"], company_id, user_id, refresh_token_hash),
                )
