from decimal import Decimal

import pytest

from app.core.money import money, money_sum, within_cent


def test_money_uses_accounting_rounding_without_float_drift():
    assert money("10.005") == Decimal("10.01")
    assert money_sum([0.1, 0.2]) == Decimal("0.30")
    assert within_cent("100.00", "100.01")


@pytest.mark.parametrize("value", ["NaN", "Infinity", None, "abc"])
def test_money_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        money(value)
