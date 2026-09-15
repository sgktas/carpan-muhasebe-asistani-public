from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Slot, QThread
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
from app.ui.components import SidebarItem, SidebarSection
from app.ui.design_system import TOKENS
from app.ui.product_pages import AutomationHubPage, ProductStatePage
from app.ui.product_registry import (
    ACTIVE,
    LOCKED,
    ProductModule,
    grouped_product_modules,
)
from app.ui.theme import MAIN_STYLE, asset_icon, crisp_pixmap


SIDEBAR_EXPANDED_WIDTH = 288
SIDEBAR_COLLAPSED_WIDTH = 78


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

        self._available_page_ids = {
            *(module.module_id for module in self.modules),
            *(item_id for item_id, _label, _icon, _factory in self.management_items),
        }
        self.product_module_states = {
            definition.module_id: self._product_module_state(
                definition, self._available_page_ids,
            )
            for _group, definitions in grouped_product_modules()
            for definition in definitions
        }

        self.nav_buttons: list[QPushButton] = []
        self.nav_icon_names: list[str] = []
        self.nav_items: list[tuple[str, str]] = []
        self._nav_status_labels: list[QLabel] = []
        self.nav_item_widgets: list[SidebarItem] = []
        self._nav_parent_by_target: dict[str, str] = {}
        self._page_indices: dict[str, int] = {}
        self._nav_section_labels: list[QLabel] = []
        self._sidebar_collapsed = False
        self._central_refresh_thread: QThread | None = None
        self._central_refresh_worker: BackgroundWorker | None = None
        self._pending_logout = False

        self.setObjectName("mainRoot")
        shell_font = QFont(TOKENS.font_family)
        shell_font.setPixelSize(TOKENS.body_size)
        self.setFont(shell_font)
        self.setWindowTitle("Çarpan Muhasebe Asistanı")
        self.resize(1366, 768)
        self.setMinimumSize(1024, 680)
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
        # Inactive legacy pages must not enlarge the application window.
        # Their own scroll areas retain access to taller content.
        self.pages.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._pages_by_id: dict[str, QWidget] = {}
        for module in self.modules:
            self._register_page(module.module_id, module.page_factory())
        for _item_id, _label, _icon, page_factory in self.management_items:
            self._register_page(_item_id, page_factory())
        self._register_product_pages()
        workspace_layout.addWidget(self.pages, 1)
        root.addWidget(workspace, 1)

        operation_center = self._pages_by_id.get("operations_center")
        if isinstance(operation_center, OperationCenterPage):
            operation_center.safe_manim_retry_requested.connect(
                self._open_safe_manim_retry
            )

        if self.nav_buttons:
            self.navigate_to(self.nav_items[0][0])

    def _register_page(self, page_id: str, page: QWidget) -> None:
        for scroll in [page, *page.findChildren(QScrollArea)]:
            if isinstance(scroll, QScrollArea) and scroll.widget() is not None:
                canvas = scroll.widget()
                canvas.setObjectName("pageCanvas")
                if canvas.layout() is not None:
                    canvas.layout().setContentsMargins(24, 24, 24, 24)
        self.pages.addWidget(page)
        self._pages_by_id[page_id] = page
        self._page_indices[page_id] = self.pages.count() - 1

    def _register_product_pages(self) -> None:
        """Bind product-level navigation to safe landing pages or existing pages."""
        available = set(self._pages_by_id)
        automation_targets = tuple(
            (item_id, title, detail)
            for item_id, title, detail in (
                ("manim_transfer", "Hareket aktarma", "MANİM kaynak adaptörüyle dosya hareketlerini eşleştirin ve çıktı planlayın."),
                ("report_editing", "Rapor standardizasyonu", "FOM kaynak adaptörüyle müşteri, satış ve tahsilat raporlarını hazırlayın."),
                ("customer_list_import", "Müşteri listesi", "Kaynak müşteri verilerini yerel çalışma için düzenleyin."),
            )
            if item_id in available
        )
        reconciliation_targets = tuple(
            (item_id, title, detail)
            for item_id, title, detail in (
                ("bank_reconciliation", "Banka mutabakatı", "Banka ve Netsis hareketlerini karşılaştırın."),
                ("cari_reconciliation", "Cari mutabakat", "Müşteri bazında mutabakat kontrolü yapın."),
            )
            if item_id in available
        )
        operations_targets = tuple(
            (item_id, title, detail)
            for item_id, title, detail in (
                ("operations_center", "Operasyon görünümü", "İşlem durumlarını, inceleme kayıtlarını ve kurtarma yönlendirmelerini görün."),
                ("history", "Geçmiş işlemler", "Tamamlanan işlemleri ve çıktı sonuçlarını inceleyin."),
                ("audit", "Güvenlik kayıtları", "Erişim ve güvenlik olaylarını inceleyin."),
            )
            if item_id in available
        )
        reports_targets = tuple(
            (item_id, title, detail)
            for item_id, title, detail in (
                ("report_editing", "Rapor standardizasyonu", "FOM kaynak adaptörüyle satış ve tahsilat raporlarını onaylı çıktı biçimlerine hazırlayın."),
            )
            if item_id in available
        )
        for _group, definitions in grouped_product_modules():
            for definition in definitions:
                state = self._product_module_state(definition, available)
                if definition.module_id == "accounting_automation":
                    page = AutomationHubPage(definition, automation_targets)
                    for target, _title, _detail in automation_targets:
                        self._nav_parent_by_target[target] = definition.module_id
                elif definition.module_id == "reconciliation":
                    page = AutomationHubPage(definition, reconciliation_targets)
                    for target, _title, _detail in reconciliation_targets:
                        self._nav_parent_by_target[target] = definition.module_id
                elif definition.module_id == "operations":
                    page = AutomationHubPage(definition, operations_targets)
                    for target, _title, _detail in operations_targets:
                        self._nav_parent_by_target[target] = definition.module_id
                elif definition.module_id == "reports":
                    page = AutomationHubPage(definition, reports_targets)
                    for target, _title, _detail in reports_targets:
                        self._nav_parent_by_target[target] = definition.module_id
                elif definition.legacy_target and state == ACTIVE and definition.legacy_target in available:
                    page = self._pages_by_id[definition.legacy_target]
                    self._page_indices[definition.module_id] = self._page_indices[definition.legacy_target]
                    self._pages_by_id[definition.module_id] = page
                    continue
                else:
                    page = ProductStatePage(definition, state=state)
                if isinstance(page, (AutomationHubPage, ProductStatePage)):
                    page.open_requested.connect(self.navigate_to)
                self._register_page(definition.module_id, page)

    def _product_module_state(self, definition: ProductModule, available: set[str]) -> str:
        if definition.default_state != ACTIVE:
            return definition.default_state
        if definition.capability and not self.session.can(definition.capability):
            return LOCKED
        required_targets = {
            "accounting_automation": {"manim_transfer", "report_editing", "customer_list_import"},
            "reconciliation": {"bank_reconciliation", "cari_reconciliation"},
            "reports": {"report_editing"},
            "operations": {"operations_center", "history"},
        }.get(definition.module_id)
        if required_targets is not None and not (required_targets & available):
            return LOCKED
        return ACTIVE

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
        search = QLineEdit()
        search.setObjectName("globalSearch")
        search.setPlaceholderText("Çalışma alanında ara · Yakında")
        search.setAccessibleName("Genel arama — yakında")
        search.setEnabled(False)
        search.setMaximumWidth(275)
        layout.addWidget(search, 1)
        company = QLabel(self.session.company_name)
        company.setObjectName("topbarCompany")
        company.setToolTip(self.session.company_name)
        company.setMaximumWidth(200)
        company.setMinimumWidth(100)
        company.setWordWrap(True)
        layout.addWidget(company)
        account = QLabel(self.username[:1].upper())
        account.setObjectName("topbarAvatar")
        account.setFixedSize(32, 32)
        account.setAlignment(Qt.AlignCenter)
        account.setToolTip(f"{self.username} · {self.session.company_name}")
        layout.addWidget(account)
        self.workspace_status.hide()
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
        self.navigate_to("manim_transfer")

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_EXPANDED_WIDTH)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(TOKENS.space_2)

        brand_area = QFrame()
        brand_area.setObjectName("brandArea")
        brand_layout = QVBoxLayout(brand_area)
        brand_layout.setContentsMargins(10, 4, 10, 8)
        brand_layout.setSpacing(TOKENS.space_1)

        logo_label = QLabel()
        logo_path = APP_PATHS.assets_dir / "carpan-logo-beyaz.png"
        if logo_path.is_file():
            logo_label.setPixmap(crisp_pixmap(self, logo_path, target_width=150))
        else:
            logo_label.setText("Çarpan")
            logo_label.setStyleSheet(
                "color:#FFFFFF; font-size:25px; font-weight:700;"
            )
        logo_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        brand_layout.addWidget(logo_label)
        self.brand_logo_label = logo_label

        descriptor = QLabel("Finansal Operasyon Platformu")
        descriptor.setObjectName("brandDescriptor")
        descriptor.setAlignment(Qt.AlignLeft)
        brand_layout.addWidget(descriptor)
        self.brand_descriptor = descriptor
        layout.addWidget(brand_area)
        self.sidebar_toggle = QPushButton("Menüyü daralt")
        self.sidebar_toggle.setObjectName("sidebarToggle")
        self.sidebar_toggle.setCursor(Qt.PointingHandCursor)
        self.sidebar_toggle.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self.sidebar_toggle)

        navigation_scroll = QScrollArea()
        navigation_scroll.setObjectName("sidebarNavigationScroll")
        navigation_scroll.setWidgetResizable(True)
        navigation_scroll.setFrameShape(QFrame.NoFrame)
        navigation_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        navigation_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        navigation_scroll.setFocusPolicy(Qt.NoFocus)
        navigation_content = QWidget()
        navigation_content.setObjectName("sidebarNavigationContent")
        navigation_layout = QVBoxLayout(navigation_content)
        navigation_layout.setContentsMargins(
            0,
            TOKENS.space_2,
            TOKENS.space_2,
            TOKENS.space_2,
        )
        navigation_layout.setSpacing(TOKENS.space_2)
        for group, definitions in grouped_product_modules():
            section = SidebarSection(group)
            self._nav_section_labels.append(section.title_label)
            for definition in definitions:
                self._add_nav_button(
                    section.layout,
                    definition.display_name,
                    definition.icon_name,
                    definition.module_id,
                    self.product_module_states[definition.module_id],
                )
            navigation_layout.addWidget(section)
        navigation_layout.addStretch(1)
        navigation_scroll.setWidget(navigation_content)
        self.sidebar_navigation_scroll = navigation_scroll
        layout.addWidget(navigation_scroll, 1)

        self.sidebar_user_card = self._build_user_card()
        layout.addWidget(self.sidebar_user_card)
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
            f"background-color:{TOKENS.brand}; color:{TOKENS.surface}; "
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
        self.sidebar.setFixedWidth(
            SIDEBAR_COLLAPSED_WIDTH if collapsed else SIDEBAR_EXPANDED_WIDTH
        )
        self.brand_descriptor.setVisible(not collapsed)
        logo_path = APP_PATHS.assets_dir / "carpan-logo-beyaz.png"
        if logo_path.is_file():
            self.brand_logo_label.setPixmap(
                crisp_pixmap(self, logo_path, target_width=38 if collapsed else 150)
            )
        self.sidebar_toggle.setText("Menüyü aç" if collapsed else "Menüyü daralt")
        self.sidebar_toggle.setToolTip("Gezinme menüsünü aç" if collapsed else "Gezinme menüsünü daralt")
        for label in self._nav_section_labels:
            label.setVisible(not collapsed)
        for status in self._nav_status_labels:
            status.setVisible(not collapsed)
        self.user_name_label.setVisible(not collapsed)
        self.user_status_label.setVisible(not collapsed)
        self._central_status_label.setVisible(not collapsed)
        self.logout_button.setText("⎋" if collapsed else "Çıkış yap")
        self.logout_button.setToolTip("Çıkış yap")
        for index, button in enumerate(self.nav_buttons):
            label = self.nav_items[index][1]
            button.setText("" if collapsed else label)
            button.setToolTip(label)
            button.setMinimumHeight(34)
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
        state: str,
    ) -> None:
        index = len(self.nav_buttons)
        item = SidebarItem(label, state)
        button = item.button
        button.setIcon(asset_icon(APP_PATHS.assets_dir, icon_name))
        button.setIconSize(QSize(18, 18))
        button.setMinimumHeight(34)
        button.clicked.connect(
            lambda _checked=False, page_index=index: self._on_nav_clicked(
                page_index
            )
        )
        layout.addWidget(item)
        self.nav_buttons.append(button)
        self.nav_icon_names.append(icon_name)
        self.nav_items.append((item_id, label))
        self._nav_status_labels.append(item.status)
        self.nav_item_widgets.append(item)

    def _on_nav_clicked(self, index: int) -> None:
        if not (0 <= index < len(self.nav_items)):
            return
        self.navigate_to(self.nav_items[index][0])

    @Slot(str)
    def navigate_to(self, page_id: str) -> None:
        page_index = self._page_indices.get(page_id)
        if page_index is None:
            return
        self.pages.setCurrentIndex(page_index)
        page = self.pages.widget(page_index)
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()
        navigation_id = self._nav_parent_by_target.get(page_id, page_id)
        index = next(
            (position for position, (item_id, _label) in enumerate(self.nav_items) if item_id == navigation_id),
            -1,
        )
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
            "dashboard": "Modüler muhasebe otomasyon çalışma alanına genel bakış.",
            "accounting_automation": "Kaynakları sınıflandırın, eşleştirme kurallarını uygulayın ve incelemeleri yönetin.",
            "tax_automation": "Vergi otomasyonu modülünün ürün hazırlık durumu.",
            "banking": "Banka bağlantısı yapılandırma ve kaynak hazırlık durumu.",
            "einvoice": "E-Fatura modül lisans ve bağlantı durumu.",
            "reconciliation": "Banka ve cari mutabakat çalışma araçları.",
            "operations": "Operasyon görünümü, geçmiş işlemler ve güvenlik kayıtları.",
            "reports": "Rapor standardizasyonu ve çıktı hazırlama çalışma alanı.",
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
