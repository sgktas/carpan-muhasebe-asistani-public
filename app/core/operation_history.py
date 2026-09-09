from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterable
from uuid import uuid4

from app.core.financial_ledger import financial_movement_from_decision
from app.core.output_evidence import build_output_evidence


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


@dataclass(frozen=True)
class FinancialMovementRecord:
    id: int
    operation_id: int
    decision: str
    outcome: str
    region: str
    bank: str
    amount: float
    rule_code: str
    source_file: str
    source_row: int


@dataclass(frozen=True)
class ExternalAcceptance:
    system: str
    verdict: str
    created_at: str


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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS financial_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id INTEGER NOT NULL,
                    company_id INTEGER,
                    created_at TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    region TEXT NOT NULL,
                    bank TEXT NOT NULL DEFAULT '',
                    amount REAL NOT NULL,
                    rule_code TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    source_row INTEGER NOT NULL,
                    FOREIGN KEY(operation_id) REFERENCES operations(id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_financial_movements_operation
                ON financial_movements(operation_id, id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_financial_movements_company_outcome
                ON financial_movements(company_id, outcome, id)
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
        if self.company_id is None:
            # Kimliği olmayan eski istemci yalnız kendi eski, firma kapsamı
            # bulunmayan kayıtlarını toparlayabilir. Firma kayıtlarına hiç
            # dokunamaz.
            clause += " AND company_id IS NULL"
        else:
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
        financial_movements: Iterable[dict] | None = None,
    ) -> None:
        if status not in {"SUCCESS", "PARTIAL"}:
            raise OperationHistoryError("İşlem yalnız SUCCESS veya PARTIAL olarak tamamlanabilir.")
        outputs = [str(Path(path)) for path in output_files]
        output_evidence = build_output_evidence(outputs)
        movements = [
            financial_movement_from_decision(payload)
            for payload in (financial_movements or ())
        ]
        summary_payload = dict(summary or {})
        summary_payload["output_integrity"] = (
            "DOĞRULANDI"
            if output_evidence["state"] == "VERIFIED"
            else "KONTROL GEREKLİ"
        )
        if movements:
            summary_payload["financial_movement_count"] = len(movements)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE operations
                SET status = ?, completed_at = ?, output_files_json = ?,
                    summary_json = ?, error_message = NULL
                WHERE id = ? AND status = 'RUNNING' AND owner_instance_id = ?
                  AND ((? IS NULL AND company_id IS NULL) OR company_id = ?)
                  AND ((? IS NULL AND user_id IS NULL) OR user_id = ?)
                """,
                (
                    status,
                    self._now(),
                    json.dumps(outputs, ensure_ascii=False),
                    json.dumps(summary_payload, ensure_ascii=False),
                    operation_id,
                    self.instance_id,
                    self.company_id,
                    self.company_id,
                    self.user_id,
                    self.user_id,
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
            if movements:
                connection.executemany(
                    """
                    INSERT INTO financial_movements (
                        operation_id, company_id, created_at, decision, outcome,
                        region, bank, amount, rule_code, source_file, source_row
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            operation_id,
                            self.company_id,
                            self._now(),
                            item.decision,
                            item.outcome,
                            item.region,
                            item.bank,
                            item.amount,
                            item.rule_code,
                            item.source_file,
                            item.source_row,
                        )
                        for item in movements
                    ],
                )
                connection.execute(
                    """
                    INSERT INTO operation_events (
                        operation_id, created_at, level, code, message, details_json
                    ) VALUES (?, ?, 'INFO', 'FINANCIAL_LEDGER_RECORDED', ?, ?)
                    """,
                    (
                        operation_id,
                        self._now(),
                        f"{len(movements)} finansal hareket özeti kaydedildi.",
                        json.dumps({"movement_count": len(movements)}, ensure_ascii=False),
                    ),
                )
            connection.execute(
                """
                INSERT INTO operation_events (
                    operation_id, created_at, level, code, message, details_json
                ) VALUES (?, ?, ?, 'OUTPUT_EVIDENCE', ?, ?)
                """,
                (
                    operation_id,
                    self._now(),
                    "INFO" if output_evidence["state"] == "VERIFIED" else "WARNING",
                    "Çıktı bütünlüğü doğrulandı."
                    if output_evidence["state"] == "VERIFIED"
                    else "Çıktı bütünlüğü için dikkat gerekli.",
                    json.dumps(output_evidence, ensure_ascii=False),
                ),
            )

    def fail(self, operation_id: int, error_message: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE operations
                SET status = 'FAILED', completed_at = ?, error_message = ?
                WHERE id = ? AND status = 'RUNNING' AND owner_instance_id = ?
                  AND ((? IS NULL AND company_id IS NULL) OR company_id = ?)
                  AND ((? IS NULL AND user_id IS NULL) OR user_id = ?)
                """,
                (
                    self._now(),
                    str(error_message),
                    operation_id,
                    self.instance_id,
                    self.company_id,
                    self.company_id,
                    self.user_id,
                    self.user_id,
                ),
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
                SELECT summary_json FROM operations
                WHERE id = ? AND status = 'RUNNING' AND owner_instance_id = ?
                  AND ((? IS NULL AND company_id IS NULL) OR company_id = ?)
                  AND ((? IS NULL AND user_id IS NULL) OR user_id = ?)
                """,
                (
                    int(operation_id),
                    self.instance_id,
                    self.company_id,
                    self.company_id,
                    self.user_id,
                    self.user_id,
                ),
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

    def record_external_acceptance(
        self,
        operation_id: int,
        *,
        system: str,
        verdict: str,
    ) -> None:
        """Kaydı dış ERP aktarım sonucuyla işaretler.

        Bu kayıt, çıktı dosyasının oluştuğunu değil kullanıcının Netsis/Psoft
        aktarımını gerçekten denediğini gösterir. Serbest metin alınmaz; böylece
        hataya ait müşteri veya finansal ayrıntılar işlem geçmişine taşınmaz.
        Aynı sonuç daha sonra tekrar kaydedilebilir; son kayıt ekranlarda geçerli
        kabul sonucu olarak görünür ve önceki kararlar denetim izi olarak kalır.
        """
        normalized_system = str(system).strip().upper()
        normalized_verdict = str(verdict).strip().upper()
        labels = {"NETSIS": "Netsis", "PSOFT": "Psoft"}
        if normalized_system not in labels:
            raise OperationHistoryError("Dış aktarım sistemi Netsis veya Psoft olmalıdır.")
        if normalized_verdict not in {"ACCEPTED", "REJECTED"}:
            raise OperationHistoryError("Dış aktarım sonucu kabul veya ret olmalıdır.")
        with self._connect() as connection:
            allowed = connection.execute(
                """
                SELECT summary_json FROM operations
                WHERE id = ? AND status IN ('SUCCESS', 'PARTIAL')
                  AND ((? IS NULL AND company_id IS NULL) OR company_id = ?)
                  AND ((? IS NULL AND user_id IS NULL) OR user_id = ?)
                """,
                (
                    int(operation_id),
                    self.company_id,
                    self.company_id,
                    self.user_id,
                    self.user_id,
                ),
            ).fetchone()
            if allowed is None:
                raise OperationHistoryError(
                    "Dış aktarım sonucu kaydedilemedi; işlem bu firma ve kullanıcıya ait değil."
                )
            accepted = normalized_verdict == "ACCEPTED"
            try:
                summary = json.loads(allowed["summary_json"] or "{}")
            except json.JSONDecodeError:
                summary = {}
            if not isinstance(summary, dict):
                summary = {}
            summary["external_acceptance"] = {
                "system": normalized_system,
                "verdict": normalized_verdict,
            }
            connection.execute(
                "UPDATE operations SET summary_json = ? WHERE id = ?",
                (json.dumps(summary, ensure_ascii=False), int(operation_id)),
            )
            connection.execute(
                """
                INSERT INTO operation_events (
                    operation_id, created_at, level, code, message, details_json
                ) VALUES (?, ?, ?, 'ERP_ACCEPTANCE_RECORDED', ?, ?)
                """,
                (
                    int(operation_id),
                    self._now(),
                    "INFO" if accepted else "WARNING",
                    f"{labels[normalized_system]} aktarımı kullanıcı tarafından "
                    f"{'kabul edildi' if accepted else 'reddedildi'}.",
                    json.dumps(
                        {"system": normalized_system, "verdict": normalized_verdict},
                        ensure_ascii=False,
                    ),
                ),
            )

    def external_acceptance(self, operation_id: int) -> list[ExternalAcceptance]:
        """Firma/kullanıcı kapsamındaki dış aktarım sonuçlarını döndürür.

        Aynı sistem için son öğe geçerli sonuçtur. Önceki sonuçlar denetim
        zincirinde silinmeden kalır.
        """
        with self._connect() as connection:
            if self.company_id is None:
                rows = connection.execute(
                    """
                    SELECT e.* FROM operation_events e
                    JOIN operations o ON o.id = e.operation_id
                    WHERE e.operation_id = ? AND e.code = 'ERP_ACCEPTANCE_RECORDED'
                      AND o.company_id IS NULL
                    ORDER BY e.id
                    """,
                    (int(operation_id),),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT e.* FROM operation_events e
                    JOIN operations o ON o.id = e.operation_id
                    WHERE e.operation_id = ? AND e.code = 'ERP_ACCEPTANCE_RECORDED'
                      AND o.company_id = ?
                    ORDER BY e.id
                    """,
                    (int(operation_id), self.company_id),
                ).fetchall()
        return [
            ExternalAcceptance(
                system=str(json.loads(row["details_json"] or "{}").get("system", "")),
                verdict=str(json.loads(row["details_json"] or "{}").get("verdict", "")),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def heartbeat(self, operation_id: int) -> None:
        """Extend a running operation's lease while its owner is still working."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE operations SET lease_expires_at = ?
                WHERE id = ? AND status = 'RUNNING' AND owner_instance_id = ?
                  AND ((? IS NULL AND company_id IS NULL) OR company_id = ?)
                  AND ((? IS NULL AND user_id IS NULL) OR user_id = ?)
                """,
                (
                    self._lease_expires_at(),
                    int(operation_id),
                    self.instance_id,
                    self.company_id,
                    self.company_id,
                    self.user_id,
                    self.user_id,
                ),
            )
            if cursor.rowcount != 1:
                raise OperationHistoryError("İşlem devam sinyali gönderilemedi; kayıt bu uygulama oturumuna ait değil.")

    def events(self, operation_id: int) -> list[OperationEvent]:
        with self._connect() as connection:
            if self.company_id is None:
                rows = connection.execute(
                    """
                    SELECT e.* FROM operation_events e
                    JOIN operations o ON o.id = e.operation_id
                    WHERE e.operation_id = ? AND o.company_id IS NULL
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

    def financial_movements(self, operation_id: int) -> list[FinancialMovementRecord]:
        """Seçili firma kapsamındaki kalıcı hareket özetlerini döndürür."""
        with self._connect() as connection:
            if self.company_id is None:
                rows = connection.execute(
                    """
                    SELECT m.* FROM financial_movements m
                    JOIN operations o ON o.id = m.operation_id
                    WHERE m.operation_id = ? AND o.company_id IS NULL
                    ORDER BY m.id
                    """,
                    (int(operation_id),),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT m.* FROM financial_movements m
                    JOIN operations o ON o.id = m.operation_id
                    WHERE m.operation_id = ? AND o.company_id = ?
                    ORDER BY m.id
                    """,
                    (int(operation_id), self.company_id),
                ).fetchall()
        return [
            FinancialMovementRecord(
                id=int(row["id"]),
                operation_id=int(row["operation_id"]),
                decision=str(row["decision"]),
                outcome=str(row["outcome"]),
                region=str(row["region"]),
                bank=str(row["bank"]),
                amount=round(float(row["amount"]), 2),
                rule_code=str(row["rule_code"]),
                source_file=str(row["source_file"]),
                source_row=int(row["source_row"]),
            )
            for row in rows
        ]

    def recent(self, limit: int = 100) -> list[OperationRecord]:
        with self._connect() as connection:
            if self.company_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM operations
                    WHERE company_id IS NULL
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
