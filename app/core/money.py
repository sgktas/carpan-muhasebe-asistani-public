from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable


CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: object) -> Decimal:
    """Bir parasal değeri iki ondalıklı, kesin Decimal değerine çevirir."""
    if isinstance(value, Decimal):
        decimal_value = value
    else:
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as error:
            raise ValueError(f"Geçersiz parasal değer: {value!r}") from error
    if not decimal_value.is_finite():
        raise ValueError(f"Geçersiz parasal değer: {value!r}")
    return decimal_value.quantize(CENT, rounding=ROUND_HALF_UP)


def money_sum(values: Iterable[object]) -> Decimal:
    return sum((money(value) for value in values), ZERO)


def within_cent(left: object, right: object) -> bool:
    return abs(money(left) - money(right)) <= CENT
