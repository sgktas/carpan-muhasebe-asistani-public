"""Merkezi denetim zincirini değiştirmeden kontrol eder.

Komut yalnız ``CARPAN_OWNER_DATABASE_URL`` ile sunucuda çalıştırılır. Bağlantı
ve olay özetleri ekrana yazılmaz; sonuçta yalnız zincir adı, olay sayısı ve
varsa bozuk olay numarası görünür.
"""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from carpan_platform.audit_chain import verify_company_audit_chains, verify_platform_audit_chain
from carpan_platform.config import Settings


def verify_database(settings: Settings):
    """Run all chain checks with the owner connection; it never writes data."""
    if not settings.owner_database_url:
        raise RuntimeError("Platform sahibi veritabanı bağlantısı yapılandırılmadı.")
    with psycopg.connect(str(settings.owner_database_url), row_factory=dict_row) as connection:
        company_rows = connection.execute(
            """SELECT id, company_id, actor_user_id, event_type, outcome, event_data,
                      previous_hash, event_hash, created_at
                 FROM carpan.audit_events ORDER BY company_id, id"""
        ).fetchall()
        platform_rows = connection.execute(
            """SELECT id, actor_user_id, event_type, outcome, event_data,
                      previous_hash, event_hash, created_at
                 FROM carpan.platform_audit_events ORDER BY id"""
        ).fetchall()
    return (*verify_company_audit_chains(company_rows), verify_platform_audit_chain(platform_rows))


def main() -> int:
    try:
        results = verify_database(Settings.from_environment())
    except (RuntimeError, psycopg.Error) as error:
        print(f"HATA: Denetim zinciri doğrulanamadı: {error}")
        return 1
    passed = True
    for result in results:
        if result.valid:
            print(f"OK: {result.chain_name} · {result.event_count} olay · {result.message}")
            continue
        passed = False
        print(
            f"HATA: {result.chain_name} · olay #{result.invalid_event_id} · {result.message}"
        )
    if not results:
        print("OK: Doğrulanacak denetim olayı yok.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
