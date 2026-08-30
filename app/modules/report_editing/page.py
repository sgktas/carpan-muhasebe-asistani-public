from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.app_paths import APP_PATHS
from app.core.output_location import resolve_output_dir
from app.core.operation_history import OperationHistory
from app.modules.report_editing.engine import (
    MODULE_ID,
    MODULE_NAME,
    ReportEditingEngine,
    refresh_customer_list_cache,
)
from app.ui.common import add_page_header
from app.ui.theme import asset_icon, crisp_pixmap


class ReportEditingPage(QWidget):
    def __init__(self, history: OperationHistory, parent=None):
        super().__init__(parent)
        self.history = history
        self.files: list[Path] = []
        self.last_output_dir: Path | None = None
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setMinimumHeight(730)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(18)

        add_page_header(
            layout,
            "FOM Rapor Düzenleme",
            "Ham müşteri, satış ve tahsilat raporlarını tek işlemde standartlaştırın; "
            "satış ve tahsilat verilerini orijinal Excel 97–2003 şablonlarına da yazdırın.",
            "MODÜL 02",
        )

        info_card = QFrame()
        info_card.setObjectName("surfaceCard")
        info_layout = QHBoxLayout(info_card)
        info_layout.setContentsMargins(20, 16, 20, 16)
        info_layout.setSpacing(12)

        for title, text in (
            ("Müşteri listesi", "Sütunları seçer, şube ayrımını düzeltir."),
            ("Satış raporu", "Kolon sırası, özel ürün fiyatı, vade ve şube."),
            ("Tahsilat raporu", "N/1 ana sayfası, ŞUBELİLER sayfası ve şube."),
        ):
            item = QFrame()
            item.setObjectName("miniInfoCard")
            col = QVBoxLayout(item)
            col.setContentsMargins(13, 11, 13, 11)
            col.setSpacing(3)
            title_label = QLabel(title)
            title_label.setObjectName("miniInfoTitle")
            text_label = QLabel(text)
            text_label.setObjectName("miniInfoText")
            text_label.setWordWrap(True)
            col.addWidget(title_label)
            col.addWidget(text_label)
            info_layout.addWidget(item, 1)
        layout.addWidget(info_card)

        upload_card = QFrame()
        upload_card.setObjectName("surfaceCard")
        upload_layout = QVBoxLayout(upload_card)
        upload_layout.setContentsMargins(22, 20, 22, 20)
        upload_layout.setSpacing(14)

        header = QHBoxLayout()
        header_col = QVBoxLayout()
        header_col.setSpacing(3)
        title = QLabel("Ham rapor dosyaları")
        title.setObjectName("cardTitle")
        subtitle = QLabel(
            "Aynı döneme ait ham müşteri listesi, satış raporu ve tahsilat raporu (.xlsx veya .xls)"
        )
        subtitle.setObjectName("cardSubtitle")
        header_col.addWidget(title)
        header_col.addWidget(subtitle)
        header.addLayout(header_col, 1)

        self.file_status = QLabel("Dosya bekleniyor")
        self.file_status.setObjectName("statusPill")
        self.file_status.setProperty("ready", "false")
        header.addWidget(self.file_status, 0, Qt.AlignTop)
        upload_layout.addLayout(header)

        self.drop_frame = QFrame()
        self.drop_frame.setObjectName("dropArea")
        self.drop_frame.setProperty("hasFiles", "false")
        self.drop_frame.setMinimumHeight(165)
        drop_layout = QVBoxLayout(self.drop_frame)
        drop_layout.setContentsMargins(18, 14, 18, 14)
        drop_layout.setSpacing(7)

        self.drop_hint = QWidget()
        hint_layout = QVBoxLayout(self.drop_hint)
        hint_layout.setContentsMargins(0, 0, 0, 0)
        hint_layout.setSpacing(7)
        hint_layout.setAlignment(Qt.AlignCenter)

        icon = QLabel()
        icon_path = APP_PATHS.assets_dir / "icons" / "report-default.png"
        if icon_path.is_file():
            icon.setPixmap(crisp_pixmap(self, icon_path, 38))
        icon.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(icon)

        drop_title = QLabel("3 ham Excel raporunu buraya sürükleyin")
        drop_title.setObjectName("dropTitle")
        drop_title.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(drop_title)

        detail = QLabel("Dosya türleri başlıklardan otomatik tanınır. Orijinal şablonlar uygulamada hazırdır.")
        detail.setObjectName("dropDetail")
        detail.setAlignment(Qt.AlignCenter)
        detail.setWordWrap(True)
        hint_layout.addWidget(detail)

        drop_layout.addWidget(self.drop_hint, 1)

        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setVisible(False)
        self.file_list.setMaximumHeight(165)
        drop_layout.addWidget(self.file_list, 1)
        upload_layout.addWidget(self.drop_frame)

        actions = QHBoxLayout()
        self.loaded_label = QLabel("Henüz dosya seçilmedi")
        self.loaded_label.setObjectName("cardSubtitle")
        actions.addWidget(self.loaded_label, 1)

        self.clear_button = QPushButton("Temizle")
        self.clear_button.setObjectName("ghost")
        self.clear_button.setIcon(asset_icon(APP_PATHS.assets_dir, "trash"))
        self.clear_button.setIconSize(QSize(15, 15))
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_files)
        actions.addWidget(self.clear_button)

        self.select_button = QPushButton("Dosya seç")
        self.select_button.setObjectName("secondary")
        self.select_button.setIcon(asset_icon(APP_PATHS.assets_dir, "folder"))
        self.select_button.setIconSize(QSize(16, 16))
        self.select_button.clicked.connect(self.select_files)
        actions.addWidget(self.select_button)
        upload_layout.addLayout(actions)
        layout.addWidget(upload_card)

        process_card = QFrame()
        process_card.setObjectName("surfaceCard")
        process_layout = QHBoxLayout(process_card)
        process_layout.setContentsMargins(20, 16, 20, 16)
        process_layout.setSpacing(18)

        progress_col = QVBoxLayout()
        progress_col.setSpacing(7)
        progress_title = QLabel("İşlem durumu")
        progress_title.setObjectName("cardTitle")
        self.progress_detail = QLabel("Ham raporları yükleyerek işleme başlayın.")
        self.progress_detail.setObjectName("cardSubtitle")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setValue(0)
        self.progress.setFixedHeight(8)
        progress_col.addWidget(progress_title)
        progress_col.addWidget(self.progress_detail)
        progress_col.addWidget(self.progress)
        process_layout.addLayout(progress_col, 1)

        self.open_output_button = QPushButton("Çıktı klasörünü aç")
        self.open_output_button.setObjectName("secondary")
        self.open_output_button.setVisible(False)
        self.open_output_button.clicked.connect(self.open_output_dir)
        process_layout.addWidget(self.open_output_button, 0, Qt.AlignBottom)

        self.start_button = QPushButton("Raporları düzenle")
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumHeight(42)
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_process)
        process_layout.addWidget(self.start_button, 0, Qt.AlignBottom)
        layout.addWidget(process_card)

        log_card = QFrame()
        log_card.setObjectName("surfaceCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 18, 20, 20)
        log_layout.setSpacing(10)

        log_header = QHBoxLayout()
        log_col = QVBoxLayout()
        log_col.setSpacing(3)
        log_title = QLabel("İşlem günlüğü")
        log_title.setObjectName("cardTitle")
        log_subtitle = QLabel("Dosya tanıma, uygulanan kurallar ve üretilen çıktılar")
        log_subtitle.setObjectName("cardSubtitle")
        log_col.addWidget(log_title)
        log_col.addWidget(log_subtitle)
        log_header.addLayout(log_col, 1)
        log_layout.addLayout(log_header)

        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log.setPlaceholderText("Rapor düzenleme kayıtları burada görüntülenecek.")
        log_layout.addWidget(self.log, 1)
        layout.addWidget(log_card, 1)

        scroll.setWidget(content)
        root.addWidget(scroll)

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
            self._load_files(files)
            event.acceptProposedAction()

    def select_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Ham rapor dosyalarını seçin",
            str(Path.home()),
            "Excel dosyaları (*.xlsx *.xls)",
        )
        if selected:
            self._load_files([Path(path) for path in selected])

    def _load_files(self, files: list[Path]) -> None:
        unique: list[Path] = []
        seen: set[str] = set()
        for path in files:
            key = str(path.resolve()).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(path)
        self.files = unique
        self.last_output_dir = None
        self.open_output_button.setVisible(False)
        self.log.clear()

        recognized_labels = {
            "customer": "Müşteri listesi",
            "sales": "Satış raporu",
            "collections": "Tahsilat raporu",
        }
        listed: list[str] = []
        problems: list[str] = []
        for path in self.files:
            try:
                file_type = ReportEditingEngine.classify_file(path)
            except Exception as error:
                file_type = None
                problems.append(f"{path.name}: {error}")
            label = recognized_labels.get(file_type, "Tanınamadı")
            listed.append(f"{label}  •  {path.name}")

        self.drop_hint.setVisible(False)
        self.file_list.clear()
        self.file_list.addItems(listed)
        self.file_list.setVisible(True)
        self.drop_frame.setProperty("hasFiles", "true")
        self.drop_frame.style().unpolish(self.drop_frame)
        self.drop_frame.style().polish(self.drop_frame)

        count = len(self.files)
        recognized_count = sum("Tanınamadı" not in item for item in listed)
        all_ready = recognized_count == count and count > 0
        self.file_status.setText(f"{recognized_count}/{count} rapor tanındı")
        self.file_status.setProperty("ready", "true" if all_ready else "false")
        self.file_status.style().unpolish(self.file_status)
        self.file_status.style().polish(self.file_status)

        self.loaded_label.setText(
            "Müşteri listesi satış/tahsilat şube bilgisinin kaynağıdır. "
            "Üç dosyayı birlikte çalıştırmanız önerilir."
        )
        self.progress.setValue(20 if all_ready else 0)
        self.progress_detail.setText(
            "Raporlar tanındı ve işleme hazır." if all_ready
            else "Tanınamayan dosyayı listeden çıkarın veya doğru ham raporu seçin."
        )
        self.start_button.setEnabled(all_ready)
        self.clear_button.setEnabled(bool(self.files))
        for problem in problems:
            self.log.append(f"UYARI: {problem}")

    def clear_files(self) -> None:
        self.files = []
        self.last_output_dir = None
        self.file_list.clear()
        self.file_list.setVisible(False)
        self.drop_hint.setVisible(True)
        self.drop_frame.setProperty("hasFiles", "false")
        self.drop_frame.style().unpolish(self.drop_frame)
        self.drop_frame.style().polish(self.drop_frame)
        self.file_status.setText("Dosya bekleniyor")
        self.file_status.setProperty("ready", "false")
        self.file_status.style().unpolish(self.file_status)
        self.file_status.style().polish(self.file_status)
        self.loaded_label.setText("Henüz dosya seçilmedi")
        self.progress.setValue(0)
        self.progress_detail.setText("Ham raporları yükleyerek işleme başlayın.")
        self.start_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.open_output_button.setVisible(False)
        self.log.clear()

    def start_process(self) -> None:
        self.start_button.setEnabled(False)
        self.select_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.open_output_button.setVisible(False)
        self.progress.setValue(35)
        self.progress_detail.setText("Raporlar okunuyor ve dönüşüm kuralları uygulanıyor...")
        self.log.append("FOM rapor düzenleme işlemi başlatıldı.")

        operation_id = self.history.start(MODULE_ID, MODULE_NAME, self.files)
        try:
            engine = ReportEditingEngine(
                self.files,
                resource_root=APP_PATHS.resource_root,
                output_root=resolve_output_dir(APP_PATHS),
                create_template_outputs=True,
            )
            result = engine.run()
            cached_customer_list = refresh_customer_list_cache(result, APP_PATHS.data_root)
            if cached_customer_list:
                result.logs.append(
                    "Düzenlenmiş müşteri listesi MANİM Aktarma hafızasına da kaydedildi."
                )
            for message in result.logs:
                self.log.append(message)
            for path in result.created_files:
                self.log.append(f"Çıktı: {path.name}")
            self.log.append(f"Çıktı klasörü: {result.output_dir}")

            self.history.complete(
                operation_id,
                result.created_files,
                result.summary(),
                status="SUCCESS" if result.unmatched_customer_codes == 0 else "PARTIAL",
            )
            self.last_output_dir = result.output_dir
            self.progress.setValue(100)
            self.progress_detail.setText(
                f"İşlem tamamlandı. {len(result.created_files)} dosya oluşturuldu."
            )
            self.open_output_button.setVisible(True)
        except Exception as error:
            self.history.fail(operation_id, str(error))
            self.progress.setValue(0)
            self.progress_detail.setText("İşlem tamamlanamadı. Hata ayrıntısını inceleyin.")
            self.log.append(f"HATA: {error}")
            QMessageBox.critical(self, "FOM rapor düzenleme hatası", str(error))
        finally:
            self.start_button.setEnabled(bool(self.files))
            self.select_button.setEnabled(True)
            self.clear_button.setEnabled(bool(self.files))

    def open_output_dir(self) -> None:
        if self.last_output_dir and self.last_output_dir.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output_dir)))
