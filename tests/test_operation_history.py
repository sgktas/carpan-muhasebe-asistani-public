import pytest

from app.core.operation_history import (
    DecisionAuditError,
    OperationHistory,
    OperationHistoryError,
)


def test_operation_history_records_success_and_failure(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3", actor="Semih")

    success_id = history.start("report_editing", "FOM Rapor Düzenleme", ["a.xlsx"])
    history.complete(success_id, ["out.xlsx"], {"created_file_count": 1})

    failed_id = history.start("manim_transfer", "MANİM Aktarma", ["m.xlsx"])
    history.fail(failed_id, "test error")

    records = history.recent()
    assert records[0].id == failed_id
    assert records[0].status == "FAILED"
    assert records[0].error_message == "test error"
    assert records[1].id == success_id
    assert records[1].status == "SUCCESS"
    assert records[1].actor == "Semih"
    assert records[1].output_files == ["out.xlsx"]
    assert [event.code for event in history.events(success_id)] == [
        "OPERATION_STARTED",
        "OPERATION_COMPLETED",
    ]
    assert [event.code for event in history.events(failed_id)] == [
        "OPERATION_STARTED",
        "OPERATION_FAILED",
    ]


def test_second_history_instance_does_not_interrupt_a_live_operation(tmp_path):
    database = tmp_path / "operations.sqlite3"
    history = OperationHistory(database)
    operation_id = history.start("manim_transfer", "MANİM Aktarma", ["m.xlsx"])

    recovered = OperationHistory(database).recent()

    record = next(item for item in recovered if item.id == operation_id)
    assert record.status == "RUNNING"
    assert record.completed_at is None


def test_expired_operation_is_recovered_as_interrupted(tmp_path):
    database = tmp_path / "operations.sqlite3"
    history = OperationHistory(database, company_id=1, instance_id="first")
    operation_id = history.start("manim_transfer", "MANİM Aktarma", ["m.xlsx"])
    with history._connect() as connection:
        connection.execute("UPDATE operations SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE id = ?", (operation_id,))

    recovered = OperationHistory(database, company_id=1, instance_id="second").recent()

    record = next(item for item in recovered if item.id == operation_id)
    assert record.status == "INTERRUPTED"
    assert record.completed_at is not None


def test_operation_history_records_company_and_user_identity(tmp_path):
    history = OperationHistory(
        tmp_path / "operations.sqlite3",
        actor="Test Kullanıcı",
        company_id=12,
        user_id=34,
    )

    operation_id = history.start("manim_transfer", "MANİM Aktarma", ["a.xlsx"])
    history.complete(operation_id, ["out.xls"])

    record = history.recent()[0]
    assert record.company_id == 12
    assert record.user_id == 34
    assert record.actor == "Test Kullanıcı"


def test_operation_history_is_scoped_to_company(tmp_path):
    database = tmp_path / "operations.sqlite3"
    first = OperationHistory(database, company_id=1, user_id=10)
    first_id = first.start("manim_transfer", "MANİM", ["first.xlsx"])
    first.complete(first_id, ["first.xls"])

    second = OperationHistory(database, company_id=2, user_id=20)
    second_id = second.start("report_editing", "FOM", ["second.xlsx"])
    second.complete(second_id, ["second.xls"])

    assert [record.id for record in first.recent()] == [first_id]
    assert [record.id for record in second.recent()] == [second_id]
    assert second.events(first_id) == []


def test_first_company_claims_legacy_operation_history(tmp_path):
    database = tmp_path / "operations.sqlite3"
    legacy = OperationHistory(database)
    operation_id = legacy.start("manim_transfer", "MANİM", ["legacy.xlsx"])
    legacy.complete(operation_id, ["legacy.xls"])

    company_history = OperationHistory(database, company_id=7, user_id=8)

    assert company_history.recent()[0].company_id == 7


def test_other_company_cannot_change_or_add_event_to_an_operation(tmp_path):
    database = tmp_path / "operations.sqlite3"
    first = OperationHistory(database, company_id=1, user_id=10, instance_id="first")
    operation_id = first.start("manim_transfer", "MANİM", ["first.xlsx"])
    second = OperationHistory(database, company_id=2, user_id=20, instance_id="second")

    for operation in (
        lambda: second.complete(operation_id, ["wrong.xls"]),
        lambda: second.fail(operation_id, "wrong"),
        lambda: second.add_event(operation_id, "WRONG", "wrong"),
        lambda: second.heartbeat(operation_id),
    ):
        with pytest.raises(OperationHistoryError):
            operation()
    assert first.recent()[0].status == "RUNNING"
    assert [event.code for event in first.events(operation_id)] == ["OPERATION_STARTED"]


def test_unscoped_or_different_user_instance_cannot_take_a_firm_operation(tmp_path):
    database = tmp_path / "operations.sqlite3"
    owner = OperationHistory(
        database,
        company_id=7,
        user_id=41,
        instance_id="shared-instance-id",
    )
    operation_id = owner.start("manim_transfer", "MANİM", ["movement.xlsx"])

    # Aynı sahiplik kimliği taklit edilse bile kimliği olmayan eski istemci
    # ya da aynı firmadaki başka kullanıcı çalışan kaydı değiştiremez.
    unscoped = OperationHistory(database, instance_id="shared-instance-id")
    other_user = OperationHistory(
        database,
        company_id=7,
        user_id=42,
        instance_id="shared-instance-id",
    )
    for history in (unscoped, other_user):
        with pytest.raises(OperationHistoryError):
            history.complete(operation_id, ["wrong.xls"])
        with pytest.raises(OperationHistoryError):
            history.add_event(operation_id, "WRONG", "wrong")

    assert unscoped.recent() == []
    assert unscoped.events(operation_id) == []
    assert owner.recent()[0].status == "RUNNING"


def test_unscoped_instance_cannot_interrupt_expired_firm_operation(tmp_path):
    database = tmp_path / "operations.sqlite3"
    owner = OperationHistory(database, company_id=7, user_id=41, instance_id="owner")
    operation_id = owner.start("manim_transfer", "MANİM", ["movement.xlsx"])
    with owner._connect() as connection:
        connection.execute(
            "UPDATE operations SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
            (operation_id,),
        )

    OperationHistory(database, instance_id="legacy").recent()

    with owner._connect() as connection:
        record = connection.execute(
            "SELECT status FROM operations WHERE id = ?", (operation_id,)
        ).fetchone()
    assert record["status"] == "RUNNING"


def test_terminal_operation_cannot_be_rewritten_or_receive_new_events(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3", company_id=1, instance_id="only")
    operation_id = history.start("manim_transfer", "MANİM", ["first.xlsx"])
    history.complete(operation_id, ["first.xls"])

    for operation in (
        lambda: history.complete(operation_id, ["second.xls"]),
        lambda: history.fail(operation_id, "wrong"),
        lambda: history.add_event(operation_id, "LATE", "wrong"),
        lambda: history.heartbeat(operation_id),
    ):
        with pytest.raises(OperationHistoryError):
            operation()
    record = history.recent()[0]
    assert record.status == "SUCCESS"
    assert record.output_files == ["first.xls"]


def test_decision_audit_is_normalized_and_scoped_to_running_operation(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3", company_id=4, user_id=9)
    operation_id = history.start("manim_transfer", "MANİM", ["movement.xlsx"])

    history.add_decision(
        operation_id,
        decision="route",
        outcome="review",
        region="Antalya",
        bank="Akbank",
        amount=7329.641,
        source_file="C:/incoming/movement.xlsx",
        source_row=17,
        rule_code="missing_bank_account_code",
        reason="BM kodu eksik",
    )

    event = history.events(operation_id)[-1]
    assert event.code == "DECISION_AUDIT"
    assert event.message == "ROUTE → REVIEW"
    assert event.details == {
        "decision": "ROUTE",
        "outcome": "REVIEW",
        "region": "ANTALYA",
        "bank": "AKBANK",
        "amount": 7329.64,
        "source_file": "C:/incoming/movement.xlsx",
        "source_row": 17,
        "rule_code": "MISSING_BANK_ACCOUNT_CODE",
        "reason": "BM kodu eksik",
    }

    with pytest.raises(DecisionAuditError):
        history.add_decision(
            operation_id,
            decision="route",
            outcome="review",
            region="Antalya",
            bank="Akbank",
            amount=1,
            source_file="movement.xlsx",
            source_row=0,
            rule_code="rule",
        )
