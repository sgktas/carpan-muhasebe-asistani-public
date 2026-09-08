from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from app.ui.platform_account_dialog import PlatformAccountDialog


_app = QApplication.instance() or QApplication([])


@pytest.mark.parametrize("connected", [False, True])
def test_account_dialog_opens_with_and_without_saved_session(connected):
    result = SimpleNamespace(
        is_connected=connected,
        session=SimpleNamespace(display_name="Test", role="ADMIN") if connected else None,
        message="Merkezi hesap bağlı değil.",
    )
    dialog = PlatformAccountDialog(SimpleNamespace(restore=lambda: result))
    try:
        loop = QEventLoop()
        QTimer.singleShot(100, loop.quit)
        loop.exec()
        assert dialog.logout_button.isEnabled() is connected
        assert dialog.login_button.isEnabled()
        assert dialog.status.text()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_account_dialog_shows_license_status_when_sync_is_available():
    result = SimpleNamespace(
        is_connected=True,
        session=SimpleNamespace(display_name="Test", role="ADMIN"),
        message="Merkezi oturum yenilendi.",
    )
    license_info = SimpleNamespace(plan_code="PRO", usable=True)
    dialog = PlatformAccountDialog(
        SimpleNamespace(restore=lambda: result),
        license_sync=lambda _session: license_info,
    )
    try:
        loop = QEventLoop()
        QTimer.singleShot(100, loop.quit)
        loop.exec()
        assert "Lisans: PRO (geçerli)" in dialog.status.text()
    finally:
        dialog.close()
        dialog.deleteLater()
