"""İzole yerel Çarpan merkezi platform veritabanını ilk kez hazırlar.

Bu araç Windows hizmeti, güvenlik duvarı kuralı veya uzak bağlantı oluşturmaz.
PostgreSQL yalnız 127.0.0.1 üzerinde dinler; veriler ve gizli değerler Git
dışındaki ``local_data/carpan_platform`` alanında kalır.
"""
from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo


PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = PROJECT_ROOT / "platform_api"
DEFAULT_ROOT = PROJECT_ROOT / "local_data" / "carpan_platform"


def _executable(path: Path) -> str:
    """PostgreSQL Windows ikili yolunu Türkçe klasörlerden güvenle çağırır."""
    if os.name == "nt":
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
        if length and length < len(buffer):
            return buffer.value
    return str(path)


def _environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PG") and not key.startswith("CARPAN_DATABASE")
    }


def _available_port() -> int:
    with socket.socket() as socket_:
        socket_.bind(("127.0.0.1", 0))
        return int(socket_.getsockname()[1])


def _run(args: list[str], *, env: dict[str, str], log_path: Path | None = None) -> None:
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    if log_path is None:
        subprocess.run(args, env=env, check=True, timeout=60, **options)
        return
    with log_path.open("wb") as log:
        subprocess.run(
            args,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=60,
            **options,
        )


def _write_environment(path: Path, *, owner_url: str, app_url: str) -> None:
    secret = secrets.token_urlsafe(48)
    path.write_text(
        "# Yalnız yerel geliştirme; Git'e eklenmez.\n"
        f"CARPAN_DATABASE_URL={app_url}\n"
        f"CARPAN_OWNER_DATABASE_URL={owner_url}\n"
        f"CARPAN_JWT_SECRET={secret}\n"
        "CARPAN_JWT_ISSUER=carpan-platform-local\n"
        "CARPAN_ENVIRONMENT=development\n"
        "CARPAN_ALLOWED_ORIGINS=http://127.0.0.1:3000\n",
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)


def _apply_migrations(owner_url: str) -> None:
    if str(API_ROOT) not in sys.path:
        sys.path.insert(0, str(API_ROOT))
    from scripts.migrate import apply_migrations

    apply_migrations(owner_url)


def _grant_application_access(owner_url: str, app_role: str) -> None:
    """Uygulama rolüne yalnız RLS ile kullanılacak en dar izinleri verir."""
    with psycopg.connect(owner_url, autocommit=True) as connection:
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE carpan_platform TO {}") .format(sql.Identifier(app_role)))
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA carpan TO {}") .format(sql.Identifier(app_role)))
        for table in (
            "companies", "users", "company_memberships", "licenses",
            "device_registrations", "refresh_tokens", "audit_events", "user_invitations",
        ):
            connection.execute(sql.SQL("GRANT SELECT ON carpan.{} TO {}") .format(sql.Identifier(table), sql.Identifier(app_role)))
        connection.execute(sql.SQL("GRANT UPDATE(failed_attempts, locked_until, last_login_at) ON carpan.users TO {}") .format(sql.Identifier(app_role)))
        connection.execute(sql.SQL("GRANT UPDATE(role, active) ON carpan.company_memberships TO {}") .format(sql.Identifier(app_role)))
        connection.execute(sql.SQL("GRANT INSERT, UPDATE ON carpan.licenses, carpan.device_registrations, carpan.refresh_tokens, carpan.user_invitations TO {}") .format(sql.Identifier(app_role)))
        connection.execute(sql.SQL("GRANT INSERT ON carpan.audit_events TO {}") .format(sql.Identifier(app_role)))
        connection.execute(sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA carpan TO {}") .format(sql.Identifier(app_role)))
        connection.execute(sql.SQL("GRANT EXECUTE ON FUNCTION carpan.resolve_company_code(text), carpan.consume_refresh_token(character), carpan.rotate_refresh_token(character, character, timestamptz), carpan.accept_user_invitation(character, text) TO {}") .format(sql.Identifier(app_role)))


def initialize(bin_dir: Path, root: Path) -> None:
    suffix = ".exe" if os.name == "nt" else ""
    initdb = bin_dir / f"initdb{suffix}"
    pg_ctl = bin_dir / f"pg_ctl{suffix}"
    if not initdb.is_file() or not pg_ctl.is_file():
        raise SystemExit("PostgreSQL bin klasöründe initdb ve pg_ctl bulunamadı.")

    root = root.resolve()
    data_dir = root / "postgres-data"
    env_path = root / "platform.env"
    if data_dir.exists() or env_path.exists():
        raise SystemExit("Yerel Çarpan platformu zaten hazırlanmış. Mevcut veriye dokunulmadı.")
    root.mkdir(parents=True, exist_ok=False)
    password_handle, password_name = tempfile.mkstemp(
        prefix="carpan-local-pg-", suffix=".tmp"
    )
    # mkstemp Windows'ta dosyayı açık bırakır; initdb'den sonra silebilmek için
    # tanıtıcıyı hemen kapatıyoruz.
    os.close(password_handle)
    password_file = Path(password_name)
    admin_password = secrets.token_urlsafe(40)
    app_password = secrets.token_urlsafe(40)
    port = _available_port()
    admin_user = "carpan_local_admin"
    app_user = "carpan_local_app"
    env = _environment()
    started = False
    try:
        password_file.write_text(admin_password + "\n", encoding="utf-8")
        _run(
            [
                _executable(initdb), "-D", str(data_dir), "-U", admin_user,
                "-A", "scram-sha-256", f"--pwfile={password_file}",
                "--encoding=UTF8", "--locale=C",
            ],
            env=env,
            log_path=root / "initialization.log",
        )
        password_file.unlink(missing_ok=True)
        _run(
            [
                _executable(pg_ctl), "-D", str(data_dir), "-l", str(root / "postgres.log"),
                "-o", f"-h 127.0.0.1 -p {port} -c max_connections=30 -c shared_buffers=64MB",
                "-w", "-t", "45", "start",
            ],
            env=env,
        )
        started = True
        admin_postgres_url = make_conninfo(
            host="127.0.0.1", port=str(port), dbname="postgres", user=admin_user,
            password=admin_password, connect_timeout=5, sslmode="disable",
        )
        with psycopg.connect(admin_postgres_url, autocommit=True) as connection:
            connection.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS").format(sql.Identifier(app_user), sql.Literal(app_password)))
            connection.execute(sql.SQL("CREATE DATABASE carpan_platform OWNER {} TEMPLATE template0").format(sql.Identifier(admin_user)))
        owner_url = make_conninfo(
            host="127.0.0.1", port=str(port), dbname="carpan_platform", user=admin_user,
            password=admin_password, connect_timeout=5, sslmode="disable",
        )
        app_url = make_conninfo(
            host="127.0.0.1", port=str(port), dbname="carpan_platform", user=app_user,
            password=app_password, connect_timeout=5, sslmode="disable",
        )
        _apply_migrations(owner_url)
        _grant_application_access(owner_url, app_user)
        _write_environment(env_path, owner_url=owner_url, app_url=app_url)
        (root / "postgres.port").write_text(str(port) + "\n", encoding="ascii")
        print("Yerel Çarpan PostgreSQL altyapısı hazırlandı.")
        print("Veri klasörü: local_data/carpan_platform (Git dışı)")
        print("Sonraki adım: ilk firma/yönetici hesabını bootstrap_company.py ile oluşturun.")
    except Exception:
        raise
    finally:
        password_file.unlink(missing_ok=True)
        if not env_path.exists() and started:
            _run([_executable(pg_ctl), "-D", str(data_dir), "-w", "-t", "30", "-m", "fast", "stop"], env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True, help="PostgreSQL bin klasörü")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Yerel, Git dışı veri klasörü")
    arguments = parser.parse_args()
    initialize(arguments.bin.resolve(strict=True), arguments.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
