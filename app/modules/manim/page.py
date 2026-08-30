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
from app.core.customer_list_cache import CustomerListCache
from app.core.output_location import resolve_output_dir
from app.core.operation_history import OperationHistory
from app.core.personnel_list_cache import PersonnelListCache
from app.core.processing_engine import (
    CustomerListUpdateRequired,
    ManualResolution,
    ProcessingEngine,
)
from app.core.region_config import RegionConfig, active_region_config_path
from app.models.records import TahsilatRecord
from app.ui.common import add_page_header
from app.ui.manual_match_dialog import ManualMatchDialog
from app.ui.odeme_onaylandi_review_dialog import OdemeOnaylandiReviewDialog
from app.ui.theme import asset_icon, crisp_pixmap


MODULE_ID = "manim_transfer"
MODULE_NAME = "MANİM Aktarma"


class ManimModulePage(QWidget):
    def __init__(self, history: OperationHistory, parent=None):
        super().__init__(parent)
        self.history = history
        self.files: list[Path] = []
        self.last_output_dir: Path | None = None
        self.last_odeme_onaylandi_items: list = []
        self.last_odeme_onaylandi_path: Path | None = None
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setMinimumHeight(710)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(18)

        add_page_header(
            layout,
            "MANİM Aktarma",
            "MANİM ve tahsilat raporlarını güvenli şekilde Netsis aktarımına hazırlayın.",
            "MODÜL 01",
        )

        upload_card = QFrame()
        upload_card.setObjectName("surfaceCard")
        upload_layout = QVBoxLayout(upload_card)
        upload_layout.setContentsMargins(22, 20, 22, 20)
        upload_layout.setSpacing(14)

        upload_header = QHBoxLayout()
        upload_header.setSpacing(12)
        upload_header_col = QVBoxLayout()
        upload_header_col.setSpacing(3)
        upload_title = QLabel("Girdi dosyaları")
        upload_title.setObjectName("cardTitle")
        self.upload_subtitle = QLabel(self._input_files_description())
        self.upload_subtitle.setObjectName("cardSubtitle")
        upload_header_col.addWidget(upload_title)
        upload_header_col.addWidget(self.upload_subtitle)
        upload_header.addLayout(upload_header_col, 1)

        self.file_status = QLabel("Dosya bekleniyor")
        self.file_status.setObjectName("statusPill")
        self.file_status.setProperty("ready", "false")
        upload_header.addWidget(self.file_status, 0, Qt.AlignTop)
        upload_layout.addLayout(upload_header)

        self.drop_frame = QFrame()
        self.drop_frame.setObjectName("dropArea")
        self.drop_frame.setProperty("hasFiles", "false")
        self.drop_frame.setMinimumHeight(174)
        self.drop_frame.setMaximumHeight(220)
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
        self.progress_detail = QLabel("Dosyaları yükleyerek işleme başlayın.")
        self.progress_detail.setObjectName("cardSubtitle")
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
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

        self.review_odeme_button = QPushButton("Ödeme Onaylandı Kayıtlarını Gözden Geçir")
        self.review_odeme_button.setObjectName("secondary")
        self.review_odeme_button.setVisible(False)
        self.review_odeme_button.clicked.connect(self.review_odeme_onaylandi)
        process_layout.addWidget(self.review_odeme_button, 0, Qt.AlignBottom)

        self.start_button = QPushButton("İşleme başla")
        self.start_button.setObjectName("primary")
        self.start_button.setEnabled(False)
        self.start_button.setMinimumHeight(42)
        self.start_button.clicked.connect(self.start_process)
        process_layout.addWidget(self.start_button, 0, Qt.AlignBottom)
        layout.addWidget(process_card)

        log_card = QFrame()
        log_card.setObjectName("surfaceCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 18, 20, 20)
        log_layout.setSpacing(10)

        log_header = QHBoxLayout()
        log_header_col = QVBoxLayout()
        log_header_col.setSpacing(3)
        log_title = QLabel("İşlem günlüğü")
        log_title.setObjectName("cardTitle")
        log_subtitle = QLabel("Doğrulamalar, eşleştirmeler ve çıktı bilgileri")
        log_subtitle.setObjectName("cardSubtitle")
        log_header_col.addWidget(log_title)
        log_header_col.addWidget(log_subtitle)
        log_header.addLayout(log_header_col, 1)
        log_layout.addLayout(log_header)

        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("İşlem kayıtları burada görüntülenecek.")
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.log, 1)
        layout.addWidget(log_card, 1)

        page.setWidget(content)
        root.addWidget(page)

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
            "MANİM aktarım dosyalarını seçin",
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
        self.progress.setValue(20)
        self.progress_detail.setText("Dosyalar yüklendi ve işlem için hazır.")
        self.start_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.log.append(f"{count} Excel dosyası yüklendi.")

    def clear_files(self) -> None:
        self.files = []
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
        self.start_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.open_output_button.setVisible(False)
        self.review_odeme_button.setVisible(False)
        self.log.clear()

    def start_process(self) -> None:
        self.start_button.setEnabled(False)
        self.select_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.open_output_button.setVisible(False)
        self.review_odeme_button.setVisible(False)
        self.progress_detail.setText("Dosyalar doğrulanıyor ve kayıtlar işleniyor...")
        self.log.append("\nİşlem başlatıldı...")
        self.progress.setValue(40)
        operation_id = self.history.start(MODULE_ID, MODULE_NAME, self.files)

        try:
            engine = ProcessingEngine(
                self.files,
                project_root=APP_PATHS.resource_root,
                data_root=APP_PATHS.data_root,
                output_root=resolve_output_dir(APP_PATHS),
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
                    "Bu dosya(lar) daha önce işlenmiş",
                    f"Şu dosya(lar) daha önce işlenmiş görünüyor:\n\n{file_list}\n\n"
                    "Yine de tekrar işlemek istiyor musunuz?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if answer == QMessageBox.Yes:
                    allow_duplicate_files = {info["hash"] for info in duplicates.values()}

            result = engine.run(
                resolver=self._resolve_pending_manually,
                allow_duplicate_files=allow_duplicate_files,
            )
            for message in result.logs:
                self.log.append(message)
            self.log.append(f"\nToplam MANİM satırı: {result.total_manim_records}")
            self.log.append(f"Geçersiz kaynak satırı: {result.invalid_manim_records}")
            self.log.append(f"Oluşturulan Netsis satırı: {result.produced_netsis_records}")
            self.log.append(f"Ödeme Onaylandı: {result.skipped_payment}")
            self.log.append(f"Referanslı: {result.skipped_reference}")
            self.log.append(f"İnceleme gereken: {result.unresolved}")
            if result.output_dir:
                self.log.append(f"Çıktı klasörü: {result.output_dir}")

            status = "SUCCESS" if result.unresolved == 0 else "PARTIAL"
            self.history.complete(
                operation_id,
                result.created_files,
                {
                    "total_manim_records": result.total_manim_records,
                    "invalid_manim_records": result.invalid_manim_records,
                    "produced_netsis_records": result.produced_netsis_records,
                    "skipped_payment": result.skipped_payment,
                    "skipped_reference": result.skipped_reference,
                    "unresolved": result.unresolved,
                },
                status=status,
            )
            self.last_output_dir = result.output_dir
            self.last_odeme_onaylandi_items = result.odeme_onaylandi_items
            self.last_odeme_onaylandi_path = result.odeme_onaylandi_path
            self.progress.setValue(100)
            self.progress_detail.setText("İşlem başarıyla tamamlandı.")
            self.open_output_button.setVisible(bool(result.output_dir))
            self.review_odeme_button.setVisible(bool(result.odeme_onaylandi_items))
            self.upload_subtitle.setText(self._input_files_description())
        except CustomerListUpdateRequired as error:
            self.history.fail(operation_id, str(error))
            self.progress.setValue(0)
            self.progress_detail.setText("Güncel müşteri listesini Müşteri Listesi modülünden içe aktarın.")
            self.log.append(f"UYARI: {error}")
            QMessageBox.information(
                self,
                "Güncel müşteri listesi gerekli",
                f"{error}\n\nSol menüdeki Müşteri Listesi modülünden ham FOM müşteri listesini "
                "içe aktarın. Ardından bu ekrana dönüp işlemi tekrar başlatın.",
            )
        except Exception as error:
            self.history.fail(operation_id, str(error))
            self.progress.setValue(0)
            self.progress_detail.setText("İşlem tamamlanamadı. Hata ayrıntısını inceleyin.")
            self.log.append(f"HATA: {error}")
            QMessageBox.critical(self, "İşlem hatası", str(error))
        finally:
            self.start_button.setEnabled(bool(self.files))
            self.select_button.setEnabled(True)
            self.clear_button.setEnabled(bool(self.files))

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

    def _resolve_pending_manually(self, pending_items, customers, tahsilat):
        if not pending_items:
            return {}
        dialog = ManualMatchDialog(pending_items, customers, self)
        dialog.exec()
        resolutions: dict[int, ManualResolution] = {}
        for index, (route, rows) in dialog.get_resolutions().items():
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
                resolutions[index] = ManualResolution(route="HAVALE", rows=tahsilat_rows)
            else:
                resolutions[index] = ManualResolution(route=route, rows=None)
        return resolutions
