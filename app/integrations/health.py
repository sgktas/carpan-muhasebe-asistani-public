"""Yerel işlem geçmişinden türetilen veri-minimum entegrasyon sağlığı."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from app.core.erp_acceptance_target import aggregate_erp_acceptance
from app.core.operation_history import OperationRecord
from app.integrations.contracts import IntegrationManifest, IntegrationMaturity


class IntegrationAcceptanceState(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NO_RESULT = "NO_RESULT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PLANNED = "PLANNED"


@dataclass(frozen=True)
class IntegrationHealth:
    integration_id: str
    state: IntegrationAcceptanceState
    text: str
    recorded_at: str | None = None
    operation_id: int | None = None


def build_integration_health(
    integrations: Iterable[IntegrationManifest],
    records: Iterable[OperationRecord],
) -> dict[str, IntegrationHealth]:
    """Her bağlantının en güncel kabul sonucunu yerel geçmişten üretir.

    Özet yalnız modül kimliği, kabul/ret sonucu ve zaman sırasını kullanır.
    Dosya içeriği, müşteri, banka, IBAN veya tutar okunmaz ve merkezileştirilmez.
    """
    all_records = tuple(records)
    result: dict[str, IntegrationHealth] = {}
    for integration in integrations:
        result[integration.integration_id] = _health_for(integration, all_records)
    return result


def _health_for(integration: IntegrationManifest, records: tuple[OperationRecord, ...]) -> IntegrationHealth:
    if integration.maturity != IntegrationMaturity.ACTIVE:
        return IntegrationHealth(integration.integration_id, IntegrationAcceptanceState.PLANNED, "Planlanıyor")
    system = str(integration.acceptance_system or "").strip().upper()
    if not system:
        return IntegrationHealth(integration.integration_id, IntegrationAcceptanceState.NOT_APPLICABLE, "Dış aktarım sonucu gerekmiyor")
    matching = tuple(
        record for record in records
        if record.module_id in integration.operation_module_ids
        and _acceptance(record, system).status != "NO_RESULT"
    )
    # ``OperationHistory.recent`` bugün en yeni kaydı önce döndürür; bu fonksiyon
    # ise dışarıdan gelen sıralamaya güvenmez. Böylece eski bir kayıt kullanıcıya
    # yanlışlıkla "son aktarım" diye gösterilmez.
    latest = max(matching, key=_operation_recency, default=None)
    if latest is None:
        return IntegrationHealth(integration.integration_id, IntegrationAcceptanceState.NO_RESULT, "Henüz aktarım sonucu kaydedilmedi")
    acceptance = _acceptance(latest, system)
    verdict = acceptance.status
    recorded_at = latest.completed_at or latest.started_at
    if verdict == "ACCEPTED":
        return IntegrationHealth(
            integration.integration_id, IntegrationAcceptanceState.ACCEPTED,
            "Son aktarım kabul edildi", recorded_at, latest.id,
        )
    if verdict == "REJECTED":
        return IntegrationHealth(
            integration.integration_id, IntegrationAcceptanceState.REJECTED,
            "Son aktarım reddedildi", recorded_at, latest.id,
        )
    if verdict == "PARTIAL":
        return IntegrationHealth(
            integration.integration_id, IntegrationAcceptanceState.NO_RESULT,
            f"Sonucun {acceptance.recorded_count}/{acceptance.candidate_count} dosyası kaydedildi",
            recorded_at, latest.id,
        )
    return IntegrationHealth(integration.integration_id, IntegrationAcceptanceState.NO_RESULT, "Henüz aktarım sonucu kaydedilmedi")


def _operation_recency(record: OperationRecord) -> tuple[str, int]:
    """İşlem geçmişi sıralaması değişse bile en yeni sonucu seçer.

    ISO-8601 zaman damgaları karakter sırası ile güvenle karşılaştırılabilir.
    Eski/bozuk bir zaman damgasında otomatik tarih uydurmak yerine işlem numarası
    ikinci anahtar olarak kullanılır.
    """
    return (str(record.completed_at or record.started_at or ""), int(record.id))


def _acceptance(record: OperationRecord, system: str):
    return aggregate_erp_acceptance(
        record.module_id, system, record.output_files, record.summary,
    )
