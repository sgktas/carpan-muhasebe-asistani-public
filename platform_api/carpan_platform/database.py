from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from carpan_platform.config import Settings


class DatabaseConfigurationError(RuntimeError):
    pass


def database_health(settings: Settings) -> bool:
    if not settings.database_configured:
        return False
    try:
        with psycopg.connect(
            str(settings.database_url), connect_timeout=3, autocommit=True
        ) as connection:
            connection.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False


def database_schema_ready(settings: Settings) -> bool:
    """Çalışan API'nin beklediği tüm migrasyonların uygulanmış olduğunu doğrular."""
    if not settings.database_configured:
        return False
    expected = {path.stem for path in (Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")}
    try:
        with psycopg.connect(
            str(settings.database_url), connect_timeout=3, autocommit=True
        ) as connection:
            rows = connection.execute("SELECT version FROM carpan.schema_migrations").fetchall()
        applied = {str(row[0]) for row in rows}
        return expected.issubset(applied)
    except psycopg.Error:
        return False


@contextmanager
def tenant_transaction(settings: Settings, company_id: UUID) -> Iterator[psycopg.Connection]:
    """RLS politikalarının firma kapsamını görmesini sağlar."""
    if not settings.database_configured:
        raise DatabaseConfigurationError("PostgreSQL bağlantısı yapılandırılmamış.")
    with psycopg.connect(str(settings.database_url), row_factory=dict_row) as connection:
        with connection.transaction():
            connection.execute("SELECT set_config('app.company_id', %s, true)", (str(company_id),))
            yield connection
