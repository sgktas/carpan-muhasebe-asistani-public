from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterable
from uuid import uuid4

from app.core.financial_ledger import financial_movement_from_decision
from app.core.output_evidence import build_output_evidence, verify_output_evidence
from app.core.execution_configuration import (
    ConfigurationRevision,
    ConfigurationSnapshot,
    bind_configuration,
    initialize_configuration_schema,
)


class OperationHistoryError(RuntimeError):
    """An operation cannot be changed by this company or application instance."""


class DecisionAuditError(ValueError):
    """A decision audit record is missing a required, safe field."""


# Kullanıcı ERP aktarım ekranında serbest hata metni yerine güvenli bir kategori
# seçer. Böylece müşteri/banka içeriği işlem geçmişine taşınmadan tekrar eden
# kabul sorunları izlenebilir.
ERP_REJECTION_REASONS = (
    ("BANK_ACCOUNT_CODE", "Banka hesap kodu"),
    ("TEMPLATE_CONTRACT", "Şablon veya sütun yapısı"),
    ("REQUIRED_FIELD", "Zorunlu alan"),
    ("AMOUNT_TOTAL", "Tutar veya toplam"),
    ("FILE_FORMAT", "Dosya biçimi"),
    ("OTHER", "Diğer / aktarım ekranı"),
)
ERP_REJECTION_REASON_LABELS = dict(ERP_REJECTION_REASONS)


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
    reason_code: str = ""
    output_name: str = ""
    output_sha256: str = ""


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
            initialize_configuration_schema(connection)
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
        *,
        configuration: ConfigurationSnapshot | None = None,
    ) -> int:
        if configuration is not None and configuration.module_id != module_id:
            raise OperationHistoryError("İşlem ayarları seçilen modüle ait değil.")
        inputs = [str(Path(path)) for path in input_files]
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
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
            if configuration is not None:
                bind_configuration(
                    connection, operation_id=operation_id, company_id=self.company_id,
                    user_id=self.user_id, created_at=self._now(), snapshot=configuration,
                )
            return operation_id

    def configuration(self, operation_id: int) -> ConfigurationRevision | None:
        """Read the settings of this company's operation, including old revisions."""
        with self._connect() as connection:
            row = connection.execute("""
                SELECT v.revision, v.module_id, v.payload_json, v.fingerprint
                FROM operation_configurations c
                JOIN operations o ON o.id = c.operation_id
                JOIN operation_configuration_versions v ON v.id = c.version_id
                WHERE o.id = ?
                  AND ((? IS NULL AND o.company_id IS NULL) OR o.company_id = ?)
            """, (int(operation_id), self.company_id, self.company_id)).fetchone()
        if row is None:
            return None
        try:
            snapshot = ConfigurationSnapshot(row["module_id"], row["payload_json"])
        except (TypeError, ValueError) as error:
            raise OperationHistoryError("Kayıtlı işlem ayarı okunamadı.") from error
        if snapshot.fingerprint != row["fingerprint"]:
            raise OperationHistoryError("Kayıtlı işlem ayarının bütünlüğü doğrulanamadı.")
        return ConfigurationRevision(int(row["revision"]), snapshot)

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
        self.add_events(operation_id, [{"code": code, "message": message, "level": level, "details": details}])

    def add_events(self, operation_id: int, events) -> None:
        """Persist a result batch atomically, preserving company/owner checks."""
        rows = [
            (int(operation_id), self._now(), str(event.get("level", "INFO")).upper(),
             str(event["code"]).strip().upper(), str(event["message"]),
             json.dumps(event.get("details") or {}, ensure_ascii=False))
            for event in events
        ]
        if not rows:
            return
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
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
            connection.executemany(
                """INSERT INTO operation_events
                   (operation_id, created_at, level, code, message, details_json)
                   VALUES (?, ?, ?, ?, ?, ?)""", rows,
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
        saklar. ``add_events`` üzerinden yazıldığı için işlem sahibi/firma ve
        çalışan işlem lease kontrolleri aynen korunur.
        """
        self.add_decisions(operation_id, [dict(decision=decision, outcome=outcome, region=region,
            bank=bank, amount=amount, source_file=source_file, source_row=source_row,
            rule_code=rule_code, reason=reason)])

    def add_decisions(self, operation_id: int, decisions) -> None:
        self.add_events(operation_id, [self._decision_event(**decision) for decision in decisions])

    @staticmethod
    def _decision_event(*, decision, outcome, region, bank, amount, source_file, source_row, rule_code, reason=""):
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
        return {"code": "DECISION_AUDIT", "message": f"{values['decision']} → {values['outcome']}",
                "details": {**values, "amount": normalized_amount, "source_row": normalized_row}}

    def record_external_acceptance(
        self,
        operation_id: int,
        *,
        system: str,
        verdict: str,
        reason_code: str = "",
        output_file: str | Path | None = None,
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
        normalized_reason = str(reason_code).strip().upper()
        labels = {"NETSIS": "Netsis", "PSOFT": "Psoft"}
        if normalized_system not in labels:
            raise OperationHistoryError("Dış aktarım sistemi Netsis veya Psoft olmalıdır.")
        if normalized_verdict not in {"ACCEPTED", "REJECTED"}:
            raise OperationHistoryError("Dış aktarım sonucu kabul veya ret olmalıdır.")
        if normalized_verdict == "ACCEPTED" and normalized_reason:
            raise OperationHistoryError("Kabul edilen aktarım için ret nedeni kaydedilemez.")
        if normalized_reason and normalized_reason not in ERP_REJECTION_REASON_LABELS:
            raise OperationHistoryError("Dış aktarım ret nedeni geçersiz.")
        with self._connect() as connection:
            allowed = connection.execute(
                """
                SELECT summary_json, output_files_json FROM operations
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
            binding = self._verified_output_binding(
                connection,
                int(operation_id),
                json.loads(allowed["output_files_json"] or "[]"),
                output_file,
            )
            accepted = normalized_verdict == "ACCEPTED"
            try:
                summary = json.loads(allowed["summary_json"] or "{}")
            except json.JSONDecodeError:
                summary = {}
            if not isinstance(summary, dict):
                summary = {}
            acceptance_payload = {
                "system": normalized_system,
                "verdict": normalized_verdict,
                "reason_code": normalized_reason,
            }
            if binding:
                acceptance_payload.update(binding)
                by_file = summary.get("external_acceptance_by_file", {})
                if not isinstance(by_file, dict):
                    by_file = {}
                by_file[binding["output_path"]] = dict(acceptance_payload)
                summary["external_acceptance_by_file"] = by_file
            summary["external_acceptance"] = acceptance_payload
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
                        {
                            "system": normalized_system,
                            "verdict": normalized_verdict,
                            "reason_code": normalized_reason,
                            **binding,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

    @staticmethod
    def _verified_output_binding(
        connection: sqlite3.Connection,
        operation_id: int,
        output_files: list[str],
        requested_output: str | Path | None,
    ) -> dict[str, object]:
        """Bind an explicit ERP verdict to the unchanged generated file."""
        if requested_output in (None, ""):
            # Geriye uyumluluk: eski ekranlar ve eski kayıtlar işlem düzeyi
            # sonucunu kullanmaya devam eder. Yeni ekranlar dosyayı açıkça
            # gönderir ve aşağıdaki sıkı kanıt kontrolünden geçer.
            return {}
        selected = str(Path(requested_output))
        normalized_outputs = [str(Path(value)) for value in output_files]
        if selected not in normalized_outputs:
            raise OperationHistoryError(
                "Aktarım sonucu yalnız bu işlemin oluşturduğu bir çıktıya kaydedilebilir."
            )
        row = connection.execute(
            """
            SELECT details_json FROM operation_events
            WHERE operation_id = ? AND code = 'OUTPUT_EVIDENCE'
            ORDER BY id DESC LIMIT 1
            """,
            (operation_id,),
        ).fetchone()
        try:
            evidence = json.loads(row["details_json"] or "{}") if row else {}
        except (TypeError, json.JSONDecodeError):
            evidence = {}
        baseline = next(
            (
                item for item in evidence.get("files", [])
                if isinstance(item, dict) and str(Path(str(item.get("path", "")))) == selected
            ),
            None,
        )
        if baseline is None or baseline.get("state") != "VERIFIED":
            raise OperationHistoryError(
                "Seçilen çıktının işlem tamamlama parmak izi bulunamadı."
            )
        comparison = verify_output_evidence({
            "algorithm": evidence.get("algorithm", ""),
            "files": [baseline],
        })
        if not comparison or comparison[0].get("comparison") != "VERIFIED":
            raise OperationHistoryError(
                "Seçilen çıktı oluşturulduktan sonra değişmiş, taşınmış veya silinmiş. "
                "ERP sonucu bu dosyaya bağlanamadı."
            )
        return {
            "output_path": selected,
            "output_name": str(baseline.get("name") or Path(selected).name),
            "output_sha256": str(baseline.get("sha256") or ""),
            "output_size": int(baseline.get("size") or 0),
        }

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
                reason_code=str(json.loads(row["details_json"] or "{}").get("reason_code", "")),
                output_name=str(json.loads(row["details_json"] or "{}").get("output_name", "")),
                output_sha256=str(json.loads(row["details_json"] or "{}").get("output_sha256", "")),
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

    def recent(self, limit: int | None = 100) -> list[OperationRecord]:
        # SQLite LIMIT -1 means all rows, still restricted to this company.
        row_limit = -1 if limit is None else max(1, int(limit))
        with self._connect() as connection:
            if self.company_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM operations
                    WHERE company_id IS NULL
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (row_limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM operations
                    WHERE company_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (self.company_id, row_limit),
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
