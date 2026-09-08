from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.app_paths import APP_PATHS
from app.core.identity import AuthenticatedSession, IdentityStore
from app.core.operation_history import OperationHistory
from app.modules.registry import build_module_registry
from app.ui.history_page import HistoryPage
from app.ui.integrations_page import IntegrationsPage
from app.ui.operation_center_page import OperationCenterPage
from app.ui.audit_page import AuditPage
from app.ui.settings_page import SettingsPage
from app.ui.team_page import ROLE_LABELS, TeamPage
from app.ui.theme import BRAND_ORANGE, MAIN_STYLE, asset_icon, crisp_pixmap


class MainWindow(QWidget):
    """Çarpan masaüstü uygulamasının modüler kurumsal kabuğu."""

    def __init__(
        self,
        session: AuthenticatedSession,
        identity_store: IdentityStore,
        on_logout=None,
    ):
        super().__init__()
        self.session = session
        self.identity_store = identity_store
        self.on_logout = on_logout
        self.username = session.display_name
        self.history = OperationHistory(
            APP_PATHS.state_dir / "operations.sqlite3",
            actor=session.display_name,
            company_id=session.company_id,
            user_id=session.user_id,
        )
        all_modules = build_module_registry(self.history)
        self.modules = [
            module for module in all_modules if session.allows_module(module.module_id)
        ]
        self.management_items: list[tuple[str, str, str, object]] = []
        if session.can("history.read"):
            self.management_items.append(
                (
                    "operations_center",
                    "Operasyon Merkezi",
                    "history",
                    lambda: OperationCenterPage(self.history),
                )
            )
            self.management_items.append(
                ("history", "Geçmiş İşlemler", "history", lambda: HistoryPage(self.history))
            )
        if session.can("users.manage"):
            self.management_items.append(
                (
                    "team",
                    "Ekip ve Yetkiler",
                    "settings",
                    lambda: TeamPage(self.identity_store, self.session),
                )
            )
        if session.can("audit.read"):
            self.management_items.append(
                (
                    "audit",
                    "Güvenlik Kayıtları",
                    "history",
                    lambda: AuditPage(self.identity_store, self.session),
                )
            )
        if session.can("settings.manage"):
            self.management_items.append(
                ("integrations", "Entegrasyonlar", "settings", IntegrationsPage)
            )
            self.management_items.append(
                ("settings", "Ayarlar", "settings", SettingsPage)
            )

        self.nav_buttons: list[QPushButton] = []
        self.nav_icon_names: list[str] = []
        self.nav_items: list[tuple[str, str]] = []

        self.setObjectName("mainRoot")
        self.setWindowTitle("Çarpan Muhasebe Asistanı")
        self.resize(1180, 760)
        self.setMinimumSize(940, 640)
        self.setStyleSheet(MAIN_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        for module in self.modules:
            self.pages.addWidget(module.page_factory())
        for _item_id, _label, _icon, page_factory in self.management_items:
            self.pages.addWidget(page_factory())
        root.addWidget(self.pages, 1)

        if self.nav_buttons:
            self._set_active_nav(0)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(250)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 20, 18, 18)
        layout.setSpacing(6)

        brand_area = QFrame()
        brand_area.setObjectName("brandArea")
        brand_layout = QVBoxLayout(brand_area)
        brand_layout.setContentsMargins(8, 0, 8, 0)
        brand_layout.setSpacing(3)

        logo_label = QLabel()
        logo_path = APP_PATHS.assets_dir / "carpan-logo-orijinal.png"
        if logo_path.is_file():
            logo_label.setPixmap(crisp_pixmap(self, logo_path, target_width=184))
        else:
            logo_label.setText("Çarpan")
            logo_label.setStyleSheet(
                "color:#214866; font-size:25px; font-weight:700;"
            )
        logo_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        brand_layout.addWidget(logo_label)

        descriptor = QLabel("MUHASEBE ASİSTANI")
        descriptor.setObjectName("brandDescriptor")
        descriptor.setAlignment(Qt.AlignRight)
        brand_layout.addWidget(descriptor)
        layout.addWidget(brand_area)
        layout.addSpacing(24)

        modules_label = QLabel("MODÜLLER")
        modules_label.setObjectName("navSection")
        layout.addWidget(modules_label)
        layout.addSpacing(3)

        for module in self.modules:
            self._add_nav_button(
                layout,
                module.nav_label,
                module.icon_name,
                module.module_id,
            )

        if self.management_items:
            layout.addSpacing(18)
            management_label = QLabel("YÖNETİM")
            management_label.setObjectName("navSection")
            layout.addWidget(management_label)
            layout.addSpacing(3)
            for item_id, label, icon_name, _factory in self.management_items:
                self._add_nav_button(layout, label, icon_name, item_id)

        layout.addStretch()
        layout.addWidget(self._build_user_card())
        return sidebar

    def _build_user_card(self) -> QFrame:
        user_card = QFrame()
        user_card.setObjectName("userCard")
        user_layout = QHBoxLayout(user_card)
        user_layout.setContentsMargins(11, 10, 11, 10)
        user_layout.setSpacing(9)

        avatar = QLabel(self.username[:1].upper())
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            f"background-color:{BRAND_ORANGE}; color:#ffffff; "
            "border-radius:17px; font-size:13px; font-weight:700;"
        )
        user_layout.addWidget(avatar)

        user_col = QVBoxLayout()
        user_col.setSpacing(1)
        name_label = QLabel(self.username)
        name_label.setObjectName("userName")
        status_label = QLabel(
            f"{self.session.company_name} · "
            f"{ROLE_LABELS.get(self.session.role, self.session.role)}"
        )
        status_label.setObjectName("userStatus")
        status_label.setWordWrap(True)
        logout_button = QPushButton("Çıkış yap")
        logout_button.setObjectName("logoutButton")
        logout_button.setCursor(Qt.PointingHandCursor)
        logout_button.clicked.connect(self._logout)

        user_col.addWidget(name_label)
        user_col.addWidget(status_label)
        user_col.addWidget(logout_button)
        user_layout.addLayout(user_col, 1)
        return user_card

    def _logout(self) -> None:
        self.identity_store.record_logout(self.session)
        if callable(self.on_logout):
            self.on_logout()
        self.close()

    def _add_nav_button(
        self,
        layout: QVBoxLayout,
        label: str,
        icon_name: str,
        item_id: str,
    ) -> None:
        index = len(self.nav_buttons)
        button = QPushButton(label)
        button.setProperty("class", "navItem")
        button.setProperty("active", "false")
        button.setIcon(asset_icon(APP_PATHS.assets_dir, icon_name))
        button.setIconSize(QSize(18, 18))
        button.setMinimumHeight(44)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(
            lambda _checked=False, page_index=index: self._on_nav_clicked(
                page_index
            )
        )
        layout.addWidget(button)
        self.nav_buttons.append(button)
        self.nav_icon_names.append(icon_name)
        self.nav_items.append((item_id, label))

    def _on_nav_clicked(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        page = self.pages.widget(index)
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()
        self._set_active_nav(index)

    def _set_active_nav(self, active_index: int) -> None:
        for index, button in enumerate(self.nav_buttons):
            active = index == active_index
            button.setProperty("active", "true" if active else "false")
            button.setIcon(
                asset_icon(
                    APP_PATHS.assets_dir,
                    self.nav_icon_names[index],
                    active=active,
                )
            )
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()
