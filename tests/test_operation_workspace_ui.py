"""Offscreen interaction tests: no customer profile or templates are opened."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

from app.core.operation_simulation import OperationSimulation
from app.ui.common import WorkflowSteps
from app.ui.operation_activity import OperationActivity
from app.ui.simulation_dashboard import SimulationDashboard
from app.ui.theme import MAIN_STYLE


_app = QApplication.instance() or QApplication([])


def sample_summary():
    return OperationSimulation().summarize([
        {"source_file": "DEMO_ANTALYA.xlsx", "source_row": 2, "region": "ANTALYA", "bank": "Garanti", "amount": 147978, "outcome": "HAVALE"},
        {"source_file": "DEMO_ANTALYA.xlsx", "source_row": 3, "region": "ANTALYA", "bank": "Garanti", "amount": 35000, "outcome": "ODEME_ONAYLANDI"},
        {"source_file": "DEMO_AYDIN.xlsx", "source_row": 2, "region": "AYDIN", "bank": "Ziraat", "amount": 12500, "outcome": "REVIEW"},
        {"source_file": "DEMO_BODRUM.xlsx", "source_row": 2, "region": "BODRUM", "bank": "Garanti", "amount": -65000, "outcome": "SAME_BANK_VIRMAN"},
    ])


def test_activity_search_level_clear_and_literal_text():
    view = OperationActivity()
    view.append("Dosyalar okundu: <b>müşteri</b>")
    view.append("UYARI: İnceleme gerekli")
    view.append("HATA: Kaynak bulunamadı\nDosya yolunu kontrol edin")
    assert view.model.rowCount() == 3
    assert "<b>müşteri</b>" in view.toPlainText()
    view.level.setCurrentText("Hata")
    assert view.proxy.rowCount() == 1
    view.table.selectRow(0)
    assert "Dosya yolunu" in view.details.toPlainText()
    view.search.setText("eşleşmeyen arama")
    assert view.proxy.rowCount() == 0
    view.clear()
    assert view.toPlainText() == ""
    assert not view.copy_button.isEnabled()
    view.deleteLater()


def test_dashboard_region_filters_recalculate_cards_and_details_selection():
    view = SimulationDashboard()
    view.set_summary(sample_summary())
    assert view.table.rowCount() == 3
    assert view.metrics["incoming_total"].text() == "195,478.00 TL"
    view.region.setCurrentText("AYDIN")
    assert view.table.rowCount() == 1
    assert view.metrics["incoming_total"].text() == "12,500.00 TL"
    assert view._visible_buckets[0].region == "AYDIN"
    view.region.setCurrentIndex(0)
    view.attention.setCurrentIndex(1)
    assert view.table.rowCount() == 1
    view.set_summary(None)
    assert view.table.rowCount() == 0
    assert not view.detail_button.isEnabled()
    assert view.metrics["incoming_total"].text() == "—"
    view.deleteLater()


def test_dashboard_does_not_claim_netsis_acceptance():
    view = SimulationDashboard()
    view.set_summary(sample_summary(), preview=False)
    assert "doğrulamaz" in view.subtitle.text()
    assert "ayrı çıktı" in view.notice.text()
    view.deleteLater()


def test_workflow_steps_visually_track_active_complete_and_attention_states():
    steps = WorkflowSteps([("Dosyaları seç", "Yükleyin"), ("Kontrol", "İnceleyin"), ("Çıktı", "Hazırlayın")])
    steps.set_active(1)
    assert steps._cards[0].property("stepState") == "complete"
    assert steps._cards[1].property("stepState") == "active"
    steps.set_state(1, "attention")
    assert steps._numbers[1].property("stepState") == "attention"
    steps.reset()
    assert steps._cards[0].property("stepState") == "active"
    assert steps._cards[2].property("stepState") == "pending"
    steps.deleteLater()


def test_workspace_at_laptop_width_and_optional_visual_capture():
    window = QWidget()
    window.setObjectName("mainRoot")
    window.setStyleSheet(MAIN_STYLE)
    layout = QVBoxLayout(window)
    layout.setContentsMargins(24, 24, 24, 24)
    dashboard = SimulationDashboard()
    dashboard.set_summary(sample_summary())
    layout.addWidget(dashboard)
    window.resize(1020, 800)
    window.show()
    _app.processEvents()
    assert window.minimumSizeHint().width() <= 1020
    assert dashboard.table.horizontalScrollBar().maximum() == 0
    destination = os.environ.get("CARPAN_UI_SCREENSHOT_DIR")
    if destination:
        from pathlib import Path
        directory = Path(destination)
        directory.mkdir(parents=True, exist_ok=True)
        assert window.grab().save(str(directory / "simulation-workspace.png"))
        layout.removeWidget(dashboard)
        dashboard.hide()
        activity = OperationActivity()
        activity.append("4 dosya okundu. Bölge ve banka eşleştirmeleri hazırlandı.")
        activity.append("Birleşik havale eşleşti: 70,978.00 + 77,000.00 TL = 147,978.00 TL.")
        activity.append("UYARI: AYDIN / Ziraat · 1 hareket kullanıcı kontrolü bekliyor.")
        activity.append("Simülasyon tamamlandı. Excel dosyası oluşturulmadı.")
        layout.addWidget(activity)
        _app.processEvents()
        assert window.grab().save(str(directory / "operation-activity.png"))
    window.close()
    window.deleteLater()
