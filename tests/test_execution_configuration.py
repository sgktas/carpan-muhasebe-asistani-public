from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3

import pytest

from app.core.execution_configuration import ConfigurationSnapshot
from app.core.operation_history import OperationHistory, OperationHistoryError


def settings(code="TEST-01"):
    return ConfigurationSnapshot.create("manim_transfer", {
        "regions": {"TEST": {"banka_kodlari": {"TESTBANK": code}}},
    })


def start(history, snapshot):
    return history.start("manim_transfer", "MANİM", ["synthetic.xlsx"], configuration=snapshot)


def test_snapshot_cannot_be_changed_through_source_or_returned_payload():
    payload = {"regions": {"TEST": {"codes": ["TEST-01"]}}}
    snapshot = ConfigurationSnapshot.create("manim_transfer", payload)
    fingerprint = snapshot.fingerprint
    payload["regions"]["TEST"]["codes"].append("CHANGED")
    snapshot.payload()["regions"]["TEST"]["codes"].clear()
    assert snapshot.payload()["regions"]["TEST"]["codes"] == ["TEST-01"]
    assert snapshot.fingerprint == fingerprint


def test_same_settings_reuse_version_and_changes_preserve_previous_run(tmp_path):
    path = tmp_path / "operations.sqlite3"
    history = OperationHistory(path, company_id=1, user_id=10)
    first = start(history, settings())
    history.complete(first, [])
    second = start(history, settings())
    third = start(history, settings("TEST-02"))
    restored = start(history, settings())
    reopened = OperationHistory(path, company_id=1, user_id=10)
    assert [reopened.configuration(item).revision for item in (first, second, third, restored)] == [1, 1, 2, 1]
    assert reopened.configuration(first).snapshot == settings()
    assert reopened.configuration(third).snapshot == settings("TEST-02")
    event = next(event for event in history.events(first) if event.code == "CONFIGURATION_CAPTURED")
    assert event.details == {"revision": 1, "fingerprint": settings().fingerprint}
    assert "TESTBANK" not in json.dumps(event.details)


def test_company_scope_is_enforced_and_versions_are_independent(tmp_path):
    path = tmp_path / "operations.sqlite3"
    first = OperationHistory(path, company_id=1, user_id=10)
    second = OperationHistory(path, company_id=2, user_id=20)
    first_id = start(first, settings())
    start(first, settings("TEST-02"))
    second_id = start(second, settings("TEST-02"))
    assert second.configuration(first_id) is None
    assert first.configuration(second_id) is None
    assert second.configuration(second_id).revision == 1
    assert OperationHistory(path).configuration(first_id) is None
    # Company colleagues can view evidence, like existing operation history.
    colleague = OperationHistory(path, company_id=1, user_id=11)
    assert colleague.configuration(first_id).snapshot == settings()


def test_wrong_module_cannot_start_an_operation(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3")
    with pytest.raises(OperationHistoryError, match="modüle"):
        history.start("report_editing", "FOM", [], configuration=settings())
    assert history.recent() == []


def test_binding_failure_rolls_back_operation_and_version_together(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3", company_id=1)
    with history._connect() as connection:
        connection.execute("""
            CREATE TRIGGER fail_binding BEFORE INSERT ON operation_configurations
            BEGIN SELECT RAISE(ABORT, 'test disk failure'); END
        """)
    with pytest.raises(sqlite3.IntegrityError, match="test disk failure"):
        start(history, settings())
    assert history.recent() == []
    with history._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM operation_configuration_versions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM operation_events").fetchone()[0] == 0


@pytest.mark.parametrize("identical", [True, False])
def test_concurrent_starts_allocate_versions_without_duplicates(tmp_path, identical):
    path = tmp_path / "operations.sqlite3"
    histories = [OperationHistory(path, company_id=1, user_id=index + 1) for index in range(8)]

    def execute(index):
        snapshot = settings("TEST" if identical else f"TEST-{index}")
        operation_id = start(histories[index], snapshot)
        return histories[index].configuration(operation_id)

    with ThreadPoolExecutor(max_workers=8) as pool:
        revisions = list(pool.map(execute, range(8)))
    assert sorted(item.revision for item in revisions) == ([1] * 8 if identical else list(range(1, 9)))
    assert len(histories[0].recent()) == 8


def test_corrupt_version_is_detected_on_read_and_reuse(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3")
    operation_id = start(history, settings())
    with history._connect() as connection:
        connection.execute("UPDATE operation_configuration_versions SET payload_json = '{}' ")
    with pytest.raises(OperationHistoryError, match="bütünlüğü"):
        history.configuration(operation_id)
    with pytest.raises(ValueError, match="bütünlüğü"):
        start(history, settings())
    assert len(history.recent()) == 1


def test_old_operations_remain_readable_after_migration(tmp_path):
    path = tmp_path / "operations.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("""
            CREATE TABLE operations (
                id INTEGER PRIMARY KEY, module_id TEXT, module_name TEXT, status TEXT,
                started_at TEXT, completed_at TEXT, input_files_json TEXT DEFAULT '[]',
                output_files_json TEXT DEFAULT '[]', summary_json TEXT DEFAULT '{}', error_message TEXT
            )
        """)
        connection.execute("""
            INSERT INTO operations(id, module_id, module_name, status, started_at)
            VALUES (1, 'manim_transfer', 'MANİM', 'SUCCESS', '2026-01-01')
        """)
    history = OperationHistory(path, company_id=1)
    assert history.configuration(1) is None
    assert history.recent()[0].status == "SUCCESS"
    assert history.configuration(start(history, settings())).revision == 1
    with history._connect() as connection:
        assert connection.execute("SELECT version FROM operation_schema_migrations").fetchall()[0][0] == 1
