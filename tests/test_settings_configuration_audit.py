from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from app.core.app_paths import AppPaths
from app.core.operation_history import OperationHistory
from app.ui import settings_page
from app.ui.settings_page import SettingsPage


_app = QApplication.instance() or QApplication([])


def session():
    return SimpleNamespace(company_id=4, user_id=8, display_name="Ayar Yöneticisi")


def test_settings_profile_selection_is_audited_and_stale_window_is_rejected(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    paths = AppPaths(root, tmp_path / "company", tmp_path / "output")
    paths.ensure_writable_dirs()
    monkeypatch.setattr(settings_page, "APP_PATHS", paths)
    monkeypatch.setattr(settings_page.QMessageBox, "warning", lambda *_args, **_kwargs: None)
    history = OperationHistory(paths.state_dir / "operations.sqlite3", company_id=4, user_id=8)
    first = SettingsPage(session(), history)
    stale = SettingsPage(session(), history)

    first._set_active_profile("output", "netsis_toplu")
    assert first._configuration_audit.recent()[0].after == {"profile_id": "netsis_toplu"}

    # The old page is not allowed to replace the newer selection invisibly.
    stale._set_active_profile("output", "netsis")
    assert first._active_profiles.get_output_profile_id() == "netsis_toplu"
    assert len(first._configuration_audit.recent()) == 1
    first.close()
    stale.close()
