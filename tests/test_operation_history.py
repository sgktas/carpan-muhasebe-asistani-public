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
