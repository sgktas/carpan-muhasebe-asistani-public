"""Whole-page layout and threaded IO regression checks with isolated demo state."""
import os
import time
from pathlib import Path
from threading import Event, get_ident
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QScrollArea, QMessageBox, QWidget
from app.core.app_paths import AppPaths
from app.core.operation_history import OperationHistory
from app.ui.local_task import LocalTask
from app.ui.theme import MAIN_STYLE

app = QApplication.instance() or QApplication([])
for font_file in ("segoeui.ttf", "segoeuib.ttf"):
    font_path = Path("C:/Windows/Fonts") / font_file
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))


def pump_until(predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.002)
    assert predicate()


def test_local_task_keeps_gui_alive_and_delivers_on_gui_thread():
    task = LocalTask()
    release = Event()
    seen, ticks = [], []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(5)
    main_thread = get_ident()
    task.succeeded.connect(lambda result: seen.append((result, get_ident())))
    def work():
        assert release.wait(3)
        return get_ident()
    try:
        assert task.start(work)
        assert not task.start(work)
        pump_until(lambda: len(ticks) >= 3)
    finally:
        release.set()
        pump_until(lambda: not task.busy)
        timer.stop()
    assert seen[0][0] != main_thread
    assert seen[0][1] == main_thread


def test_local_task_failure_can_retry():
    task = LocalTask()
    errors, results = [], []
    task.failed.connect(errors.append)
    task.succeeded.connect(results.append)
    def fail():
        raise ValueError("demo failure")
    task.start(fail)
    pump_until(lambda: not task.busy)
    assert str(errors[0]) == "demo failure"
    assert task.start(lambda: 42)
    pump_until(lambda: not task.busy)
    assert results == [42]


def test_whole_pages_at_multiple_widths(tmp_path, monkeypatch):
    from app.modules.report_editing import page as fom
    from app.modules.bank_reconciliation import page as bank
    from app.modules.manim import page as manim
    paths = AppPaths(tmp_path / "resources", tmp_path / "state", tmp_path / "output")
    for module in (fom, bank, manim):
        monkeypatch.setattr(module, "APP_PATHS", paths)
    history = OperationHistory(tmp_path / "history.db")
    app.setStyleSheet(MAIN_STYLE)
    pages = [fom.ReportEditingPage(history), bank.BankReconciliationPage(history), manim.ManimModulePage(history)]
    try:
        for page in pages:
            for width in (760, 1100, 1440):
                page.resize(width, 900)
                page.show()
                for _ in range(5):
                    app.processEvents()
                assert page.width() == width
                for scroll in page.findChildren(QScrollArea):
                    if scroll.isVisible():
                        assert scroll.widget().width() <= scroll.viewport().width(), [(type(w).__name__, w.objectName(), w.minimumSizeHint().width()) for w in scroll.widget().findChildren(QWidget) if w.minimumSizeHint().width() > 600]
                folder = os.environ.get("CARPAN_UI_SCREENSHOT_DIR")
                if folder:
                    target = Path(folder)
                    target.mkdir(parents=True, exist_ok=True)
                    assert page.grab().save(str(target / f"{type(page).__name__}-{width}.png"))
            page.resize(1100, 900)
            page.input_panel.set_expanded(False)
            if isinstance(page, manim.ManimModulePage):
                from app.core.operation_simulation import OperationSimulation
                page.dashboard.set_summary(OperationSimulation().summarize([
                    {"source_file": "DEMO.xlsx", "source_row": 2, "region": "ANTALYA", "bank": "Garanti", "amount": 147978, "outcome": "HAVALE"},
                    {"source_file": "DEMO.xlsx", "source_row": 3, "region": "AYDIN", "bank": "Ziraat", "amount": 12500, "outcome": "REVIEW"},
                ]))
            elif isinstance(page, bank.BankReconciliationPage):
                page._show_result_card({"banka_adi": "Garanti", "bolge": "ANTALYA", "durum": "KONTROL GEREKLİ", "toplam_alinan_tutar": 250000, "toplam_gonderilen_tutar": 120000, "fark": 12500}, "demo.xlsx", "11.09.2026")
            else:
                page._operation_id = history.start("report_editing", "Demo", [])
                page._process_succeeded(SimpleNamespace(logs=[], created_files=[Path("ENT-Muhasebe_Entegrasyon(Tahsilatlar).xls")], output_dir=tmp_path, unmatched_customer_codes=0, summary=lambda: {}))
            for _ in range(5):
                app.processEvents()
            if folder:
                assert page.grab().save(str(target / f"{type(page).__name__}-results.png"))
            page.hide()
    finally:
        for page in pages:
            page.close()
            page.deleteLater()


def test_fom_failure_restores_controls_without_outputs(tmp_path, monkeypatch):
    from app.modules.report_editing import page as fom
    monkeypatch.setattr(fom, "APP_PATHS", AppPaths(tmp_path, tmp_path, tmp_path))
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: None)
    page = fom.ReportEditingPage(OperationHistory(tmp_path / "history.db"))
    monkeypatch.setattr(page, "_selected_template_problem", lambda: None)
    def fail(files):
        raise ValueError("Demo şablon kontrolü")
    monkeypatch.setattr(page, "_prepare_reports", fail)
    page.files = [tmp_path / "demo.xlsx"]
    page.start_button.setEnabled(True)
    page.start_process()
    assert page.is_busy
    assert not page.select_button.isEnabled()
    page.clear_files()
    assert page.files
    pump_until(lambda: not page.is_busy)
    assert page.select_button.isEnabled()
    assert page.start_button.isEnabled()
    assert page.last_output_dir is None
    assert page.detail_panel.toggle.isChecked()
    page.deleteLater()


def test_full_history_not_capped_at_one_hundred(tmp_path):
    history = OperationHistory(tmp_path / "history.db")
    for _ in range(105):
        history.start("demo", "Demo", [])
    assert len(history.recent()) == 100
    assert len(history.recent(None)) == 105


def test_file_classification_is_background_and_blocks_duplicate_load(tmp_path, monkeypatch):
    from app.modules.report_editing import page as fom
    monkeypatch.setattr(fom, "APP_PATHS", AppPaths(tmp_path, tmp_path, tmp_path))
    page = fom.ReportEditingPage(OperationHistory(tmp_path / "history.db"))
    monkeypatch.setattr(page, "_selected_template_problem", lambda: None)
    release = Event()
    def classify(files):
        assert release.wait(3)
        return ["Satış raporu • demo.xlsx"], [], {"sales"}
    monkeypatch.setattr(page, "_classify_files", classify)
    try:
        page._load_files([tmp_path / "demo.xlsx"])
        assert page.is_busy
        page._load_files([tmp_path / "other.xlsx"])
        assert page.files == [tmp_path / "demo.xlsx"]
        assert not page.start_button.isEnabled()
    finally:
        release.set()
        pump_until(lambda: not page.is_busy)
    assert page.start_button.isEnabled()
    assert page.select_button.isEnabled()
    page.deleteLater()
