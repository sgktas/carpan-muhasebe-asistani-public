from __future__ import annotations

import json
import os
from pathlib import Path
import secrets


class InstallationIdentityStore:
    """Bu Windows kurulumunu temsil eden, kişisel veri içermeyen yerel kimlik.

    Donanım seri numarası, MAC adresi veya kullanıcı adı toplanmaz. Merkezi
    platforma yalnız bu rastgele kurulum kimliğinin sunucuda hesaplanan özeti
    gönderilir.
    """

    FILE_NAME = "installation_identity.json"

    def __init__(self, installation_data_root: str | Path):
        self.path = Path(installation_data_root) / self.FILE_NAME

    def get_or_create(self) -> str:
        current = self._read()
        if current:
            return current
        identity = secrets.token_urlsafe(32)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"installation_id": identity}, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
        return identity

    def _read(self) -> str | None:
        if not self.path.is_file():
            return None
        try:
            value = json.loads(self.path.read_text(encoding="utf-8")).get("installation_id")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        normalized = str(value or "").strip()
        return normalized if len(normalized) >= 16 else None
