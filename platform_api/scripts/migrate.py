from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from carpan_platform.config import Settings


def main() -> None:
    settings = Settings.from_environment()
    if not settings.database_configured:
        raise SystemExit("CARPAN_DATABASE_URL tanımlanmadı; migrasyon uygulanmadı.")

    apply_migrations(str(settings.database_url))


def apply_migrations(database_url: str) -> None:
    """Apply the same checksum-protected migrations in deployment and tests."""

    migrations_dir = PROJECT_ROOT / "migrations"
    migration_paths = sorted(migrations_dir.glob("*.sql"))
    if not migration_paths:
        raise SystemExit("Uygulanacak migrasyon bulunamadı.")

    with psycopg.connect(database_url) as connection:
        with connection.transaction():
            connection.execute("CREATE SCHEMA IF NOT EXISTS carpan")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS carpan.schema_migrations (
                    version TEXT PRIMARY KEY,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            for path in migration_paths:
                version = path.stem
                content = path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
                existing = connection.execute(
                    "SELECT checksum FROM carpan.schema_migrations WHERE version = %s",
                    (version,),
                ).fetchone()
                if existing:
                    if str(existing[0]) != checksum:
                        raise RuntimeError(
                            f"{path.name} daha önce farklı içerikle uygulanmış; durduruldu."
                        )
                    continue
                connection.execute(content)
                connection.execute(
                    """
                    INSERT INTO carpan.schema_migrations(version, checksum)
                    VALUES (%s, %s)
                    """,
                    (version, checksum),
                )
                print(f"Uygulandı: {path.name}")


if __name__ == "__main__":
    main()
