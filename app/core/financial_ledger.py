from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path


class FinancialMovementError(ValueError):
    """Kalıcı finansal hareket özeti güvenli değil veya eksik."""


@dataclass(frozen=True)
class FinancialMovement:
    decision: str
    outcome: str
    region: str
    bank: str
    amount: float
    rule_code: str
    source_file: str
    source_row: int


def financial_movement_from_decision(payload: dict) -> FinancialMovement:
    """MANİM kararından kişisel veri içermeyen finansal hareket özeti üretir."""
    values = {
        "decision": str(payload.get("decision", "")).strip().upper(),
        "outcome": str(payload.get("outcome", "")).strip().upper(),
        "region": str(payload.get("region", "")).strip().upper(),
        "bank": str(payload.get("bank", "")).strip().upper(),
        "rule_code": str(payload.get("rule_code", "")).strip().upper(),
        # Sadece ad saklanır; kullanıcı klasör yolu işlem defterine taşınmaz.
        "source_file": Path(str(payload.get("source_file", "")).strip()).name,
    }
    if not all(values[key] for key in ("decision", "outcome", "region", "rule_code", "source_file")):
        raise FinancialMovementError(
            "Finansal hareket için karar, sonuç, bölge, kural ve kaynak zorunludur."
        )
    try:
        amount = round(float(payload.get("amount")), 2)
        source_row = int(payload.get("source_row"))
    except (TypeError, ValueError) as error:
        raise FinancialMovementError("Finansal hareket tutarı veya kaynak satırı geçersiz.") from error
    if not math.isfinite(amount):
        raise FinancialMovementError("Finansal hareket tutarı sonlu bir sayı olmalıdır.")
    if source_row < 1:
        raise FinancialMovementError("Finansal hareket kaynak satırı 1 veya daha büyük olmalıdır.")
    return FinancialMovement(
        decision=values["decision"],
        outcome=values["outcome"],
        region=values["region"],
        bank=values["bank"],
        amount=amount,
        rule_code=values["rule_code"],
        source_file=values["source_file"],
        source_row=source_row,
    )
