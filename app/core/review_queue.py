"""Durable, firm-scoped queue for MANİM records requiring human review."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from hashlib import sha256
import sqlite3
from uuid import uuid4


class ReviewQueueError(RuntimeError):
    """A review item cannot be changed in its current state."""


@dataclass(frozen=True)
class ReviewMember:
    source_file: str
    source_row: int
    amount: float
    region: str
    bank: str
    reason: str
    source_hash: str = ""
    sheet_name: str = ""


@dataclass(frozen=True)
class ReviewGroup:
    group_id: str
    company_id: int | None
    operation_id: int | None
    status: str
    assigned_user_id: int | None
    created_at: str
    updated_at: str
    members: tuple[ReviewMember, ...]
    version: int = 1

    @property
    def total_amount(self) -> float:
        return round(sum(item.amount for item in self.members), 2)


@dataclass(frozen=True)
class ReviewQueueEvent:
    group_id: str
    actor_user_id: int | None
    previous_status: str
    new_status: str
    previous_version: int
    new_version: int
    created_at: str
    resolution_code: str | None = None


class ReviewQueue:
    """Stores pending review groups in the local operations database.

    Only safe operational metadata is retained. Customer names, IBANs, raw
    descriptions and customer codes stay in the generated review workbook.
    """

    def __init__(self, database_path: str | Path, *, company_id: int | None = None):
        self.database_path = Path(database_path)
        self.company_id = company_id
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _connection(self):
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_queue_groups (
                    group_id TEXT PRIMARY KEY,
                    company_id INTEGER,
                    operation_id INTEGER,
                    status TEXT NOT NULL CHECK(status IN ('OPEN','ASSIGNED','RESOLVED','CANCELLED')),
                    assigned_user_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolution_code TEXT,
                    version INTEGER NOT NULL DEFAULT 1 CHECK(version > 0),
                    UNIQUE(company_id, operation_id, group_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_queue_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id TEXT NOT NULL REFERENCES review_queue_groups(group_id) ON DELETE CASCADE,
                    source_file TEXT NOT NULL,
                    source_row INTEGER NOT NULL CHECK(source_row > 0),
                    amount REAL NOT NULL,
                    region TEXT NOT NULL,
                    bank TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    source_hash TEXT NOT NULL DEFAULT '',
                    sheet_name TEXT NOT NULL DEFAULT ''
                )
                """
            )
            # Eski yerel kuyruklar korunur; yeni kimlik alanları boş ise
            # kullanıcı kaynak doğrulamasını tekrar yapmalıdır.
            self._add_column_if_missing(connection, "review_queue_groups", "version", "INTEGER NOT NULL DEFAULT 1")
            self._add_column_if_missing(connection, "review_queue_members", "source_hash", "TEXT NOT NULL DEFAULT ''")
            self._add_column_if_missing(connection, "review_queue_members", "sheet_name", "TEXT NOT NULL DEFAULT ''")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_queue_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id TEXT NOT NULL REFERENCES review_queue_groups(group_id) ON DELETE CASCADE,
                    company_id INTEGER,
                    actor_user_id INTEGER,
                    previous_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    previous_version INTEGER NOT NULL,
                    new_version INTEGER NOT NULL,
                    resolution_code TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_queue_scope ON review_queue_groups(company_id, status, updated_at DESC)"
            )

    def enqueue(
        self,
        members: list[ReviewMember],
        *,
        operation_id: int | None = None,
        group_id: str | None = None,
    ) -> str | None:
        if not members:
            return None
        normalized = tuple(self._normalize_member(item) for item in members)
        group_id = group_id or uuid4().hex
        now = self._now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO review_queue_groups
                   (group_id, company_id, operation_id, status, created_at, updated_at, version)
                   VALUES (?, ?, ?, 'OPEN', ?, ?, 1)""",
                (group_id, self.company_id, operation_id, now, now),
            )
            connection.executemany(
                """INSERT INTO review_queue_members
                   (group_id, source_file, source_row, amount, region, bank, reason, source_hash, sheet_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(group_id, item.source_file, item.source_row, item.amount, item.region, item.bank, item.reason,
                  item.source_hash, item.sheet_name)
                 for item in normalized],
            )
            self._add_event(connection, group_id, None, "", "OPEN", 0, 1, None, now)
        return group_id

    def list(self, *, status: str | None = "OPEN", limit: int = 200) -> list[ReviewGroup]:
        clauses = ["company_id IS ?"]
        parameters: list[object] = [self.company_id]
        if status is not None:
            clauses.append("status = ?")
            parameters.append(str(status).upper())
        parameters.append(max(1, int(limit)))
        with self._connection() as connection:
            groups = connection.execute(
                f"SELECT * FROM review_queue_groups WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?",
                parameters,
            ).fetchall()
            return [self._hydrate(connection, row) for row in groups]

    def assign(self, group_id: str, user_id: int, *, expected_version: int | None = None) -> None:
        self._transition(group_id, from_status=("OPEN", "ASSIGNED"), to_status="ASSIGNED", user_id=user_id,
                         expected_version=expected_version)

    def resolve(self, group_id: str, *, user_id: int, resolution_code: str, expected_version: int | None = None) -> None:
        code = str(resolution_code).strip().upper()
        if not code or len(code) > 60:
            raise ValueError("İnceleme sonucu zorunlu ve kısa bir kod olmalıdır.")
        self._transition(group_id, from_status=("OPEN", "ASSIGNED"), to_status="RESOLVED", user_id=user_id,
                         resolution_code=code, expected_version=expected_version)

    def reopen(self, group_id: str, *, user_id: int, expected_version: int | None = None) -> None:
        self._transition(group_id, from_status=("RESOLVED", "CANCELLED"), to_status="OPEN", user_id=user_id,
                         resolution_code=None, expected_version=expected_version)

    def _transition(self, group_id: str, *, from_status: tuple[str, ...], to_status: str,
                    user_id: int, resolution_code: str | None = None, expected_version: int | None = None) -> None:
        now = self._now()
        placeholders = ",".join("?" for _ in from_status)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            managed = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_workflow_state'").fetchone()
            if managed:
                raise ReviewQueueError("Görev değişiklikleri yetkili ekip iş akışından yapılmalıdır.")
            row = connection.execute(
                f"SELECT status, version FROM review_queue_groups WHERE group_id = ? AND company_id IS ? AND status IN ({placeholders})",
                (group_id, self.company_id, *from_status),
            ).fetchone()
            if row is None:
                raise ReviewQueueError("İnceleme kaydı güncel değil veya başka firma kapsamındadır.")
            previous_version = int(row["version"])
            if expected_version is not None and int(expected_version) != previous_version:
                raise ReviewQueueError("İnceleme kaydı başka bir kullanıcı tarafından güncellendi; ekranı yenileyin.")
            cursor = connection.execute(
                f"UPDATE review_queue_groups SET status = ?, assigned_user_id = ?, resolution_code = ?, updated_at = ?, version = version + 1 WHERE group_id = ? AND company_id IS ? AND status IN ({placeholders}) AND version = ?",
                (to_status, int(user_id), resolution_code, now, group_id, self.company_id, *from_status, previous_version),
            )
            if cursor.rowcount != 1:
                raise ReviewQueueError("İnceleme kaydı başka bir kullanıcı tarafından güncellendi; ekranı yenileyin.")
            self._add_event(connection, group_id, user_id, str(row["status"]), to_status,
                            previous_version, previous_version + 1, resolution_code, now)

    def _hydrate(self, connection: sqlite3.Connection, row: sqlite3.Row) -> ReviewGroup:
        members = connection.execute(
            "SELECT source_file, source_row, amount, region, bank, reason, source_hash, sheet_name FROM review_queue_members WHERE group_id = ? ORDER BY id",
            (row["group_id"],),
        ).fetchall()
        return ReviewGroup(
            group_id=str(row["group_id"]), company_id=row["company_id"], operation_id=row["operation_id"],
            status=str(row["status"]), assigned_user_id=row["assigned_user_id"],
            created_at=str(row["created_at"]), updated_at=str(row["updated_at"]),
            members=tuple(ReviewMember(str(item["source_file"]), int(item["source_row"]), round(float(item["amount"]), 2),
                                       str(item["region"]), str(item["bank"]), str(item["reason"]),
                                       str(item["source_hash"]), str(item["sheet_name"])) for item in members),
            version=int(row["version"]),
        )

    @staticmethod
    def _normalize_member(item: ReviewMember) -> ReviewMember:
        return ReviewMember(str(item.source_file), int(item.source_row), round(float(item.amount), 2),
                            str(item.region).strip().upper(), str(item.bank).strip().upper(), str(item.reason).strip()[:240],
                            str(item.source_hash).strip().lower(), str(item.sheet_name).strip()[:120])

    def source_integrity(self, group: ReviewGroup, source_files: dict[str, str | Path]) -> tuple[bool, str]:
        """Validate the source identities supplied by the user without reading Excel content."""
        for member in group.members:
            if not member.source_hash or not member.sheet_name:
                return False, "Bu eski inceleme kaydında kaynak kimliği yok; dosyayı yeniden değerlendirmeniz gerekir."
            candidate = source_files.get(member.source_file)
            if candidate is None or not Path(candidate).is_file():
                return False, f"Kaynak dosya bulunamadı: {member.source_file}"
            if self.file_hash(candidate) != member.source_hash:
                return False, f"Kaynak dosya değişmiş: {member.source_file}; eski inceleme kararı uygulanamaz."
        return True, "Kaynak kimlikleri doğrulandı."

    def events(self, group_id: str) -> tuple[ReviewQueueEvent, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM review_queue_events WHERE group_id = ? AND company_id IS ? ORDER BY id",
                (group_id, self.company_id),
            ).fetchall()
        return tuple(ReviewQueueEvent(str(row["group_id"]), row["actor_user_id"], str(row["previous_status"]),
                                      str(row["new_status"]), int(row["previous_version"]), int(row["new_version"]),
                                      str(row["created_at"]), row["resolution_code"]) for row in rows)

    @staticmethod
    def file_hash(path: str | Path) -> str:
        digest = sha256()
        with Path(path).open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _add_column_if_missing(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _add_event(self, connection: sqlite3.Connection, group_id: str, actor_user_id: int | None,
                   previous_status: str, new_status: str, previous_version: int, new_version: int,
                   resolution_code: str | None, created_at: str) -> None:
        connection.execute(
            """INSERT INTO review_queue_events
               (group_id, company_id, actor_user_id, previous_status, new_status,
                previous_version, new_version, resolution_code, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (group_id, self.company_id, actor_user_id, previous_status, new_status,
             previous_version, new_version, resolution_code, created_at),
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
