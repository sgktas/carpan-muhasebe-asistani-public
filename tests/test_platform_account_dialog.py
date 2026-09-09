from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEventLoop, QThread, QTimer
from PySide6.QtWidgets import QApplication

from app.ui.platform_account_dialog import PlatformAccountDialog


_app = QApplication.instance() or QApplication([])


def _run_immediately(self, operation, on_success):
    """Durum arayüzü testinde gerçek ağ işçisi oluşturmadan sonucu uygular."""
    self._auth_success_handler = on_success
    on_success(operation())


@pytest.mark.parametrize("connected", [False, True])
def test_account_dialog_opens_with_and_without_saved_session(connected, monkeypatch):
    monkeypatch.setattr(PlatformAccountDialog, "_run_async", _run_immediately)
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


def test_account_dialog_shows_license_status_when_sync_is_available(monkeypatch):
    monkeypatch.setattr(PlatformAccountDialog, "_run_async", _run_immediately)
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


def test_account_dialog_applies_result_on_ui_thread_without_worker_race(monkeypatch):
    # PySide'ın gerçek QThread yaşam döngüsü, Linux CI'da süreç düzeyinde
    # çökebiliyor. İşçi sınıfı burada doğrulanacak bir iş kuralı taşımıyor;
    # arayüz sonucu ana Qt iş parçacığında uygulamasını güvenle test ederiz.
    monkeypatch.setattr(PlatformAccountDialog, "_run_async", _run_immediately)
    result = SimpleNamespace(
        is_connected=False,
        session=None,
        message="Merkezi hesap bağlı değil.",
    )

    dialog = PlatformAccountDialog(SimpleNamespace(restore=lambda: result))
    applied_threads = []
    original_handler = dialog._auth_success_handler

    def record_handler(payload):
        applied_threads.append(QThread.currentThread())
        original_handler(payload)

    class _FinishedThread:
        def quit(self):
            pass

    dialog._auth_success_handler = record_handler
    dialog._auth_thread = _FinishedThread()
    try:
        dialog._finish_async((result, None, None))
        assert applied_threads == [_app.thread()]
    finally:
        dialog._auth_thread = None
        dialog.close()
        dialog.deleteLater()
