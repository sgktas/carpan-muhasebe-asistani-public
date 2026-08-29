from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.app_paths import APP_PATHS
from app.ui.theme import LOGIN_STYLE, crisp_pixmap

ASSETS_DIR = APP_PATHS.assets_dir


class LoginWindow(QWidget):
    """Çarpan Muhasebe Asistanı kurumsal giriş ekranı."""

    def __init__(self, on_login_success):
        super().__init__()
        self.on_login_success = on_login_success
        self.setObjectName("loginRoot")
        self.setWindowTitle("Çarpan Muhasebe Asistanı — Giriş")
        self.resize(620, 700)
        self.setMinimumSize(560, 640)
        self.setStyleSheet(LOGIN_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(420)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(38, 34, 38, 30)
        card_layout.setSpacing(0)

        accent_line = QFrame()
        accent_line.setObjectName("accentLine")
        accent_line.setFixedHeight(4)
        accent_line.setFixedWidth(46)
        card_layout.addWidget(accent_line, 0, Qt.AlignHCenter)
        card_layout.addSpacing(24)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_path = ASSETS_DIR / "carpan-logo-orijinal.png"
        if logo_path.is_file():
            logo_label.setPixmap(crisp_pixmap(self, logo_path, target_width=250))
        else:
            logo_label.setText("Çarpan")
            logo_label.setStyleSheet("color:#214866; font-size:30px; font-weight:700;")
        card_layout.addWidget(logo_label)
        card_layout.addSpacing(12)

        eyebrow = QLabel("MASAÜSTÜ OPERASYON UYGULAMASI")
        eyebrow.setObjectName("loginEyebrow")
        eyebrow.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(eyebrow)
        card_layout.addSpacing(22)

        title = QLabel("Muhasebe Asistanı")
        title.setObjectName("loginTitle")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)
        card_layout.addSpacing(6)

        subtitle = QLabel("Aktarım ve muhasebe operasyonlarınızı güvenle yönetin.")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(30)

        user_label = QLabel("Kullanıcı adı")
        user_label.setProperty("class", "fieldLabel")
        card_layout.addWidget(user_label)
        card_layout.addSpacing(6)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Kullanıcı adınızı girin")
        card_layout.addWidget(self.username_input)
        card_layout.addSpacing(16)

        password_label = QLabel("Parola")
        password_label.setProperty("class", "fieldLabel")
        card_layout.addWidget(password_label)
        card_layout.addSpacing(6)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("İsteğe bağlı")
        self.password_input.returnPressed.connect(self._try_login)
        card_layout.addWidget(self.password_input)
        card_layout.addSpacing(24)

        login_button = QPushButton("Giriş yap")
        login_button.setObjectName("loginButton")
        login_button.setCursor(Qt.PointingHandCursor)
        login_button.clicked.connect(self._try_login)
        card_layout.addWidget(login_button)
        card_layout.addSpacing(24)

        version = QLabel("v1.0 · Çarpan Muhasebe Asistanı")
        version.setObjectName("versionLabel")
        version.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(version)

        outer.addWidget(card)

    def _try_login(self) -> None:
        username = self.username_input.text().strip() or "kullanıcı"
        self.on_login_success(username)
        self.close()
