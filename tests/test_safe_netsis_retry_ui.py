import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea
from PySide6.QtGui import QFontDatabase

from app.core.identity import IdentityStore
from app.core.operation_history import OperationHistory
from app.core.operation_simulation import (
    OperationSimulation,
    simulation_summary_payload,
)
from app.modules.manim.page import ManimModulePage
from app.ui.operation_center_page import OperationCenterPage
from app.ui.theme import MAIN_STYLE


_app = QApplication.instance() or QApplication([])
_app.setStyleSheet(MAIN_STYLE)
for _font_file in ("segoeui.ttf", "segoeuib.ttf"):
    _font_path = Path("C:/Windows/Fonts") / _font_file
    if _font_path.exists():
        QFontDatabase.addApplicationFont(str(_font_path))


def test_netsis_rejection_is_visible_and_emits_safe_retry_request(tmp_path):
    identity = IdentityStore(tmp_path / "identity.sqlite3")
    admin = identity.create_initial_admin(
        "Çarpan Test", "admin", "Test Yönetici", "Guvenli1234"
    )
    history = OperationHistory(
        tmp_path / "operations.sqlite3",
        company_id=admin.company_id,
        user_id=admin.user_id,
    )
    source = tmp_path / "ANTALYA_MANIM.xlsx"
    source.touch()
    output = tmp_path / "05_ANTALYA.xlsx"
    output.touch()
    operation_id = history.start("manim_transfer", "MANİM Aktarma", [source])
    history.complete(operation_id, [output])
    history.record_external_acceptance(
        operation_id,
        system="NETSIS",
        verdict="REJECTED",
        reason_code="BANK_ACCOUNT_CODE",
    )

    page = OperationCenterPage(history, identity_store=identity, session=admin)
    requests = []
    page.safe_manim_retry_requested.connect(requests.append)

    assert page.rejection_table.rowCount() == 1
    assert page.rejection_table.item(0, 2).text() == output.name
    assert page.rejection_table.item(0, 3).text() == "Banka hesap kodu"
    assert page.rejection_table.item(0, 4).text() == "Hazır · 1/1"
    assert page.prepare_manim_retry_button.isEnabled()
    page.retry_profile_combo.setCurrentIndex(
        page.retry_profile_combo.findData("netsis")
    )
    page.prepare_manim_retry_button.click()

    assert requests == [{
        "operation_id": operation_id,
        "input_files": [str(source)],
        "output_profile_id": "netsis",
        "reason": "Netsis aktarımı reddedildi: Banka hesap kodu.",
    }]
    page.deleteLater()


def test_safe_retry_loads_sources_but_does_not_start_operation(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3")
    source = tmp_path / "ANTALYA_MANIM.xlsx"
    source.touch()
    page = ManimModulePage(history)

    page.prepare_safe_retry(
        [source],
        output_profile_id="netsis",
        origin_operation_id=41,
        reason="Netsis aktarımı reddedildi: Banka hesap kodu.",
    )

    assert page.files == [source]
    assert page.havale_template_combo.currentData() == "netsis"
    assert page.start_button.isEnabled()
    assert page.retry_context_label.isVisibleTo(page)
    assert "#41" in page.retry_context_label.text()
    assert history.recent() == []
    page.deleteLater()


def test_missing_retry_source_is_shown_and_cannot_be_loaded(tmp_path):
    identity = IdentityStore(tmp_path / "identity.sqlite3")
    admin = identity.create_initial_admin(
        "Çarpan Test", "admin", "Test Yönetici", "Guvenli1234"
    )
    history = OperationHistory(
        tmp_path / "operations.sqlite3",
        company_id=admin.company_id,
        user_id=admin.user_id,
    )
    missing = tmp_path / "SILINMIS_MANIM.xlsx"
    operation_id = history.start("manim_transfer", "MANİM Aktarma", [missing])
    history.complete(operation_id, [tmp_path / "output.xls"])
    history.record_external_acceptance(
        operation_id,
        system="NETSIS",
        verdict="REJECTED",
        reason_code="FILE_FORMAT",
    )

    page = OperationCenterPage(history, identity_store=identity, session=admin)

    assert page.rejection_table.item(0, 4).text() == "Eksik · 0/1"
    assert not page.prepare_manim_retry_button.isEnabled()
    assert missing.name in page.rejection_detail.text()
    page.deleteLater()


def test_operation_center_shows_exact_completed_manim_distribution(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3")
    source = tmp_path / "ANTALYA_MANIM.xlsx"
    source.touch()
    output = tmp_path / "05_ANTALYA.xls"
    output.touch()
    result = OperationSimulation().summarize(
        [
            {
                "source_file": source.name,
                "source_row": 2,
                "region": "ANTALYA",
                "bank": "Garanti",
                "amount": 100,
                "outcome": "HAVALE",
                "rule_code": "TEST",
            }
        ],
        netsis_records=[type("Row", (), {"bolge": "ANTALYA", "banka": "Garanti", "tutar": 60})()],
    )
    operation_id = history.start("manim_transfer", "MANİM Aktarma", [source])
    history.complete(
        operation_id,
        [output],
        {"operation_result": simulation_summary_payload(result)},
    )

    page = OperationCenterPage(history)

    assert page.operation_result_combo.currentData() == operation_id
    assert page.operation_result_dashboard.metrics["incoming_total"].text() == "100.00 TL"
    assert page.operation_result_dashboard.metrics["netsis_total"].text() == "60.00 TL"
    assert page.operation_result_dashboard.metrics["pending_total"].text() == "40.00 TL"
    assert "1 bölge/banka" in page.operation_result_context.text()
    assert "Netsis sonucu henüz kaydedilmedi" in page.operation_result_context.text()
    screenshot_dir = os.environ.get("CARPAN_UI_SCREENSHOT_DIR")
    if screenshot_dir:
        target = Path(screenshot_dir)
        target.mkdir(parents=True, exist_ok=True)
        page.resize(1280, 900)
        page.show()
        _app.processEvents()
        scroll = page.findChild(QScrollArea)
        scroll.ensureWidgetVisible(page.operation_result_dashboard)
        _app.processEvents()
        assert page.grab().save(str(target / "operation-center-post-result.png"))
    page.deleteLater()


def test_operation_center_can_record_explicit_netsis_result(tmp_path, monkeypatch):
    identity = IdentityStore(tmp_path / "identity.sqlite3")
    admin = identity.create_initial_admin(
        "Çarpan Test", "admin", "Test Yönetici", "Guvenli1234"
    )
    history = OperationHistory(
        tmp_path / "operations.sqlite3",
        company_id=admin.company_id,
        user_id=admin.user_id,
    )
    source = tmp_path / "ANTALYA_MANIM.xlsx"
    output = tmp_path / "05_ANTALYA.xls"
    source.touch()
    output.touch()
    operation_id = history.start("manim_transfer", "MANİM Aktarma", [source])
    history.complete(operation_id, [output])
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    page = OperationCenterPage(history, identity_store=identity, session=admin)

    assert page.record_operation_result_button.isEnabled()
    assert page._save_completed_manim_acceptance(operation_id, "REJECTED", "BANK_ACCOUNT_CODE")

    latest = history.recent()[0]
    assert latest.summary["external_acceptance"] == {
        "system": "NETSIS",
        "verdict": "REJECTED",
        "reason_code": "BANK_ACCOUNT_CODE",
    }
    assert page.rejection_table.rowCount() == 1
    page.deleteLater()
