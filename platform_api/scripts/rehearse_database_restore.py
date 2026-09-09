"""Yedeği yalnız geçici bir PostgreSQL veritabanına geri yükleyerek sınar.

Gerçek merkezi veritabanına asla geri yükleme yapmaz. Bu araç, yalnız açık
``--allow-restore-rehearsal`` onayıyla rastgele adlandırılmış bir deneme
veritabanı oluşturur, yedeği oraya açar, şemayı doğrular ve kendi oluşturduğu
deneme veritabanını siler.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import subprocess

import psycopg
from psycopg import sql

try:  # Script olarak ve testte modül olarak güvenle kullanılabilir.
    from scripts.database_backup import binary, database_target
    from scripts.verify_database_backup import verify
except ModuleNotFoundError:  # python scripts/rehearse_database_restore.py
    from database_backup import binary, database_target
    from verify_database_backup import verify


RESTORE_DATABASE_PREFIX = "carpan_restore_check_"


def rehearsal_database_name() -> str:
    """Kullanıcı veritabanlarıyla çakışmayacak, denetlenebilir geçici ad."""
    return f"{RESTORE_DATABASE_PREFIX}{secrets.token_hex(8)}"


def restore_rehearsal(*, owner_url: str, pg_bin: Path, backup_path: Path) -> list[str]:
    """Yedeği geçici veritabanında sınar; sonuç ne olursa olsun onu kaldırır."""
    verify(backup_path=backup_path, pg_bin=pg_bin)
    target = database_target(owner_url)
    temporary_database = rehearsal_database_name()
    environment = os.environ.copy()
    environment["PGPASSWORD"] = target.password
    maintenance_connection = psycopg.connect(
        host=target.host,
        port=target.port,
        dbname="postgres",
        user=target.user,
        password=target.password,
        autocommit=True,
        connect_timeout=10,
    )
    try:
        maintenance_connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(temporary_database))
        )
        command = [
            str(binary(pg_bin, "pg_restore")), "--exit-on-error", "--no-owner", "--no-acl",
            "--host", target.host, "--port", target.port, "--username", target.user,
            "--dbname", temporary_database, str(backup_path),
        ]
        subprocess.run(command, env=environment, check=True, timeout=300, capture_output=True)
        with psycopg.connect(
            host=target.host, port=target.port, dbname=temporary_database,
            user=target.user, password=target.password, connect_timeout=10,
        ) as connection:
            rows = connection.execute(
                "SELECT version FROM carpan.schema_migrations ORDER BY version"
            ).fetchall()
            connection.execute("SELECT 1 FROM carpan.companies LIMIT 1")
        return [str(row[0]) for row in rows]
    finally:
        try:
            maintenance_connection.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(temporary_database))
            )
        finally:
            maintenance_connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True, help="pg_restore bulunan PostgreSQL bin klasörü")
    parser.add_argument("--backup", type=Path, required=True, help="Sınanacak .dump dosyası")
    parser.add_argument(
        "--allow-restore-rehearsal", action="store_true",
        help="Yalnız geçici deneme veritabanına geri yükleme yapılmasına açık onay verir.",
    )
    arguments = parser.parse_args()
    if not arguments.allow_restore_rehearsal:
        raise SystemExit("Geri yükleme tatbikatı için --allow-restore-rehearsal açıkça verilmelidir.")
    owner_url = os.getenv("CARPAN_OWNER_DATABASE_URL")
    if not owner_url:
        raise SystemExit("CARPAN_OWNER_DATABASE_URL tanımlı değil; tatbikat yapılmadı.")
    try:
        versions = restore_rehearsal(
            owner_url=owner_url,
            pg_bin=arguments.pg_bin.resolve(strict=True),
            backup_path=arguments.backup.resolve(strict=True),
        )
    except (OSError, ValueError, psycopg.Error, subprocess.SubprocessError) as error:
        raise SystemExit(f"Geri yükleme tatbikatı başarısız: {error}") from None
    print(f"Geri yükleme tatbikatı başarılı: {len(versions)} migrasyon doğrulandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
