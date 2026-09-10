"""İlk merkezi platform sahibi hesabını, yalnız sunucu terminalinde oluşturur."""
from __future__ import annotations

import argparse
import getpass
import os
import re

import psycopg

from carpan_platform.platform_owner import PlatformOwnerRepository
from carpan_platform.security import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    arguments = parser.parse_args()
    owner_url = os.getenv("CARPAN_OWNER_DATABASE_URL")
    if not owner_url:
        raise SystemExit("CARPAN_OWNER_DATABASE_URL tanımlı değil; platform sahibi oluşturulmadı.")
    username = str(arguments.username).strip().casefold()
    display_name = " ".join(str(arguments.display_name).split())
    if not re.fullmatch(r"[a-z0-9._-]{3,80}", username) or not display_name or len(display_name) > 160:
        raise SystemExit("Kullanıcı adı veya görünen ad geçersiz.")
    password = getpass.getpass("Platform sahibi parolası: ")
    confirmation = getpass.getpass("Parola tekrar: ")
    if password != confirmation:
        raise SystemExit("Parolalar eşleşmiyor; kayıt oluşturulmadı.")
    password_hash = hash_password(password)
    with psycopg.connect(owner_url) as connection:
        with connection.transaction():
            existing = connection.execute("SELECT 1 FROM carpan.platform_operators LIMIT 1").fetchone()
            if existing:
                raise SystemExit("Platform sahibi zaten tanımlı; bu ilk-kurulum aracı durduruldu.")
            user = connection.execute(
                "INSERT INTO carpan.users(username, display_name, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (username, display_name, password_hash),
            ).fetchone()
            connection.execute("INSERT INTO carpan.platform_operators(user_id) VALUES (%s)", (user[0],))
            PlatformOwnerRepository._append_audit(
                connection,
                actor_user_id=user[0],
                event_type="PLATFORM_OPERATOR_BOOTSTRAPPED",
                outcome="SUCCESS",
            )
    print("İlk platform sahibi hesabı oluşturuldu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
