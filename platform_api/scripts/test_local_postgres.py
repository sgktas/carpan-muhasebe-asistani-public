"""Start a private, password-protected PostgreSQL cluster for tests, then stop it.

No Windows service, firewall change, production connection or customer data.
Pass a trusted PostgreSQL bin directory; this script never downloads executables.
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

from psycopg.conninfo import make_conninfo


ROOT = Path(__file__).resolve().parents[2]


def executable_path(path: Path) -> str:
    # PostgreSQL's Windows bootstrap can misread non-ASCII installation paths.
    if os.name == "nt":
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
        if length and length < len(buffer):
            return buffer.value
    return str(path)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", required=True, type=Path)
    parser.add_argument("--all", action="store_true", help="Run the entire application suite as well.")
    args = parser.parse_args()
    binary_root = args.bin.resolve(strict=True)
    suffix = ".exe" if os.name == "nt" else ""
    initdb = binary_root / ("initdb" + suffix)
    pg_ctl = binary_root / ("pg_ctl" + suffix)
    if not initdb.is_file() or not pg_ctl.is_file():
        parser.error("The bin directory must contain initdb and pg_ctl.")
    run = Path(tempfile.mkdtemp(prefix="carpan-pg-test-"))
    data = run / "cluster"
    password_file = run / "bootstrap-password.tmp"
    password = secrets.token_urlsafe(40)
    password_file.write_text(password + "\n", encoding="utf-8")
    if os.name != "nt":
        password_file.chmod(0o600)
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG") and not k.startswith("CARPAN_DATABASE")}
    env["PYTHONIOENCODING"] = "utf-8"
    hidden = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    start_attempted = False
    try:
        with (run / "initialization.log").open("wb") as log:
            subprocess.run([executable_path(initdb), "-D", str(data), "-U", "carpan_test_admin",
                            "-A", "scram-sha-256", "--pwfile", str(password_file),
                            "--encoding=UTF8", "--locale=C"],
                           env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60, **hidden)
        password_file.unlink()
        start_attempted = True
        subprocess.run([executable_path(pg_ctl), "-D", str(data), "-l", str(run / "server.log"),
                        "-o", f"-h 127.0.0.1 -p {port} -c max_connections=30 -c shared_buffers=32MB",
                        "-w", "-t", "30", "start"], env=env, check=True, timeout=45, **hidden)
        env["CARPAN_TEST_PG_ADMIN_DSN"] = make_conninfo(
            host="127.0.0.1", port=str(port), dbname="postgres", user="carpan_test_admin",
            password=password, connect_timeout=5, sslmode="disable",
        )
        env["CARPAN_TEST_REQUIRE_POSTGRES"] = "1"
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG"] = "1"
        tests = [] if args.all else ["platform_api/tests/postgres"]
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests, "-p", "no:cacheprovider",
                                 "--basetemp", str(run / "pytest")], cwd=ROOT, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300, **hidden)
        print(result.stdout.decode("utf-8", errors="replace"))
        return result.returncode
    finally:
        password_file.unlink(missing_ok=True)
        if start_attempted:
            # Only this freshly-created cluster can be stopped here.
            subprocess.run([executable_path(pg_ctl), "-D", str(data), "-w", "-t", "30", "-m", "fast", "stop"],
                           env=env, check=True, timeout=45, **hidden)
        print(f"Test logs (local only): {run}")


if __name__ == "__main__":
    raise SystemExit(main())
