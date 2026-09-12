from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Slot, QThread
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from app.core.app_paths import APP_PATHS
from app.core.identity import AuthenticatedSession, IdentityStore
from app.core.operation_history import OperationHistory
from app.core.entitlements import effective_entitlements
from app.core.platform_connection import PlatformLicense
from app.core.platform_license_policy import central_license_access
from app.modules.registry import build_module_registry
from app.ui.history_page import HistoryPage
from app.ui.integrations_page import IntegrationsPage
from app.ui.operation_center_page import OperationCenterPage
from app.ui.audit_page import AuditPage
from app.ui.background_task import BackgroundWorker
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
        central_license: PlatformLicense | None = None,
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
        local_module_ids = [
            module.module_id
            for module in all_modules
            if session.allows_module(module.module_id)
        ]
        entitlements = effective_entitlements(
            local_module_ids=local_module_ids,
            central_module_ids=(central_license.enabled_modules if central_license else None),
            central_license_usable=central_license_access(central_license),
        )
        self.modules = [
            module for module in all_modules if entitlements.allows(module.module_id)
        ]
        self.management_items: list[tuple[str, str, str, object]] = []
        if session.can("history.read"):
            self.management_items.append(
                (
                    "operations_center",
                    "Operasyon Merkezi",
                    "history",
                    lambda: OperationCenterPage(
                        self.history,
                        identity_store=self.identity_store,
                        session=self.session,
                    ),
                )
            )
            self.management_items.append(
                (
                    "history",
                    "Geçmiş İşlemler",
                    "history",
                    lambda: HistoryPage(
                        self.history,
                        can_record_external_acceptance=session.can(
                            "operations.acceptance.record"
                        ),
                    ),
                )
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
                ("integrations", "Entegrasyonlar", "settings", lambda: IntegrationsPage(history=self.history))
            )
            self.management_items.append(
                ("settings", "Ayarlar", "settings", lambda: SettingsPage(self.session, self.history))
            )

        self.nav_buttons: list[QPushButton] = []
        self.nav_icon_names: list[str] = []
        self.nav_items: list[tuple[str, str]] = []
        self._nav_section_labels: list[QLabel] = []
        self._sidebar_collapsed = False
        self._central_refresh_thread: QThread | None = None
        self._central_refresh_worker: BackgroundWorker | None = None
        self._pending_logout = False

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

        workspace = QFrame()
        workspace.setObjectName("workspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        workspace_layout.addWidget(self._build_workspace_header())

        self.pages = QStackedWidget()
        self._pages_by_id: dict[str, QWidget] = {}
        for module in self.modules:
            page = module.page_factory()
            self.pages.addWidget(page)
            self._pages_by_id[module.module_id] = page
        for _item_id, _label, _icon, page_factory in self.management_items:
            page = page_factory()
            self.pages.addWidget(page)
            self._pages_by_id[_item_id] = page
        workspace_layout.addWidget(self.pages, 1)
        root.addWidget(workspace, 1)

        operation_center = self._pages_by_id.get("operations_center")
        if isinstance(operation_center, OperationCenterPage):
            operation_center.safe_manim_retry_requested.connect(
                self._open_safe_manim_retry
            )

        if self.nav_buttons:
            self._set_active_nav(0)

    def _build_workspace_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("workspaceHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 12, 28, 12)
        layout.setSpacing(10)
        self.workspace_heading = QLabel("Çalışma alanı")
        self.workspace_heading.setObjectName("workspaceHeading")
        self.workspace_subtitle = QLabel("Günlük finans operasyonları")
        self.workspace_subtitle.setObjectName("workspaceSubtitle")
        title_column = QVBoxLayout()
        title_column.setSpacing(1)
        title_column.addWidget(self.workspace_heading)
        title_column.addWidget(self.workspace_subtitle)
        layout.addLayout(title_column, 1)
        self.workspace_status = QLabel("Yerel çalışma alanı")
        self.workspace_status.setObjectName("workspaceStatus")
        layout.addWidget(self.workspace_status)
        return header

    @Slot(object)
    def _open_safe_manim_retry(self, request: dict) -> None:
        page = self._pages_by_id.get("manim_transfer")
        prepare = getattr(page, "prepare_safe_retry", None)
        if not callable(prepare):
            QMessageBox.warning(self, "Yeniden çalışma", "MANİM modülü kullanılamıyor.")
            return
        try:
            prepare(
                request.get("input_files", []),
                output_profile_id=str(request.get("output_profile_id", "netsis")),
                origin_operation_id=int(request.get("operation_id", 0)),
                reason=str(request.get("reason", "Netsis aktarımı reddedildi.")),
            )
        except Exception as error:
            QMessageBox.warning(self, "Yeniden çalışma hazırlanamadı", str(error))
            return
        index = next(
            (position for position, (item_id, _label) in enumerate(self.nav_items) if item_id == "manim_transfer"),
            -1,
        )
        if index >= 0:
            self._on_nav_clicked(index)

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
        self.brand_descriptor = descriptor
        layout.addWidget(brand_area)
        self.sidebar_toggle = QPushButton("Menüyü daralt")
        self.sidebar_toggle.setObjectName("sidebarToggle")
        self.sidebar_toggle.setCursor(Qt.PointingHandCursor)
        self.sidebar_toggle.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self.sidebar_toggle)
        layout.addSpacing(12)

        modules_label = QLabel("MODÜLLER")
        modules_label.setObjectName("navSection")
        self._nav_section_labels.append(modules_label)
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
            self._nav_section_labels.append(management_label)
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
        self._central_status_label = QLabel()
        self._central_status_label.setObjectName("userStatus")
        self._central_status_label.setWordWrap(True)
        logout_button = QPushButton("Çıkış yap")
        logout_button.setObjectName("logoutButton")
        logout_button.setCursor(Qt.PointingHandCursor)
        logout_button.clicked.connect(self._logout)

        user_col.addWidget(name_label)
        user_col.addWidget(status_label)
        user_col.addWidget(self._central_status_label)
        user_col.addWidget(logout_button)
        self.user_name_label = name_label
        self.user_status_label = status_label
        self.logout_button = logout_button
        user_layout.addLayout(user_col, 1)
        return user_card

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        collapsed = self._sidebar_collapsed
        self.sidebar.setFixedWidth(78 if collapsed else 250)
        self.brand_descriptor.setVisible(not collapsed)
        self.sidebar_toggle.setText("Menüyü aç" if collapsed else "Menüyü daralt")
        self.sidebar_toggle.setToolTip("Gezinme menüsünü aç" if collapsed else "Gezinme menüsünü daralt")
        for label in self._nav_section_labels:
            label.setVisible(not collapsed)
        self.user_name_label.setVisible(not collapsed)
        self.user_status_label.setVisible(not collapsed)
        self._central_status_label.setVisible(not collapsed)
        self.logout_button.setText("⎋" if collapsed else "Çıkış yap")
        self.logout_button.setToolTip("Çıkış yap")
        for index, button in enumerate(self.nav_buttons):
            label = self.nav_items[index][1]
            button.setText("" if collapsed else label)
            button.setToolTip(label)
            button.setMinimumHeight(44)
        self.sidebar.style().unpolish(self.sidebar)
        self.sidebar.style().polish(self.sidebar)
        self.sidebar.update()

    def _logout(self) -> None:
        if self._local_operation_running():
            self._central_status_label.setText("Dosyalar hazırlanıyor; işlem tamamlanınca çıkış yapabilirsiniz.")
            return
        self.identity_store.record_logout(self.session)
        if self._central_refresh_thread is not None:
            self._pending_logout = True
            self._central_status_label.setText("Merkezi kontrol tamamlanıyor; ardından çıkış yapılacak.")
            return
        self._complete_logout()

    def _complete_logout(self) -> None:
        if callable(self.on_logout):
            self.on_logout()
        self.close()

    def refresh_central_license_async(self, operation) -> None:
        """Açılışta merkezi lisansı arayüzü bekletmeden yeniler."""
        if self._central_refresh_thread is not None:
            return
        thread = QThread(self)
        worker = BackgroundWorker(operation)
        worker.moveToThread(thread)
        self._central_refresh_thread = thread
        self._central_refresh_worker = worker
        self._central_status_label.setText("Merkezi lisans kontrol ediliyor…")
        thread.started.connect(worker.run)
        worker.finished.connect(self._apply_central_refresh)
        worker.failed.connect(self._central_refresh_failed)
        thread.finished.connect(self._clear_central_refresh)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    @Slot(object)
    def _apply_central_refresh(self, result) -> None:
        message = str(getattr(result, "message", "Merkezi lisans kontrol edildi."))
        self._central_status_label.setText(message)
        if self._central_refresh_thread is not None:
            self._central_refresh_thread.quit()

    @Slot(object)
    def _central_refresh_failed(self, _error) -> None:
        # Ağ/servis sorunu yerel muhasebe iş akışını durdurmaz.
        self._central_status_label.setText("Merkezi lisans şu an doğrulanamadı; yerel çalışma devam ediyor.")
        if self._central_refresh_thread is not None:
            self._central_refresh_thread.quit()

    @Slot()
    def _clear_central_refresh(self) -> None:
        self._central_refresh_thread = None
        self._central_refresh_worker = None
        if self._pending_logout:
            self._pending_logout = False
            self._complete_logout()

    def closeEvent(self, event) -> None:
        if self._local_operation_running():
            self._central_status_label.setText("Dosyalar hazırlanıyor; işlem tamamlanınca pencereyi kapatabilirsiniz.")
            event.ignore()
            return
        if self._central_refresh_thread is not None:
            self._central_status_label.setText("Merkezi kontrol tamamlanıyor; pencere birazdan kapanacak.")
            event.ignore()
            return
        super().closeEvent(event)

    def _local_operation_running(self):
        return any(bool(getattr(widget, "is_busy", False)) for widget in self.findChildren(QWidget))

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
        if 0 <= active_index < len(self.nav_items):
            label = self.nav_items[active_index][1]
            self.workspace_heading.setText(label)
            self.workspace_subtitle.setText(self._workspace_subtitle(active_index))

    def _workspace_subtitle(self, index: int) -> str:
        item_id = self.nav_items[index][0]
        subtitles = {
            "manim_transfer": "Banka hareketlerini kontrol edin, eşleştirin ve aktarım planını yönetin.",
            "report_editing": "Satış ve tahsilat raporlarını Netsis/Psoft aktarımına hazırlayın.",
            "bank_reconciliation": "Banka ve Netsis hareketlerini karşılaştırıp farkları inceleyin.",
            "operations_center": "Bugünkü öncelikleri, inceleme kuyruklarını ve ERP kalite sinyallerini izleyin.",
            "history": "Tamamlanan işlemleri ve çıktı sonuçlarını izleyin.",
            "team": "Ekip, rol ve sorumluluk kapsamını yönetin.",
            "audit": "Güvenlik olaylarını ve erişim kayıtlarını inceleyin.",
            "integrations": "Onaylı çıktı sözleşmelerini ve entegrasyon durumlarını kontrol edin.",
            "settings": "Çalışma alanı ayarlarını ve onaylı şablon kontrollerini yönetin.",
        }
        return subtitles.get(item_id, "Çalışma alanınızı yönetin.")
