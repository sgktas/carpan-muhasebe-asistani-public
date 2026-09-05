from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterable


@dataclass(frozen=True)
class OperationRecord:
    id: int
    module_id: str
    module_name: str
    actor: str
    status: str
    started_at: str
    completed_at: str | None
    input_files: list[str]
    output_files: list[str]
    summary: dict
    error_message: str | None


@dataclass(frozen=True)
class OperationEvent:
    id: int
    operation_id: int
    created_at: str
    level: str
    code: str
    message: str
    details: dict


class OperationHistory:
    """Modüllerin ortak işlem geçmişi.

    Veriler kullanıcıya ait kalıcı ``data`` klasöründeki SQLite dosyasında
    saklanır. Yeni modüller aynı tabloya yalnız kendi ``module_id`` değeriyle
    kayıt bırakır.
    """

    def __init__(self, database_path: str | Path, actor: str = ""):
        self.database_path = Path(database_path)
        self.actor = str(actor).strip()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_id TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    input_files_json TEXT NOT NULL DEFAULT '[]',
                    output_files_json TEXT NOT NULL DEFAULT '[]',
                    summary_json TEXT NOT NULL DEFAULT '{}',
                    error_message TEXT
                )
                """
            )
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(operations)").fetchall()
            }
            if "actor" not in columns:
                connection.execute(
                    "ALTER TABLE operations ADD COLUMN actor TEXT NOT NULL DEFAULT ''"
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS operation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    level TEXT NOT NULL,
                    code TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(operation_id) REFERENCES operations(id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_operation_events_operation
                ON operation_events(operation_id, id)
                """
            )
            # Uygulama elektrik kesintisi veya zorla kapatma nedeniyle yarım
            # kaldıysa eski RUNNING kayıtları sonsuza kadar devam ediyor
            # görünmesin.
            now = self._now()
            connection.execute(
                """
                UPDATE operations
                SET status = 'INTERRUPTED', completed_at = ?,
                    error_message = COALESCE(error_message, 'Uygulama beklenmeden kapandı.')
                WHERE status = 'RUNNING'
                """,
                (now,),
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_operations_started
                ON operations(started_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_operations_module
                ON operations(module_id, started_at DESC)
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def start(
        self,
        module_id: str,
        module_name: str,
        input_files: Iterable[str | Path],
    ) -> int:
        inputs = [str(Path(path)) for path in input_files]
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO operations (
                    module_id, module_name, actor, status, started_at, input_files_json
                ) VALUES (?, ?, ?, 'RUNNING', ?, ?)
                """,
                (
                    module_id,
                    module_name,
                    self.actor,
                    self._now(),
                    json.dumps(inputs, ensure_ascii=False),
                ),
            )
            operation_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO operation_events (
                    operation_id, created_at, level, code, message, details_json
                ) VALUES (?, ?, 'INFO', 'OPERATION_STARTED', 'İşlem başlatıldı.', '{}')
                """,
                (operation_id, self._now()),
            )
            return operation_id

    def complete(
        self,
        operation_id: int,
        output_files: Iterable[str | Path],
        summary: dict | None = None,
        status: str = "SUCCESS",
    ) -> None:
        outputs = [str(Path(path)) for path in output_files]
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE operations
                SET status = ?, completed_at = ?, output_files_json = ?,
                    summary_json = ?, error_message = NULL
                WHERE id = ?
                """,
                (
                    status,
                    self._now(),
                    json.dumps(outputs, ensure_ascii=False),
                    json.dumps(summary or {}, ensure_ascii=False),
                    operation_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO operation_events (
                    operation_id, created_at, level, code, message, details_json
                ) VALUES (?, ?, 'INFO', 'OPERATION_COMPLETED', 'İşlem tamamlandı.', ?)
                """,
                (
                    operation_id,
                    self._now(),
                    json.dumps({"status": status, "output_count": len(outputs)}, ensure_ascii=False),
                ),
            )

    def fail(self, operation_id: int, error_message: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE operations
                SET status = 'FAILED', completed_at = ?, error_message = ?
                WHERE id = ?
                """,
                (self._now(), str(error_message), operation_id),
            )
            connection.execute(
                """
                INSERT INTO operation_events (
                    operation_id, created_at, level, code, message, details_json
                ) VALUES (?, ?, 'ERROR', 'OPERATION_FAILED', ?, '{}')
                """,
                (operation_id, self._now(), str(error_message)),
            )

    def add_event(
        self,
        operation_id: int,
        code: str,
        message: str,
        *,
        level: str = "INFO",
        details: dict | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO operation_events (
                    operation_id, created_at, level, code, message, details_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(operation_id),
                    self._now(),
                    str(level).upper(),
                    str(code).strip().upper(),
                    str(message),
                    json.dumps(details or {}, ensure_ascii=False),
                ),
            )

    def events(self, operation_id: int) -> list[OperationEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM operation_events
                WHERE operation_id = ?
                ORDER BY id
                """,
                (int(operation_id),),
            ).fetchall()
        return [
            OperationEvent(
                id=int(row["id"]),
                operation_id=int(row["operation_id"]),
                created_at=str(row["created_at"]),
                level=str(row["level"]),
                code=str(row["code"]),
                message=str(row["message"]),
                details=json.loads(row["details_json"] or "{}"),
            )
            for row in rows
        ]

    def recent(self, limit: int = 100) -> list[OperationRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM operations
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()

        result: list[OperationRecord] = []
        for row in rows:
            result.append(
                OperationRecord(
                    id=int(row["id"]),
                    module_id=str(row["module_id"]),
                    module_name=str(row["module_name"]),
                    actor=str(row["actor"] or ""),
                    status=str(row["status"]),
                    started_at=str(row["started_at"]),
                    completed_at=row["completed_at"],
                    input_files=json.loads(row["input_files_json"] or "[]"),
                    output_files=json.loads(row["output_files_json"] or "[]"),
                    summary=json.loads(row["summary_json"] or "{}"),
                    error_message=row["error_message"],
                )
            )
        return result
