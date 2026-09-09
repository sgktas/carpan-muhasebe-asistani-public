import pytest

from app.core.financial_ledger import FinancialMovementError, financial_movement_from_decision
from app.core.operation_history import OperationHistory


def _decision(**overrides) -> dict:
    payload = {
        "decision": "MATCH",
        "outcome": "HAVALE",
        "region": "ANTALYA",
        "bank": "GARANTI",
        "amount": 7329.64,
        "source_file": "C:/incoming/antalya.xlsx",
        "source_row": 17,
        "rule_code": "AUTOMATIC_CUSTOMER_MATCH",
    }
    return {**payload, **overrides}


def test_financial_movement_normalizes_only_safe_decision_fields():
    movement = financial_movement_from_decision(
        _decision(source_file="C:/private/antalya.xlsx", amount=100.129)
    )

    assert movement.source_file == "antalya.xlsx"
    assert movement.amount == 100.13
    assert movement.region == "ANTALYA"

    with pytest.raises(FinancialMovementError):
        financial_movement_from_decision(_decision(source_row=0))


def test_completed_operation_records_company_scoped_financial_movements(tmp_path):
    output = tmp_path / "aktarim.xls"
    output.write_bytes(b"output")
    first = OperationHistory(tmp_path / "operations.sqlite3", company_id=1, user_id=2)
    operation_id = first.start("manim_transfer", "MANİM", ["girdi.xlsx"])

    first.complete(operation_id, [output], financial_movements=[_decision()])

    movements = first.financial_movements(operation_id)
    assert len(movements) == 1
    assert movements[0].amount == 7329.64
    assert movements[0].source_file == "antalya.xlsx"
    assert first.recent()[0].summary["financial_movement_count"] == 1
    assert first.events(operation_id)[-2].code == "FINANCIAL_LEDGER_RECORDED"

    second = OperationHistory(tmp_path / "operations.sqlite3", company_id=2, user_id=3)
    assert second.financial_movements(operation_id) == []
