import pytest

from app.core.publication_journal import (
    PublicationJournal,
    PublicationRecoveryRequired,
)


def test_published_output_blocks_silent_replay_until_it_is_committed(tmp_path):
    journal = PublicationJournal(tmp_path / "publications.sqlite3", company_id=7)
    publication_id = journal.publish(
        operation_id=12,
        source_hashes=["source-a", "source-b"],
        output_dir=tmp_path / "MANIM AKTARMA - 11092026",
        output_files=[tmp_path / "MANIM AKTARMA - 11092026" / "01_BODRUM.xls"],
    )
    with pytest.raises(PublicationRecoveryRequired, match="tamamlanmamış"):
        journal.assert_reprocessable(["source-b"])
    journal.commit(publication_id)
    journal.assert_reprocessable(["source-a"])
    entry = journal.list()[0]
    assert entry.status == "COMMITTED"
    assert entry.operation_id == 12
    assert entry.committed_at


def test_publication_journal_is_company_scoped(tmp_path):
    database = tmp_path / "publications.sqlite3"
    PublicationJournal(database, company_id=1).publish(
        operation_id=1, source_hashes=["same-source"], output_dir="C:/out", output_files=[]
    )
    PublicationJournal(database, company_id=2).assert_reprocessable(["same-source"])


def test_retry_requires_explicit_recovery_confirmation(tmp_path):
    journal = PublicationJournal(tmp_path / "publications.sqlite3", company_id=7)
    publication_id = journal.publish(
        operation_id=12, source_hashes=["source-a"], output_dir="C:/out", output_files=[]
    )
    journal.approve_retry(publication_id)
    journal.assert_reprocessable(["source-a"])
    assert journal.list()[0].status == "RECOVERY_CONFIRMED"


def test_retry_operations_require_exact_same_source_set(tmp_path):
    journal = PublicationJournal(tmp_path / "publications.sqlite3", company_id=7)
    exact = journal.publish(
        operation_id=12,
        source_hashes=["source-a", "source-b"],
        output_dir="C:/exact",
        output_files=[],
    )
    journal.commit(exact)
    subset = journal.publish(
        operation_id=13,
        source_hashes=["source-a"],
        output_dir="C:/subset",
        output_files=[],
    )
    journal.commit(subset)

    assert journal.committed_operation_ids_for_exact_sources(
        {"source-b", "source-a"}
    ) == (12,)
    assert journal.committed_operation_ids_for_exact_sources({"source-a"}) == (13,)
