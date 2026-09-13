from __future__ import annotations

import json
import sqlite3

import pytest

from app.core import identity
from app.core.identity import IdentityStore
from app.core.operation_history import OperationHistory
from app.core.operation_read_model import (
    ATTENTION,
    CONSISTENT,
    HISTORY_PUBLICATION_MISMATCH,
    OUTPUT_MISSING,
    PROCESSED_SOURCE_MISSING,
    PUBLICATION_PENDING_COMMIT,
    RECOVERY_REQUIRED,
    REVIEW_PENDING,
    OperationReadModel,
)
from app.core.processed_files_log import ProcessedFilesLog
from app.core.publication_journal import PublicationJournal
from app.core.review_queue import ReviewMember, ReviewQueue
from app.core.review_workflow import ReviewWorkflow


SOURCE_HASH = "d" * 64


def _stores(tmp_path, *, company_id=7, user_id=11, lease_seconds=None, monkeypatch=None):
    if lease_seconds is not None:
        monkeypatch.setattr(OperationHistory, "LEASE_SECONDS", lease_seconds)
    data = tmp_path / "data"
    history = OperationHistory(
        data / "operations.sqlite3",
        company_id=company_id,
        user_id=user_id,
        instance_id="test-instance",
    )
    journal = PublicationJournal(
        data / "publication_journal.sqlite3", company_id=company_id,
    )
    queue = ReviewQueue(data / "operations.sqlite3", company_id=company_id)
    processed = ProcessedFilesLog(data / "processed_files.json")
    return data, history, journal, queue, processed


def _operation(tmp_path, history, *, status="SUCCESS"):
    source = tmp_path / "synthetic-source.xlsx"
    source.write_bytes(b"synthetic source")
    output = tmp_path / "synthetic-output.xlsx"
    output.write_bytes(b"synthetic output")
    operation_id = history.start("manim_transfer", "MANIM", [source])
    if status in {"SUCCESS", "PARTIAL"}:
        history.complete(operation_id, [output], status=status)
    return operation_id, source, output


def _publication(journal, operation_id, output, *, committed=True):
    publication_id = journal.publish(
        operation_id=operation_id,
        source_hashes=[SOURCE_HASH],
        output_dir=output.parent,
        output_files=[output],
    )
    if committed:
        journal.commit(publication_id)
    return publication_id


def _model(history, journal=None, queue=None, processed=None, workflow=None):
    return OperationReadModel(
        history,
        publication_journal=journal,
        review_queue=queue,
        review_workflow=workflow,
        processed_files=processed,
    )


def test_normal_successful_operation_is_consistent(tmp_path):
    _data, history, journal, queue, processed = _stores(tmp_path)
    operation_id, _source, output = _operation(tmp_path, history)
    publication_id = _publication(journal, operation_id, output)
    processed.mark_processed(SOURCE_HASH, "synthetic-source.xlsx", 1)

    view = _model(history, journal, queue, processed).get_operation_view(operation_id)

    assert view.history_status == "SUCCESS"
    assert view.publication_status == "COMMITTED"
    assert view.publication_id == publication_id
    assert view.publication_output_files == (str(output),)
    assert view.open_review_group_count == 0
    assert view.pending_review_count == 0
    assert view.processed_source_state == "ALL_PROCESSED"
    assert view.output_presence_state == "PRESENT"
    assert view.consistency_status == CONSISTENT
    assert view.attention_reasons == ()


def test_committed_and_interrupted_raw_states_are_preserved(tmp_path, monkeypatch):
    data, history, journal, queue, processed = _stores(
        tmp_path, lease_seconds=-1, monkeypatch=monkeypatch,
    )
    operation_id, _source, output = _operation(tmp_path, history, status="RUNNING")
    _publication(journal, operation_id, output)
    processed.mark_processed(SOURCE_HASH, "synthetic-source.xlsx", 1)
    restarted = OperationHistory(
        data / "operations.sqlite3",
        company_id=7,
        user_id=11,
        instance_id="restarted-instance",
    )

    view = _model(restarted, journal, queue, processed).get_operation_view(operation_id)

    assert view.history_status == "INTERRUPTED"
    assert view.publication_status == "COMMITTED"
    assert view.consistency_status == ATTENTION
    assert HISTORY_PUBLICATION_MISMATCH in view.attention_reasons


def test_published_operation_requires_recovery_without_hiding_history(tmp_path):
    _data, history, journal, queue, processed = _stores(tmp_path)
    operation_id, _source, output = _operation(tmp_path, history, status="RUNNING")
    _publication(journal, operation_id, output, committed=False)

    view = _model(history, journal, queue, processed).get_operation_view(operation_id)

    assert view.history_status == "RUNNING"
    assert view.publication_status == "PUBLISHED"
    assert view.consistency_status == RECOVERY_REQUIRED
    assert PUBLICATION_PENDING_COMMIT in view.attention_reasons


def test_open_review_group_and_workflow_phase_are_visible(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "PASSWORD_ITERATIONS", 1000)
    identity_store = IdentityStore(tmp_path / "identity.sqlite3")
    admin = identity_store.create_initial_admin(
        "Synthetic Company", "admin", "Synthetic Administrator", "Guvenli1234",
    )
    _data, history, journal, queue, processed = _stores(
        tmp_path, company_id=admin.company_id, user_id=admin.user_id,
    )
    operation_id, source, output = _operation(tmp_path, history, status="PARTIAL")
    _publication(journal, operation_id, output)
    processed.mark_processed(SOURCE_HASH, source.name, 1)
    group_id = queue.enqueue(
        [
            ReviewMember(
                source.name, 2, 10.0, "TEST-REGION", "TEST-BANK",
                "Synthetic review", SOURCE_HASH, "SyntheticSheet",
            )
        ],
        operation_id=operation_id,
    )
    workflow = ReviewWorkflow(queue, identity_store, admin)

    view = _model(
        history, journal, queue, processed, workflow,
    ).get_operation_view(operation_id)

    assert view.reviews[0].group_id == group_id
    assert view.reviews[0].status == "OPEN"
    assert view.reviews[0].phase == "OPEN"
    assert view.open_review_group_count == 1
    assert view.pending_review_count == 1
    assert REVIEW_PENDING in view.attention_reasons
    assert view.consistency_status == ATTENTION


def test_company_scope_never_exposes_another_company_operation(tmp_path):
    data, company_a, journal_a, queue_a, processed_a = _stores(
        tmp_path, company_id=7, user_id=11,
    )
    operation_id, _source, output = _operation(tmp_path, company_a)
    _publication(journal_a, operation_id, output)
    processed_a.mark_processed(SOURCE_HASH, "synthetic-source.xlsx", 1)
    model = _model(company_a, journal_a, queue_a, processed_a)

    assert model.get_operation_view(operation_id, company_id=8) is None
    company_b = OperationHistory(data / "operations.sqlite3", company_id=8, user_id=12)
    journal_b = PublicationJournal(
        data / "publication_journal.sqlite3", company_id=8,
    )
    queue_b = ReviewQueue(data / "operations.sqlite3", company_id=8)
    assert _model(company_b, journal_b, queue_b).get_operation_view(operation_id) is None


def test_cross_company_store_configuration_is_rejected(tmp_path):
    data, history, _journal, _queue, _processed = _stores(tmp_path, company_id=7)
    wrong_journal = PublicationJournal(
        data / "publication_journal.sqlite3", company_id=8,
    )
    with pytest.raises(ValueError, match="different company"):
        OperationReadModel(history, publication_journal=wrong_journal)


def test_history_only_operation_is_still_represented(tmp_path):
    _data, history, _journal, _queue, _processed = _stores(tmp_path)
    operation_id, _source, output = _operation(tmp_path, history)

    view = OperationReadModel(history).get_operation_view(operation_id)

    assert view.history_status == "SUCCESS"
    assert view.history_output_files == (str(output),)
    assert view.publications == ()
    assert view.reviews == ()
    assert view.processed_source_state == "NO_SOURCES"
    assert view.consistency_status == CONSISTENT


def test_missing_physical_output_is_an_explicit_attention_reason(tmp_path):
    _data, history, journal, queue, processed = _stores(tmp_path)
    operation_id, _source, output = _operation(tmp_path, history)
    _publication(journal, operation_id, output)
    processed.mark_processed(SOURCE_HASH, "synthetic-source.xlsx", 1)
    output.unlink()

    view = _model(history, journal, queue, processed).get_operation_view(operation_id)

    assert view.history_status == "SUCCESS"
    assert view.publication_status == "COMMITTED"
    assert view.output_presence_state == "MISSING"
    assert OUTPUT_MISSING in view.attention_reasons
    assert view.consistency_status == ATTENTION


def test_committed_publication_with_unmarked_source_is_visible(tmp_path):
    _data, history, journal, queue, processed = _stores(tmp_path)
    operation_id, _source, output = _operation(tmp_path, history)
    _publication(journal, operation_id, output)

    view = _model(history, journal, queue, processed).get_operation_view(operation_id)

    assert view.processed_source_state == "NONE_PROCESSED"
    assert PROCESSED_SOURCE_MISSING in view.attention_reasons
    assert view.consistency_status == ATTENTION


def test_missing_or_null_operation_identity_has_stable_no_result(tmp_path):
    _data, history, journal, queue, processed = _stores(tmp_path)
    output = tmp_path / "orphan-output.xlsx"
    output.write_bytes(b"orphan")
    journal.publish(
        operation_id=None,
        source_hashes=[SOURCE_HASH],
        output_dir=tmp_path,
        output_files=[output],
    )
    model = _model(history, journal, queue, processed)

    assert model.get_operation_view(None) is None
    assert model.get_operation_view(999_999) is None


def test_read_model_does_not_mutate_any_store(tmp_path):
    data, history, journal, queue, processed = _stores(tmp_path)
    operation_id, source, output = _operation(tmp_path, history, status="PARTIAL")
    _publication(journal, operation_id, output, committed=False)
    processed.mark_processed(SOURCE_HASH, source.name, 1)
    queue.enqueue(
        [ReviewMember(source.name, 2, 10.0, "TEST-REGION", "TEST-BANK", "Review")],
        operation_id=operation_id,
    )

    def snapshot():
        with sqlite3.connect(data / "operations.sqlite3") as connection:
            operation_rows = connection.execute(
                "SELECT id, status FROM operations ORDER BY id"
            ).fetchall()
            review_rows = connection.execute(
                "SELECT group_id, status, version FROM review_queue_groups ORDER BY group_id"
            ).fetchall()
        publications = tuple(
            (item.publication_id, item.status)
            for item in journal.list(status=None)
        )
        processed_payload = json.loads(
            (data / "processed_files.json").read_text(encoding="utf-8")
        )
        return operation_rows, review_rows, publications, processed_payload

    before = snapshot()
    view = _model(history, journal, queue, processed).get_operation_view(operation_id)
    after = snapshot()

    assert view is not None
    assert after == before


def test_legacy_operation_remains_visible_through_read_model(tmp_path):
    database = tmp_path / "operations.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id TEXT NOT NULL,
                module_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                input_files_json TEXT NOT NULL DEFAULT '[]',
                output_files_json TEXT NOT NULL DEFAULT '[]',
                summary_json TEXT NOT NULL DEFAULT '{}',
                error_message TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO operations(
                module_id, module_name, status, started_at, completed_at
            ) VALUES ('manim_transfer', 'MANIM', 'SUCCESS', ?, ?)
            """,
            ("2026-01-01T00:00:00+00:00", "2026-01-01T00:01:00+00:00"),
        )
    history = OperationHistory(database, company_id=7, user_id=11)

    view = OperationReadModel(history).get_operation_view(1)

    assert view is not None
    assert view.company_id == 7
    assert view.history_status == "SUCCESS"
    assert view.consistency_status == CONSISTENT

