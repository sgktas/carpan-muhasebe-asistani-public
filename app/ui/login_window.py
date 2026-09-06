from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.app_paths import APP_PATHS
from app.core.identity import AuthenticationError, IdentityError, IdentityStore
from app.ui.theme import LOGIN_STYLE, crisp_pixmap

ASSETS_DIR = APP_PATHS.assets_dir


class LoginWindow(QWidget):
    """İlk firma kurulumunu ve parolalı yerel oturumu yönetir."""

    def __init__(self, identity_store: IdentityStore, on_login_success):
        super().__init__()
        self.identity_store = identity_store
        self.on_login_success = on_login_success
        self.setup_mode = identity_store.needs_initial_setup()
        self.setObjectName("loginRoot")
        self.setWindowTitle("Çarpan Muhasebe Asistanı — Güvenli Giriş")
        self.resize(620, 780 if self.setup_mode else 700)
        self.setMinimumSize(560, 680 if self.setup_mode else 620)
        self.setStyleSheet(LOGIN_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(430)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(38, 30, 38, 28)
        card_layout.setSpacing(0)

        accent_line = QFrame()
        accent_line.setObjectName("accentLine")
        accent_line.setFixedSize(46, 4)
        card_layout.addWidget(accent_line, 0, Qt.AlignHCenter)
        card_layout.addSpacing(20)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_path = ASSETS_DIR / "carpan-logo-orijinal.png"
        if logo_path.is_file():
            logo_label.setPixmap(crisp_pixmap(self, logo_path, target_width=240))
        else:
            logo_label.setText("Çarpan")
            logo_label.setStyleSheet("color:#214866; font-size:30px; font-weight:700;")
        card_layout.addWidget(logo_label)
        card_layout.addSpacing(10)

        eyebrow = QLabel("FİNANS OPERASYON ÇALIŞMA ALANI")
        eyebrow.setObjectName("loginEyebrow")
        eyebrow.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(eyebrow)
        card_layout.addSpacing(18)

        title = QLabel("İlk Kurulum" if self.setup_mode else "Güvenli Giriş")
        title.setObjectName("loginTitle")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)
        card_layout.addSpacing(6)

        subtitle = QLabel(
            "Firmanızı ve ilk yönetici hesabını oluşturun."
            if self.setup_mode
            else "Firmanızı seçip kullanıcı hesabınızla çalışma alanını açın."
        )
        subtitle.setObjectName("loginSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(22)

        if self.setup_mode:
            self.company_name_input = self._add_field(
                card_layout, "Firma adı", "Örn. Çarpan Dağıtım"
            )
            self.display_name_input = self._add_field(
                card_layout, "Yönetici adı soyadı", "Örn. Ayşe Yılmaz"
            )
        else:
            self.company_combo = QComboBox()
            self.company_combo.setAccessibleName("Firma")
            for company in self.identity_store.companies():
                self.company_combo.addItem(company.name, company.id)
            self._add_labeled_widget(card_layout, "Firma", self.company_combo)

        self.username_input = self._add_field(
            card_layout, "Kullanıcı adı", "Kullanıcı adınızı girin"
        )
        self.password_input = self._add_field(
            card_layout,
            "Parola" if not self.setup_mode else "Yönetici parolası",
            "En az 10 karakter, harf ve rakam" if self.setup_mode else "Parolanızı girin",
            password=True,
        )
        if self.setup_mode:
            self.password_confirm_input = self._add_field(
                card_layout, "Parola tekrar", "Parolayı yeniden girin", password=True
            )

        show_password = QCheckBox("Parolayı göster")
        show_password.toggled.connect(self._toggle_password_visibility)
        card_layout.addWidget(show_password)
        card_layout.addSpacing(10)

        self.error_label = QLabel()
        self.error_label.setObjectName("loginError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        card_layout.addWidget(self.error_label)
        card_layout.addSpacing(12)

        login_button = QPushButton(
            "Güvenli çalışma alanını oluştur" if self.setup_mode else "Giriş yap"
        )
        login_button.setObjectName("loginButton")
        login_button.setCursor(Qt.PointingHandCursor)
        login_button.clicked.connect(self._submit)
        card_layout.addWidget(login_button)
        card_layout.addSpacing(18)

        version = QLabel("Çarpan Muhasebe Asistanı · Yerel güvenli çalışma")
        version.setObjectName("versionLabel")
        version.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(version)
        outer.addWidget(card)

        target = self.password_confirm_input if self.setup_mode else self.password_input
        target.returnPressed.connect(self._submit)

    def _add_field(
        self,
        layout: QVBoxLayout,
        label: str,
        placeholder: str,
        *,
        password: bool = False,
    ) -> QLineEdit:
        widget = QLineEdit()
        widget.setPlaceholderText(placeholder)
        widget.setAccessibleName(label)
        if password:
            widget.setEchoMode(QLineEdit.Password)
        self._add_labeled_widget(layout, label, widget)
        return widget

    @staticmethod
    def _add_labeled_widget(layout: QVBoxLayout, text: str, widget: QWidget) -> None:
        label = QLabel(text)
        label.setProperty("class", "fieldLabel")
        layout.addWidget(label)
        layout.addSpacing(5)
        layout.addWidget(widget)
        layout.addSpacing(12)

    def _toggle_password_visibility(self, visible: bool) -> None:
        mode = QLineEdit.Normal if visible else QLineEdit.Password
        self.password_input.setEchoMode(mode)
        if self.setup_mode:
            self.password_confirm_input.setEchoMode(mode)

    def _submit(self) -> None:
        self.error_label.hide()
        try:
            if self.setup_mode:
                if self.password_input.text() != self.password_confirm_input.text():
                    raise IdentityError("Parolalar birbiriyle aynı değil.")
                session = self.identity_store.create_initial_admin(
                    company_name=self.company_name_input.text(),
                    username=self.username_input.text(),
                    display_name=self.display_name_input.text(),
                    password=self.password_input.text(),
                )
            else:
                company_id = self.company_combo.currentData()
                if company_id is None:
                    raise AuthenticationError("Aktif bir firma çalışma alanı bulunamadı.")
                session = self.identity_store.authenticate(
                    self.username_input.text(),
                    self.password_input.text(),
                    int(company_id),
                )
        except IdentityError as error:
            self.error_label.setText(str(error))
            self.error_label.show()
            return

        self.on_login_success(session)
        self.close()
