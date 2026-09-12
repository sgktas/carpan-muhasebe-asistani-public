import pytest

from app.core.tahsilat_consumption_ledger import (
    TahsilatConsumptionError,
    TahsilatConsumptionLedger,
)
from app.models.records import TahsilatRecord


def _row(amount: float, *, source_row: int = 2) -> TahsilatRecord:
    return TahsilatRecord(
        musteri_kodu="C001",
        musteri_ismi="TEST",
        belge_tarihi=None,
        tutar=amount,
        source_hash="source-hash",
        source_sheet="ŞUBELİLER",
        source_row=source_row,
        source_amount=1000.0,
    )


def test_partial_consumption_leaves_exact_remaining_balance(tmp_path):
    ledger = TahsilatConsumptionLedger(tmp_path / "consumption.sqlite3", company_id=1)
    source = _row(1000.0)

    ledger.consume([_row(625.25)], operation_id=10)

    available = ledger.available_rows([source])
    assert len(available) == 1
    assert available[0].tutar == 374.75
    balance = ledger.balances([source])[0]
    assert balance.consumed_amount == 625.25
    assert balance.remaining_amount == 374.75


def test_fully_consumed_source_row_is_not_offered_again(tmp_path):
    ledger = TahsilatConsumptionLedger(tmp_path / "consumption.sqlite3", company_id=1)
    source = _row(1000.0)
    ledger.consume([source], operation_id=10)

    assert ledger.available_rows([source]) == []


def test_consumption_cannot_exceed_original_source_amount(tmp_path):
    ledger = TahsilatConsumptionLedger(tmp_path / "consumption.sqlite3", company_id=1)
    ledger.consume([_row(800.0)], operation_id=10)

    with pytest.raises(TahsilatConsumptionError, match="kullanılabilir bakiyesi"):
        ledger.consume([_row(250.0)], operation_id=11)


def test_consumption_is_company_scoped(tmp_path):
    database = tmp_path / "consumption.sqlite3"
    source = _row(1000.0)
    TahsilatConsumptionLedger(database, company_id=1).consume([source], operation_id=10)

    other_company = TahsilatConsumptionLedger(database, company_id=2)
    assert other_company.available_rows([source])[0].tutar == 1000.0


def test_exact_source_retry_moves_consumption_to_new_operation(tmp_path):
    database = tmp_path / "consumption.sqlite3"
    ledger = TahsilatConsumptionLedger(database, company_id=1)
    source = _row(1000.0)
    ledger.consume([source], operation_id=10)

    retry_rows = ledger.available_rows([source], reusable_operation_ids=[10])
    assert retry_rows[0].tutar == 1000.0
    ledger.assert_can_consume(retry_rows, reusable_operation_ids=[10])
    ledger.replace_for_retry(
        retry_rows,
        operation_id=11,
        reusable_operation_ids=[10],
    )

    assert ledger.available_rows([source]) == []
    with ledger._connection() as connection:
        operation_ids = [
            row["operation_id"]
            for row in connection.execute(
                "SELECT operation_id FROM tahsilat_consumptions"
            )
        ]
    assert operation_ids == [11]


def test_retry_does_not_ignore_unrelated_operation_consumption(tmp_path):
    ledger = TahsilatConsumptionLedger(tmp_path / "consumption.sqlite3", company_id=1)
    source = _row(1000.0)
    ledger.consume([_row(600.0)], operation_id=10)

    available = ledger.available_rows([source], reusable_operation_ids=[99])
    assert available[0].tutar == 400.0
