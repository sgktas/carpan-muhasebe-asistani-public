"""Merkezi PostgreSQL veritabanının parolasız komut satırı güvenliğiyle yedeğini alır.

Yalnız ``CARPAN_OWNER_DATABASE_URL`` kullanılır. Bağlantı parolası pg_dump
komut satırına yazılmaz, yalnız alt sürecin geçici ortam değişkeninde kalır.
Bu araç silme veya geri yükleme yapmaz.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import psycopg
from psycopg.conninfo import conninfo_to_dict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "local_data" / "carpan_platform" / "backups"


@dataclass(frozen=True)
class DatabaseTarget:
    host: str
    port: str
    database: str
    user: str
    password: str


def database_target(url: str) -> DatabaseTarget:
    values = conninfo_to_dict(str(url))
    required = {"host", "port", "dbname", "user", "password"}
    if not required.issubset(values):
        raise ValueError("Yedekleme bağlantı ayarı eksik.")
    return DatabaseTarget(
        host=str(values["host"]), port=str(values["port"]), database=str(values["dbname"]),
        user=str(values["user"]), password=str(values["password"]),
    )


def binary(pg_bin: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    path = pg_bin / f"{name}{suffix}"
    if not path.is_file():
        raise ValueError(f"PostgreSQL aracı bulunamadı: {name}")
    return path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def migration_versions(owner_url: str) -> list[str]:
    with psycopg.connect(owner_url, connect_timeout=5) as connection:
        rows = connection.execute("SELECT version FROM carpan.schema_migrations ORDER BY version").fetchall()
    return [str(row[0]) for row in rows]


def create_backup(*, owner_url: str, pg_bin: Path, output_dir: Path) -> tuple[Path, Path]:
    target = database_target(owner_url)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    backup_path = output_dir / f"carpan-platform-{timestamp}.dump"
    temporary_path = backup_path.with_suffix(".dump.tmp")
    if backup_path.exists() or temporary_path.exists():
        raise RuntimeError("Bu zaman damgasıyla zaten bir yedek var; işlem durduruldu.")
    environment = os.environ.copy()
    environment["PGPASSWORD"] = target.password
    command = [
        str(binary(pg_bin, "pg_dump")), "--format=custom", "--no-owner", "--no-acl",
        "--host", target.host, "--port", target.port, "--username", target.user,
        "--file", str(temporary_path), target.database,
    ]
    try:
        subprocess.run(command, env=environment, check=True, timeout=300, capture_output=True)
        os.replace(temporary_path, backup_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    manifest_path = backup_path.with_suffix(".json")
    manifest = {
        "format": "carpan-postgresql-backup-v1",
        "backup_file": backup_path.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sha256": file_sha256(backup_path),
        "size_bytes": backup_path.stat().st_size,
        "migration_versions": migration_versions(owner_url),
    }
    temporary_manifest = manifest_path.with_suffix(".json.tmp")
    temporary_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_manifest, manifest_path)
    return backup_path, manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True, help="pg_dump bulunan PostgreSQL bin klasörü")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_BACKUP_DIR, help="Yedek klasörü")
    arguments = parser.parse_args()
    owner_url = os.getenv("CARPAN_OWNER_DATABASE_URL")
    if not owner_url:
        raise SystemExit("CARPAN_OWNER_DATABASE_URL tanımlı değil; yedek alınmadı.")
    try:
        backup_path, manifest_path = create_backup(
            owner_url=owner_url, pg_bin=arguments.pg_bin.resolve(strict=True),
            output_dir=arguments.output_dir.resolve(),
        )
    except (OSError, ValueError, psycopg.Error, subprocess.SubprocessError, RuntimeError) as error:
        raise SystemExit(f"Yedek alınamadı: {error}") from None
    print(f"Yedek hazır: {backup_path.name}")
    print(f"Bütünlük kaydı: {manifest_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
