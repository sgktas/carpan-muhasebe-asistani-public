from app.core.operation_history import OperationHistory


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


def test_running_operation_is_recovered_as_interrupted(tmp_path):
    database = tmp_path / "operations.sqlite3"
    history = OperationHistory(database)
    operation_id = history.start("manim_transfer", "MANİM Aktarma", ["m.xlsx"])

    recovered = OperationHistory(database).recent()

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
