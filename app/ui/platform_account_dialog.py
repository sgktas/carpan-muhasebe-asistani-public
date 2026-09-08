from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from app.core.platform_auth_service import PlatformAuthService


class PlatformAccountDialog(QDialog):
    """Merkezi hesap için sade giriş/çıkış ekranı; yerel kullanıcı hesabını değiştirmez."""

    def __init__(self, service: PlatformAuthService, parent=None):
        super().__init__(parent)
        self._service = service
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
        self._refresh()

    def _refresh(self) -> None:
        current = self._service.restore()
        if current.is_connected and current.session:
            self.status.setText(f"Bağlı hesap: {current.session.display_name} · Rol: {current.session.role}")
            self.logout_button.setEnabled(True)
            return
        self.status.setText(current.message)
        self.logout_button.setEnabled(False)

    def _sign_in(self) -> None:
        result = self._service.sign_in(
            company_code=self.company.text(), username=self.username.text(), password=self.password.text()
        )
        self.password.clear()
        self.status.setText(result.message)
        if result.is_connected:
            self.logout_button.setEnabled(True)
            QMessageBox.information(self, "Merkezi hesap", result.message)
        else:
            QMessageBox.warning(self, "Merkezi hesap", result.message)

    def _sign_out(self) -> None:
        result = self._service.sign_out()
        self.status.setText(result.message)
        self.logout_button.setEnabled(False)
