"""Merkezi lisansın yerelde ne zaman etkili olacağını tek noktadan belirler."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.platform_connection import PlatformLicense


def central_license_access(
    license_info: PlatformLicense | None,
    *,
    now: datetime | None = None,
) -> bool | None:
    """Modül erişimi için ``True`` / ``False`` / "henüz zorlanmıyor" döndürür."""
    if license_info is None:
        return None
    if not license_info.usable:
        return False
    # Geçiş döneminde merkezi lisans bilgisi görünürdür ama yerel iş akışını
    # kesmez. Firma politikası açıkça etkinleştirildiğinde aşağıdaki süre işler.
    if not license_info.enforcement_required:
        return None
    if not license_info.fetched_at:
        return False
    try:
        checked_at = datetime.fromisoformat(license_info.fetched_at.replace("Z", "+00:00"))
        if checked_at.tzinfo is None:
            return False
    except (TypeError, ValueError):
        return False
    grace_hours = min(max(int(license_info.offline_grace_hours), 0), 720)
    return checked_at + timedelta(hours=grace_hours) >= (now or datetime.now(timezone.utc))
