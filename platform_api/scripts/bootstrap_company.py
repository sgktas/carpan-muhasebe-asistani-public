from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path
import re
import sys

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from carpan_platform.config import Settings
from carpan_platform.identity_repository import CentralIdentityRepository
from carpan_platform.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Çarpan merkezi platformunda ilk firma ve yönetici hesabını oluşturur."
    )
    parser.add_argument("--company-code", required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    arguments = parser.parse_args()

    settings = Settings.from_environment()
    if not settings.database_configured:
        raise SystemExit("CARPAN_DATABASE_URL tanımlanmadı.")
    company_code = _company_code(arguments.company_code)
    username = _username(arguments.username)
    password = getpass("İlk yönetici parolası: ")
    confirmation = getpass("Parolayı tekrar girin: ")
    if password != confirmation:
        raise SystemExit("Parolalar aynı değil.")
    password_hash = hash_password(password)

    # Bu komut yalnız migrasyon/veritabanı sahibi kullanıcıyla çalıştırılır.
    # Uygulama kullanıcısı RLS politikalarını devre dışı bırakamaz.
    with psycopg.connect(str(settings.database_url)) as connection:
        with connection.transaction():
            connection.execute("SET LOCAL row_security = off")
            existing = connection.execute("SELECT COUNT(*) FROM carpan.companies").fetchone()
            if int(existing[0]) > 0:
                raise SystemExit(
                    "Merkezi platformda zaten firma var. Yeni firma oluşturma yetkili yönetim akışından yapılmalı."
                )
            company = connection.execute(
                """
                INSERT INTO carpan.companies(code, name)
                VALUES (%s, %s)
                RETURNING id
                """,
                (company_code, " ".join(arguments.company_name.split())),
            ).fetchone()
            user = connection.execute(
                """
                INSERT INTO carpan.users(username, display_name, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (username, " ".join(arguments.display_name.split()), password_hash),
            ).fetchone()
            company_id, user_id = company[0], user[0]
            connection.execute(
                """
                INSERT INTO carpan.company_memberships(company_id, user_id, role)
                VALUES (%s, %s, 'ADMIN')
                """,
                (company_id, user_id),
            )
            CentralIdentityRepository._append_audit(
                connection,
                company_id=company_id,
                actor_user_id=user_id,
                event_type="INITIAL_ADMIN_CREATED",
                outcome="SUCCESS",
                event_data={"username": username, "role": "ADMIN"},
            )
    print(f"Firma oluşturuldu: {company_code}")
    print(f"İlk yönetici oluşturuldu: {username}")


def _company_code(value: str) -> str:
    code = re.sub(r"[^A-Z0-9_-]", "", str(value).upper())
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{1,39}", code):
        raise SystemExit("Firma kodu 2-40 karakter; büyük harf, rakam, _ veya - içermeli.")
    return code


def _username(value: str) -> str:
    username = str(value).strip().casefold()
    if not re.fullmatch(r"[a-z0-9._-]{3,80}", username):
        raise SystemExit("Kullanıcı adı 3-80 karakter; küçük harf, rakam, ., _ veya - içermeli.")
    return username


if __name__ == "__main__":
    main()
