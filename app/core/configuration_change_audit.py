"""Local, company-scoped audit trail for editable operating settings."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3


class ConfigurationChangeConflict(RuntimeError):
    """A different settings window has already changed the same subject."""


@dataclass(frozen=True)
class ConfigurationChange:
    id: int
    subject: str
    revision: int
    actor: str
    created_at: str
    before_fingerprint: str
    after_fingerprint: str
    before: dict
    after: dict


class ConfigurationChangeAudit:
    """Keeps editable settings history outside source templates and central API.

    The change payload belongs only to the current firm's local workspace. The
    database is not used to recreate an approved Excel template or bypass its
    integrity validation.
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        company_id: int | None,
        user_id: int | None,
        actor: str,
    ):
        self.database_path = Path(database_path)
        self.company_id = company_id
        self.user_id = user_id
        self.actor = str(actor).strip()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _connection(self):
        """Commit or roll back and always close the per-operation connection."""
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS configuration_change_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER,
                    user_id INTEGER,
                    actor TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK (revision > 0),
                    before_fingerprint TEXT NOT NULL,
                    after_fingerprint TEXT NOT NULL,
                    before_json TEXT NOT NULL,
                    after_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(company_id, subject, revision)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_configuration_change_company
                ON configuration_change_events(company_id, id DESC)
            """)

    @staticmethod
    def fingerprint(value: dict) -> str:
        return hashlib.sha256(ConfigurationChangeAudit._canonical(value).encode("utf-8")).hexdigest()

    @staticmethod
    def _canonical(value: dict) -> str:
        if not isinstance(value, dict):
            raise ValueError("Ayar kaydı bir nesne olmalıdır.")
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def latest_fingerprint(self, subject: str) -> str | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT after_fingerprint FROM configuration_change_events
                WHERE subject = ? AND ((? IS NULL AND company_id IS NULL) OR company_id = ?)
                ORDER BY id DESC LIMIT 1
                """,
                (str(subject), self.company_id, self.company_id),
            ).fetchone()
        return str(row["after_fingerprint"]) if row else None

    def record(
        self,
        subject: str,
        *,
        before: dict,
        after: dict,
        expected_fingerprint: str | None = None,
    ) -> ConfigurationChange | None:
        """Record one reversible settings change, rejecting a stale editor.

        ``expected_fingerprint`` is the last visible change state when a
        settings editor was opened. It prevents two settings windows from
        silently overwriting each other's audited decision.
        """
        normalized_subject = str(subject).strip()
        if not normalized_subject:
            raise ValueError("Ayar değişikliği için konu zorunludur.")
        before_json, after_json = self._canonical(before), self._canonical(after)
        before_fingerprint = self.fingerprint(before)
        after_fingerprint = self.fingerprint(after)
        if before_fingerprint == after_fingerprint:
            return None
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                """
                SELECT revision, after_fingerprint FROM configuration_change_events
                WHERE subject = ? AND ((? IS NULL AND company_id IS NULL) OR company_id = ?)
                ORDER BY id DESC LIMIT 1
                """,
                (normalized_subject, self.company_id, self.company_id),
            ).fetchone()
            actual = str(current["after_fingerprint"]) if current else None
            if current is not None and actual != expected_fingerprint:
                raise ConfigurationChangeConflict(
                    "Bu ayar başka bir açık pencerede değiştirildi. Ekranı yenileyip tekrar deneyin."
                )
            if current is None and expected_fingerprint is not None:
                raise ConfigurationChangeConflict(
                    "Bu ayarın önceki sürümü artık bulunamadı. Ekranı yenileyip tekrar deneyin."
                )
            revision = (int(current["revision"]) if current else 0) + 1
            cursor = connection.execute(
                """
                INSERT INTO configuration_change_events(
                    company_id, user_id, actor, subject, revision,
                    before_fingerprint, after_fingerprint, before_json, after_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.company_id, self.user_id, self.actor, normalized_subject, revision,
                    before_fingerprint, after_fingerprint, before_json, after_json, self._now(),
                ),
            )
            return ConfigurationChange(
                int(cursor.lastrowid), normalized_subject, revision, self.actor, self._now(),
                before_fingerprint, after_fingerprint, json.loads(before_json), json.loads(after_json),
            )

    def recent(self, limit: int = 50) -> list[ConfigurationChange]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM configuration_change_events
                WHERE ((? IS NULL AND company_id IS NULL) OR company_id = ?)
                ORDER BY id DESC LIMIT ?
                """,
                (self.company_id, self.company_id, max(1, int(limit))),
            ).fetchall()
        return [
            ConfigurationChange(
                id=int(row["id"]), subject=str(row["subject"]), revision=int(row["revision"]),
                actor=str(row["actor"]), created_at=str(row["created_at"]),
                before_fingerprint=str(row["before_fingerprint"]),
                after_fingerprint=str(row["after_fingerprint"]),
                before=json.loads(row["before_json"]), after=json.loads(row["after_json"]),
            )
            for row in rows
        ]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
