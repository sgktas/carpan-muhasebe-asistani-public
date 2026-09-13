from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest

from app.core.customer_list_cache import CustomerListCache
from app.core.mapping_store import MappingStore
from app.core.processed_files_log import ProcessedFilesLog
from app.core.processing_engine import ProcessingEngine
from app.core.publication_journal import PublicationJournal, PublicationRecoveryRequired
from app.core.review_queue import ReviewMember, ReviewQueue
from app.core.tahsilat_consumption_ledger import (
    TahsilatConsumptionError,
    TahsilatConsumptionLedger,
)
from app.models.records import TahsilatRecord


SOURCE_HASH = "a" * 64
MAPPING_KEY = "SYNTHETIC MANUAL DESCRIPTION"
MAPPING_VALUE = "TEST-CUSTOMER"


def _raise_at(stage: str):
    def fail(*_args, **_kwargs):
        raise RuntimeError(f"injected failure: {stage}")

    return fail


def _environment(tmp_path, *, operation_id=41, review_group_count=1):
    data_root = tmp_path / "workspace"
    state_dir = data_root / "data"
    state_dir.mkdir(parents=True)
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    output_file = output_dir / "synthetic-output.xlsx"
    output_file.write_bytes(b"synthetic output")
    customer_file = tmp_path / "synthetic-customers.xlsx"
    customer_file.write_bytes(b"synthetic customer fixture")

    engine = object.__new__(ProcessingEngine)
    engine.data_root = data_root
    engine.company_id = 7
    engine.operation_id = operation_id
    result = SimpleNamespace(
        output_dir=output_dir,
        created_files=[output_file],
        review_queue_groups=0,
        consumed_tahsilat_rows=0,
        logs=[],
    )
    journal = PublicationJournal(
        state_dir / "publication_journal.sqlite3", company_id=7,
    )
    processed = ProcessedFilesLog(state_dir / "processed_files.json")
    ledger = TahsilatConsumptionLedger(
        state_dir / "tahsilat_consumption.sqlite3", company_id=7,
    )
    cache = CustomerListCache(data_root)
    mappings = MappingStore(state_dir / "customer_mappings.json")
    receipt = TahsilatRecord(
        "TEST-CUSTOMER", "Synthetic Customer", None, 125.50,
        source_hash=SOURCE_HASH,
        source_sheet="SyntheticSheet",
        source_row=2,
        source_amount=125.50,
    )
    review_groups = [
        [
            ReviewMember(
                f"synthetic-{index}.xlsx", index + 2, 125.50,
                "TEST-REGION", "TEST-BANK", "Synthetic review",
                SOURCE_HASH, "SyntheticSheet",
            )
        ]
        for index in range(review_group_count)
    ]
    return SimpleNamespace(
        data_root=data_root,
        state_dir=state_dir,
        output_file=output_file,
        customer_file=customer_file,
        engine=engine,
        result=result,
        journal=journal,
        processed=processed,
        ledger=ledger,
        cache=cache,
        mappings=mappings,
        receipt=receipt,
        review_groups=review_groups,
        processed_candidates=[(SOURCE_HASH, "synthetic-source.xlsx", 1)],
    )


def _commit(environment):
    environment.engine._commit_successful_run(
        environment.result,
        environment.journal,
        environment.processed,
        environment.processed_candidates,
        environment.review_groups,
        environment.ledger,
        [environment.receipt],
        (),
        environment.cache,
        environment.customer_file,
        True,
        environment.mappings,
        [(MAPPING_KEY, MAPPING_VALUE)],
    )


def _persistent_state(environment):
    fresh_journal = PublicationJournal(
        environment.state_dir / "publication_journal.sqlite3", company_id=7,
    )
    reviews = ReviewQueue(
        environment.state_dir / "operations.sqlite3", company_id=7,
    ).list(status=None)
    balance = environment.ledger.balances([environment.receipt])[0]
    return {
        "published": len(fresh_journal.list(status="PUBLISHED")),
        "committed": len(fresh_journal.list(status="COMMITTED")),
        "reviews": len(reviews),
        "consumed": balance.consumed_amount,
        "cache": environment.cache.get() is not None,
        "mapping": MappingStore(
            environment.state_dir / "customer_mappings.json"
        ).get(MAPPING_KEY),
        "processed": ProcessedFilesLog(
            environment.state_dir / "processed_files.json"
        ).is_processed(SOURCE_HASH),
    }


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        ("publish", (0, 0, 0, 0.0, False, None, None)),
        ("review", (1, 0, 0, 0.0, False, None, None)),
        ("consumption", (1, 0, 1, 0.0, False, None, None)),
        ("cache", (1, 0, 1, 125.50, False, None, None)),
        ("mapping", (1, 0, 1, 125.50, True, None, None)),
        ("processed", (1, 0, 1, 125.50, True, MAPPING_VALUE, None)),
        ("commit", (1, 0, 1, 125.50, True, MAPPING_VALUE, True)),
    ],
    ids=list("ABCDEFG"),
)
def test_current_partial_failure_matrix_is_preserved(tmp_path, monkeypatch, stage, expected):
    environment = _environment(tmp_path)
    if stage == "publish":
        monkeypatch.setattr(environment.journal, "publish", _raise_at(stage))
    elif stage == "review":
        monkeypatch.setattr(ReviewQueue, "enqueue", _raise_at(stage))
    elif stage == "consumption":
        monkeypatch.setattr(environment.ledger, "replace_for_retry", _raise_at(stage))
    elif stage == "cache":
        monkeypatch.setattr(environment.cache, "save", _raise_at(stage))
    elif stage == "mapping":
        monkeypatch.setattr(environment.mappings, "set_many", _raise_at(stage))
    elif stage == "processed":
        monkeypatch.setattr(environment.processed, "mark_many", _raise_at(stage))
    elif stage == "commit":
        monkeypatch.setattr(environment.journal, "commit", _raise_at(stage))

    with pytest.raises(RuntimeError, match=f"injected failure: {stage}"):
        _commit(environment)

    state = _persistent_state(environment)
    actual = (
        state["published"],
        state["committed"],
        state["reviews"],
        state["consumed"],
        state["cache"],
        state["mapping"],
        bool(state["processed"]) if state["processed"] else None,
    )
    assert actual == expected
    assert environment.output_file.is_file()


def test_second_review_group_failure_keeps_first_group_and_stops_later_stages(
    tmp_path, monkeypatch,
):
    environment = _environment(tmp_path, review_group_count=3)
    original_enqueue = ReviewQueue.enqueue
    calls = 0

    def fail_second(queue, members, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected failure: second review")
        return original_enqueue(queue, members, **kwargs)

    monkeypatch.setattr(ReviewQueue, "enqueue", fail_second)
    with pytest.raises(RuntimeError, match="second review"):
        _commit(environment)

    state = _persistent_state(environment)
    assert calls == 2
    assert state["published"] == 1 and state["committed"] == 0
    assert state["reviews"] == 1
    assert state["consumed"] == 0.0
    assert state["cache"] is False
    assert state["mapping"] is None
    assert state["processed"] is None


@pytest.mark.parametrize("failure_stage", ["cache", "mapping", "processed"])
def test_exact_source_retry_after_post_consumption_failure_preserves_current_semantics(
    tmp_path, monkeypatch, failure_stage,
):
    environment = _environment(tmp_path)
    target = {
        "cache": (environment.cache, "save"),
        "mapping": (environment.mappings, "set_many"),
        "processed": (environment.processed, "mark_many"),
    }[failure_stage]
    monkeypatch.setattr(target[0], target[1], _raise_at(failure_stage))

    with pytest.raises(RuntimeError, match=failure_stage):
        _commit(environment)

    published = environment.journal.list(status="PUBLISHED")
    assert len(published) == 1
    with pytest.raises(PublicationRecoveryRequired):
        environment.journal.assert_reprocessable([SOURCE_HASH])

    environment.journal.approve_retry(published[0].publication_id)
    environment.journal.assert_reprocessable([SOURCE_HASH])
    reusable = environment.journal.committed_operation_ids_for_exact_sources(
        [SOURCE_HASH]
    )
    assert reusable == ()
    assert environment.ledger.available_rows(
        [environment.receipt], reusable_operation_ids=reusable,
    ) == []
    with pytest.raises(TahsilatConsumptionError):
        environment.ledger.replace_for_retry(
            [environment.receipt], operation_id=42,
            reusable_operation_ids=reusable,
        )


def test_corrupt_processed_file_does_not_bypass_published_source_guard(tmp_path):
    environment = _environment(tmp_path)
    environment.journal.publish(
        operation_id=environment.engine.operation_id,
        source_hashes=[SOURCE_HASH],
        output_dir=environment.result.output_dir,
        output_files=environment.result.created_files,
    )
    processed_path = environment.state_dir / "processed_files.json"
    processed_path.write_text("{broken", encoding="utf-8")

    assert ProcessedFilesLog(processed_path).is_processed(SOURCE_HASH) is None
    with pytest.raises(PublicationRecoveryRequired):
        environment.journal.assert_reprocessable([SOURCE_HASH])


def test_persistent_run_currently_allows_missing_operation_identity(tmp_path):
    environment = _environment(tmp_path, operation_id=None)
    _commit(environment)

    publication = environment.journal.list(status="COMMITTED")[0]
    review = ReviewQueue(
        environment.state_dir / "operations.sqlite3", company_id=7,
    ).list(status=None)[0]
    with sqlite3.connect(environment.state_dir / "tahsilat_consumption.sqlite3") as connection:
        ledger_operation_id = connection.execute(
            "SELECT operation_id FROM tahsilat_consumptions"
        ).fetchone()[0]
    assert publication.operation_id is None
    assert review.operation_id is None
    assert ledger_operation_id is None
    assert ProcessedFilesLog(
        environment.state_dir / "processed_files.json"
    ).is_processed(SOURCE_HASH)


def test_publication_journal_does_not_validate_missing_or_modified_outputs(tmp_path):
    environment = _environment(tmp_path)
    missing = environment.output_file
    published_id = environment.journal.publish(
        operation_id=41,
        source_hashes=[SOURCE_HASH],
        output_dir=environment.result.output_dir,
        output_files=[missing],
    )
    missing.unlink()
    published = environment.journal.list(status="PUBLISHED")[0]
    assert published.output_files == (str(missing),)
    assert not missing.exists()

    changed = environment.output_file.parent / "changed.xlsx"
    changed.write_bytes(b"before")
    committed_id = environment.journal.publish(
        operation_id=42,
        source_hashes=["b" * 64],
        output_dir=environment.result.output_dir,
        output_files=[changed],
    )
    environment.journal.commit(committed_id)
    changed.write_bytes(b"after")
    committed = environment.journal.list(status="COMMITTED")[0]
    assert committed.publication_id == committed_id
    assert committed.output_files == (str(changed),)
    assert changed.read_bytes() == b"after"
    assert published_id != committed_id
