from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from app.core.platform_connection import PlatformLicense


@dataclass(frozen=True)
class CachedPlatformLicense:
    license: PlatformLicense
    company_id: int
    user_id: int
    api_url: str
    fetched_at: datetime


class PlatformLicenseStore:
    """Merkezi lisans metadata'sını firma/kullanıcı kapsamıyla saklar."""

    FILE_NAME = "platform_license.json"

    def __init__(self, data_root: str | Path):
        self.path = Path(data_root) / self.FILE_NAME

    def save(self, license_info: PlatformLicense, *, company_id: int, user_id: int, api_url: str) -> None:
        payload = {
            "plan_code": license_info.plan_code,
            "status": license_info.status,
            "expires_at": license_info.expires_at,
            "enabled_modules": sorted(license_info.enabled_modules),
            "usable": license_info.usable,
            "company_id": int(company_id),
            "user_id": int(user_id),
            "api_url": str(api_url),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)

    def load(self, *, company_id: int, user_id: int, api_url: str) -> PlatformLicense | None:
        if not self.path.is_file():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if int(payload["company_id"]) != int(company_id) or int(payload["user_id"]) != int(user_id):
                return None
            if str(payload["api_url"]) != str(api_url):
                return None
            return PlatformLicense(
                plan_code=str(payload["plan_code"]),
                status=str(payload["status"]),
                expires_at=str(payload["expires_at"]) if payload.get("expires_at") else None,
                enabled_modules=frozenset(str(item) for item in payload.get("enabled_modules", [])),
                usable=bool(payload["usable"]),
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
