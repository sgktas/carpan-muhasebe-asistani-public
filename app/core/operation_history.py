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
    status: str
    started_at: str
    completed_at: str | None
    input_files: list[str]
    output_files: list[str]
    summary: dict
    error_message: str | None


class OperationHistory:
    """Modüllerin ortak işlem geçmişi.

    Veriler kullanıcıya ait kalıcı ``data`` klasöründeki SQLite dosyasında
    saklanır. Yeni modüller aynı tabloya yalnız kendi ``module_id`` değeriyle
    kayıt bırakır.
    """

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
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
                    module_id, module_name, status, started_at, input_files_json
                ) VALUES (?, ?, 'RUNNING', ?, ?)
                """,
                (
                    module_id,
                    module_name,
                    self._now(),
                    json.dumps(inputs, ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

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
