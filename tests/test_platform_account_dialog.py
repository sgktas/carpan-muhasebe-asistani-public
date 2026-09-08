from types import SimpleNamespace

import pytest
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
        assert dialog.logout_button.isEnabled() is connected
        assert dialog.login_button.isEnabled()
        assert dialog.status.text()
    finally:
        dialog.close()
        dialog.deleteLater()
