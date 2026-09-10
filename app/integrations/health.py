"""Yerel işlem geçmişinden türetilen veri-minimum entegrasyon sağlığı."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

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
    matching = (
        record for record in records
        if record.module_id in integration.operation_module_ids
        and _acceptance(record.summary).get("system") == system
    )
    latest = next(matching, None)
    if latest is None:
        return IntegrationHealth(integration.integration_id, IntegrationAcceptanceState.NO_RESULT, "Henüz aktarım sonucu kaydedilmedi")
    verdict = _acceptance(latest.summary).get("verdict")
    if verdict == "ACCEPTED":
        return IntegrationHealth(integration.integration_id, IntegrationAcceptanceState.ACCEPTED, "Son aktarım kabul edildi")
    if verdict == "REJECTED":
        return IntegrationHealth(integration.integration_id, IntegrationAcceptanceState.REJECTED, "Son aktarım reddedildi")
    return IntegrationHealth(integration.integration_id, IntegrationAcceptanceState.NO_RESULT, "Henüz aktarım sonucu kaydedilmedi")


def _acceptance(summary: object) -> dict[str, str]:
    if not isinstance(summary, dict):
        return {}
    value = summary.get("external_acceptance")
    if not isinstance(value, dict):
        return {}
    return {
        "system": str(value.get("system", "")).strip().upper(),
        "verdict": str(value.get("verdict", "")).strip().upper(),
    }
