from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from app.core.platform_auth_service import PlatformAuthService


class _AuthWorker(QObject):
    finished = Signal(object)
    failed = Signal(object)

    def __init__(self, operation):
        super().__init__()
        self._operation = operation

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self._operation())
        except Exception as error:  # UI thread must receive failures, not crash.
            self.failed.emit(error)


class PlatformAccountDialog(QDialog):
    """Merkezi hesap için sade giriş/çıkış ekranı; yerel kullanıcı hesabını değiştirmez."""

    def __init__(self, service: PlatformAuthService, parent=None):
        super().__init__(parent)
        self._service = service
        self._auth_thread: QThread | None = None
        self._auth_worker: _AuthWorker | None = None
        self.setWindowTitle("Merkezi Hesap")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        title = QLabel("Merkezi Hesap")
        title.setObjectName("cardTitle")
        explanation = QLabel("Lisans ve cihaz yönetimi için giriş yapın. Excel, banka ve müşteri verileri bilgisayarınızda kalır.")
        explanation.setObjectName("cardSubtitle")
        explanation.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(explanation)

        form = QFormLayout()
        self.company = QLineEdit()
        self.company.setPlaceholderText("Firma kodu")
        self.username = QLineEdit()
        self.username.setPlaceholderText("Kullanıcı adı")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Parola")
        form.addRow("Firma kodu", self.company)
        form.addRow("Kullanıcı adı", self.username)
        form.addRow("Parola", self.password)
        layout.addLayout(form)

        self.status = QLabel()
        self.status.setObjectName("miniInfoText")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.login_button = QPushButton("Güvenli giriş yap")
        self.login_button.setObjectName("secondary")
        self.login_button.clicked.connect(self._sign_in)
        self.logout_button = QPushButton("Bu cihazdan çıkış yap")
        self.logout_button.setObjectName("secondary")
        self.logout_button.clicked.connect(self._sign_out)
        close = QPushButton("Kapat")
        close.clicked.connect(self.accept)
        buttons.addWidget(self.login_button)
        buttons.addWidget(self.logout_button)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._run_async(self._service.restore, self._apply_restore)

    def _apply_restore(self, current) -> None:
        if current.is_connected and current.session:
            self.status.setText(f"Bağlı hesap: {current.session.display_name} · Rol: {current.session.role}")
            self.logout_button.setEnabled(True)
            return
        self.status.setText(current.message)
        self.logout_button.setEnabled(False)

    def _sign_in(self) -> None:
        company_code = self.company.text()
        username = self.username.text()
        password = self.password.text()
        self.password.clear()
        self._run_async(
            lambda: self._service.sign_in(
                company_code=company_code, username=username, password=password
            ),
            self._apply_sign_in,
        )

    def _apply_sign_in(self, result) -> None:
        self.status.setText(result.message)
        if result.is_connected:
            self.logout_button.setEnabled(True)
            QMessageBox.information(self, "Merkezi hesap", result.message)
        else:
            QMessageBox.warning(self, "Merkezi hesap", result.message)

    def _sign_out(self) -> None:
        self._run_async(self._service.sign_out, self._apply_sign_out)

    def _apply_sign_out(self, result) -> None:
        self.status.setText(result.message)
        self.logout_button.setEnabled(False)

    def _run_async(self, operation, on_success) -> None:
        if self._auth_thread is not None:
            return
        self.login_button.setEnabled(False)
        self.logout_button.setEnabled(False)
        thread = QThread(self)
        worker = _AuthWorker(operation)
        worker.moveToThread(thread)
        self._auth_thread = thread
        self._auth_worker = worker
        thread.started.connect(worker.run)
        worker.finished.connect(lambda result: self._finish_async(thread, worker, on_success, result))
        worker.failed.connect(lambda error: self._fail_async(thread, worker, error))
        thread.finished.connect(lambda: self._clear_async(thread, worker))
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _finish_async(self, thread, worker, on_success, result) -> None:
        if self._auth_thread is not thread:
            return
        on_success(result)
        self.login_button.setEnabled(True)
        thread.quit()

    def _fail_async(self, thread, worker, error) -> None:
        if self._auth_thread is not thread:
            return
        self.status.setText("Merkezi platform bağlantısı tamamlanamadı.")
        self.login_button.setEnabled(True)
        QMessageBox.warning(self, "Merkezi hesap", str(error))
        thread.quit()

    def _clear_async(self, thread, worker) -> None:
        if self._auth_thread is thread:
            self._auth_thread = None
            self._auth_worker = None

    def closeEvent(self, event) -> None:
        if self._auth_thread is not None:
            self.status.setText("Merkezi işlem tamamlanıyor; pencere kapanınca yerel işlem etkilenmez.")
            event.ignore()
            return
        super().closeEvent(event)
