"""Çarpan merkezi API dağıtımından önce güvenli ve salt-okunur kontrol yapar."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from carpan_platform.config import Settings
from carpan_platform.database import database_schema_ready


def main() -> int:
    settings = Settings.from_environment()
    checks = {
        "İmzalama anahtarı": settings.token_signing_configured,
        "Veritabanı ve migrasyonlar": database_schema_ready(settings),
    }
    failed = False
    for label, passed in checks.items():
        print(f"{'OK' if passed else 'HATA'}: {label}")
        failed = failed or not passed
    if failed:
        print("Dağıtım durduruldu. Gizli değerler ekrana yazdırılmadı.")
        return 1
    print("Merkezi API dağıtıma hazır.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
