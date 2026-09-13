from __future__ import annotations

import json
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core import identity
from app.core.identity import IdentityStore
from app.core.operation_history import OperationHistory
from app.core.processed_files_log import ProcessedFilesLog
from app.core.publication_journal import PublicationJournal
from app.core.review_queue import ReviewMember, ReviewQueue
from app.ui.operation_center_page import OperationCenterPage


_APP = QApplication.instance() or QApplication([])
SOURCE_HASH = "e" * 64


def _operation(tmp_path, history, *, status="SUCCESS", name="synthetic"):
    source = tmp_path / f"{name}-source.xlsx"
    source.write_bytes(b"synthetic source")
    output = tmp_path / f"{name}-output.xlsx"
    output.write_bytes(b"synthetic output")
    operation_id = history.start("manim_transfer", "MANIM", [source])
    if status in {"SUCCESS", "PARTIAL"}:
        history.complete(operation_id, [output], status=status)
    elif status == "FAILED":
        history.fail(operation_id, "Synthetic failure")
    return operation_id, source, output


def _publication(history, operation_id, output, *, committed=True):
    journal = PublicationJournal(
        history.database_path.parent / "publication_journal.sqlite3",
        company_id=history.company_id,
    )
    publication_id = journal.publish(
        operation_id=operation_id,
        source_hashes=[SOURCE_HASH],
        output_dir=output.parent,
        output_files=[output],
    )
    if committed:
        journal.commit(publication_id)
    return journal, publication_id


def _mark_processed(history, source_name="synthetic-source.xlsx"):
    ProcessedFilesLog(
        history.database_path.parent / "processed_files.json"
    ).mark_processed(SOURCE_HASH, source_name, 1)


def test_operation_center_renders_consistent_unified_state(tmp_path):
    history = OperationHistory(tmp_path / "data" / "operations.sqlite3", company_id=7)
    operation_id, source, output = _operation(tmp_path, history)
    _publication(history, operation_id, output)
    _mark_processed(history, source.name)

    page = OperationCenterPage(history)

    assert page.consistency_operation_combo.currentData() == operation_id
    assert page.consistency_status.text() == "Durum tutarlı"
    assert "Geçmiş: Başarılı" in page.consistency_facts.text()
    assert "Yayın: Tamamlandı" in page.consistency_facts.text()
    assert "Açık kayıt yok" in page.consistency_facts.text()
    assert page.consistency_reasons.text() == "Kontrol nedeni bulunmuyor."
    assert f"Operasyon #{operation_id}" in page.consistency_diagnostics.text()
    assert "Yayın kaydı: 1" in page.consistency_diagnostics.text()
    assert "Önem düzeyi: normal" in page.consistency_status.accessibleDescription()
    page.deleteLater()


def test_operation_center_shows_committed_and_interrupted_split_state(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(OperationHistory, "LEASE_SECONDS", -1)
    database = tmp_path / "data" / "operations.sqlite3"
    history = OperationHistory(database, company_id=7, instance_id="first")
    operation_id, source, output = _operation(tmp_path, history, status="RUNNING")
    _publication(history, operation_id, output)
    _mark_processed(history, source.name)
    restarted = OperationHistory(database, company_id=7, instance_id="second")

    page = OperationCenterPage(restarted)

    assert page.consistency_status.text() == "Kontrol gerekiyor"
    assert "Geçmiş: Yarım kaldı" in page.consistency_facts.text()
    assert "Yayın: Tamamlandı" in page.consistency_facts.text()
    assert "Çıktı yayını tamamlanmış, fakat operasyon geçmişi tamamlanmamış" in page.consistency_reasons.text()
    assert "Durum tutarlı" not in page.consistency_status.text()
    page.deleteLater()


def test_operation_center_shows_published_recovery_required(tmp_path):
    history = OperationHistory(tmp_path / "data" / "operations.sqlite3", company_id=7)
    operation_id, _source, output = _operation(tmp_path, history, status="RUNNING")
    _publication(history, operation_id, output, committed=False)

    page = OperationCenterPage(history)

    assert page.consistency_status.text() == "Kurtarma kontrolü gerekiyor"
    assert "Yayın: Yayımlandı · tamamlanma bekliyor" in page.consistency_facts.text()
    assert "yerel tamamlanma kaydı henüz oluşmamış" in page.consistency_reasons.text()
    assert "Sessiz yeniden çalışma" in page.consistency_reasons.text()
    assert page.consistency_action_button.text() == "Yayın ve kurtarma kontrolüne git"
    assert not page.consistency_action_button.isHidden()
    assert page._consistency_action_target == "publication_recovery"
    assert page.recovery_table.rowCount() == 1
    page.deleteLater()


def test_operation_center_shows_open_review_without_replacing_review_board(tmp_path):
    history = OperationHistory(tmp_path / "data" / "operations.sqlite3", company_id=7)
    operation_id, source, output = _operation(tmp_path, history, status="PARTIAL")
    _publication(history, operation_id, output)
    _mark_processed(history, source.name)
    queue = ReviewQueue(history.database_path, company_id=7)
    queue.enqueue(
        [ReviewMember(source.name, 2, 10.0, "TEST-REGION", "TEST-BANK", "Review")],
        operation_id=operation_id,
    )

    page = OperationCenterPage(history)

    assert page.consistency_status.text() == "Kontrol gerekiyor"
    assert "İnceleme: 1 açık grup · 1 kayıt" in page.consistency_facts.text()
    assert "açık inceleme kayıtları" in page.consistency_reasons.text()
    assert page.consistency_action_button.text() == "İnceleme kayıtlarına git"
    assert page._consistency_action_target == "review_board"
    assert page.review_board is not None
    page.deleteLater()


def test_operation_center_shows_missing_output_without_calling_it_corrupt(tmp_path):
    history = OperationHistory(tmp_path / "data" / "operations.sqlite3", company_id=7)
    operation_id, source, output = _operation(tmp_path, history)
    _publication(history, operation_id, output)
    _mark_processed(history, source.name)
    output.unlink()

    page = OperationCenterPage(history)

    assert page.consistency_status.text() == "Kontrol gerekiyor"
    assert "Çıktı: Kayıtlı dosyalar bulunamıyor" in page.consistency_facts.text()
    assert "artık bulunamıyor" in page.consistency_reasons.text()
    assert "bozuk" not in page.consistency_reasons.text().casefold()
    assert "otomatik olarak yeniden üretilmez" in page.consistency_reasons.text()
    page.deleteLater()


def test_processed_source_missing_wording_is_explicitly_non_fatal(tmp_path):
    history = OperationHistory(tmp_path / "data" / "operations.sqlite3", company_id=7)
    operation_id, _source, output = _operation(tmp_path, history)
    _publication(history, operation_id, output)

    page = OperationCenterPage(history)

    assert page.consistency_status.text() == "Kontrol gerekiyor"
    assert "İşlenmiş kaydı yok" in page.consistency_facts.text()
    assert "tek başına veri kaybı veya işlem başarısızlığı anlamına gelmez" in page.consistency_reasons.text()
    page.deleteLater()


def test_multiple_attention_reasons_render_in_stable_priority_order(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(OperationHistory, "LEASE_SECONDS", -1)
    database = tmp_path / "data" / "operations.sqlite3"
    history = OperationHistory(database, company_id=7, instance_id="first")
    operation_id, source, output = _operation(
        tmp_path, history, status="RUNNING", name="multi-reason",
    )
    _publication(history, operation_id, output)
    queue = ReviewQueue(history.database_path, company_id=7)
    queue.enqueue(
        [ReviewMember(source.name, 2, 10.0, "TEST-REGION", "TEST-BANK", "Review")],
        operation_id=operation_id,
    )
    output.unlink()
    restarted = OperationHistory(database, company_id=7, instance_id="second")

    page = OperationCenterPage(restarted)
    reasons = page.consistency_reasons.text()

    titles = (
        "Geçmiş ve yayın durumu farklı",
        "İnceleme kararı bekleniyor",
        "Kayıtlı çıktı dosyası bulunamıyor",
        "İşlenmiş kaynak kaydı eksik",
    )
    assert all(title in reasons for title in titles)
    assert [reasons.index(title) for title in titles] == sorted(
        reasons.index(title) for title in titles
    )
    assert page.consistency_action_button.text() == "İnceleme kayıtlarına git"
    page.deleteLater()


def test_severity_is_expressed_in_text_and_accessible_description(tmp_path):
    history = OperationHistory(tmp_path / "data" / "operations.sqlite3", company_id=7)
    operation_id, _source, output = _operation(tmp_path, history, status="RUNNING")
    _publication(history, operation_id, output, committed=False)

    page = OperationCenterPage(history)

    assert page.consistency_status.text() == "Kurtarma kontrolü gerekiyor"
    assert "kurtarma kontrolü gerekiyor" in (
        page.consistency_status.accessibleDescription().casefold()
    )
    assert page.consistency_status.property("consistencySeverity") == "critical"
    assert page.consistency_action_button.focusPolicy() != Qt.NoFocus
    page.deleteLater()


def test_operation_center_combo_is_company_scoped(tmp_path):
    database = tmp_path / "data" / "operations.sqlite3"
    company_a = OperationHistory(database, company_id=7)
    operation_a, _source_a, _output_a = _operation(tmp_path, company_a, name="company-a")
    company_b = OperationHistory(database, company_id=8)
    operation_b, _source_b, _output_b = _operation(tmp_path, company_b, name="company-b")

    page = OperationCenterPage(company_a)

    visible_ids = {
        page.consistency_operation_combo.itemData(index)
        for index in range(page.consistency_operation_combo.count())
    }
    assert visible_ids == {operation_a}
    assert operation_b not in visible_ids
    page.deleteLater()


def test_history_only_legacy_operation_does_not_show_false_critical_error(tmp_path):
    history = OperationHistory(tmp_path / "data" / "operations.sqlite3", company_id=7)
    operation_id, _source, _output = _operation(tmp_path, history)

    page = OperationCenterPage(history)

    assert page.consistency_operation_combo.currentData() == operation_id
    assert page.consistency_status.text() == "Durum tutarlı"
    assert "Yayın: Kayıt yok" in page.consistency_facts.text()
    assert "Kaynak kaydı: Bağlı kaynak yok" in page.consistency_facts.text()
    page.deleteLater()


def test_existing_recovery_action_still_calls_publication_journal(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(identity, "PASSWORD_ITERATIONS", 1000)
    identity_store = IdentityStore(tmp_path / "identity.sqlite3")
    admin = identity_store.create_initial_admin(
        "Synthetic Company", "admin", "Synthetic Administrator", "Guvenli1234",
    )
    history = OperationHistory(
        tmp_path / "data" / "operations.sqlite3",
        company_id=admin.company_id,
        user_id=admin.user_id,
    )
    operation_id, _source, output = _operation(tmp_path, history, status="RUNNING")
    _journal, publication_id = _publication(
        history, operation_id, output, committed=False,
    )
    page = OperationCenterPage(history, identity_store=identity_store, session=admin)
    page.recovery_table.selectRow(0)
    approved = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: QMessageBox.Yes)
    monkeypatch.setattr(
        page.publication_journal,
        "approve_retry",
        lambda value: approved.append(value),
    )

    page._approve_recovery_retry()

    assert approved == [publication_id]
    page.deleteLater()


def test_operation_center_rendering_does_not_mutate_stores(tmp_path):
    history = OperationHistory(tmp_path / "data" / "operations.sqlite3", company_id=7)
    operation_id, source, output = _operation(tmp_path, history, status="PARTIAL")
    journal, _publication_id = _publication(
        history, operation_id, output, committed=False,
    )
    _mark_processed(history, source.name)
    queue = ReviewQueue(history.database_path, company_id=7)
    queue.enqueue(
        [ReviewMember(source.name, 2, 10.0, "TEST-REGION", "TEST-BANK", "Review")],
        operation_id=operation_id,
    )
    page = OperationCenterPage(history)

    def snapshot():
        with sqlite3.connect(history.database_path) as connection:
            operations = connection.execute(
                "SELECT id, status FROM operations ORDER BY id"
            ).fetchall()
            reviews = connection.execute(
                "SELECT group_id, status, version FROM review_queue_groups ORDER BY group_id"
            ).fetchall()
        publications = tuple(
            (entry.publication_id, entry.status)
            for entry in journal.list(status=None)
        )
        processed = json.loads(
            (history.database_path.parent / "processed_files.json").read_text(
                encoding="utf-8"
            )
        )
        return operations, reviews, publications, processed

    before = snapshot()
    page.refresh()
    page._render_operation_consistency()
    after = snapshot()

    assert after == before
    page.deleteLater()
