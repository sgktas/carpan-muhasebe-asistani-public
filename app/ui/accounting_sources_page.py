from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.app_paths import APP_PATHS
from app.core.customer_list_cache import CustomerListCache
from app.core.operation_history import OperationHistory
from app.core.output_location import resolve_output_dir
from app.modules.report_editing.engine import (
    MODULE_ID,
    MODULE_NAME,
    ReportEditingEngine,
    refresh_customer_list_cache,
)
from app.ui.local_task import LocalTask


_TYPE_LABELS = {
    "customer": "Müşteri listesi",
    "sales": "Satış raporu",
    "collections": "Tahsilat raporu",
}


class AccountingSourcePreparationPage(QWidget):
    """Premium source-preparation surface for FOM/raw accounting inputs.

    It reuses the existing ReportEditingEngine and persistence semantics, but
    deliberately avoids exposing the legacy ReportEditingPage inside the new
    Muhasebe Otomasyonu product shell.
    """

    back_to_work_requested = Signal()
    manim_sources_requested = Signal()

    def __init__(self, history: OperationHistory, parent=None):
        super().__init__(parent)
        self.history = history
        self.files: list[Path] = []
        self.last_output_dir: Path | None = None
        self._recognized: dict[str, Path] = {}
        self._operation_id: int | None = None

        self.scan_task = LocalTask(self)
        self.scan_task.succeeded.connect(self._scan_succeeded)
        self.scan_task.failed.connect(self._scan_failed)
        self.scan_task.settled.connect(self._scan_settled)

        self.process_task = LocalTask(self)
        self.process_task.succeeded.connect(self._process_succeeded)
        self.process_task.failed.connect(self._process_failed)
        self.process_task.settled.connect(self._process_settled)

        self.setAcceptDrops(True)
        self._build_ui()

    @property
    def is_busy(self) -> bool:
        return self.scan_task.busy or self.process_task.busy

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(3)
        title = QLabel("Kaynaklar")
        title.setObjectName("automationPageTitle")
        subtitle = QLabel(
            "MANİM hareketleri, FOM / tahsilat ve müşteri listesi kaynaklarını aynı çalışma alanından hazırlayın."
        )
        subtitle.setObjectName("automationPageSubtitle")
        subtitle.setWordWrap(True)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)

        self.back_button = QPushButton("← Yeni çalışmaya dön")
        self.back_button.setObjectName("secondary")
        self.back_button.clicked.connect(self.back_to_work_requested.emit)
        header.addWidget(self.back_button, 0, Qt.AlignTop)
        root.addLayout(header)

        source_routes = QHBoxLayout()
        self.manim_source_button = QPushButton("MANİM · Hareket kaynağı ekle", self)
        self.manim_source_button.setObjectName("secondary")
        self.manim_source_button.clicked.connect(self.manim_sources_requested.emit)
        source_routes.addWidget(self.manim_source_button)
        source_routes.addWidget(QLabel("FOM / Tahsilat ve Müşteri Listesi · Aşağıdan dosya ekleyin", self), 1)
        root.addLayout(source_routes)

        summary = QFrame()
        summary.setObjectName("automationMetricStrip")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(8)
        self.metric_labels: dict[str, QLabel] = {}
        for key, caption in (
            ("customer", "Müşteri listesi"),
            ("sales", "Satış raporu"),
            ("collections", "Tahsilat raporu"),
        ):
            card = QFrame()
            card.setObjectName("sourceTypeCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)
            card_layout.setSpacing(2)
            label = QLabel(caption)
            label.setObjectName("metricLabel")
            value = QLabel("Bekleniyor")
            value.setObjectName("sourceTypeValue")
            card_layout.addWidget(label)
            card_layout.addWidget(value)
            summary_layout.addWidget(card, 1)
            self.metric_labels[key] = value
        root.addWidget(summary)

        intake = QFrame()
        intake.setObjectName("surfaceCard")
        intake_layout = QHBoxLayout(intake)
        intake_layout.setContentsMargins(16, 12, 16, 12)
        intake_layout.setSpacing(12)
        intake_text = QVBoxLayout()
        intake_text.setSpacing(2)
        intake_title = QLabel("Ham FOM kaynakları")
        intake_title.setObjectName("panelTitle")
        self.intake_detail = QLabel(
            "Dosyaları sürükleyin veya seçin. Türler başlıklardan otomatik tanınır."
        )
        self.intake_detail.setObjectName("cardSubtitle")
        self.intake_detail.setWordWrap(True)
        intake_text.addWidget(intake_title)
        intake_text.addWidget(self.intake_detail)
        intake_layout.addLayout(intake_text, 1)

        self.clear_button = QPushButton("Temizle")
        self.clear_button.setObjectName("ghost")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_files)
        intake_layout.addWidget(self.clear_button)

        self.select_button = QPushButton("Dosya ekle")
        self.select_button.setObjectName("secondary")
        self.select_button.clicked.connect(self.select_files)
        intake_layout.addWidget(self.select_button)
        root.addWidget(intake)

        body = QFrame()
        body.setObjectName("surfaceCard")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("automationSourcePreparationTable")
        self.table.setHorizontalHeaderLabels(("Dosya", "Tür", "Durum"))
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setMinimumHeight(230)
        body_layout.addWidget(self.table)
        root.addWidget(body, 1)

        footer = QHBoxLayout()
        self.status_label = QLabel("Henüz kaynak seçilmedi")
        self.status_label.setObjectName("automationRuntimeStatus")
        self.status_label.setWordWrap(True)
        footer.addWidget(self.status_label, 1)

        self.open_output_button = QPushButton("Çıktı klasörünü aç")
        self.open_output_button.setObjectName("secondary")
        self.open_output_button.setVisible(False)
        self.open_output_button.clicked.connect(self.open_output_dir)
        footer.addWidget(self.open_output_button)

        self.prepare_button = QPushButton("Raporları hazırla")
        self.prepare_button.setObjectName("primary")
        self.prepare_button.setEnabled(False)
        self.prepare_button.clicked.connect(self.start_process)
        footer.addWidget(self.prepare_button)
        root.addLayout(footer)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(
            Path(url.toLocalFile()).suffix.lower() in {".xlsx", ".xls"}
            for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if Path(url.toLocalFile()).suffix.lower() in {".xlsx", ".xls"}
        ]
        if paths:
            self.load_files(paths)
            event.acceptProposedAction()

    def select_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Ham FOM kaynaklarını seçin",
            str(Path.home()),
            "Excel dosyaları (*.xlsx *.xls)",
        )
        if selected:
            self.load_files([Path(path) for path in selected])

    def load_files(self, files: list[Path]) -> None:
        if self.is_busy:
            return
        unique: list[Path] = []
        seen: set[str] = set()
        for path in files:
            key = str(path.resolve()).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(path)
        self.files = unique
        self.last_output_dir = None
        self._recognized = {}
        self.open_output_button.setVisible(False)
        self.prepare_button.setEnabled(False)
        self.clear_button.setEnabled(bool(unique))
        self.select_button.setEnabled(False)
        self.status_label.setText("Kaynak türleri tanınıyor…")
        self._set_table_pending(unique)
        self.scan_task.start(lambda: self._classify_files(tuple(unique)))

    @staticmethod
    def _classify_files(files: tuple[Path, ...]) -> tuple[dict[str, Path], list[tuple[Path, str | None, str | None]]]:
        recognized: dict[str, Path] = {}
        rows: list[tuple[Path, str | None, str | None]] = []
        for path in files:
            try:
                file_type = ReportEditingEngine.classify_file(path)
                error = None
            except Exception as exc:
                file_type = None
                error = str(exc)
            if file_type and file_type in recognized:
                error = f"Aynı rapor türünden ikinci dosya: {recognized[file_type].name}"
                file_type = None
            elif file_type:
                recognized[file_type] = path
            rows.append((path, file_type, error))
        return recognized, rows

    def _set_table_pending(self, files: list[Path]) -> None:
        self.table.setRowCount(len(files))
        for row, path in enumerate(files):
            self.table.setItem(row, 0, QTableWidgetItem(path.name))
            self.table.setItem(row, 1, QTableWidgetItem("Tanınıyor…"))
            self.table.setItem(row, 2, QTableWidgetItem("Bekliyor"))

    @Slot(object)
    def _scan_succeeded(self, payload) -> None:
        recognized, rows = payload
        self._recognized = dict(recognized)
        self.table.setRowCount(len(rows))
        valid = True
        for row, (path, file_type, error) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(path.name))
            self.table.setItem(row, 1, QTableWidgetItem(_TYPE_LABELS.get(file_type, "Tanınamadı")))
            status = error or ("Hazır" if file_type else "Bu dosya FOM kaynağı olarak tanınmadı")
            self.table.setItem(row, 2, QTableWidgetItem(status))
            if error or not file_type:
                valid = False
        for key, value in self.metric_labels.items():
            value.setText("Hazır" if key in recognized else "—")
        if not recognized:
            valid = False
        if valid:
            self.status_label.setText(
                f"{len(recognized)} kaynak türü tanındı. Raporları hazırlayabilirsiniz."
            )
        else:
            self.status_label.setText(
                "Tanınmayan veya yinelenen kaynak var. Dosya listesini düzeltin."
            )
        self.prepare_button.setEnabled(valid)

    @Slot(object)
    def _scan_failed(self, error) -> None:
        self.status_label.setText(f"Kaynaklar okunamadı: {error}")
        self.prepare_button.setEnabled(False)

    @Slot()
    def _scan_settled(self) -> None:
        self.select_button.setEnabled(True)
        self.clear_button.setEnabled(bool(self.files))

    def clear_files(self) -> None:
        if self.is_busy:
            return
        self.files = []
        self._recognized = {}
        self.last_output_dir = None
        self.table.setRowCount(0)
        for value in self.metric_labels.values():
            value.setText("Bekleniyor")
        self.status_label.setText("Henüz kaynak seçilmedi")
        self.prepare_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.open_output_button.setVisible(False)

    def start_process(self) -> None:
        if self.is_busy or not self.files or not self.prepare_button.isEnabled():
            return
        try:
            self._operation_id = self.history.start(MODULE_ID, MODULE_NAME, self.files)
        except Exception as error:
            self._process_failed(error)
            return
        self.prepare_button.setEnabled(False)
        self.select_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.open_output_button.setVisible(False)
        self.status_label.setText("FOM kaynakları hazırlanıyor…")
        files = tuple(self.files)
        self.process_task.start(lambda: self._prepare_reports(files))

    @staticmethod
    def _prepare_reports(files: tuple[Path, ...]):
        engine = ReportEditingEngine(
            files,
            resource_root=APP_PATHS.resource_root,
            output_root=resolve_output_dir(APP_PATHS),
            customer_cache_path=CustomerListCache(APP_PATHS.data_root).get(),
            create_template_outputs=True,
        )
        result = engine.run()
        cached_customer_list = refresh_customer_list_cache(result, APP_PATHS.data_root)
        if cached_customer_list:
            result.logs.append("Düzenlenmiş müşteri listesi muhasebe çalışma hafızasına kaydedildi.")
        return result

    @Slot(object)
    def _process_succeeded(self, result) -> None:
        status = "SUCCESS" if result.unmatched_customer_codes == 0 else "PARTIAL"
        if self._operation_id is not None:
            self.history.complete(
                self._operation_id,
                result.created_files,
                result.summary(),
                status=status,
            )
        self.last_output_dir = result.output_dir
        self.status_label.setText(
            f"Hazır · {len(result.created_files)} çıktı oluşturuldu"
            + (
                f" · {result.unmatched_customer_codes} müşteri kodu kontrol bekliyor"
                if result.unmatched_customer_codes
                else ""
            )
        )
        self.open_output_button.setVisible(bool(self.last_output_dir))
        self.prepare_button.setText("Yeniden hazırla")

    @Slot(object)
    def _process_failed(self, error) -> None:
        if self._operation_id is not None:
            self.history.fail(self._operation_id, str(error))
        self.status_label.setText("Kaynak hazırlama tamamlanamadı")
        QMessageBox.critical(self, "Kaynak hazırlama hatası", str(error))

    @Slot()
    def _process_settled(self) -> None:
        self._operation_id = None
        self.select_button.setEnabled(True)
        self.clear_button.setEnabled(bool(self.files))
        self.prepare_button.setEnabled(bool(self._recognized))

    def open_output_dir(self) -> None:
        if self.last_output_dir and self.last_output_dir.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output_dir)))
