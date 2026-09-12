"""Large operational logs, atomic history batches, and repeated local jobs."""
import os
import sqlite3
import time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QThread
from PySide6.QtWidgets import QApplication
from app.ui.operation_activity import OperationActivity
from app.ui.local_task import LocalTask
from app.core.operation_history import OperationHistory, OperationHistoryError, DecisionAuditError

app = QApplication.instance() or QApplication([])


def wait_finished(task):
    deadline = time.monotonic() + 5
    while task.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.001)
    assert not task.busy
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_large_log_keeps_all_records_search_counts_and_copy():
    view = OperationActivity()
    messages = [f"{'HATA:' if i % 100 == 0 else 'UYARI:' if i % 10 == 0 else 'Bilgi:'} Satır {i}" for i in range(20000)]
    view.append_many(messages)
    assert view.model.rowCount() == 20000
    assert "1,800 uyarı" in view.counts.text()
    assert "200 hata" in view.counts.text()
    view.level.setCurrentText("Hata")
    assert view.proxy.rowCount() == 200
    view.search.setText("Satır 19900")
    assert view.proxy.rowCount() == 1
    assert view.toPlainText().splitlines() == messages
    view.clear()
    view.append("UYARI: Yeni işlem")
    assert "1 uyarı" in view.counts.text() and "0 hata" in view.counts.text()
    view.deleteLater()


def test_repeated_jobs_release_threads_and_do_not_overlap_callbacks():
    task = LocalTask()
    results, errors, nested = [], [], []
    task.succeeded.connect(results.append)
    task.failed.connect(errors.append)
    task.succeeded.connect(lambda _: nested.append(task.start(lambda: "overlap")))
    def failure():
        raise ValueError("demo")
    for index in range(40):
        assert task.start(failure if index % 2 else lambda index=index: index)
        wait_finished(task)
    assert results == list(range(0, 40, 2))
    assert len(errors) == 20
    assert nested == [False] * 20
    assert task.findChildren(QThread) == []
    task.deleteLater()


def test_large_event_batch_preserves_order_and_owner_scope(tmp_path):
    history = OperationHistory(tmp_path / "history.db", company_id=1, user_id=1)
    operation = history.start("demo", "Demo", [])
    history.add_events(operation, [{"code": "PROCESS_LOG", "message": f"Satır {i}"} for i in range(5000)])
    messages = [e.message for e in history.events(operation) if e.code == "PROCESS_LOG"]
    assert messages == [f"Satır {i}" for i in range(5000)]
    foreign = OperationHistory(tmp_path / "history.db", company_id=2, user_id=1)
    with pytest.raises(OperationHistoryError):
        foreign.add_events(operation, [{"code": "TEST", "message": "yabancı"}])
    history.complete(operation, [])
    with pytest.raises(OperationHistoryError):
        history.add_events(operation, [{"code": "TEST", "message": "geç"}])


def test_batch_disk_failure_rolls_back_earlier_rows(tmp_path):
    history = OperationHistory(tmp_path / "history.db")
    operation = history.start("demo", "Demo", [])
    before = len(history.events(operation))
    with history._connect() as connection:
        connection.execute("CREATE TRIGGER fail_batch BEFORE INSERT ON operation_events WHEN NEW.code='FAIL' BEGIN SELECT RAISE(ABORT,'disk failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        history.add_events(operation, [{"code": "GOOD", "message": "a"}, {"code": "FAIL", "message": "b"}])
    assert len(history.events(operation)) == before


def test_invalid_decision_batch_is_not_partially_written(tmp_path):
    history = OperationHistory(tmp_path / "history.db")
    operation = history.start("demo", "Demo", [])
    decision = dict(decision="MATCH", outcome="HAVALE", region="AYDIN", bank="GARANTI", amount=25, source_file="demo", source_row=1, rule_code="RULE")
    with pytest.raises(DecisionAuditError):
        history.add_decisions(operation, [decision, {**decision, "source_row": 0}])
    assert not [e for e in history.events(operation) if e.code == "DECISION_AUDIT"]
    history.add_decisions(operation, [decision, {**decision, "source_row": 2}])
    assert len([e for e in history.events(operation) if e.code == "DECISION_AUDIT"]) == 2
