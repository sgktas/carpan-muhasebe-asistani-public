from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from app.core.erp_acceptance_target import aggregate_erp_acceptance
from app.core.operation_history import ERP_REJECTION_REASON_LABELS, OperationRecord


ATTENTION_STATUSES = frozenset({"PARTIAL", "FAILED", "INTERRUPTED"})


@dataclass(frozen=True)
class OperationPeriodSummary:
    """Yerel işlem geçmişinden türetilen, finansal veri içermeyen dönem özeti."""

    operation_count: int
    successful_count: int
    accepted_count: int
    attention_count: int
    reconciliation_attention_count: int


@dataclass(frozen=True)
class OperationCenterSnapshot:
    total_operations: int
    successful_operations: int
    attention_operations: int
    generated_files: int
    unresolved_items: int
    simulation_verified: int
    simulation_mismatches: int
    netsis_rejections: int
    psoft_rejections: int
    reconciliation_attention: int
    weekly_summary: OperationPeriodSummary
    attention_records: tuple[OperationRecord, ...]


def build_operation_center_snapshot(
    records: Iterable[OperationRecord],
    *,
    attention_limit: int = 12,
    now: datetime | None = None,
) -> OperationCenterSnapshot:
    """İşlem geçmişini kullanıcıya dönük operasyon özeti haline getirir.

    Bu fonksiyon yalnız firma kapsamındaki ``OperationHistory`` kayıtlarını
    kullanır; ham banka, Excel veya müşteri verisi merkezileştirilmez.
    """
    all_records = tuple(records)
    weekly_summary = _period_summary(all_records, days=7, now=now)
    attention = tuple(
        record for record in all_records if _needs_attention(record)
    )[: max(1, int(attention_limit))]
    unresolved = sum(_integer_summary(record.summary, "unresolved") for record in all_records)
    simulation_verified = sum(_simulation_status(record.summary) == "MATCH" for record in all_records)
    simulation_mismatches = sum(_simulation_status(record.summary) == "MISMATCH" for record in all_records)
    netsis_rejections = sum(
        _erp_acceptance(record, "NETSIS").status == "REJECTED"
        for record in all_records
    )
    psoft_rejections = sum(
        _erp_acceptance(record, "PSOFT").status == "REJECTED"
        for record in all_records
    )
    reconciliation_attention = sum(_reconciliation_needs_attention(record) for record in all_records)
    return OperationCenterSnapshot(
        total_operations=len(all_records),
        successful_operations=sum(record.status == "SUCCESS" for record in all_records),
        attention_operations=sum(_needs_attention(record) for record in all_records),
        generated_files=sum(len(record.output_files) for record in all_records),
        unresolved_items=unresolved,
        simulation_verified=simulation_verified,
        simulation_mismatches=simulation_mismatches,
        netsis_rejections=netsis_rejections,
        psoft_rejections=psoft_rejections,
        reconciliation_attention=reconciliation_attention,
        weekly_summary=weekly_summary,
        attention_records=attention,
    )


def _period_summary(
    records: tuple[OperationRecord, ...], *, days: int, now: datetime | None,
) -> OperationPeriodSummary:
    reference = (now or datetime.now().astimezone()).astimezone()
    earliest = reference - timedelta(days=days)
    period_records = tuple(
        record for record in records
        if (started_at := _operation_datetime(record.started_at, timezone=reference.tzinfo)) is not None
        and earliest <= started_at <= reference
    )
    accepted_count = sum(
        any(_erp_acceptance(record, system).status == "ACCEPTED" for system in ("NETSIS", "PSOFT"))
        for record in period_records
    )
    return OperationPeriodSummary(
        operation_count=len(period_records),
        successful_count=sum(record.status == "SUCCESS" for record in period_records),
        accepted_count=accepted_count,
        attention_count=sum(_needs_attention(record) for record in period_records),
        reconciliation_attention_count=sum(_reconciliation_needs_attention(record) for record in period_records),
    )


def _operation_datetime(value: str, *, timezone):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def operation_attention_text(record: OperationRecord) -> str:
    if _simulation_status(record.summary) == "MISMATCH":
        return "Simülasyon ve gerçek aktarım planı farklı; bölge/banka toplamlarını kontrol edin."
    acceptance = next(
        (value for value in (_erp_acceptance(record, "NETSIS"), _erp_acceptance(record, "PSOFT"))
         if value.status == "REJECTED"),
        None,
    )
    if acceptance:
        system = {"NETSIS": "Netsis", "PSOFT": "Psoft"}.get(acceptance.system, "Dış sistem")
        reason = ERP_REJECTION_REASON_LABELS.get(acceptance.reason_code)
        if reason:
            return f"{system} aktarımı reddedildi: {reason}."
        return f"{system} aktarımı reddedildi; çıktı sözleşmesini ve aktarım ekranını kontrol edin."
    if _reconciliation_needs_attention(record):
        reconciliation = _reconciliation(record.summary)
        status = reconciliation.get("status")
        bank_only = _integer_value(reconciliation.get("bank_only_count"))
        netsis_only = _integer_value(reconciliation.get("netsis_only_count"))
        if status == "OPENING_BALANCE":
            amount = _decimal_value(reconciliation.get("opening_difference"))
            return f"Banka mutabakatında dönem hareketleri tutuyor; devreden bakiye farkı {amount:,.2f} TL."
        if status == "OPEN_ITEMS":
            return f"Banka mutabakatı bakiyesi tutuyor; {bank_only + netsis_only} açıklanamayan kayıt var."
        amount = _decimal_value(reconciliation.get("difference"))
        return (
            f"Banka mutabakatı tutmuyor: fark {amount:,.2f} TL; "
            f"bankada {bank_only}, Netsis'te {netsis_only} açık kayıt var."
        )
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
    rejected = any(
        _erp_acceptance(record, system).status == "REJECTED"
        for system in ("NETSIS", "PSOFT")
    )
    return _simulation_status(record.summary) == "MISMATCH" or _reconciliation_needs_attention(record) or record.status in ATTENTION_STATUSES or bool(
        rejected
    )


def _erp_acceptance(record: OperationRecord, system: str):
    return aggregate_erp_acceptance(
        record.module_id, system, record.output_files, record.summary,
    )


def _reconciliation_needs_attention(record: OperationRecord) -> bool:
    return record.module_id == "bank_reconciliation" and _reconciliation(record.summary).get("status") in {
        "OPEN_ITEMS", "OPENING_BALANCE", "MISMATCH"
    }


def _reconciliation(summary: dict) -> dict:
    try:
        value = summary.get("reconciliation", {})
    except AttributeError:
        return {}
    return value if isinstance(value, dict) else {}


def _integer_value(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _decimal_value(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _integer_summary(summary: dict, key: str) -> int:
    try:
        value = int(summary.get(key, 0))
    except (AttributeError, TypeError, ValueError):
        return 0
    return max(0, value)


def _simulation_status(summary: dict) -> str:
    try:
        value = summary.get("simulation", {})
    except AttributeError:
        return ""
    return str(value.get("status", "")).strip().upper() if isinstance(value, dict) else ""
