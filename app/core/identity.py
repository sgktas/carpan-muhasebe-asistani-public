from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3


PASSWORD_ITERATIONS = 600_000
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15


class IdentityError(ValueError):
    pass


class AuthenticationError(IdentityError):
    pass


@dataclass(frozen=True)
class Company:
    id: int
    code: str
    name: str


@dataclass(frozen=True)
class CompanyMember:
    user_id: int
    username: str
    display_name: str
    role: str
    active: bool
    last_login_at: str | None


@dataclass(frozen=True)
class SecurityAuditEvent:
    id: int
    created_at: str
    user_id: int | None
    action: str
    outcome: str
    details: dict


@dataclass(frozen=True)
class AuthenticatedSession:
    user_id: int
    username: str
    display_name: str
    company_id: int
    company_code: str
    company_name: str
    role: str

    def can(self, permission: str) -> bool:
        allowed = ROLE_PERMISSIONS.get(self.role, frozenset())
        if "*" in allowed or permission in allowed:
            return True
        namespace = permission.split(".", 1)[0] + ".*"
        return namespace in allowed

    def allows_module(self, module_id: str) -> bool:
        return self.can(f"module.{module_id}")


ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "ADMIN": frozenset({"*"}),
    "OPERATOR": frozenset({"module.*", "history.read"}),
    "APPROVER": frozenset(
        {"module.manim_transfer", "history.read", "operations.approve"}
    ),
    "AUDITOR": frozenset({"history.read", "audit.read"}),
}


class IdentityStore:
    """Yerel firma, kullanıcı, rol ve zincirlenmiş güvenlik denetim kaydı."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            versions = {
                int(row[0])
                for row in connection.execute(
                    "SELECT version FROM schema_migrations"
                ).fetchall()
            }
            if 1 not in versions:
                self._apply_v1(connection)

    def _apply_v1(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash BLOB NOT NULL,
                password_salt BLOB NOT NULL,
                password_iterations INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
                last_login_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS company_memberships (
                company_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                PRIMARY KEY (company_id, user_id),
                FOREIGN KEY (company_id) REFERENCES companies(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS security_audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                company_id INTEGER,
                user_id INTEGER,
                action TEXT NOT NULL,
                outcome TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            );

            CREATE INDEX IF NOT EXISTS idx_memberships_user
            ON company_memberships(user_id, active);

            CREATE INDEX IF NOT EXISTS idx_security_audit_created
            ON security_audit_events(created_at, id);
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (1, ?)",
            (self._now(),),
        )

    def needs_initial_setup(self) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM users").fetchone()
        return int(row[0]) == 0

    def create_initial_admin(
        self,
        company_name: str,
        username: str,
        display_name: str,
        password: str,
    ) -> AuthenticatedSession:
        company_name = " ".join(str(company_name).split())
        username = self._normalize_username(username)
        display_name = " ".join(str(display_name).split())
        self._validate_setup(company_name, username, display_name, password)

        salt, password_hash = self._password_digest(password)
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]):
                raise IdentityError("İlk yönetici kurulumu daha önce tamamlanmış.")
            company_code = self._company_code(company_name)
            company_cursor = connection.execute(
                "INSERT INTO companies(code, name, created_at) VALUES (?, ?, ?)",
                (company_code, company_name, now),
            )
            company_id = int(company_cursor.lastrowid)
            user_cursor = connection.execute(
                """
                INSERT INTO users(
                    username, display_name, password_hash, password_salt,
                    password_iterations, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    display_name,
                    password_hash,
                    salt,
                    PASSWORD_ITERATIONS,
                    now,
                ),
            )
            user_id = int(user_cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO company_memberships(
                    company_id, user_id, role, created_at
                ) VALUES (?, ?, 'ADMIN', ?)
                """,
                (company_id, user_id, now),
            )
            self._append_audit(
                connection,
                company_id=company_id,
                user_id=user_id,
                action="INITIAL_ADMIN_CREATED",
                outcome="SUCCESS",
                details={"username": username, "role": "ADMIN"},
            )

        return AuthenticatedSession(
            user_id=user_id,
            username=username,
            display_name=display_name,
            company_id=company_id,
            company_code=company_code,
            company_name=company_name,
            role="ADMIN",
        )

    def companies(self) -> list[Company]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, code, name FROM companies WHERE active = 1 ORDER BY name"
            ).fetchall()
        return [Company(int(row["id"]), str(row["code"]), str(row["name"])) for row in rows]

    def members(self, session: AuthenticatedSession) -> list[CompanyMember]:
        self._require_admin(session)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT u.id, u.username, u.display_name, u.last_login_at,
                       m.role, u.active AS user_active, m.active AS membership_active
                FROM company_memberships m
                JOIN users u ON u.id = m.user_id
                WHERE m.company_id = ?
                ORDER BY u.display_name, u.username
                """,
                (session.company_id,),
            ).fetchall()
        return [
            CompanyMember(
                user_id=int(row["id"]),
                username=str(row["username"]),
                display_name=str(row["display_name"]),
                role=str(row["role"]),
                active=bool(row["user_active"] and row["membership_active"]),
                last_login_at=row["last_login_at"],
            )
            for row in rows
        ]

    def create_user(
        self,
        session: AuthenticatedSession,
        *,
        username: str,
        display_name: str,
        password: str,
        role: str,
    ) -> int:
        self._require_admin(session)
        username = self._normalize_username(username)
        display_name = " ".join(str(display_name).split())
        role = self._validated_role(role)
        self._validate_user(username, display_name, password)
        salt, password_hash = self._password_digest(password)
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    INSERT INTO users(
                        username, display_name, password_hash, password_salt,
                        password_iterations, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        username,
                        display_name,
                        password_hash,
                        salt,
                        PASSWORD_ITERATIONS,
                        now,
                    ),
                )
                user_id = int(cursor.lastrowid)
                connection.execute(
                    """
                    INSERT INTO company_memberships(
                        company_id, user_id, role, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (session.company_id, user_id, role, now),
                )
                self._append_audit(
                    connection,
                    company_id=session.company_id,
                    user_id=session.user_id,
                    action="USER_CREATED",
                    outcome="SUCCESS",
                    details={
                        "created_user_id": user_id,
                        "username": username,
                        "role": role,
                    },
                )
        except sqlite3.IntegrityError as error:
            raise IdentityError("Bu kullanıcı adı zaten kullanılıyor.") from error
        return user_id

    def update_member(
        self,
        session: AuthenticatedSession,
        user_id: int,
        *,
        role: str,
        active: bool,
    ) -> None:
        self._require_admin(session)
        role = self._validated_role(role)
        user_id = int(user_id)
        if user_id == session.user_id and (not active or role != "ADMIN"):
            raise IdentityError("Kendi yönetici erişiminizi kaldıramazsınız.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE company_memberships
                SET role = ?, active = ?
                WHERE company_id = ? AND user_id = ?
                """,
                (role, int(bool(active)), session.company_id, user_id),
            )
            if cursor.rowcount != 1:
                raise IdentityError("Kullanıcı bu firmaya bağlı değil.")
            self._append_audit(
                connection,
                company_id=session.company_id,
                user_id=session.user_id,
                action="USER_ACCESS_UPDATED",
                outcome="SUCCESS",
                details={"target_user_id": user_id, "role": role, "active": bool(active)},
            )

    def reset_password(
        self,
        session: AuthenticatedSession,
        user_id: int,
        new_password: str,
    ) -> None:
        self._require_admin(session)
        if len(new_password) < 10 or not any(char.isalpha() for char in new_password) or not any(
            char.isdigit() for char in new_password
        ):
            raise IdentityError("Parola en az 10 karakter, bir harf ve bir rakam içermeli.")
        user_id = int(user_id)
        salt, password_hash = self._password_digest(new_password)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            membership = connection.execute(
                """
                SELECT 1 FROM company_memberships
                WHERE company_id = ? AND user_id = ?
                """,
                (session.company_id, user_id),
            ).fetchone()
            if membership is None:
                raise IdentityError("Kullanıcı bu firmaya bağlı değil.")
            connection.execute(
                """
                UPDATE users
                SET password_hash = ?, password_salt = ?, password_iterations = ?,
                    failed_attempts = 0, locked_until = NULL
                WHERE id = ?
                """,
                (password_hash, salt, PASSWORD_ITERATIONS, user_id),
            )
            self._append_audit(
                connection,
                company_id=session.company_id,
                user_id=session.user_id,
                action="PASSWORD_RESET",
                outcome="SUCCESS",
                details={"target_user_id": user_id},
            )

    def authenticate(
        self,
        username: str,
        password: str,
        company_id: int,
    ) -> AuthenticatedSession:
        normalized_username = self._normalize_username(username)
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT
                    u.*, c.code AS company_code, c.name AS company_name,
                    c.active AS company_active, m.role, m.active AS membership_active
                FROM users u
                LEFT JOIN company_memberships m
                    ON m.user_id = u.id AND m.company_id = ?
                LEFT JOIN companies c ON c.id = m.company_id
                WHERE u.username = ?
                """,
                (int(company_id), normalized_username),
            ).fetchone()

            if row is None:
                self._append_audit(
                    connection,
                    company_id=int(company_id),
                    user_id=None,
                    action="LOGIN",
                    outcome="FAILED",
                    details={"reason": "INVALID_CREDENTIALS"},
                )
                connection.commit()
                raise AuthenticationError("Kullanıcı adı, parola veya firma hatalı.")

            user_id = int(row["id"])
            locked_until = self._parse_time(row["locked_until"])
            if locked_until and locked_until > now:
                self._append_audit(
                    connection,
                    company_id=int(company_id),
                    user_id=user_id,
                    action="LOGIN",
                    outcome="BLOCKED",
                    details={"reason": "TEMPORARILY_LOCKED"},
                )
                connection.commit()
                raise AuthenticationError(
                    "Hesap geçici olarak kilitli. Bir süre sonra yeniden deneyin."
                )

            valid_password = self._verify_password(
                password,
                bytes(row["password_salt"]),
                bytes(row["password_hash"]),
                int(row["password_iterations"]),
            )
            valid_access = all(
                (
                    bool(row["active"]),
                    bool(row["membership_active"]),
                    bool(row["company_active"]),
                    str(row["role"] or "") in ROLE_PERMISSIONS,
                )
            )
            if not valid_password or not valid_access:
                attempts = int(row["failed_attempts"] or 0) + 1
                lock_value = None
                if attempts >= MAX_FAILED_ATTEMPTS:
                    attempts = 0
                    lock_value = (now + timedelta(minutes=LOCK_MINUTES)).isoformat(
                        timespec="seconds"
                    )
                connection.execute(
                    "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (attempts, lock_value, user_id),
                )
                self._append_audit(
                    connection,
                    company_id=int(company_id),
                    user_id=user_id,
                    action="LOGIN",
                    outcome="FAILED",
                    details={"reason": "INVALID_CREDENTIALS"},
                )
                connection.commit()
                raise AuthenticationError("Kullanıcı adı, parola veya firma hatalı.")

            login_time = now.isoformat(timespec="seconds")
            connection.execute(
                """
                UPDATE users
                SET failed_attempts = 0, locked_until = NULL, last_login_at = ?
                WHERE id = ?
                """,
                (login_time, user_id),
            )
            self._append_audit(
                connection,
                company_id=int(company_id),
                user_id=user_id,
                action="LOGIN",
                outcome="SUCCESS",
                details={"role": str(row["role"])},
            )

            return AuthenticatedSession(
                user_id=user_id,
                username=str(row["username"]),
                display_name=str(row["display_name"]),
                company_id=int(company_id),
                company_code=str(row["company_code"]),
                company_name=str(row["company_name"]),
                role=str(row["role"]),
            )

    def record_logout(self, session: AuthenticatedSession) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._append_audit(
                connection,
                company_id=session.company_id,
                user_id=session.user_id,
                action="LOGOUT",
                outcome="SUCCESS",
                details={},
            )

    def audit_events(
        self,
        session: AuthenticatedSession,
        limit: int = 200,
    ) -> list[SecurityAuditEvent]:
        if not session.can("audit.read"):
            raise IdentityError("Güvenlik kayıtları için denetim yetkisi gerekli.")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, user_id, action, outcome, details_json
                FROM security_audit_events
                WHERE company_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session.company_id, max(1, int(limit))),
            ).fetchall()
        return [
            SecurityAuditEvent(
                id=int(row["id"]),
                created_at=str(row["created_at"]),
                user_id=row["user_id"],
                action=str(row["action"]),
                outcome=str(row["outcome"]),
                details=json.loads(row["details_json"] or "{}"),
            )
            for row in rows
        ]

    def audit_chain_is_valid(self) -> bool:
        previous_hash = "0" * 64
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM security_audit_events ORDER BY id"
            ).fetchall()
        for row in rows:
            if str(row["previous_hash"]) != previous_hash:
                return False
            expected = self._event_hash(
                created_at=str(row["created_at"]),
                company_id=row["company_id"],
                user_id=row["user_id"],
                action=str(row["action"]),
                outcome=str(row["outcome"]),
                details_json=str(row["details_json"]),
                previous_hash=previous_hash,
            )
            if not hmac.compare_digest(expected, str(row["event_hash"])):
                return False
            previous_hash = expected
        return True

    def _append_audit(
        self,
        connection: sqlite3.Connection,
        *,
        company_id: int | None,
        user_id: int | None,
        action: str,
        outcome: str,
        details: dict,
    ) -> None:
        previous_row = connection.execute(
            "SELECT event_hash FROM security_audit_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        previous_hash = str(previous_row[0]) if previous_row else "0" * 64
        created_at = self._now()
        details_json = json.dumps(
            details,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        event_hash = self._event_hash(
            created_at=created_at,
            company_id=company_id,
            user_id=user_id,
            action=action,
            outcome=outcome,
            details_json=details_json,
            previous_hash=previous_hash,
        )
        connection.execute(
            """
            INSERT INTO security_audit_events(
                created_at, company_id, user_id, action, outcome,
                details_json, previous_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                company_id,
                user_id,
                action,
                outcome,
                details_json,
                previous_hash,
                event_hash,
            ),
        )

    @staticmethod
    def _event_hash(**payload) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _password_digest(password: str) -> tuple[bytes, bytes]:
        salt = secrets.token_bytes(32)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PASSWORD_ITERATIONS,
        )
        return salt, digest

    @staticmethod
    def _verify_password(
        password: str,
        salt: bytes,
        expected: bytes,
        iterations: int,
    ) -> bool:
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            str(password).encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(actual, expected)

    @staticmethod
    def _validate_setup(
        company_name: str,
        username: str,
        display_name: str,
        password: str,
    ) -> None:
        if len(company_name) < 2:
            raise IdentityError("Firma adı en az 2 karakter olmalı.")
        if not re.fullmatch(r"[a-z0-9._-]{3,50}", username):
            raise IdentityError(
                "Kullanıcı adı 3-50 karakter olmalı; küçük harf, rakam, nokta, "
                "alt çizgi ve kısa çizgi kullanılabilir."
            )
        if len(display_name) < 2:
            raise IdentityError("Görünen ad en az 2 karakter olmalı.")
        if len(password) < 10:
            raise IdentityError("Parola en az 10 karakter olmalı.")
        if not any(char.isalpha() for char in password) or not any(
            char.isdigit() for char in password
        ):
            raise IdentityError("Parola en az bir harf ve bir rakam içermeli.")

    @classmethod
    def _validate_user(cls, username: str, display_name: str, password: str) -> None:
        cls._validate_setup("Firma", username, display_name, password)

    @staticmethod
    def _validated_role(role: str) -> str:
        normalized = str(role).strip().upper()
        if normalized not in ROLE_PERMISSIONS:
            raise IdentityError("Geçersiz kullanıcı rolü.")
        return normalized

    @staticmethod
    def _require_admin(session: AuthenticatedSession) -> None:
        if not session.can("users.manage"):
            raise IdentityError("Bu işlem için yönetici yetkisi gerekli.")

    @staticmethod
    def _normalize_username(value: str) -> str:
        return str(value).strip().casefold()

    @staticmethod
    def _company_code(value: str) -> str:
        normalized = str(value).upper()
        replacements = str.maketrans("ÇĞİÖŞÜ", "CGIOSU")
        normalized = normalized.translate(replacements)
        normalized = re.sub(r"[^A-Z0-9]+", "_", normalized).strip("_")
        return (normalized or "FIRMA")[:40]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _parse_time(value) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
