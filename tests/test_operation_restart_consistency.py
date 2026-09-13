from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core import identity
from app.core.identity import IdentityStore
from app.core.operation_history import OperationHistory
from app.core.processed_files_log import ProcessedFilesLog
from app.core.publication_journal import PublicationJournal
from app.core.review_queue import ReviewMember, ReviewQueue
from app.core.review_workflow import ReviewWorkflow
from app.core.tahsilat_consumption_ledger import TahsilatConsumptionLedger
from app.models.records import TahsilatRecord
from app.ui.operation_center_page import OperationCenterPage


_APP = QApplication.instance() or QApplication([])
SOURCE_HASH = "c" * 64


def _review_action(workflow, group_id, action, **kwargs):
    task = next(task for task in workflow.list() if task.group.group_id == group_id)
    workflow.act(group_id, action, expected_version=task.group.version, **kwargs)


def test_committed_publication_can_coexist_with_recovered_interrupted_history(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(OperationHistory, "LEASE_SECONDS", -1)
    operations_database = tmp_path / "operations.sqlite3"
    history = OperationHistory(
        operations_database, company_id=7, user_id=11, instance_id="first-instance",
    )
    source = tmp_path / "synthetic-source.xlsx"
    source.write_bytes(b"source")
    output = tmp_path / "synthetic-output.xlsx"
    output.write_bytes(b"output")
    operation_id = history.start("manim_transfer", "MANIM", [source])

    journal = PublicationJournal(
        tmp_path / "publication_journal.sqlite3", company_id=7,
    )
    publication_id = journal.publish(
        operation_id=operation_id,
        source_hashes=[SOURCE_HASH],
        output_dir=tmp_path,
        output_files=[output],
    )
    journal.commit(publication_id)

    restarted = OperationHistory(
        operations_database, company_id=7, user_id=11, instance_id="second-instance",
    )
    record = restarted.recent()[0]
    assert record.id == operation_id
    assert record.status == "INTERRUPTED"
    assert journal.list(status="PUBLISHED") == ()
    committed = journal.list(status="COMMITTED")
    assert len(committed) == 1
    assert committed[0].operation_id == operation_id


def test_operation_center_exposes_divergent_history_publication_and_review_state(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(identity, "PASSWORD_ITERATIONS", 1000)
    monkeypatch.setattr(OperationHistory, "LEASE_SECONDS", -1)
    identity_store = IdentityStore(tmp_path / "identity.sqlite3")
    admin = identity_store.create_initial_admin(
        "Synthetic Company", "admin", "Synthetic Administrator", "Guvenli1234",
    )
    operations_database = tmp_path / "operations.sqlite3"
    history = OperationHistory(
        operations_database,
        company_id=admin.company_id,
        user_id=admin.user_id,
        instance_id="first-instance",
    )
    source = tmp_path / "synthetic-source.xlsx"
    source.write_bytes(b"source")
    output = tmp_path / "synthetic-output.xlsx"
    output.write_bytes(b"output")
    operation_id = history.start("manim_transfer", "MANIM", [source])

    journal = PublicationJournal(
        tmp_path / "publication_journal.sqlite3", company_id=admin.company_id,
    )
    journal.publish(
        operation_id=operation_id,
        source_hashes=[SOURCE_HASH],
        output_dir=tmp_path,
        output_files=[output],
    )
    queue = ReviewQueue(operations_database, company_id=admin.company_id)
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
    _review_action(workflow, group_id, "claim")
    _review_action(workflow, group_id, "start")

    restarted = OperationHistory(
        operations_database,
        company_id=admin.company_id,
        user_id=admin.user_id,
        instance_id="second-instance",
    )
    page = OperationCenterPage(
        restarted, identity_store=identity_store, session=admin,
    )
    page.refresh()

    assert restarted.recent()[0].status == "INTERRUPTED"
    assert len(page._pending_publications) == 1
    assert page._pending_publications[0].status == "PUBLISHED"
    assert page.recovery_table.rowCount() == 1
    assert page.recovery_table.item(0, 3).text() == "Kurtarma gerekli"
    review_task = next(
        task for task in page.review_board.tasks
        if task.group.group_id == group_id
    )
    assert review_task.phase == "IN_REVIEW"
    assert any(record.id == operation_id for record in page._attention_records)
    page.deleteLater()


def test_existing_legacy_operation_database_remains_readable(tmp_path):
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
                module_id, module_name, status, started_at, completed_at,
                input_files_json, output_files_json, summary_json
            ) VALUES (?, ?, 'SUCCESS', ?, ?, ?, ?, ?)
            """,
            (
                "manim_transfer", "MANIM", "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:01:00+00:00",
                json.dumps(["synthetic-source.xlsx"]),
                json.dumps(["synthetic-output.xlsx"]),
                json.dumps({"unresolved": 0}),
            ),
        )

    records = OperationHistory(database, company_id=7, user_id=11).recent()
    assert len(records) == 1
    assert records[0].status == "SUCCESS"
    assert records[0].company_id == 7
    assert records[0].input_files == ["synthetic-source.xlsx"]


def test_existing_publication_database_remains_readable(tmp_path):
    database = tmp_path / "publication_journal.sqlite3"
    published_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE manim_publications (
                publication_id TEXT PRIMARY KEY,
                company_id INTEGER,
                operation_id INTEGER,
                status TEXT NOT NULL,
                source_hashes_json TEXT NOT NULL,
                output_dir TEXT NOT NULL,
                output_files_json TEXT NOT NULL,
                published_at TEXT NOT NULL,
                committed_at TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO manim_publications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "synthetic-publication", 7, 41, "PUBLISHED",
                json.dumps([SOURCE_HASH]), str(tmp_path),
                json.dumps([str(tmp_path / "synthetic-output.xlsx")]),
                published_at, None,
            ),
        )

    entries = PublicationJournal(database, company_id=7).list(status="PUBLISHED")
    assert len(entries) == 1
    assert entries[0].publication_id == "synthetic-publication"
    assert entries[0].source_hashes == (SOURCE_HASH,)


def test_existing_consumption_database_remains_readable(tmp_path):
    database = tmp_path / "tahsilat_consumption.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE tahsilat_consumptions (
                company_id INTEGER,
                source_hash TEXT NOT NULL,
                source_sheet TEXT NOT NULL,
                source_row INTEGER NOT NULL,
                operation_id INTEGER,
                amount_cents INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO tahsilat_consumptions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                7, SOURCE_HASH, "SyntheticSheet", 2, 41, 12550,
                "2026-01-01T00:00:00+00:00",
            ),
        )
    row = TahsilatRecord(
        "TEST-CUSTOMER", "Synthetic Customer", None, 125.50,
        source_hash=SOURCE_HASH,
        source_sheet="SyntheticSheet",
        source_row=2,
        source_amount=125.50,
    )
    ledger = TahsilatConsumptionLedger(database, company_id=7)
    balance = ledger.balances([row])[0]
    assert balance.consumed_amount == 125.50
    assert balance.remaining_amount == 0.0


def test_existing_processed_files_json_remains_readable(tmp_path):
    path = tmp_path / "processed_files.json"
    path.write_text(
        json.dumps(
            {
                SOURCE_HASH: {
                    "dosya_adi": "synthetic-source.xlsx",
                    "tarih": "2026-01-01 00:00:00",
                    "kayit_sayisi": 3,
                }
            }
        ),
        encoding="utf-8",
    )

    record = ProcessedFilesLog(path).is_processed(SOURCE_HASH)
    assert record == {
        "dosya_adi": "synthetic-source.xlsx",
        "tarih": "2026-01-01 00:00:00",
        "kayit_sayisi": 3,
    }
