from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QWidget

from app.core import identity
from app.core.identity import IdentityStore
from app.ui.login_window import LoginWindow
from app.ui import main_window


_app = QApplication.instance() or QApplication([])


def test_first_run_setup_and_following_login(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "PASSWORD_ITERATIONS", 1_000)
    store = IdentityStore(tmp_path / "platform.sqlite3")
    sessions = []
    setup = LoginWindow(store, sessions.append)
    assert setup.setup_mode
    setup.company_name_input.setText("Çarpan Test")
    setup.display_name_input.setText("Test Yönetici")
    setup.username_input.setText("admin")
    setup.password_input.setText("Guvenli1234")
    setup.password_confirm_input.setText("Guvenli1234")

    setup._submit()

    assert sessions[0].company_name == "Çarpan Test"
    login = LoginWindow(store, sessions.append)
    assert not login.setup_mode
    login.username_input.setText("admin")
    login.password_input.setText("Guvenli1234")
    login._submit()
    assert len(sessions) == 2


def test_login_shows_error_without_opening_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "PASSWORD_ITERATIONS", 1_000)
    store = IdentityStore(tmp_path / "platform.sqlite3")
    admin = store.create_initial_admin(
        "Çarpan Test", "admin", "Test Yönetici", "Guvenli1234"
    )
    sessions = []
    login = LoginWindow(store, sessions.append)
    login.username_input.setText(admin.username)
    login.password_input.setText("yanlis")

    login._submit()

    assert not sessions
    assert login.error_label.isVisibleTo(login)


def test_approver_sees_only_authorized_module_and_operations_views(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "PASSWORD_ITERATIONS", 1_000)
    store = IdentityStore(tmp_path / "platform.sqlite3")
    admin = store.create_initial_admin(
        "Çarpan Test", "admin", "Test Yönetici", "Guvenli1234"
    )
    store.create_user(
        admin,
        username="onay",
        display_name="Onay Sorumlusu",
        password="Onaylayan1234",
        role="APPROVER",
    )
    approver = store.authenticate("onay", "Onaylayan1234", admin.company_id)
    fake_modules = [
        SimpleNamespace(
            module_id="manim_transfer",
            nav_label="MANİM",
            icon_name="transfer",
            page_factory=QWidget,
        ),
        SimpleNamespace(
            module_id="bank_reconciliation",
            nav_label="Banka",
            icon_name="folder",
            page_factory=QWidget,
        ),
    ]
    monkeypatch.setattr(main_window, "build_module_registry", lambda _history: fake_modules)
    monkeypatch.setattr(
        main_window,
        "APP_PATHS",
        SimpleNamespace(
            state_dir=tmp_path / "state",
            assets_dir=Path(__file__).resolve().parents[1] / "assets",
        ),
    )

    window = main_window.MainWindow(approver, store)

    assert [item[0] for item in window.nav_items] == [
        "manim_transfer",
        "operations_center",
        "history",
    ]
    window.close()
