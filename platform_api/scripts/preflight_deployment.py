"""Çarpan merkezi API dağıtımından önce güvenli ve salt-okunur kontrol yapar."""
from __future__ import annotations

import os
import shutil
import socket
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from carpan_platform.config import Settings
from carpan_platform.database import database_schema_ready, owner_database_schema_ready


MINIMUM_SERVER_MEMORY_BYTES = 4 * 1024**3
MINIMUM_AVAILABLE_DISK_BYTES = 20 * 1024**3


def server_capacity_ready(root: Path = Path("/")) -> tuple[bool, str]:
    """Return a safe, secret-free readiness result for a Linux VPS.

    The central API is intentionally not installed on undersized servers.  On
    Windows/macOS this check is not applicable because the script is commonly
    used there for local development validation.
    """

    if os.name != "posix" or not Path("/proc/meminfo").is_file():
        return True, "Yerel geliştirme ortamı: sunucu kapasitesi denetimi atlandı"

    memory_lines = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
    values: dict[str, int] = {}
    for line in memory_lines:
        key, _, raw_value = line.partition(":")
        parts = raw_value.split()
        if parts and parts[0].isdigit():
            values[key] = int(parts[0]) * 1024

    total_memory = values.get("MemTotal", 0)
    free_disk = shutil.disk_usage(root).free
    ready = total_memory >= MINIMUM_SERVER_MEMORY_BYTES and free_disk >= MINIMUM_AVAILABLE_DISK_BYTES
    return (
        ready,
        "Sunucu kapasitesi: "
        f"RAM {total_memory / 1024**3:.1f} GB (en az 4.0 GB), "
        f"boş disk {free_disk / 1024**3:.1f} GB (en az 20.0 GB)",
    )


def api_port_available(port: int = 8010) -> bool:
    """Check the local-only API port without starting a service."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def main() -> int:
    settings = Settings.from_environment()
    capacity_ready, capacity_message = server_capacity_ready()
    checks = {
        capacity_message: capacity_ready,
        "Yerel API portu 8010": api_port_available(),
        "İmzalama anahtarı": settings.token_signing_configured,
        "Veritabanı ve migrasyonlar": database_schema_ready(settings),
        "Platform sahibi bağlantısı ve migrasyonlar": owner_database_schema_ready(settings),
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
