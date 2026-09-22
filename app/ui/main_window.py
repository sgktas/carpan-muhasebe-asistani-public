from __future__ import annotations

from pathlib import Path

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
from app.ui.accounting_sources_page import AccountingSourcePreparationPage
from app.ui.accounting_resolution_page import AccountingResolutionPage
from app.ui.accounting_outputs_page import AccountingOutputsPage
from app.ui.product_registry import (
    ACTIVE,
    LOCKED,
    ProductModule,
    grouped_product_modules,
)
from app.ui.theme import MAIN_STYLE, crisp_pixmap
from app.ui.workspace_icons import product_sidebar_icon, shell_icon


SIDEBAR_EXPANDED_WIDTH = 220
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
                ("settings", "Ayarlar", "settings", lambda: SettingsPage(self.session, self.history, self.identity_store))
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
        self._sidebar_sections: list[SidebarSection] = []
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
        settings_page = self._pages_by_id.get("settings")
        if settings_page is not None and hasattr(settings_page, "company_renamed"):
            settings_page.company_renamed.connect(self._apply_company_session)
        automation_page = self._pages_by_id.get("manim_transfer")
        automation_workspace = getattr(automation_page, "accounting_workspace", None)
        if automation_workspace is not None and hasattr(automation_workspace, "source_tools_requested"):
            automation_workspace.matching_requested.connect(lambda: self._open_accounting_mode("rules"))
            automation_workspace.source_tools_requested.connect(
                lambda: self._open_accounting_mode("sources")
            )
        if automation_page is not None and hasattr(automation_page, "source_preparation_requested"):
            automation_page.source_preparation_requested.connect(self._open_source_preparation_with_files)
        if hasattr(self, "accounting_sources_page"):
            self.accounting_sources_page.manim_sources_requested.connect(
                lambda: self._open_accounting_mode("new")
            )
            if automation_workspace is not None:
                self.accounting_sources_page.manim_sources_requested.connect(
                    automation_workspace.add_sources_requested.emit
                )
        workspace_layout.addWidget(self.pages, 1)
        root.addWidget(workspace, 1)

        operation_center = self._pages_by_id.get("operations_center")
        if isinstance(operation_center, OperationCenterPage):
            automation = self._pages_by_id.get("manim_transfer")
            if hasattr(automation, "accounting_workspace"):
                automation.accounting_workspace.operation_reader = operation_center.operation_read_model
            operation_center.safe_manim_retry_requested.connect(
                self._open_safe_manim_retry
            )

        if self.nav_buttons:
            self.navigate_to(self.nav_items[0][0])

    def _register_page(self, page_id: str, page: QWidget) -> None:
        for scroll in [page, *page.findChildren(QScrollArea)]:
            if isinstance(scroll, QScrollArea) and scroll.widget() is not None:
                if scroll.objectName() in {"automationCanvasScroll", "resolutionEditorScroll", "inspectorEvidenceScroll"}:
                    continue  # These workspaces own their responsive spacing.
                canvas = scroll.widget()
                canvas.setObjectName("pageCanvas")
                if canvas.layout() is not None:
                    margin = 0 if page_id == "manim_transfer" else 24
                    canvas.layout().setContentsMargins(margin, margin, margin, margin)
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
                ("report_editing", "FOM Rapor Motoru", "Ham FOM müşteri, satış ve tahsilat raporlarını onaylı muhasebe girdilerine hazırlayın."),
                ("customer_list_import", "Müşteri Listesi", "Kaynak müşteri verilerini yerel çalışma için düzenleyin ve hafızaya alın."),
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
        # FOM is a source-preparation adapter under Muhasebe Otomasyonu > Kaynaklar.
        # It must not surface as a standalone product under Raporlar.
        reports_targets: tuple[tuple[str, str, str], ...] = ()
        for _group, definitions in grouped_product_modules():
            for definition in definitions:
                state = self._product_module_state(definition, available)
                if definition.module_id == "accounting_automation":
                    if "manim_transfer" in available and hasattr(self._pages_by_id["manim_transfer"], "accounting_workspace"):
                        page = self._pages_by_id["manim_transfer"]
                        self._pages_by_id[definition.module_id] = page
                        self._page_indices[definition.module_id] = self._page_indices["manim_transfer"]
                        self.accounting_sources_page = AccountingSourcePreparationPage(self.history)
                        self.accounting_sources_page.back_to_work_requested.connect(
                            lambda: self._open_accounting_mode("new")
                        )
                        page.tabs.addTab(self.accounting_sources_page, "Kaynaklar")

                        self.accounting_resolution_page = AccountingResolutionPage()
                        self.accounting_resolution_page.back_to_work_requested.connect(
                            lambda: self._open_accounting_mode("new")
                        )
                        self.accounting_resolution_page.resolutions_submitted.connect(
                            lambda resolutions, automation_page=page: self._submit_accounting_resolutions(
                                automation_page, resolutions
                            )
                        )
                        page.tabs.addTab(self.accounting_resolution_page, "Eşleştirme & Kurallar")
                        self.accounting_outputs_page = AccountingOutputsPage(page.accounting_workspace, self.history,
                            allow_history=self.session.can('history.read'))
                        page.tabs.addTab(self.accounting_outputs_page, "Çıktılar")
                        self.accounting_outputs_page.settings_requested.connect(lambda target=page: target.tabs.setCurrentIndex(1))
                        self.accounting_outputs_page.history_requested.connect(lambda: self.navigate_to('history'))
                        page.accounting_workspace.outputs_requested.connect(lambda: self._open_accounting_mode('outputs'))
                        if hasattr(page, "integrated_manual_review_requested"):
                            page.integrated_manual_review_requested.connect(
                                self._open_integrated_manual_review
                            )
                        for target, _title, _detail in automation_targets:
                            self._nav_parent_by_target[target] = definition.module_id
                        continue
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
                    page = ProductStatePage(definition, state=state)
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

    def _display_company_name(self) -> str:
        raw = " ".join(str(self.session.company_name or "").split())
        generic = {
            "çarpan muhasebe asistanı",
            "carpan muhasebe asistani",
            "çarpan",
            "carpan",
        }
        if not raw or raw.casefold() in generic:
            return "Firma tanımlanmamış"
        return raw

    @Slot(object)
    def _apply_company_session(self, updated_session) -> None:
        """Refresh visible company identity after Settings updates it locally."""
        self.session = updated_session
        text = self._display_company_name()
        if hasattr(self, "sidebar_company_name"):
            self.sidebar_company_name.setText(text)
            self.sidebar_company_name.setToolTip(updated_session.company_name)
        if hasattr(self, "topbar_company_label"):
            self.topbar_company_label.setText(text)
            self.topbar_company_label.setToolTip(updated_session.company_name)
        if hasattr(self, "sidebar_user_card"):
            self.sidebar_user_card.setToolTip(
                f"{updated_session.company_name} · {ROLE_LABELS.get(updated_session.role, updated_session.role)}"
            )

    def _build_workspace_header(self) -> QFrame:
        """Compact finance-workspace top bar matching the approved mockup."""
        header = QFrame()
        header.setObjectName("workspaceHeader")
        self.workspace_header = header
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 0, 16, 0)
        layout.setSpacing(10)

        breadcrumb = QHBoxLayout()
        breadcrumb.setSpacing(7)
        self.workspace_heading = QLabel("Çalışma alanı")
        self.workspace_heading.setObjectName("workspaceHeading")
        self.workspace_context = QLabel("›  Yeni çalışma")
        self.workspace_context.setObjectName("workspaceContext")
        self.workspace_context.hide()
        breadcrumb.addWidget(self.workspace_heading)
        breadcrumb.addWidget(self.workspace_context)
        breadcrumb.addStretch(1)
        layout.addLayout(breadcrumb, 1)

        # Kept for compatibility with tests and other pages; the premium shell
        # presents this context in the breadcrumb instead of a second line.
        self.workspace_subtitle = QLabel("Günlük finans operasyonları")
        self.workspace_subtitle.setObjectName("workspaceSubtitle")
        self.workspace_subtitle.hide()

        self.workspace_status = QLabel("Yerel çalışma alanı")
        self.workspace_status.setObjectName("workspaceStatus")
        self.workspace_status.hide()

        local_mode = QPushButton("Dosya tabanlı çalışma")
        local_mode.setObjectName("topbarTextAction")
        local_mode.setIcon(shell_icon("file", 14))
        local_mode.setIconSize(QSize(14, 14))
        local_mode.setFocusPolicy(Qt.NoFocus)
        local_mode.setToolTip("Bu çalışma mevcut yerel dosya adaptörlerini kullanır.")
        layout.addWidget(local_mode)

        history_button = QPushButton("Geçmiş")
        history_button.setObjectName("topbarTextAction")
        history_button.setIcon(shell_icon("history", 14))
        history_button.setIconSize(QSize(14, 14))
        history_button.clicked.connect(lambda: self.navigate_to("history"))
        history_button.setEnabled("history" in self._available_page_ids)
        layout.addWidget(history_button)

        search = QLineEdit()
        search.setObjectName("globalSearch")
        search.setPlaceholderText("Müşteri, belge, tutar ara…")
        search.setAccessibleName("Genel arama — yakında")
        search.setReadOnly(True)
        search.setMinimumWidth(190)
        search.setMaximumWidth(280)
        search.addAction(shell_icon("search", 14, "#6D7C92"), QLineEdit.LeadingPosition)
        layout.addWidget(search)

        company_box = QFrame()
        company_box.setObjectName("topbarCompanyBox")
        company_layout = QHBoxLayout(company_box)
        company_layout.setContentsMargins(10, 7, 9, 7)
        company_layout.setSpacing(8)
        company_text = QVBoxLayout()
        company_text.setContentsMargins(0, 0, 0, 0)
        company_text.setSpacing(0)
        company_label = QLabel(self._display_company_name())
        company_label.setObjectName("topbarCompany")
        company_label.setMaximumWidth(185)
        company_label.setToolTip(
            self.session.company_name if self._display_company_name() != "Firma tanımlanmamış"
            else "Yerel kurulumdaki firma adı ürün adı olarak kayıtlı; gerçek firma adı henüz tanımlı değil."
        )
        company_context = QLabel("Yerel çalışma alanı")
        company_context.setObjectName("topbarCompanyContext")
        company_text.addWidget(company_label)
        company_text.addWidget(company_context)
        company_layout.addLayout(company_text)
        company_avatar = QLabel(self.username[:1].upper())
        company_avatar.setObjectName("topbarAvatar")
        company_avatar.setFixedSize(24, 24)
        company_avatar.setAlignment(Qt.AlignCenter)
        company_avatar.setToolTip(self.username)
        company_layout.addWidget(company_avatar)
        self.topbar_company_label = company_label
        self.topbar_company_context = company_context
        company_box.hide()
        self.topbar_company_box = company_box

        bell = QPushButton()
        bell.setObjectName("topbarIconAction")
        bell.setIcon(shell_icon("bell", 15))
        bell.setIconSize(QSize(15, 15))
        bell.setEnabled(False)
        bell.setToolTip("Bildirimler — yakında")
        bell.setFixedSize(32, 32)
        layout.addWidget(bell)
        panel_toggle = QPushButton()
        panel_toggle.setObjectName("topbarIconAction")
        panel_toggle.setIcon(shell_icon("panel", 15))
        panel_toggle.setIconSize(QSize(15, 15))
        panel_toggle.setFixedSize(32, 32)
        panel_toggle.setToolTip("Çalışma görünümü")
        panel_toggle.setEnabled(False)
        layout.addWidget(panel_toggle)
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
        layout.setContentsMargins(10, 10, 8, 8)
        layout.setSpacing(5)

        brand_area = QFrame()
        brand_area.setObjectName("brandArea")
        brand_layout = QVBoxLayout(brand_area)
        brand_layout.setContentsMargins(0, 0, 0, 6)
        brand_layout.setSpacing(0)

        logo_label = QLabel()
        logo_path = APP_PATHS.assets_dir / "carpan_brand_mockup_exact4x.png"
        if logo_path.is_file():
            logo_label.setPixmap(crisp_pixmap(self, logo_path, target_width=151))
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
        descriptor.hide()
        layout.addWidget(brand_area)

        company_card = QFrame()
        company_card.setObjectName("companyCard")
        company_layout = QHBoxLayout(company_card)
        company_layout.setContentsMargins(9, 6, 8, 6)
        company_layout.setSpacing(8)
        company_text = QVBoxLayout()
        company_text.setSpacing(1)
        company_name = QLabel(self._display_company_name())
        company_name.setObjectName("companyCardName")
        company_name.setToolTip(self.session.company_name)
        company_name.setTextInteractionFlags(Qt.TextSelectableByMouse)
        company_hint = QLabel("Yerel çalışma alanı")
        company_hint.setObjectName("companyCardHint")
        company_text.addWidget(company_name)
        company_text.addWidget(company_hint)
        company_layout.addLayout(company_text, 1)
        company_chevron = QPushButton("⌄")
        company_chevron.setObjectName("companyCardChevron")
        company_chevron.setFixedSize(22, 22)
        company_chevron.setToolTip("Firma ayarlarını aç")
        company_chevron.clicked.connect(lambda _checked=False: self.navigate_to("settings"))
        company_layout.addWidget(company_chevron)
        self.company_card = company_card
        self.sidebar_company_name = company_name
        self.sidebar_company_hint = company_hint
        layout.addWidget(company_card)

        self.sidebar_toggle = QPushButton("Menüyü daralt")
        self.sidebar_toggle.setObjectName("sidebarToggle")
        self.sidebar_toggle.setCursor(Qt.PointingHandCursor)
        self.sidebar_toggle.clicked.connect(self._toggle_sidebar)
        self.sidebar_toggle.hide()
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
        navigation_layout.setContentsMargins(0, 2, 4, 2)
        navigation_layout.setSpacing(5)
        self._navigation_layout = navigation_layout
        for group, definitions in grouped_product_modules():
            section = SidebarSection(group)
            section.title_label.hide()
            self._nav_section_labels.append(section.title_label)
            self._sidebar_sections.append(section)
            for definition in definitions:
                self._add_nav_button(
                    section.layout,
                    definition.display_name,
                    definition.icon_name,
                    definition.module_id,
                    self.product_module_states[definition.module_id],
                )
                if definition.module_id == "accounting_automation":
                    self._build_accounting_subnav(section.layout)
                if definition.module_id == "operations" and self.session.can("history.read"):
                    history_button = QPushButton("◷  Geçmiş & Audit")
                    history_button.setObjectName("accountingSubnavButton")
                    history_button.clicked.connect(lambda _checked=False: self.navigate_to("history"))
                    section.layout.addWidget(history_button)
            navigation_layout.addWidget(section)
        navigation_layout.addStretch(1)
        navigation_scroll.setWidget(navigation_content)
        self.sidebar_navigation_scroll = navigation_scroll
        # Keep the sidebar scrollbar consistently slim even when Qt hides it
        # after the denser navigation layout no longer needs scrolling.
        self.sidebar_navigation_scroll.verticalScrollBar().setFixedWidth(6)
        layout.addWidget(navigation_scroll, 1)

        self.sidebar_settings_button = QPushButton("Ayarlar")
        self.sidebar_settings_button.setObjectName("sidebarFixedSettings")
        self.sidebar_settings_button.setIcon(product_sidebar_icon("settings", 18))
        self.sidebar_settings_button.setIconSize(QSize(18, 18))
        self.sidebar_settings_button.setCursor(Qt.PointingHandCursor)
        self.sidebar_settings_button.clicked.connect(lambda _checked=False: self.navigate_to("settings"))
        self.sidebar_settings_button.setVisible("settings" in self._available_page_ids)
        layout.addWidget(self.sidebar_settings_button)

        self.sidebar_user_card = self._build_user_card()
        layout.addWidget(self.sidebar_user_card)
        self._sync_sidebar_density()
        return sidebar

    def _build_accounting_subnav(self, layout: QVBoxLayout) -> None:
        self._accounting_expanded = True
        self.accounting_subnav = QFrame()
        self.accounting_subnav.setObjectName("accountingSubnav")
        column = QVBoxLayout(self.accounting_subnav)
        column.setContentsMargins(16, 0, 0, 2)
        column.setSpacing(3)
        self._accounting_subnav_buttons = []
        entries = (
            ("overview", "Genel Bakış"),
            ("new", "Yeni Çalışma"),
            ("sources", "Kaynaklar"),
            ("rules", "Eşleştirme & Kurallar"),
            ("review", "İnceleme Merkezi"),
            ("outputs", "Çıktılar"),
        )
        for mode, label in entries:
            button = QPushButton(label)
            button.setObjectName("accountingSubnavButton")
            button.setProperty("active", "true" if mode == "new" else "false")
            button.clicked.connect(lambda _checked=False, selected=mode: self._open_accounting_mode(selected))
            column.addWidget(button)
            self._accounting_subnav_buttons.append((mode, button))
        layout.addWidget(self.accounting_subnav)

    def _open_accounting_mode(self, mode: str) -> None:
        self._accounting_expanded = True
        self.navigate_to("accounting_automation")
        page = self._pages_by_id.get("accounting_automation")
        workspace = getattr(page, "accounting_workspace", None)
        tabs = getattr(page, "tabs", None)
        if mode == "outputs":
            if tabs is not None and hasattr(self, 'accounting_outputs_page'):
                self.accounting_outputs_page.refresh()
                tabs.setCurrentWidget(self.accounting_outputs_page)
        elif mode == "sources":
            # Source preparation (FOM/customer inputs) is an integrated product
            # surface, not the old standalone report module.
            if tabs is not None and tabs.count() > 2:
                tabs.setCurrentIndex(2)
            elif workspace is not None:
                if tabs is not None:
                    tabs.setCurrentIndex(0)
                workspace.set_mode("sources")
        elif mode == "rules":
            # The fourth hidden tab is the integrated replacement for the
            # legacy ManualMatchDialog.  During processing the worker safely
            # waits while the user resolves records here.
            if tabs is not None and tabs.count() > 3:
                tabs.setCurrentIndex(3)
        else:
            if tabs is not None:
                tabs.setCurrentIndex(0)
            if workspace is not None:
                if mode == "overview":
                    workspace.set_mode("sources")
                else:
                    workspace.set_mode("new")
                    if mode == "review":
                        workspace.set_filter_mode("attention")
        for item_mode, button in getattr(self, "_accounting_subnav_buttons", []):
            button.setProperty("active", "true" if item_mode == mode else "false")
            button.style().unpolish(button)
            button.style().polish(button)


    @Slot(object)
    def _open_integrated_manual_review(self, request) -> None:
        """Open the in-product matching workspace for a waiting engine request."""
        resolution_page = getattr(self, "accounting_resolution_page", None)
        if resolution_page is None:
            return
        resolution_page.load_request(request.pending_items, request.customers)
        self._open_accounting_mode("rules")

    def _submit_accounting_resolutions(self, automation_page, resolutions) -> None:
        """Return integrated decisions to the paused ProcessingEngine worker."""
        if hasattr(automation_page, "submit_integrated_manual_resolutions"):
            automation_page.submit_integrated_manual_resolutions(resolutions)
        self._open_accounting_mode("new")

    @Slot(object)
    def _open_source_preparation_with_files(self, files) -> None:
        self._open_accounting_mode("sources")
        source_page = getattr(self, "accounting_sources_page", None)
        if source_page is not None:
            source_page.load_files([Path(path) for path in files])

    def _build_user_card(self) -> QFrame:
        """Compact account affordance; operational status stays in tooltips."""
        user_card = QFrame()
        user_card.setObjectName("userCard")
        user_layout = QHBoxLayout(user_card)
        user_layout.setContentsMargins(7, 7, 5, 7)
        user_layout.setSpacing(8)

        avatar = QLabel(self.username[:1].upper())
        avatar.setObjectName("sidebarAvatar")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignCenter)
        user_layout.addWidget(avatar)

        user_col = QVBoxLayout()
        user_col.setSpacing(0)
        name_label = QLabel(self.username)
        name_label.setObjectName("userName")
        status_label = QLabel(ROLE_LABELS.get(self.session.role, self.session.role))
        status_label.setObjectName("userStatus")
        status_label.setWordWrap(False)
        user_col.addWidget(name_label)
        user_col.addWidget(status_label)
        user_layout.addLayout(user_col, 1)

        # Kept as a hidden compatibility/status sink.  Long platform messages
        # belong in a tooltip, not as a paragraph in the navigation rail.
        self._central_status_label = QLabel()
        self._central_status_label.setObjectName("userStatus")
        self._central_status_label.hide()
        user_layout.addWidget(self._central_status_label)

        logout_button = QPushButton("↗")
        logout_button.setObjectName("logoutButton")
        logout_button.setFixedSize(25, 25)
        logout_button.setCursor(Qt.PointingHandCursor)
        logout_button.setToolTip("Çıkış yap")
        logout_button.clicked.connect(self._logout)
        user_layout.addWidget(logout_button)

        self.user_name_label = name_label
        self.user_status_label = status_label
        self.logout_button = logout_button
        user_card.setToolTip(f"{self.session.company_name} · {ROLE_LABELS.get(self.session.role, self.session.role)}")
        return user_card

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        collapsed = self._sidebar_collapsed
        self.sidebar.setFixedWidth(
            SIDEBAR_COLLAPSED_WIDTH if collapsed else SIDEBAR_EXPANDED_WIDTH
        )
        self.brand_descriptor.hide()
        if hasattr(self, "company_card"):
            self.company_card.setVisible(not collapsed)
        if hasattr(self, "accounting_subnav"):
            self._sync_accounting_subnav()
        logo_path = APP_PATHS.assets_dir / "carpan-logo-beyaz.png"
        if logo_path.is_file():
            self.brand_logo_label.setPixmap(
                crisp_pixmap(self, logo_path, target_width=38 if collapsed else 132)
            )
        self.sidebar_toggle.setText("Menüyü aç" if collapsed else "Menüyü daralt")
        self.sidebar_toggle.setToolTip("Gezinme menüsünü aç" if collapsed else "Gezinme menüsünü daralt")
        for label in self._nav_section_labels:
            label.hide()
        for item in self.nav_item_widgets:
            item.set_collapsed(collapsed)
        self.user_name_label.setVisible(not collapsed)
        self.user_status_label.setVisible(not collapsed)
        self._central_status_label.hide()
        if hasattr(self, "sidebar_settings_button"):
            self.sidebar_settings_button.setText("" if collapsed else "Ayarlar")
            self.sidebar_settings_button.setToolTip("Ayarlar")
        self.logout_button.setText("↗")
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
        self.sidebar_user_card.setToolTip("Merkezi lisans kontrol ediliyor…")
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
        self.sidebar_user_card.setToolTip(message)
        if self._central_refresh_thread is not None:
            self._central_refresh_thread.quit()

    @Slot(object)
    def _central_refresh_failed(self, _error) -> None:
        # Ağ/servis sorunu yerel muhasebe iş akışını durdurmaz.
        self._central_status_label.setText("Merkezi lisans şu an doğrulanamadı; yerel çalışma devam ediyor.")
        self.sidebar_user_card.setToolTip("Merkezi lisans doğrulanamadı · Yerel çalışma devam ediyor")
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
        item.show_status = state != ACTIVE or item_id in {'accounting_automation', 'reconciliation'}
        item.status.setVisible(item.show_status)
        button = item.button
        button.setIcon(product_sidebar_icon(item_id, 18))
        button.setIconSize(QSize(18, 18))
        button.setMinimumHeight(26)
        button.clicked.connect(
            lambda _checked=False, page_index=index: self._on_nav_clicked(
                page_index
            )
        )
        layout.addWidget(item)
        if item_id == "settings":
            item.hide()
        self.nav_buttons.append(button)
        self.nav_icon_names.append(icon_name)
        self.nav_items.append((item_id, label))
        self._nav_status_labels.append(item.status)
        self.nav_item_widgets.append(item)
        if item_id == "accounting_automation":
            item.expandable = True
            item.chevron.show()
            item.chevron.clicked.connect(lambda _checked=False, i=index: self._on_nav_clicked(i))

    def _on_nav_clicked(self, index: int) -> None:
        if not (0 <= index < len(self.nav_items)):
            return
        if self.nav_items[index][0] == "accounting_automation":
            if self.nav_buttons[index].property("active") == "true":
                self._accounting_expanded = not self._accounting_expanded
                self._sync_accounting_subnav()
                return
            self._accounting_expanded = True
        self.navigate_to(self.nav_items[index][0])

    def _sync_sidebar_density(self) -> None:
        """Use the rail height instead of leaving a dead block above Settings.

        The accounting submenu consumes real vertical space when open, so the
        parent-module rhythm tightens.  With it closed, parent rows spread out
        toward the fixed Settings/profile footer, matching the approved mockup.
        """
        expanded = bool(getattr(self, "_accounting_expanded", False)) and not self._sidebar_collapsed
        section_spacing = 4 if expanded else 13
        for section in self._sidebar_sections:
            section.layout.setSpacing(section_spacing)
        if hasattr(self, "_navigation_layout"):
            self._navigation_layout.setSpacing(4 if expanded else 8)

    def _sync_accounting_subnav(self) -> None:
        expanded = self._accounting_expanded and not self._sidebar_collapsed
        self.accounting_subnav.setVisible(expanded)
        for (item_id, _), item in zip(self.nav_items, self.nav_item_widgets):
            if item_id == "accounting_automation":
                item.chevron.setText("⌃" if expanded else "⌄")
                item.chevron.setAccessibleName("Alt menüyü daralt" if expanded else "Alt menüyü aç")
        self._sync_sidebar_density()

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
            self.nav_item_widgets[index].setProperty('active', 'true' if active else 'false')
            self.nav_item_widgets[index].style().unpolish(self.nav_item_widgets[index])
            self.nav_item_widgets[index].style().polish(self.nav_item_widgets[index])
            button.setProperty("active", "true" if active else "false")
            button.setIcon(
                product_sidebar_icon(self.nav_items[index][0], 18, active=active)
            )
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()
        if hasattr(self, "sidebar_settings_button"):
            settings_active = 0 <= active_index < len(self.nav_items) and self.nav_items[active_index][0] == "settings"
            self.sidebar_settings_button.setProperty("active", "true" if settings_active else "false")
            self.sidebar_settings_button.setIcon(product_sidebar_icon("settings", 18, active=settings_active))
            self.sidebar_settings_button.style().unpolish(self.sidebar_settings_button)
            self.sidebar_settings_button.style().polish(self.sidebar_settings_button)
        if 0 <= active_index < len(self.nav_items):
            label = self.nav_items[active_index][1]
            self.workspace_heading.setText(label)
            self.workspace_subtitle.setText(self._workspace_subtitle(active_index))
            accounting = self.nav_items[active_index][0] == "accounting_automation"
            if hasattr(self, "workspace_context"):
                self.workspace_context.setVisible(accounting)
                self.workspace_context.setText("›  Yeni çalışma")
            if hasattr(self, "accounting_subnav"):
                self._sync_accounting_subnav()

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
