"""Local, immutable configuration evidence shared by operation workflows."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import sqlite3


@dataclass(frozen=True)
class ConfigurationSnapshot:
    module_id: str
    payload_json: str

    def __post_init__(self) -> None:
        if not self.module_id or not isinstance(json.loads(self.payload_json), dict):
            raise ValueError("İşlem ayarı bir modül ve ayar nesnesi içermelidir.")

    @classmethod
    def create(cls, module_id: str, payload: dict) -> ConfigurationSnapshot:
        # Mapping order can affect region fallback order / first matching column.
        # Preserve it: reordering is allowed to create a different revision.
        return cls(module_id, json.dumps(payload, ensure_ascii=False, allow_nan=False,
                                        separators=(",", ":")))

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.payload_json.encode("utf-8")).hexdigest()

    def payload(self) -> dict:
        """Each caller receives its own copy, never the captured settings."""
        return json.loads(self.payload_json)


@dataclass(frozen=True)
class ConfigurationRevision:
    revision: int
    snapshot: ConfigurationSnapshot


def initialize_configuration_schema(connection: sqlite3.Connection) -> None:
    """Additive migration in the operation database; identity schema is separate."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS operation_schema_migrations (
            version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS operation_configuration_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_key TEXT NOT NULL,
            module_id TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision > 0),
            fingerprint TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by INTEGER,
            UNIQUE(scope_key, module_id, revision),
            UNIQUE(scope_key, module_id, fingerprint)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS operation_configurations (
            operation_id INTEGER PRIMARY KEY REFERENCES operations(id),
            version_id INTEGER NOT NULL REFERENCES operation_configuration_versions(id)
        )
    """)
    connection.execute("""
        INSERT OR IGNORE INTO operation_schema_migrations(version, applied_at)
        VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    """)


def bind_configuration(
    connection: sqlite3.Connection, *, operation_id: int,
    company_id: int | None, user_id: int | None, created_at: str,
    snapshot: ConfigurationSnapshot,
) -> ConfigurationRevision:
    """Caller owns the same write transaction as operation creation."""
    scope = f"company:{company_id}" if company_id is not None else "legacy"
    row = connection.execute("""
        SELECT id, revision, payload_json FROM operation_configuration_versions
        WHERE scope_key = ? AND module_id = ? AND fingerprint = ?
    """, (scope, snapshot.module_id, snapshot.fingerprint)).fetchone()
    if row is None:
        revision = connection.execute("""
            SELECT COALESCE(MAX(revision), 0) + 1
            FROM operation_configuration_versions WHERE scope_key = ? AND module_id = ?
        """, (scope, snapshot.module_id)).fetchone()[0]
        cursor = connection.execute("""
            INSERT INTO operation_configuration_versions
                (scope_key, module_id, revision, fingerprint, payload_json, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (scope, snapshot.module_id, revision, snapshot.fingerprint,
              snapshot.payload_json, created_at, user_id))
        version_id = cursor.lastrowid
    else:
        if row["payload_json"] != snapshot.payload_json:
            raise ValueError("Kayıtlı işlem ayarının bütünlüğü doğrulanamadı.")
        version_id, revision = row["id"], row["revision"]
    connection.execute("""
        INSERT INTO operation_configurations(operation_id, version_id) VALUES (?, ?)
    """, (operation_id, version_id))
    connection.execute("""
        INSERT INTO operation_events
            (operation_id, created_at, level, code, message, details_json)
        VALUES (?, ?, 'INFO', 'CONFIGURATION_CAPTURED', ?, ?)
    """, (operation_id, created_at, f"İşlem ayarları sürüm {revision} ile sabitlendi.",
          json.dumps({"revision": revision, "fingerprint": snapshot.fingerprint})))
    return ConfigurationRevision(revision, snapshot)
