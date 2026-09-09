"""Çarpan PostgreSQL yedeğinin bütünlüğünü ve pg_restore tarafından okunmasını doğrular."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

try:  # Script olarak ve testte modül olarak güvenle kullanılabilir.
    from scripts.database_backup import binary, file_sha256
except ModuleNotFoundError:  # python scripts/verify_database_backup.py
    from database_backup import binary, file_sha256


def verify(*, backup_path: Path, pg_bin: Path) -> None:
    manifest_path = backup_path.with_suffix(".json")
    if not backup_path.is_file() or not manifest_path.is_file():
        raise ValueError("Yedek veya bütünlük kaydı bulunamadı.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "carpan-postgresql-backup-v1" or manifest.get("backup_file") != backup_path.name:
        raise ValueError("Yedek bütünlük kaydı bu dosyayla eşleşmiyor.")
    if manifest.get("sha256") != file_sha256(backup_path):
        raise ValueError("Yedek dosyasının bütünlük değeri değişmiş.")
    subprocess.run(
        [str(binary(pg_bin, "pg_restore")), "--list", str(backup_path)],
        check=True, timeout=120, capture_output=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True, help="pg_restore bulunan PostgreSQL bin klasörü")
    parser.add_argument("--backup", type=Path, required=True, help="Doğrulanacak .dump dosyası")
    arguments = parser.parse_args()
    try:
        verify(backup_path=arguments.backup.resolve(strict=True), pg_bin=arguments.pg_bin.resolve(strict=True))
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Yedek doğrulanamadı: {error}") from None
    print("Yedek bütünlüğü ve PostgreSQL okunabilirliği doğrulandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
