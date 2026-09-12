"""Merkezi denetim zincirini salt-okunur doğrulayan küçük çekirdek.

Bu modül müşteri, banka, Excel veya finansal hareket verisi işlemez. Yalnız
denetim olaylarının mevcut özet alanlarından yeniden hash üreterek zincirin
araya kayıt ekleme/değiştirme karşısında tutarlı kalıp kalmadığını kontrol eder.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Iterable, Mapping


GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class AuditChainVerification:
    chain_name: str
    event_count: int
    valid: bool
    invalid_event_id: int | None = None
    message: str = ""


def verify_company_audit_chains(rows: Iterable[Mapping[str, object]]) -> tuple[AuditChainVerification, ...]:
    """Firma başına ayrık olan ``carpan.audit_events`` zincirlerini denetler."""
    groups: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        groups.setdefault(str(row.get("company_id", "")), []).append(row)
    return tuple(
        _verify_chain(f"firma:{company_id}", grouped_rows, include_company_id=True)
        for company_id, grouped_rows in sorted(groups.items())
    )


def verify_platform_audit_chain(rows: Iterable[Mapping[str, object]]) -> AuditChainVerification:
    """Platform sahibinin tek, küresel denetim zincirini denetler."""
    return _verify_chain("platform", rows, include_company_id=False)


def _verify_chain(
    chain_name: str,
    rows: Iterable[Mapping[str, object]],
    *,
    include_company_id: bool,
) -> AuditChainVerification:
    ordered = sorted(rows, key=lambda row: int(row.get("id", 0)))
    previous_hash = GENESIS_HASH
    for row in ordered:
        event_id = _event_id(row)
        stored_previous = str(row.get("previous_hash", ""))
        stored_hash = str(row.get("event_hash", ""))
        if stored_previous != previous_hash:
            return AuditChainVerification(
                chain_name, len(ordered), False, event_id,
                "Önceki olay özeti zincirle uyuşmuyor.",
            )
        expected_hash = _event_hash(row, previous_hash=previous_hash, include_company_id=include_company_id)
        if stored_hash != expected_hash:
            return AuditChainVerification(
                chain_name, len(ordered), False, event_id,
                "Olay özeti yeniden hesaplanan değerle uyuşmuyor.",
            )
        previous_hash = stored_hash
    return AuditChainVerification(chain_name, len(ordered), True, message="Denetim zinciri doğrulandı.")


def _event_id(row: Mapping[str, object]) -> int | None:
    try:
        return int(row.get("id", 0))
    except (TypeError, ValueError):
        return None


def _event_hash(
    row: Mapping[str, object],
    *,
    previous_hash: str,
    include_company_id: bool,
) -> str:
    """Yazma katmanlarındaki kanonik JSON sözleşmesini birebir uygular."""
    event_data = row.get("event_data", {})
    if isinstance(event_data, str):
        try:
            event_data = json.loads(event_data)
        except json.JSONDecodeError:
            # Bozuk JSON zaten denetim olayının değiştirildiğini gösterir.
            event_data = event_data
    data_json = json.dumps(event_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload: dict[str, object] = {
        "actor_user_id": _nullable_text(row.get("actor_user_id")),
        "created_at": _timestamp_text(row.get("created_at")),
        "event_data": data_json,
        "event_type": str(row.get("event_type", "")),
        "outcome": str(row.get("outcome", "")),
        "previous_hash": previous_hash,
    }
    if include_company_id:
        payload["company_id"] = str(row.get("company_id", ""))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _nullable_text(value: object) -> str | None:
    return None if value is None else str(value)


def _timestamp_text(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    return str(value)
