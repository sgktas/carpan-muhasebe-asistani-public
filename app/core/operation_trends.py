"""Yerel işlem geçmişi için filtrelenebilir, veri-minimum trend özetleri."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
from typing import Iterable

from app.core.erp_acceptance_target import aggregate_erp_acceptance, erp_rejection_reason_codes
from app.core.operation_history import OperationRecord


@dataclass(frozen=True)
class OperationTrendSummary:
    operation_count: int
    successful_count: int
    partial_count: int
    failed_count: int
    netsis_accepted: int
    netsis_rejected: int
    psoft_accepted: int
    psoft_rejected: int
    netsis_rejection_reasons: tuple[tuple[str, int], ...]
    psoft_rejection_reasons: tuple[tuple[str, int], ...]


def filter_operation_records(
    records: Iterable[OperationRecord], *, period_days: int | None, now: datetime | None = None,
) -> list[OperationRecord]:
    """Dönem dışı ve tarihi okunamayan kayıtları dönemli görünümden ayırır."""

    values = list(records)
    if period_days is None:
        return values
    reference = (now or datetime.now().astimezone()).astimezone()
    earliest = reference - timedelta(days=max(1, int(period_days)))
    return [
        record for record in values
        if (started_at := _as_datetime(record.started_at, timezone=reference.tzinfo)) is not None
        and earliest <= started_at <= reference
    ]


def build_operation_trend_summary(records: Iterable[OperationRecord]) -> OperationTrendSummary:
    values = tuple(records)
    netsis = tuple(_erp_status(record, "NETSIS") for record in values)
    psoft = tuple(_erp_status(record, "PSOFT") for record in values)
    return OperationTrendSummary(
        operation_count=len(values),
        successful_count=sum(record.status == "SUCCESS" for record in values),
        partial_count=sum(record.status == "PARTIAL" for record in values),
        failed_count=sum(record.status in {"FAILED", "INTERRUPTED"} for record in values),
        netsis_accepted=sum(item == "ACCEPTED" for item in netsis),
        netsis_rejected=sum(item == "REJECTED" for item in netsis),
        psoft_accepted=sum(item == "ACCEPTED" for item in psoft),
        psoft_rejected=sum(item == "REJECTED" for item in psoft),
        netsis_rejection_reasons=_rejection_reasons(values, "NETSIS"),
        psoft_rejection_reasons=_rejection_reasons(values, "PSOFT"),
    )


def _erp_status(record: OperationRecord, system: str) -> str:
    return aggregate_erp_acceptance(
        record.module_id, system, record.output_files, record.summary,
    ).status


def _rejection_reasons(records: Iterable[OperationRecord], system: str) -> tuple[tuple[str, int], ...]:
    counts = Counter(
        reason
        for record in records
        for reason in erp_rejection_reason_codes(
            record.module_id, system, record.output_files, record.summary,
        )
    )
    return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _as_datetime(value: str, *, timezone: tzinfo | None) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)
