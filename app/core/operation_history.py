from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterable
from uuid import uuid4


class OperationHistoryError(RuntimeError):
    """An operation cannot be changed by this company or application instance."""


class DecisionAuditError(ValueError):
    """A decision audit record is missing a required, safe field."""


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
    company_id: int | None = None
    user_id: int | None = None


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

    LEASE_SECONDS = 8 * 60 * 60

    def __init__(
        self,
        database_path: str | Path,
        actor: str = "",
        *,
        company_id: int | None = None,
        user_id: int | None = None,
        instance_id: str | None = None,
    ):
        self.database_path = Path(database_path)
        self.actor = str(actor).strip()
        self.company_id = int(company_id) if company_id is not None else None
        self.user_id = int(user_id) if user_id is not None else None
        self.instance_id = str(instance_id or uuid4())
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        if self.company_id is not None:
            self._claim_legacy_records()

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
            if "company_id" not in columns:
                connection.execute(
                    "ALTER TABLE operations ADD COLUMN company_id INTEGER"
                )
            if "user_id" not in columns:
                connection.execute("ALTER TABLE operations ADD COLUMN user_id INTEGER")
            if "owner_instance_id" not in columns:
                connection.execute("ALTER TABLE operations ADD COLUMN owner_instance_id TEXT")
            if "lease_expires_at" not in columns:
                connection.execute("ALTER TABLE operations ADD COLUMN lease_expires_at TEXT")
                # Old versions had no owner/lease. They cannot still be proven
                # live after this application version starts.
                connection.execute(
                    "UPDATE operations SET lease_expires_at = ? WHERE status = 'RUNNING'",
                    (self._now(),),
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
            self._recover_expired_operations(connection)
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
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_operations_running_lease
                ON operations(status, company_id, lease_expires_at)
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _lease_expires_at(self) -> str:
        from datetime import timedelta

        return (datetime.now(timezone.utc) + timedelta(seconds=self.LEASE_SECONDS)).isoformat(timespec="seconds")

    def _recover_expired_operations(self, connection: sqlite3.Connection) -> None:
        """Recover only operations whose owner lease is genuinely stale.

        Constructing a second history object is not evidence that another live
        process crashed, so it must never interrupt its work immediately.
        """
        clause = "status = 'RUNNING' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?"
        values: list[object] = [self._now()]
        if self.company_id is not None:
            clause += " AND company_id = ?"
            values.append(self.company_id)
        connection.execute(
            f"""
            UPDATE operations
            SET status = 'INTERRUPTED', completed_at = ?,
                error_message = COALESCE(error_message, 'Uygulama beklenmeden kapandı.')
            WHERE {clause}
            """,
            (self._now(), *values),
        )

    def _claim_legacy_records(self) -> None:
        """İlk firma kurulumunda eski firma kimliksiz geçmişi kaybetme."""
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE operations SET company_id = ?
                WHERE company_id IS NULL
                  AND NOT EXISTS (SELECT 1 FROM operations WHERE company_id IS NOT NULL)
                """,
                (self.company_id,),
            )

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
                    module_id, module_name, actor, company_id, user_id,
                    status, started_at, input_files_json, owner_instance_id, lease_expires_at
                ) VALUES (?, ?, ?, ?, ?, 'RUNNING', ?, ?, ?, ?)
                """,
                (
                    module_id,
                    module_name,
                    self.actor,
                    self.company_id,
                    self.user_id,
                    self._now(),
                    json.dumps(inputs, ensure_ascii=False),
                    self.instance_id,
                    self._lease_expires_at(),
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
        if status not in {"SUCCESS", "PARTIAL"}:
            raise OperationHistoryError("İşlem yalnız SUCCESS veya PARTIAL olarak tamamlanabilir.")
        outputs = [str(Path(path)) for path in output_files]
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE operations
                SET status = ?, completed_at = ?, output_files_json = ?,
                    summary_json = ?, error_message = NULL
                WHERE id = ? AND status = 'RUNNING' AND owner_instance_id = ?
                  AND (? IS NULL OR company_id = ?)
                """,
                (
                    status,
                    self._now(),
                    json.dumps(outputs, ensure_ascii=False),
                    json.dumps(summary or {}, ensure_ascii=False),
                    operation_id,
                    self.instance_id,
                    self.company_id,
                    self.company_id,
                ),
            )
            if cursor.rowcount != 1:
                raise OperationHistoryError("İşlem tamamlanamadı; kayıt başka firmaya, eski bir oturuma veya tamamlanmış duruma ait.")
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
            cursor = connection.execute(
                """
                UPDATE operations
                SET status = 'FAILED', completed_at = ?, error_message = ?
                WHERE id = ? AND status = 'RUNNING' AND owner_instance_id = ?
                  AND (? IS NULL OR company_id = ?)
                """,
                (self._now(), str(error_message), operation_id, self.instance_id, self.company_id, self.company_id),
            )
            if cursor.rowcount != 1:
                raise OperationHistoryError("İşlem başarısız olarak kaydedilemedi; kayıt başka firmaya, eski bir oturuma veya tamamlanmış duruma ait.")
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
            allowed = connection.execute(
                """
                SELECT 1 FROM operations
                WHERE id = ? AND status = 'RUNNING' AND owner_instance_id = ?
                  AND (? IS NULL OR company_id = ?)
                """,
                (int(operation_id), self.instance_id, self.company_id, self.company_id),
            ).fetchone()
            if allowed is None:
                raise OperationHistoryError("İşlem olayı eklenemedi; kayıt bu uygulama oturumuna ait değil.")
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

    def add_decision(
        self,
        operation_id: int,
        *,
        decision: str,
        outcome: str,
        region: str,
        bank: str,
        amount: float,
        source_file: str,
        source_row: int,
        rule_code: str,
        reason: str = "",
    ) -> None:
        """Append a normalized, immutable routing/eşleştirme karar kaydı.

        Karar günlüğü ham açıklama, IBAN veya müşteri adı taşımaz; yalnızca
        yeniden denetim için gereken kaynak satırı, tutar ve kural kimliğini
        saklar. ``add_event`` üzerinden yazıldığı için işlem sahibi/firma ve
        çalışan işlem lease kontrolleri aynen korunur.
        """
        values = {
            "decision": str(decision).strip().upper(),
            "outcome": str(outcome).strip().upper(),
            "region": str(region).strip().upper(),
            "bank": str(bank).strip().upper(),
            "rule_code": str(rule_code).strip().upper(),
            "source_file": str(source_file).strip(),
            "reason": str(reason).strip()[:240],
        }
        if not all(values[key] for key in ("decision", "outcome", "region", "rule_code", "source_file")):
            raise DecisionAuditError("Karar günlüğü için karar, sonuç, bölge, kural ve kaynak zorunludur.")
        try:
            normalized_amount = round(float(amount), 2)
            normalized_row = int(source_row)
        except (TypeError, ValueError) as error:
            raise DecisionAuditError("Karar günlüğü tutar ve satır numarası geçersiz.") from error
        if normalized_row < 1:
            raise DecisionAuditError("Kaynak satırı 1 veya daha büyük olmalıdır.")
        self.add_event(
            operation_id,
            "DECISION_AUDIT",
            f"{values['decision']} → {values['outcome']}",
            details={
                **values,
                "amount": normalized_amount,
                "source_row": normalized_row,
            },
        )

    def heartbeat(self, operation_id: int) -> None:
        """Extend a running operation's lease while its owner is still working."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE operations SET lease_expires_at = ?
                WHERE id = ? AND status = 'RUNNING' AND owner_instance_id = ?
                  AND (? IS NULL OR company_id = ?)
                """,
                (self._lease_expires_at(), int(operation_id), self.instance_id, self.company_id, self.company_id),
            )
            if cursor.rowcount != 1:
                raise OperationHistoryError("İşlem devam sinyali gönderilemedi; kayıt bu uygulama oturumuna ait değil.")

    def events(self, operation_id: int) -> list[OperationEvent]:
        with self._connect() as connection:
            if self.company_id is None:
                rows = connection.execute(
                    """
                    SELECT e.* FROM operation_events e
                    WHERE e.operation_id = ?
                    ORDER BY e.id
                    """,
                    (int(operation_id),),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT e.* FROM operation_events e
                    JOIN operations o ON o.id = e.operation_id
                    WHERE e.operation_id = ? AND o.company_id = ?
                    ORDER BY e.id
                    """,
                    (int(operation_id), self.company_id),
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
            if self.company_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM operations
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (max(1, int(limit)),),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM operations
                    WHERE company_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (self.company_id, max(1, int(limit))),
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
                    company_id=row["company_id"],
                    user_id=row["user_id"],
                )
            )
        return result
    LEASE_SECONDS = 8 * 60 * 60
