from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import UUID

import psycopg

from carpan_platform.config import Settings
from carpan_platform.database import DatabaseConfigurationError, tenant_transaction
from carpan_platform.security import (
    create_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)


MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15


class LoginRejected(ValueError):
    """İstemciye tek tip giriş hatası döndürmek için kullanılır."""


class CentralIdentityRepository:
    """PostgreSQL/RLS kapsamında merkezi kullanıcı giriş işlemleri."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def authenticate(
        self,
        *,
        company_code: str,
        username: str,
        password: str,
    ) -> dict:
        result = self._authenticate_and_record(
            company_code=company_code, username=username, password=password
        )
        # Reject only after the transaction commits the failed-attempt counter
        # and audit event. Unexpected storage errors must still roll back.
        if result is None:
            raise LoginRejected("Firma, kullanıcı adı veya parola hatalı.")
        return result

    def _authenticate_and_record(
        self,
        *,
        company_code: str,
        username: str,
        password: str,
    ) -> dict | None:
        company_id = self._resolve_company_id(company_code)
        normalized_username = str(username).strip().casefold()
        with tenant_transaction(self.settings, company_id) as connection:
            row = connection.execute(
                """
                SELECT
                    u.id AS user_id,
                    u.username,
                    u.display_name,
                    u.password_hash,
                    u.status AS user_status,
                    u.failed_attempts,
                    u.locked_until,
                    m.role,
                    m.active AS membership_active
                FROM carpan.company_memberships m
                JOIN carpan.users u ON u.id = m.user_id
                WHERE m.company_id = %s
                  AND lower(u.username) = %s
                FOR UPDATE OF u
                """,
                (company_id, normalized_username),
            ).fetchone()
            # Read the clock after acquiring the row lock, not before waiting.
            now = datetime.now(timezone.utc)
            if row is None:
                self._append_audit(
                    connection,
                    company_id=company_id,
                    actor_user_id=None,
                    event_type="LOGIN",
                    outcome="FAILED",
                    event_data={"reason": "INVALID_CREDENTIALS"},
                )
                return None

            user_id = UUID(str(row["user_id"]))
            locked_until = row["locked_until"]
            if locked_until and locked_until > now:
                self._append_audit(
                    connection,
                    company_id=company_id,
                    actor_user_id=user_id,
                    event_type="LOGIN",
                    outcome="BLOCKED",
                    event_data={"reason": "TEMPORARILY_LOCKED"},
                )
                return None

            valid = (
                str(row["user_status"]) == "ACTIVE"
                and bool(row["membership_active"])
                and verify_password(password, str(row["password_hash"]))
            )
            if not valid:
                attempts = int(row["failed_attempts"] or 0) + 1
                lock_until = None
                if attempts >= MAX_FAILED_ATTEMPTS:
                    attempts = 0
                    lock_until = now + timedelta(minutes=LOCK_MINUTES)
                connection.execute(
                    """
                    UPDATE carpan.users
                    SET failed_attempts = %s, locked_until = %s
                    WHERE id = %s
                    """,
                    (attempts, lock_until, user_id),
                )
                self._append_audit(
                    connection,
                    company_id=company_id,
                    actor_user_id=user_id,
                    event_type="LOGIN",
                    outcome="FAILED",
                    event_data={"reason": "INVALID_CREDENTIALS"},
                )
                return None

            connection.execute(
                """
                UPDATE carpan.users
                SET failed_attempts = 0, locked_until = NULL, last_login_at = %s
                WHERE id = %s
                """,
                (now, user_id),
            )
            self._append_audit(
                connection,
                company_id=company_id,
                actor_user_id=user_id,
                event_type="LOGIN",
                outcome="SUCCESS",
                event_data={"role": str(row["role"])},
            )
            return {
                "user_id": user_id,
                "company_id": company_id,
                "display_name": str(row["display_name"]),
                "role": str(row["role"]),
            }

    def create_refresh_session(self, *, company_id: UUID, user_id: UUID) -> str:
        """Ham belirteci yalnız istemciye döndürür; veritabanında sadece özeti kalır."""
        raw_token = create_refresh_token()
        with tenant_transaction(self.settings, company_id) as connection:
            connection.execute(
                """
                INSERT INTO carpan.refresh_tokens(company_id, user_id, token_hash, expires_at)
                VALUES (%s, %s, %s, %s)
                """,
                (company_id, user_id, hash_refresh_token(raw_token), refresh_token_expiry()),
            )
        return raw_token

    def rotate_refresh_session(self, raw_token: str) -> dict:
        """Tek kullanımlık yenileme ile eski oturumu iptal eder ve kimliği döndürür."""
        token_hash = hash_refresh_token(raw_token)
        if not self.settings.database_configured:
            raise DatabaseConfigurationError("PostgreSQL bağlantısı yapılandırılmamış.")
        with psycopg.connect(str(self.settings.database_url)) as connection:
            with connection.transaction():
                row = connection.execute(
                    "SELECT * FROM carpan.consume_refresh_token(%s)", (token_hash,)
                ).fetchone()
        if row is None:
            raise LoginRejected("Oturum yenileme belirteci geçersiz.")
        return {
            "company_id": UUID(str(row[0])),
            "user_id": UUID(str(row[1])),
            "display_name": str(row[2]),
            "role": str(row[3]),
        }

    def revoke_refresh_session(self, *, company_id: UUID, user_id: UUID, raw_token: str) -> None:
        with tenant_transaction(self.settings, company_id) as connection:
            connection.execute(
                """
                UPDATE carpan.refresh_tokens
                SET revoked_at = now()
                WHERE company_id = %s AND user_id = %s AND token_hash = %s AND revoked_at IS NULL
                """,
                (company_id, user_id, hash_refresh_token(raw_token)),
            )

    def _resolve_company_id(self, company_code: str) -> UUID:
        if not self.settings.database_configured:
            raise DatabaseConfigurationError("PostgreSQL bağlantısı yapılandırılmamış.")
        with psycopg.connect(str(self.settings.database_url)) as connection:
            row = connection.execute(
                "SELECT carpan.resolve_company_code(%s)",
                (str(company_code).strip(),),
            ).fetchone()
        if not row or row[0] is None:
            raise LoginRejected("Firma, kullanıcı adı veya parola hatalı.")
        return UUID(str(row[0]))

    @staticmethod
    def _append_audit(
        connection,
        *,
        company_id: UUID,
        actor_user_id: UUID | None,
        event_type: str,
        outcome: str,
        event_data: dict,
    ) -> None:
        connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(company_id),))
        previous = connection.execute(
            """
            SELECT event_hash
            FROM carpan.audit_events
            WHERE company_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (company_id,),
        ).fetchone()
        previous_hash = str(previous["event_hash"]) if previous else "0" * 64
        created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        data_json = json.dumps(event_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload = json.dumps(
            {
                "company_id": str(company_id),
                "actor_user_id": str(actor_user_id) if actor_user_id else None,
                "event_type": event_type,
                "outcome": outcome,
                "event_data": data_json,
                "previous_hash": previous_hash,
                "created_at": created_at,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        event_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        connection.execute(
            """
            INSERT INTO carpan.audit_events(
                company_id, actor_user_id, event_type, outcome, event_data,
                previous_hash, event_hash, created_at
            ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)
            """,
            (
                company_id,
                actor_user_id,
                event_type,
                outcome,
                data_json,
                previous_hash,
                event_hash,
                created_at,
            ),
        )
