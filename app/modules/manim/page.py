from __future__ import annotations
from app.ui.operation_activity import OperationActivity
from app.ui.simulation_dashboard import SimulationDashboard
from app.ui.accounting_workspace import AccountingWorkspace
from app.ui.operation_breakdown import presentation_evidence

from dataclasses import dataclass, field
import logging
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QSize, Qt, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.app_paths import APP_PATHS
from app.core.active_profile_store import ActiveProfileStore
from app.core.app_logging import LOGGER_NAME
from app.core.customer_list_cache import CustomerListCache
from app.core.output_location import resolve_output_dir
from app.core.operation_history import OperationHistory
from app.core.operation_simulation import simulation_summary_payload
from app.core.output_profile import OutputProfileStore
from app.core.personnel_list_cache import PersonnelListCache
from app.core.processing_engine import ManualResolution, ProcessingEngine
from app.core.manim_input_classifier import ManimInputClassifier
from app.modules.report_editing.engine import ReportEditingEngine
from app.core.region_config import RegionConfig, active_region_config_path
from app.models.records import TahsilatRecord
from app.ui.common import Disclosure, WorkflowSteps, add_page_header
from app.ui.manual_match_dialog import ManualMatchDialog
from app.ui.odeme_onaylandi_review_dialog import OdemeOnaylandiReviewDialog
from app.ui.theme import asset_icon, crisp_pixmap


MODULE_ID = "manim_transfer"
MODULE_NAME = "MANİM Aktarma"

logger = logging.getLogger(LOGGER_NAME)


class _AccountingCanvas(QWidget):
    """Let the workspace's own scroll areas handle long documents."""

    def heightForWidth(self, width: int) -> int:
        # A preferred wrapped-document height would expand the outer legacy
        # scroll area, moving persistent output actions below the viewport.
        return self.minimumSizeHint().height()


@dataclass
class _ManualReviewRequest:
    pending_items: list
    customers: list
    tahsilat: list
    completed: Event = field(default_factory=Event)
    resolutions: dict | None = None


class _ProcessingWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    manual_review_requested = Signal(object)

    def __init__(self, engine: ProcessingEngine, allow_duplicate_files: set[str]):
        super().__init__()
        self.engine = engine
        self.allow_duplicate_files = allow_duplicate_files

    @Slot()
    def run(self) -> None:
        try:
            result = self.engine.run(
                resolver=self._request_manual_review,
                allow_duplicate_files=self.allow_duplicate_files,
            )
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.finished.emit(result)

    def _request_manual_review(self, pending_items, customers, tahsilat):
        request = _ManualReviewRequest(pending_items, customers, tahsilat)
        self.manual_review_requested.emit(request)
        request.completed.wait()
        return request.resolutions or {}


class _SimulationWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, engine: ProcessingEngine):
        super().__init__()
        self.engine = engine

    @Slot()
    def run(self) -> None:
        try:
            configuration = self.engine.prepare_configuration()
            self.finished.emit((self.engine.run(dry_run=True), configuration.fingerprint))
        except Exception as error:
            self.failed.emit(str(error))


class ManimModulePage(QWidget):
    source_preparation_requested = Signal(object)
    integrated_manual_review_requested = Signal(object)

    def __init__(self, history: OperationHistory, parent=None):
        super().__init__(parent)
        self.history = history
        self.files: list[Path] = []
        self.last_output_dir: Path | None = None
        self.last_odeme_onaylandi_items: list = []
        self.last_odeme_onaylandi_path: Path | None = None
        self._processing_thread: QThread | None = None
        self._processing_worker: _ProcessingWorker | None = None
        self._simulation_thread: QThread | None = None
        self._simulation_worker: _SimulationWorker | None = None
        self._operation_id: int | None = None
        self._active_manual_review_request: _ManualReviewRequest | None = None
        self._preflight_summary = None
        self._preflight_fingerprint: str | None = None
        self._active_profiles = ActiveProfileStore(APP_PATHS.data_root)
        self._output_profile_store = OutputProfileStore(
            APP_PATHS.config_dir, APP_PATHS.data_root / "config"
        )
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("manimTabs")

        page = QScrollArea()
        self.work_scroll = page
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = _AccountingCanvas()
        content.setMinimumHeight(620)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.workflow_steps = WorkflowSteps(
            [
                ("Dosyaları seç", "Excel girdilerini yükleyin"),
                ("Planı kontrol et", "Simülasyonla dağılımı görün"),
                ("Kararları gözden geçir", "Gerekirse eşleştirme yapın"),
                ("Çıktıyı hazırla", "Netsis dosyalarını alın"),
            ]
        )
        layout.addWidget(self.workflow_steps)
        self.workflow_steps.hide()

        upload_card = QFrame()
        upload_card.setObjectName("surfaceCard")
        upload_layout = QVBoxLayout(upload_card)
        upload_layout.setContentsMargins(14, 12, 14, 12)
        upload_layout.setSpacing(8)

        upload_header = QHBoxLayout()
        upload_header.setSpacing(12)
        upload_header_col = QVBoxLayout()
        upload_header_col.setSpacing(3)
        upload_title = QLabel("Girdi dosyaları")
        upload_title.setObjectName("cardTitle")
        self.upload_subtitle = QLabel(self._input_files_description())
        self.upload_subtitle.setObjectName("cardSubtitle")
        self.upload_subtitle.setWordWrap(True)
        upload_header_col.addWidget(upload_title)
        upload_header_col.addWidget(self.upload_subtitle)
        upload_header.addLayout(upload_header_col, 1)

        self.file_status = QLabel("Dosya bekleniyor")
        self.file_status.setObjectName("statusPill")
        self.file_status.setProperty("ready", "false")
        upload_header.addWidget(self.file_status, 0, Qt.AlignTop)
        upload_layout.addLayout(upload_header)

        self.retry_context_label = QLabel()
        self.retry_context_label.setObjectName("retryContextBanner")
        self.retry_context_label.setStyleSheet(
            "background:#fff7ed; border:1px solid #fdba74; border-radius:8px; "
            "color:#9a3412; padding:10px 12px; font-weight:600;"
        )
        self.retry_context_label.setWordWrap(True)
        self.retry_context_label.setVisible(False)
        upload_layout.addWidget(self.retry_context_label)

        self.drop_frame = QFrame()
        self.drop_frame.setObjectName("dropArea")
        self.drop_frame.setProperty("hasFiles", "false")
        self.drop_frame.setMinimumHeight(110)
        self.drop_frame.setMaximumHeight(140)
        drop_layout = QVBoxLayout(self.drop_frame)
        drop_layout.setContentsMargins(18, 16, 18, 16)
        drop_layout.setSpacing(8)

        self.drop_hint_container = QWidget()
        hint_layout = QVBoxLayout(self.drop_hint_container)
        hint_layout.setContentsMargins(0, 0, 0, 0)
        hint_layout.setSpacing(7)
        hint_layout.setAlignment(Qt.AlignCenter)

        upload_icon = QLabel()
        upload_icon_path = APP_PATHS.assets_dir / "icons" / "upload-default.png"
        if upload_icon_path.is_file():
            upload_icon.setPixmap(crisp_pixmap(self, upload_icon_path, 38))
        upload_icon.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(upload_icon)

        drop_title = QLabel("Excel dosyalarını buraya sürükleyin")
        drop_title.setObjectName("dropTitle")
        drop_title.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(drop_title)

        drop_detail = QLabel("Desteklenen formatlar: .xlsx ve .xls")
        drop_detail.setObjectName("dropDetail")
        drop_detail.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(drop_detail)
        drop_layout.addWidget(self.drop_hint_container, 1)

        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setVisible(False)
        self.file_list.setMaximumHeight(176)
        drop_layout.addWidget(self.file_list, 1)
        upload_layout.addWidget(self.drop_frame)

        file_actions = QHBoxLayout()
        file_actions.setSpacing(8)
        self.loaded_files_label = QLabel("Henüz dosya seçilmedi")
        self.loaded_files_label.setObjectName("cardSubtitle")
        self.loaded_files_label.setWordWrap(True)
        file_actions.addWidget(self.loaded_files_label, 1)

        self.clear_button = QPushButton("Temizle")
        self.clear_button.setObjectName("ghost")
        self.clear_button.setIcon(asset_icon(APP_PATHS.assets_dir, "trash"))
        self.clear_button.setIconSize(QSize(15, 15))
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_files)
        file_actions.addWidget(self.clear_button)

        self.select_button = QPushButton("Dosya seç")
        self.select_button.setObjectName("secondary")
        self.select_button.setIcon(asset_icon(APP_PATHS.assets_dir, "folder"))
        self.select_button.setIconSize(QSize(16, 16))
        self.select_button.clicked.connect(self.select_files)
        file_actions.addWidget(self.select_button)
        upload_layout.addLayout(file_actions)
        self.input_panel = Disclosure("Girdi dosyaları · seç / kontrol et", upload_card, expanded=True)
        self.input_panel.hide()
        layout.addWidget(self.input_panel)

        process_card = QFrame()
        process_card.setObjectName("surfaceCard")
        process_layout = QVBoxLayout(process_card)
        process_layout.setContentsMargins(20, 16, 20, 16)
        process_layout.setSpacing(18)

        progress_col = QVBoxLayout()
        progress_col.setSpacing(7)
        progress_title = QLabel("İşlem durumu")
        progress_title.setObjectName("cardTitle")
        self.progress_detail = QLabel("Dosyaları yükleyerek işleme başlayın.")
        self.progress_detail.setObjectName("cardSubtitle")
        self.progress_detail.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        progress_col.addWidget(progress_title)
        progress_col.addWidget(self.progress_detail)
        progress_col.addWidget(self.progress)
        self.result_summary = QLabel()
        self.result_summary.setObjectName("cardSubtitle")
        self.result_summary.setWordWrap(True)
        self.result_summary.setVisible(False)
        progress_col.addWidget(self.result_summary)
        process_layout.addLayout(progress_col, 1)

        summary_title = QLabel("Aktarım özeti")
        summary_title.setObjectName("cardTitle")
        process_layout.addWidget(summary_title)
        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(10)
        summary_grid.setVerticalSpacing(8)
        self.summary_metrics: dict[str, QLabel] = {}
        for column, (key, title) in enumerate(
            (("sources", "Kaynak hareketi"), ("netsis", "Netsis satırı"), ("review", "İnceleme"), ("pending", "Bekleyen bakiye"))
        ):
            metric = QFrame()
            metric.setObjectName("metricCard")
            metric_layout = QVBoxLayout(metric)
            metric_layout.setContentsMargins(12, 9, 12, 9)
            metric_layout.setSpacing(2)
            value = QLabel("—")
            value.setObjectName("metricValue")
            label = QLabel(title)
            label.setObjectName("metricLabel")
            metric_layout.addWidget(value)
            metric_layout.addWidget(label)
            summary_grid.addWidget(metric, 0, column)
            self.summary_metrics[key] = value
        process_layout.addLayout(summary_grid)
        process_layout.removeItem(summary_grid)
        summary_title.hide()
        for value in self.summary_metrics.values():
            value.parentWidget().hide()
        self.progress.hide()  # Runtime text communicates actual stages, not a synthetic percentage.
        primary_actions = QHBoxLayout()
        primary_actions.addStretch(1)
        process_layout.addLayout(primary_actions)
        result_actions = QHBoxLayout()
        result_actions.setSpacing(8)
        process_layout.addLayout(result_actions)

        self.open_output_button = QPushButton("Çıktı klasörünü aç")
        self.open_output_button.setObjectName("secondary")
        self.open_output_button.setVisible(False)
        self.open_output_button.clicked.connect(self.open_output_dir)
        result_actions.addWidget(self.open_output_button)

        self.review_odeme_button = QPushButton("Ödeme onaylandı kayıtlarını incele")
        self.review_odeme_button.setObjectName("secondary")
        self.review_odeme_button.setVisible(False)
        self.review_odeme_button.clicked.connect(self.review_odeme_onaylandi)
        result_actions.addWidget(self.review_odeme_button)
        self.simulation_button = QPushButton("Simülasyon Özetini Gör")
        self.simulation_button.setObjectName("secondary")
        self.simulation_button.setVisible(False)
        self.simulation_button.clicked.connect(self.show_simulation_summary)
        result_actions.addWidget(self.simulation_button)
        self.preflight_button = QPushButton("1. Planı önizle")
        self.preflight_button.setObjectName("secondary")
        self.preflight_button.setEnabled(False)
        self.preflight_button.clicked.connect(self.run_preflight_simulation)
        primary_actions.addWidget(self.preflight_button)

        self.start_button = QPushButton("2. Çıktıları hazırla")
        self.start_button.setObjectName("primary")
        self.start_button.setEnabled(False)
        self.start_button.setMinimumHeight(42)
        self.start_button.clicked.connect(self.start_process)
        primary_actions.addWidget(self.start_button)
        process_card.hide()
        layout.addWidget(process_card)
        self.accounting_workspace = AccountingWorkspace(self.history, APP_PATHS)
        self.accounting_workspace.sources_ready.connect(lambda: self.input_panel.set_expanded(False))
        self.accounting_workspace.add_sources_requested.connect(self.select_files)
        self.accounting_workspace.clear_sources_requested.connect(self.clear_files)
        self.accounting_workspace.preview_requested.connect(self.run_preflight_simulation)
        self.accounting_workspace.output_requested.connect(self.start_process)
        upload_layout.removeWidget(self.retry_context_label)
        layout.addWidget(self.retry_context_label)
        layout.addWidget(self.accounting_workspace, 1)

        log_card = QFrame()
        log_card.setObjectName("surfaceCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 18, 20, 20)
        log_layout.setSpacing(10)

        log_header = QHBoxLayout()
        log_header_col = QVBoxLayout()
        log_header_col.setSpacing(3)
        log_title = QLabel("Operasyon çalışma alanı")
        log_title.setObjectName("cardTitle")
        log_subtitle = QLabel("Aktarım planını inceleyin; işlem ayrıntılarına gerektiğinde geçin.")
        log_subtitle.setObjectName("cardSubtitle")
        log_subtitle.setWordWrap(True)
        log_header_col.addWidget(log_title)
        log_header_col.addWidget(log_subtitle)
        log_header.addLayout(log_header_col, 1)
        log_layout.addLayout(log_header)

        self.log = OperationActivity()
        self.log.setObjectName("log")
        self.log.setPlaceholderText("İşlem kayıtları burada görüntülenecek.")
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.operation_tabs = QTabWidget()
        self.dashboard = SimulationDashboard()
        self.operation_tabs.addTab(self.dashboard, "Aktarım planı")
        self.operation_tabs.addTab(self.log, "İşlem günlüğü")
        log_layout.addWidget(self.operation_tabs, 1)
        self.execution_details = Disclosure("İşlem günlüğü ve ayrıntılı motor dağılımı", log_card)
        self.execution_details.hide()
        layout.addWidget(self.execution_details)

        page.setWidget(content)
        self.tabs.addTab(page, "Muhasebe Otomasyonu")
        self.tabs.addTab(self._build_output_settings_tab(), "Çıktı Ayarları")
        self.tabs.tabBar().hide()
        root.addWidget(self.tabs)

    def _build_output_settings_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(18)

        add_page_header(
            layout,
            "Aktarım Ayarları",
            "Havale ve ileride referanslı kayıtlar için kullanılacak çıktı şablonunu seçin.",
            "MODÜL 01",
        )

        card = QFrame()
        card.setObjectName("surfaceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(10)
        title = QLabel("Havale çıktı şablonu")
        title.setObjectName("cardTitle")
        subtitle = QLabel(
            "Mevcut banka-bölge ayrımlı şablon korunur. Toplu şablon seçildiğinde "
            "Garanti, Yapı Kredi ve Ziraat kayıtları her bölge için tek dosyada, "
            "ilgili BM banka kodlarıyla yazılır."
        )
        subtitle.setObjectName("cardSubtitle")
        subtitle.setWordWrap(True)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        self.havale_template_combo = QComboBox()
        self._havale_profiles = [
            profile for profile in self._output_profile_store.list_profiles()
            if profile.category == "havale"
        ]
        for profile in self._havale_profiles:
            self.havale_template_combo.addItem(profile.name, profile.profile_id)
        active_profile_id = self._active_profiles.get_output_profile_id()
        selected_index = self.havale_template_combo.findData(active_profile_id)
        self.havale_template_combo.setCurrentIndex(max(0, selected_index))
        self.havale_template_combo.currentIndexChanged.connect(self._change_havale_template)
        card_layout.addWidget(self.havale_template_combo)

        self.havale_template_detail = QLabel()
        self.havale_template_detail.setObjectName("cardSubtitle")
        self.havale_template_detail.setWordWrap(True)
        card_layout.addWidget(self.havale_template_detail)
        self._update_havale_template_detail()
        layout.addWidget(card)

        reference_card = QFrame()
        reference_card.setObjectName("surfaceCard")
        reference_layout = QVBoxLayout(reference_card)
        reference_layout.setContentsMargins(22, 18, 22, 18)
        reference_layout.setSpacing(10)
        reference_title = QLabel("Referanslı kayıt çıktı şablonu")
        reference_title.setObjectName("cardTitle")
        reference_text = QLabel(
            "Negatif Referanslı hareketlerden hedef şirket hesabı kesin bulunan virmanlar "
            "bölge bazında, tüm bankalar aynı dosyada olacak şekilde hazırlanır. Diğer "
            "Referanslı kayıtlar mevcut inceleme dosyasında kalır."
        )
        reference_text.setObjectName("cardSubtitle")
        reference_text.setWordWrap(True)
        reference_layout.addWidget(reference_title)
        reference_layout.addWidget(reference_text)

        self.reference_template_combo = QComboBox()
        self._reference_profiles = [
            profile for profile in self._output_profile_store.list_profiles()
            if profile.category == "referansli"
        ]
        for profile in self._reference_profiles:
            self.reference_template_combo.addItem(profile.name, profile.profile_id)
        active_reference_id = self._active_profiles.get_reference_output_profile_id()
        reference_index = self.reference_template_combo.findData(active_reference_id)
        self.reference_template_combo.setCurrentIndex(max(0, reference_index))
        self.reference_template_combo.currentIndexChanged.connect(
            self._change_reference_template
        )
        reference_layout.addWidget(self.reference_template_combo)

        self.reference_template_detail = QLabel()
        self.reference_template_detail.setObjectName("cardSubtitle")
        self.reference_template_detail.setWordWrap(True)
        reference_layout.addWidget(self.reference_template_detail)
        self._update_reference_template_detail()
        layout.addWidget(reference_card)
        layout.addStretch()
        return page

    def _change_havale_template(self, index: int) -> None:
        if index < 0:
            return
        profile_id = self.havale_template_combo.itemData(index)
        if profile_id:
            self._active_profiles.set_output_profile_id(str(profile_id))
        self._update_havale_template_detail()

    def _update_havale_template_detail(self) -> None:
        profile_id = self.havale_template_combo.currentData()
        profile = next(
            (item for item in self._havale_profiles if item.profile_id == profile_id),
            None,
        )
        if profile:
            self.havale_template_detail.setText(profile.description)

    def _change_reference_template(self, index: int) -> None:
        if index < 0:
            return
        profile_id = self.reference_template_combo.itemData(index)
        if profile_id:
            self._active_profiles.set_reference_output_profile_id(str(profile_id))
        self._update_reference_template_detail()

    def _update_reference_template_detail(self) -> None:
        profile_id = self.reference_template_combo.currentData()
        profile = next(
            (item for item in self._reference_profiles if item.profile_id == profile_id),
            None,
        )
        self.reference_template_detail.setText(profile.description if profile else "")

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(
            Path(url.toLocalFile()).suffix.lower() in {".xlsx", ".xls"}
            for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        files = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if Path(url.toLocalFile()).suffix.lower() in {".xlsx", ".xls"}
        ]
        if files:
            if self._route_raw_fom_sources(files):
                event.acceptProposedAction()
                return
            self._load_files(files)
            event.acceptProposedAction()

    def select_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Muhasebe kaynak dosyalarını seçin",
            str(Path.home()),
            "Excel dosyaları (*.xlsx *.xls)",
        )
        if selected:
            files = [Path(path) for path in selected]
            if self._route_raw_fom_sources(files):
                return
            self._load_files(files)

    def _route_raw_fom_sources(self, files: list[Path]) -> bool:
        """Send raw FOM-only selections to Kaynak Hazırlama instead of MANİM preview.

        Accounting output still requires at least one MANİM source.  When every
        selected file is a raw FOM customer/sales/collections report and there
        is no MANİM source, routing it into the accounting engine would only
        produce the misleading "En az bir MANİM raporu bulunamadı" error.
        """
        if not files:
            return False
        try:
            bundle = ManimInputClassifier().classify(files)
        except Exception:
            return False
        if bundle.manim_files:
            return False
        recognized = []
        for path in files:
            try:
                recognized.append(ReportEditingEngine.classify_file(path))
            except Exception:
                return False
        if not recognized or any(file_type is None for file_type in recognized):
            return False
        self.source_preparation_requested.emit(tuple(files))
        return True

    def _load_files(self, files: list[Path]) -> None:
        if self._processing_thread is not None or self._simulation_thread is not None:
            return
        self._reset_simulation()
        self.retry_context_label.clear()
        self.retry_context_label.setVisible(False)
        unique: list[Path] = []
        seen: set[str] = set()
        for path in files:
            key = str(path.resolve()).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(path)
        self.files = unique
        self.accounting_workspace.load(self.files)
        self.accounting_workspace.set_runtime_status("Yerel çalışma · Kaynaklar okunuyor…")
        self.last_output_dir = None
        self.open_output_button.setVisible(False)
        self.review_odeme_button.setVisible(False)
        self.log.clear()
        if not self.files:
            return

        self.drop_hint_container.setVisible(False)
        self.file_list.clear()
        self.file_list.addItems(file.name for file in self.files)
        self.file_list.setVisible(True)
        self.drop_frame.setProperty("hasFiles", "true")
        self.drop_frame.style().unpolish(self.drop_frame)
        self.drop_frame.style().polish(self.drop_frame)

        count = len(self.files)
        self.file_status.setText(f"{count} dosya hazır")
        self.file_status.setProperty("ready", "true")
        self.file_status.style().unpolish(self.file_status)
        self.file_status.style().polish(self.file_status)
        self.loaded_files_label.setText(
            f"{count} Excel dosyası seçildi. İşleme başlamadan önce listeyi kontrol edin."
        )
        self.loaded_files_label.setWordWrap(True)
        self.upload_subtitle.setWordWrap(True)
        self.workflow_steps.reset()
        self.input_panel.set_expanded(True)
        self.progress.setValue(20)
        self.progress_detail.setText("1/4 • Dosyalar yüklendi ve ön kontrol için hazır.")
        self.workflow_steps.set_active(1)
        self.start_button.setEnabled(True)
        self.preflight_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.log.append(f"{count} Excel dosyası yüklendi.")

    def prepare_safe_retry(
        self,
        files: list[str | Path],
        *,
        output_profile_id: str,
        origin_operation_id: int,
        reason: str,
    ) -> None:
        """Ret alınan çalışmanın kaynaklarını yükler; işlemi otomatik başlatmaz."""
        if self._processing_thread is not None or self._simulation_thread is not None:
            raise RuntimeError("MANİM'de devam eden işlem bitmeden yeniden çalışma hazırlanamaz.")
        paths = [Path(value) for value in files]
        missing = [path for path in paths if not path.is_file()]
        if not paths or missing:
            names = ", ".join(path.name for path in missing) or "kaynak dosya"
            raise FileNotFoundError(f"Yeniden çalışma kaynakları bulunamadı: {names}")
        profile_index = self.havale_template_combo.findData(output_profile_id)
        if profile_index < 0:
            raise ValueError("Seçilen havale çıktı profili artık kullanılamıyor.")
        self.havale_template_combo.setCurrentIndex(profile_index)
        self.tabs.setCurrentIndex(0)
        self._load_files(paths)
        profile_name = self.havale_template_combo.currentText()
        self.retry_context_label.setText(
            f"Netsis ret kaydı #{origin_operation_id} yeniden çalışma için hazırlandı. "
            f"Neden: {reason} Yeni çıktı: {profile_name}. Önce planı kontrol edin; işlem siz başlatmadan çalışmaz."
        )
        self.retry_context_label.setVisible(True)
        self.log.append(
            f"Güvenli yeniden çalışma hazırlandı: işlem #{origin_operation_id} · {profile_name}."
        )

    def clear_files(self) -> None:
        if self._processing_thread is not None or self._simulation_thread is not None:
            return
        self.input_panel.set_expanded(True)
        self._reset_simulation()
        self.files = []
        self.accounting_workspace.load([])
        self.accounting_workspace.set_runtime_status("Yerel çalışma · Kaynak bekleniyor")
        self.retry_context_label.clear()
        self.retry_context_label.setVisible(False)
        self.last_output_dir = None
        self.file_list.clear()
        self.file_list.setVisible(False)
        self.drop_hint_container.setVisible(True)
        self.drop_frame.setProperty("hasFiles", "false")
        self.drop_frame.style().unpolish(self.drop_frame)
        self.drop_frame.style().polish(self.drop_frame)
        self.file_status.setText("Dosya bekleniyor")
        self.file_status.setProperty("ready", "false")
        self.file_status.style().unpolish(self.file_status)
        self.file_status.style().polish(self.file_status)
        self.loaded_files_label.setText("Henüz dosya seçilmedi")
        self.progress.setValue(0)
        self.progress_detail.setText("Dosyaları yükleyerek işleme başlayın.")
        self.workflow_steps.reset()
        self.result_summary.setVisible(False)
        for value in self.summary_metrics.values():
            value.setText("—")
        self.start_button.setEnabled(False)
        self.preflight_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.open_output_button.setVisible(False)
        self.review_odeme_button.setVisible(False)
        self.preflight_button.setEnabled(False)
        self.log.clear()

    def start_process(self) -> None:
        if self._processing_thread is not None or self._simulation_thread is not None or not self.files:
            return
        self.accounting_workspace.set_busy(True, "Yerel çalışma · Muhasebe kararı hazırlanıyor…")
        self.start_button.setEnabled(False)
        self.select_button.setEnabled(False)
        self.preflight_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.open_output_button.setVisible(False)
        self.review_odeme_button.setVisible(False)
        self.progress_detail.setText("2/4 • Dosyalar doğrulanıyor ve kayıtlar sınıflandırılıyor...")
        self.workflow_steps.set_active(2)
        if self._preflight_summary is None:
            self.workflow_steps.set_state(1, "pending")
        self.result_summary.setVisible(False)
        self.log.append("\nİşlem başlatıldı...")
        self.progress.setRange(0, 0)
        self._operation_id = None
        try:
            engine = ProcessingEngine(
                self.files,
                project_root=APP_PATHS.resource_root,
                data_root=APP_PATHS.data_root,
                output_root=resolve_output_dir(APP_PATHS),
                company_id=self.history.company_id,
            )
            configuration = engine.prepare_configuration()
            self._actual_configuration_fingerprint = configuration.fingerprint
            if self._preflight_fingerprint and self._preflight_fingerprint != configuration.fingerprint:
                self.log.append(
                    "UYARI: Simülasyondan sonra profil veya bölge ayarı değişti; aktarım sonucu önizlemeden farklılaşabilir."
                )
            duplicates = engine.find_duplicate_manim_files()
            allow_duplicate_files: set[str] = set()
            if duplicates:
                file_list = "\n".join(
                    f"• {path.name} ({info['tarih']}, {info['kayit_sayisi']} kayıt)"
                    for path, info in duplicates.items()
                )
                answer = QMessageBox.question(
                    self,
                    "Daha önce işlenmiş kaynaklar",
                    f"Şu MANİM kaynakları daha önce işlenmiş:\n\n{file_list}\n\n"
                    "Tekrar işlerseniz mevcut çıktılar silinmez; aynı işlem tarihi için "
                    "yeni bir çıktı klasörü oluşturulur (örneğin _2, _3).\n\n"
                    "Bu kaynakları tekrar işleyip yeni çıktı oluşturmak istiyor musunuz?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if answer != QMessageBox.Yes:
                    self.log.append(
                        "Tekrar işleme iptal edildi; daha önce işlenmiş kaynaklar değiştirilmedi."
                    )
                    self.progress.setRange(0, 100)
                    self.progress.setValue(0)
                    self.progress_detail.setText(
                        "Tekrar işleme iptal edildi. Kaynaklar yüklü durumda bırakıldı."
                    )
                    self._processing_finished()
                    self.accounting_workspace.set_runtime_status(
                        "Yerel çalışma · Tekrar işleme iptal edildi"
                    )
                    return
                allow_duplicate_files = {info["hash"] for info in duplicates.values()}
                self.log.append(
                    f"{len(duplicates)} mükerrer MANİM kaynağı kullanıcı onayıyla yeniden işlenecek; "
                    "yeni çıktı klasörü oluşturulacak."
                )

            # Kullanıcı mükerrer kaynak kararını verdikten sonra operasyon kaydı
            # açılır. İptal edilen bir tekrar denemesi geçmişte sahte SUCCESS/0
            # çıktı işlemi oluşturmamalıdır.
            self._operation_id = self.history.start(
                MODULE_ID, MODULE_NAME, self.files,
                configuration=configuration,
            )
            engine.operation_id = self._operation_id
            revision = self.history.configuration(self._operation_id)
            if revision is not None:
                self.log.append(f"Bu işlemde kullanılan ayar sürümü: {revision.revision}")
        except Exception as error:
            self._process_failed(str(error))
            self._processing_finished()
            return

        self._processing_thread = QThread(self)
        self._processing_worker = _ProcessingWorker(engine, allow_duplicate_files)
        self._processing_worker.moveToThread(self._processing_thread)
        self._processing_thread.started.connect(self._processing_worker.run)
        self._processing_worker.manual_review_requested.connect(self._handle_manual_review)
        self._processing_worker.finished.connect(self._process_succeeded)
        self._processing_worker.failed.connect(self._process_failed)
        self._processing_worker.finished.connect(self._processing_thread.quit)
        self._processing_worker.failed.connect(self._processing_thread.quit)
        self._processing_thread.finished.connect(self._processing_worker.deleteLater)
        self._processing_thread.finished.connect(self._processing_thread.deleteLater)
        self._processing_thread.finished.connect(self._processing_finished)
        self._processing_thread.start()

    @Slot(object)
    def _handle_manual_review(self, request: _ManualReviewRequest) -> None:
        """Pause processing and move manual decisions into the product workspace."""
        self._active_manual_review_request = request
        self.accounting_workspace.set_runtime_status(
            "Yerel çalışma · Belirsiz kayıtlar Eşleştirme & Kurallar ekranında karar bekliyor"
        )
        self.progress_detail.setText(
            "3/4 • Belirsiz kayıtlar Eşleştirme & Kurallar ekranında kullanıcı onayı bekliyor."
        )
        self.workflow_steps.set_state(2, "attention")
        self.integrated_manual_review_requested.emit(request)

    @Slot(object)
    def submit_integrated_manual_resolutions(self, raw_resolutions) -> None:
        """Resume the waiting ProcessingEngine worker with integrated UI decisions."""
        request = self._active_manual_review_request
        if request is None:
            return
        try:
            request.resolutions = self._manual_resolution_objects(raw_resolutions)
            self.accounting_workspace.set_runtime_status(
                "Yerel çalışma · Eşleştirme kararları uygulanıyor…"
            )
            self.progress_detail.setText(
                "3/4 • Eşleştirme kararları motora aktarılıyor…"
            )
        finally:
            self._active_manual_review_request = None
            request.completed.set()

    @Slot(object)
    def _process_succeeded(self, result) -> None:
        self.log.append_many(result.logs)
        self.log.append(f"\nToplam MANİM satırı: {result.total_manim_records}")
        self.log.append(f"Geçersiz kaynak satırı: {result.invalid_manim_records}")
        self.log.append(f"Oluşturulan Netsis satırı: {result.produced_netsis_records}")
        self.log.append(f"Ödeme Onaylandı: {result.skipped_payment}")
        self.log.append(f"Referanslı: {result.skipped_reference}")
        self.log.append(f"Hesaplar arası virman: {result.virman_records}")
        self.log.append(f"Kural Çalıştı: {result.skipped_rule}")
        self.log.append(f"İnceleme gereken: {result.unresolved}")
        if result.consumed_tahsilat_rows:
            self.log.append(
                f"Kullanımı kesinleşen tahsilat kaynak satırı: {result.consumed_tahsilat_rows}"
            )
        if result.simulation_summary is not None:
            summary = result.simulation_summary
            self.log.append(
                f"Simülasyon özeti: MANİM {summary.manim_total:,.2f} TL → "
                f"Netsis {summary.netsis_total:,.2f} TL; fark {summary.difference:,.2f} TL."
            )
        if result.output_dir:
            self.log.append(f"Çıktı klasörü: {result.output_dir}")

        status = "SUCCESS" if result.unresolved == 0 else "PARTIAL"
        if self._operation_id is not None:
            simulation_record = self._simulation_record(result.simulation_summary)
            self.history.add_events(self._operation_id, [
                {"code": "PROCESS_LOG", "message": message,
                 "level": "WARNING" if message.startswith("UYARI") else "INFO"}
                for message in result.logs
            ])
            self.history.add_decisions(self._operation_id, result.decision_audits)
            self.history.complete(
                self._operation_id,
                result.created_files,
                {
                    "total_manim_records": result.total_manim_records,
                    "invalid_manim_records": result.invalid_manim_records,
                    "produced_netsis_records": result.produced_netsis_records,
                    "skipped_payment": result.skipped_payment,
                    "skipped_reference": result.skipped_reference,
                    "virman_records": result.virman_records,
                    "skipped_rule": result.skipped_rule,
                    "unresolved": result.unresolved,
                    "consumed_tahsilat_rows": result.consumed_tahsilat_rows,
                    "simulation": simulation_record,
                    "operation_result": simulation_summary_payload(
                        result.simulation_summary
                    ),
                    "operation_presentation": presentation_evidence(result.simulation_summary),
                },
                status=status,
                financial_movements=result.decision_audits,
            )
        self.last_output_dir = result.output_dir
        self.last_odeme_onaylandi_items = result.odeme_onaylandi_items
        self.last_odeme_onaylandi_path = result.odeme_onaylandi_path
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress_detail.setText(
            "4/4 • Çıktılar hazır; kontrol bekleyen kayıtlar var." if result.unresolved
            else "4/4 • Dosya hazırlama tamamlandı. Netsis aktarımını ayrıca kontrol edin."
        )
        self.workflow_steps.set_state(0, "complete")
        self.workflow_steps.set_state(1, "complete" if self._preflight_summary is not None else "pending")
        self.workflow_steps.set_state(2, "attention" if result.unresolved else "complete")
        self.workflow_steps.set_state(3, "complete")
        self.result_summary.setText(
            f"Netsis: {result.produced_netsis_records:,} • "
            f"Ödeme Onaylandı: {result.skipped_payment:,} • "
            f"Referanslı: {result.skipped_reference:,} • "
            f"Virman: {result.virman_records:,} • "
            f"Kural Çalıştı: {result.skipped_rule:,} • "
            f"İnceleme: {result.unresolved:,} • "
            f"Tahsilat kaynağı: {result.consumed_tahsilat_rows:,}"
        )
        self.result_summary.setVisible(True)
        self.summary_metrics["sources"].setText(f"{result.total_manim_records:,}")
        self.summary_metrics["netsis"].setText(f"{result.produced_netsis_records:,}")
        self.summary_metrics["review"].setText(f"{result.unresolved:,}")
        self.summary_metrics["pending"].setText(
            f"{abs(result.simulation_summary.difference):,.2f} TL"
            if result.simulation_summary is not None and result.simulation_summary.difference
            else "0,00 TL"
        )
        self.open_output_button.setVisible(bool(result.output_dir))
        self.input_panel.set_expanded(False)
        self.review_odeme_button.setVisible(bool(result.odeme_onaylandi_items))
        self._last_simulation_summary = result.simulation_summary
        self._last_summary_is_preview = False
        self.dashboard.set_summary(result.simulation_summary, preview=False)
        self.operation_tabs.setCurrentIndex(0)
        self.work_scroll.ensureWidgetVisible(self.accounting_workspace)
        self._compare_with_preflight(result.simulation_summary)
        self.simulation_button.setVisible(result.simulation_summary is not None)
        self.upload_subtitle.setText(self._input_files_description())
        try:
            self.accounting_workspace.set_result(
                result, preview=False, operation_id=self._operation_id
            )
        except Exception as error:
            # The engine/persistence work is already complete here.  A visual
            # refresh problem must not make a successful accounting operation
            # appear to run forever.
            logger.exception("Muhasebe otomasyon merkezi görünümü yenilenemedi")
            self.log.append(f"UYARI: Çıktı hazırlandı ancak çalışma alanı yenilenemedi: {error}")
            self.accounting_workspace.set_busy(
                False, "Yerel çalışma · Çıktı hazır; görünüm yenileme uyarısı"
            )

    @Slot(str)
    def _process_failed(self, error: str) -> None:
        self.accounting_workspace.set_busy(False, "Yerel çalışma · İşlem tamamlanamadı")
        self.execution_details.set_expanded(True)
        logger.error("MANİM aktarımı tamamlanamadı: %s", error)
        if self._operation_id is not None:
            self.history.fail(self._operation_id, error)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_detail.setText("İşlem tamamlanamadı. Hata ayrıntısını inceleyin.")
        self.workflow_steps.set_state(2, "attention")
        self.result_summary.setText("İşlem tamamlanamadı. Yeniden denemeden önce işlem günlüğünü ve varsa çıktı klasörünü kontrol edin.")
        self.result_summary.setVisible(True)
        self.log.append(f"HATA: {error}")
        self.operation_tabs.setCurrentIndex(1)
        QMessageBox.critical(self, "İşlem hatası", error)

    def show_simulation_summary(self) -> None:
        summary = getattr(self, "_last_simulation_summary", None)
        if summary is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("MANİM · Aktarım planı")
        dialog.resize(1160, 820)
        layout = QVBoxLayout(dialog)
        dashboard = SimulationDashboard(dialog)
        dashboard.set_summary(summary, preview=getattr(self, "_last_summary_is_preview", True))
        layout.addWidget(dashboard)
        close = QPushButton("Kapat")
        close.setObjectName("secondary")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, 0, Qt.AlignRight)
        dialog.exec()

    def run_preflight_simulation(self) -> None:
        if not self.files or self._simulation_thread is not None or self._processing_thread is not None:
            return
        self.accounting_workspace.set_busy(True, "Yerel çalışma · Plan önizlemesi hazırlanıyor…")
        self._reset_simulation()
        self.preflight_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.select_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.progress_detail.setText("Simülasyon hazırlanıyor; Excel çıktısı oluşturulmayacak...")
        self.workflow_steps.set_active(1)
        engine = ProcessingEngine(
            self.files,
            project_root=APP_PATHS.resource_root,
            data_root=APP_PATHS.data_root,
            output_root=resolve_output_dir(APP_PATHS),
            company_id=self.history.company_id,
        )
        self._simulation_thread = QThread(self)
        self._simulation_worker = _SimulationWorker(engine)
        self._simulation_worker.moveToThread(self._simulation_thread)
        self._simulation_thread.started.connect(self._simulation_worker.run)
        self._simulation_worker.finished.connect(self._simulation_succeeded)
        self._simulation_worker.failed.connect(self._simulation_failed)
        self._simulation_worker.finished.connect(self._simulation_thread.quit)
        self._simulation_worker.failed.connect(self._simulation_thread.quit)
        self._simulation_thread.finished.connect(self._simulation_worker.deleteLater)
        self._simulation_thread.finished.connect(self._simulation_thread.deleteLater)
        self._simulation_thread.finished.connect(self._simulation_finished)
        self._simulation_thread.start()

    @Slot(object)
    def _simulation_succeeded(self, payload) -> None:
        result, fingerprint = payload
        if result.simulation_summary is None:
            QMessageBox.information(self, "Simülasyon", "Simülasyon için hesaplanabilir karar kaydı bulunamadı.")
            return
        self._last_simulation_summary = result.simulation_summary
        self._last_summary_is_preview = True
        self.dashboard.set_summary(result.simulation_summary, preview=True)
        self.operation_tabs.setCurrentIndex(0)
        self._preflight_summary = result.simulation_summary
        self._preflight_fingerprint = str(fingerprint)
        try:
            self.accounting_workspace.set_result(result, preview=True)
        except Exception as error:
            logger.exception("Muhasebe otomasyon merkezi önizleme görünümü yenilenemedi")
            self.log.append(f"UYARI: Önizleme tamamlandı ancak çalışma alanı yenilenemedi: {error}")
            self.accounting_workspace.set_busy(
                False, "Yerel çalışma · Önizleme hazır; görünüm yenileme uyarısı"
            )
        self.input_panel.set_expanded(False)
        self.progress_detail.setText("Simülasyon tamamlandı; çıktı ve işlenmiş dosya kaydı oluşturulmadı.")
        self.workflow_steps.set_active(2)
        self.simulation_button.setVisible(True)
        self.dashboard.setFocus()
        self.work_scroll.ensureWidgetVisible(self.accounting_workspace)

    def _reset_simulation(self) -> None:
        self._preflight_summary = None
        self._preflight_fingerprint = None
        self._last_simulation_summary = None
        self.simulation_button.setVisible(False)
        self.dashboard.set_summary(None)

    @Slot(str)
    def _simulation_failed(self, error: str) -> None:
        self.accounting_workspace.set_busy(False, "Yerel çalışma · Simülasyon tamamlanamadı")
        self.progress_detail.setText("Simülasyon tamamlanamadı.")
        self.workflow_steps.set_state(1, "attention")
        QMessageBox.critical(self, "Simülasyon hatası", error)

    @Slot()
    def _simulation_finished(self) -> None:
        self._simulation_thread = None
        self._simulation_worker = None
        self.accounting_workspace.set_busy(False)
        self.preflight_button.setEnabled(bool(self.files) and self._processing_thread is None)
        self.start_button.setEnabled(bool(self.files) and self._processing_thread is None)
        self.select_button.setEnabled(self._processing_thread is None)
        self.clear_button.setEnabled(bool(self.files) and self._processing_thread is None)

    def _compare_with_preflight(self, actual) -> None:
        preview = self._preflight_summary
        if preview is None or actual is None:
            return
        if self._simulation_record(actual)["status"] == "MATCH":
            self.log.append("Simülasyon dağılımı doğrulandı: bölge/banka, kaynak kararları, tutarlar ve ayar sürümü aynı. Bu, Netsis kabul onayı değildir.")
            return
        self.log.append(
            "UYARI: Gerçek plan simülasyondan farklı. "
            f"Simülasyon Netsis {preview.netsis_total:,.2f} TL, gerçek plan {actual.netsis_total:,.2f} TL."
        )

    def _simulation_record(self, actual) -> dict:
        if actual is None:
            return {"status": "NOT_AVAILABLE"}
        preview = self._preflight_summary
        if preview is None:
            status = "NOT_RUN"
        elif preview.matches(actual) and self._preflight_fingerprint == getattr(self, "_actual_configuration_fingerprint", None):
            status = "MATCH"
        else:
            status = "MISMATCH"
        return {
            "status": status,
            "preflight_manim_total": str(preview.manim_total) if preview else None,
            "preflight_netsis_total": str(preview.netsis_total) if preview else None,
            "actual_manim_total": str(actual.manim_total),
            "actual_netsis_total": str(actual.netsis_total),
            "configuration_fingerprint": self._preflight_fingerprint if preview else None,
        }

    @Slot()
    def _processing_finished(self) -> None:
        self._processing_thread = None
        self._processing_worker = None
        self._operation_id = None
        self.accounting_workspace.set_busy(False)
        self.start_button.setEnabled(bool(self.files))
        self.preflight_button.setEnabled(bool(self.files))
        self.select_button.setEnabled(True)
        self.clear_button.setEnabled(bool(self.files))

    @property
    def is_busy(self):
        return self._processing_thread is not None or self._simulation_thread is not None

    @staticmethod
    def _input_files_description() -> str:
        cache = CustomerListCache(APP_PATHS.data_root)
        if cache.get():
            return "MANİM dosyaları + tahsilat raporu • son müşteri listesi hafızadan kullanılır"
        return "MANİM dosyaları + tahsilat raporu • önce Müşteri Listesi modülünden liste içe aktarın"

    def open_output_dir(self) -> None:
        if self.last_output_dir and self.last_output_dir.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output_dir)))

    def review_odeme_onaylandi(self) -> None:
        if not self.last_odeme_onaylandi_items or not self.last_odeme_onaylandi_path:
            return
        region_config = RegionConfig(
            active_region_config_path(APP_PATHS.config_dir, APP_PATHS.data_root)
        )
        personnel_cache = PersonnelListCache(APP_PATHS.data_root)
        dialog = OdemeOnaylandiReviewDialog(
            self.last_odeme_onaylandi_items,
            self.last_odeme_onaylandi_path,
            region_config,
            personnel_cache,
            self,
        )
        dialog.exec()

    @staticmethod
    def _manual_resolution_objects(raw_resolutions) -> dict[int, ManualResolution]:
        resolutions: dict[int, ManualResolution] = {}
        for index, (route, rows, allow_partial) in dict(raw_resolutions or {}).items():
            if route == "HAVALE" and rows:
                tahsilat_rows = [
                    TahsilatRecord(
                        musteri_kodu=code,
                        musteri_ismi="(manuel eşleştirme)",
                        belge_tarihi=None,
                        tutar=amount,
                    )
                    for code, amount in rows
                ]
                resolutions[index] = ManualResolution(
                    route="HAVALE",
                    rows=tahsilat_rows,
                    allow_partial=allow_partial,
                )
            else:
                resolutions[index] = ManualResolution(route=route, rows=None)
        return resolutions

    def _resolve_pending_manually(self, pending_items, customers, tahsilat):
        """Legacy fallback for direct compatibility callers/tests only."""
        if not pending_items:
            return {}
        dialog = ManualMatchDialog(pending_items, customers, self)
        dialog.exec()
        return self._manual_resolution_objects(dialog.get_resolutions())
