from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from app.core.operation_history import OperationRecord


ATTENTION_STATUSES = frozenset({"PARTIAL", "FAILED", "INTERRUPTED"})


@dataclass(frozen=True)
class OperationCenterSnapshot:
    total_operations: int
    successful_operations: int
    attention_operations: int
    generated_files: int
    unresolved_items: int
    attention_records: tuple[OperationRecord, ...]


def build_operation_center_snapshot(
    records: Iterable[OperationRecord],
    *,
    attention_limit: int = 12,
) -> OperationCenterSnapshot:
    """İşlem geçmişini kullanıcıya dönük operasyon özeti haline getirir.

    Bu fonksiyon yalnız firma kapsamındaki ``OperationHistory`` kayıtlarını
    kullanır; ham banka, Excel veya müşteri verisi merkezileştirilmez.
    """
    all_records = tuple(records)
    attention = tuple(
        record for record in all_records if _needs_attention(record)
    )[: max(1, int(attention_limit))]
    unresolved = sum(_integer_summary(record.summary, "unresolved") for record in all_records)
    return OperationCenterSnapshot(
        total_operations=len(all_records),
        successful_operations=sum(record.status == "SUCCESS" for record in all_records),
        attention_operations=sum(_needs_attention(record) for record in all_records),
        generated_files=sum(len(record.output_files) for record in all_records),
        unresolved_items=unresolved,
        attention_records=attention,
    )


def operation_attention_text(record: OperationRecord) -> str:
    acceptance = _external_acceptance(record.summary)
    if acceptance and acceptance.get("verdict") == "REJECTED":
        system = {"NETSIS": "Netsis", "PSOFT": "Psoft"}.get(
            acceptance.get("system"),
            "Dış sistem",
        )
        return f"{system} aktarımı reddedildi; çıktı sözleşmesini ve aktarım ekranını kontrol edin."
    if record.status == "PARTIAL":
        unresolved = _integer_summary(record.summary, "unresolved")
        return (
            f"{unresolved} kayıt inceleme bekliyor."
            if unresolved
            else "İşlem kısmi tamamlandı; çıktıları ve inceleme listesini kontrol edin."
        )
    if record.status == "FAILED":
        return record.error_message or "İşlem tamamlanamadı; işlem ayrıntılarını kontrol edin."
    if record.status == "INTERRUPTED":
        return "İşlem yarım kaldı; gerekirse aynı girdilerle tekrar başlatın."
    return "İşlem kontrol gerektiriyor."


def _needs_attention(record: OperationRecord) -> bool:
    acceptance = _external_acceptance(record.summary)
    return record.status in ATTENTION_STATUSES or bool(
        acceptance and acceptance.get("verdict") == "REJECTED"
    )


def _external_acceptance(summary: dict) -> dict[str, str]:
    try:
        value = summary.get("external_acceptance", {})
    except AttributeError:
        return {}
    if not isinstance(value, dict):
        return {}
    return {
        "system": str(value.get("system", "")).strip().upper(),
        "verdict": str(value.get("verdict", "")).strip().upper(),
    }


def _integer_summary(summary: dict, key: str) -> int:
    try:
        value = int(summary.get(key, 0))
    except (AttributeError, TypeError, ValueError):
        return 0
    return max(0, value)
