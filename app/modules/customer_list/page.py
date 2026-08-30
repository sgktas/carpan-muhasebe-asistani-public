from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.app_paths import APP_PATHS
from app.core.customer_list_cache import CustomerListCache
from app.core.operation_history import OperationHistory
from app.modules.customer_list.engine import (
    MODULE_ID,
    MODULE_NAME,
    CustomerListImportEngine,
)
from app.modules.report_editing.engine import ReportEditingEngine
from app.ui.common import add_page_header
from app.ui.theme import asset_icon, crisp_pixmap


class CustomerListPage(QWidget):
    def __init__(self, history: OperationHistory, parent=None):
        super().__init__(parent)
        self.history = history
        self.source_path: Path | None = None
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 30, 34, 30)
        root.setSpacing(18)

        add_page_header(
            root,
            "Müşteri Listesi",
            "Ham FOM müşteri listesini düzenleyin ve MANİM Aktarma için hafızaya alın.",
            "MODÜL 05",
        )

        info = QFrame()
        info.setObjectName("surfaceCard")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(20, 17, 20, 17)
        info_layout.setSpacing(5)
        info_title = QLabel("Nasıl çalışır?")
        info_title.setObjectName("cardTitle")
        info_text = QLabel(
            "Ham müşteri listesini tek başına seçin. Uygulama FOM Rapor Düzenleme "
            "kurallarını uygular, Aydın/Nazilli ayrımını düzeltir ve hazırlanan "
            "listeyi sonraki MANİM işlemleri için saklar."
        )
        info_text.setObjectName("cardSubtitle")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_title)
        info_layout.addWidget(info_text)
        root.addWidget(info)

        upload = QFrame()
        upload.setObjectName("surfaceCard")
        upload_layout = QVBoxLayout(upload)
        upload_layout.setContentsMargins(22, 20, 22, 20)
        upload_layout.setSpacing(14)
        title = QLabel("Ham FOM müşteri listesi")
        title.setObjectName("cardTitle")
        subtitle = QLabel("Tek bir .xlsx veya .xls dosyası seçin.")
        subtitle.setObjectName("cardSubtitle")
        upload_layout.addWidget(title)
        upload_layout.addWidget(subtitle)

        self.drop_frame = QFrame()
        self.drop_frame.setObjectName("dropArea")
        self.drop_frame.setProperty("hasFiles", "false")
        self.drop_frame.setMinimumHeight(150)
        drop_layout = QVBoxLayout(self.drop_frame)
        drop_layout.setAlignment(Qt.AlignCenter)
        icon = QLabel()
        icon_path = APP_PATHS.assets_dir / "icons" / "upload-default.png"
        if icon_path.is_file():
            icon.setPixmap(crisp_pixmap(self, icon_path, 38))
        icon.setAlignment(Qt.AlignCenter)
        self.drop_title = QLabel("Müşteri listesini buraya sürükleyin")
        self.drop_title.setObjectName("dropTitle")
        self.drop_title.setAlignment(Qt.AlignCenter)
        self.drop_detail = QLabel("Dosya henüz seçilmedi")
        self.drop_detail.setObjectName("dropDetail")
        self.drop_detail.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(icon)
        drop_layout.addWidget(self.drop_title)
        drop_layout.addWidget(self.drop_detail)
        upload_layout.addWidget(self.drop_frame)

        actions = QHBoxLayout()
        self.clear_button = QPushButton("Temizle")
        self.clear_button.setObjectName("ghost")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_file)
        actions.addWidget(self.clear_button)
        actions.addStretch()
        self.select_button = QPushButton("Dosya seç")
        self.select_button.setObjectName("secondary")
        self.select_button.setIcon(asset_icon(APP_PATHS.assets_dir, "folder"))
        self.select_button.setIconSize(QSize(16, 16))
        self.select_button.clicked.connect(self.select_file)
        actions.addWidget(self.select_button)
        upload_layout.addLayout(actions)
        root.addWidget(upload)

        status = QFrame()
        status.setObjectName("surfaceCard")
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(20, 16, 20, 16)
        status_layout.setSpacing(18)
        left = QVBoxLayout()
        status_title = QLabel("Hafızadaki liste")
        status_title.setObjectName("cardTitle")
        self.cache_status = QLabel(self._cache_status_text())
        self.cache_status.setObjectName("cardSubtitle")
        self.cache_status.setWordWrap(True)
        left.addWidget(status_title)
        left.addWidget(self.cache_status)
        status_layout.addLayout(left, 1)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.progress.setValue(0)
        left.addWidget(self.progress)
        self.start_button = QPushButton("Listeyi hazırla ve kaydet")
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumHeight(42)
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_import)
        status_layout.addWidget(self.start_button, 0, Qt.AlignBottom)
        root.addWidget(status)

        log_card = QFrame()
        log_card.setObjectName("surfaceCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 18, 20, 20)
        log_title = QLabel("İşlem günlüğü")
        log_title.setObjectName("cardTitle")
        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Müşteri listesi içe aktarma kayıtları burada görüntülenecek.")
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.log, 1)
        root.addWidget(log_card, 1)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(
            Path(url.toLocalFile()).suffix.lower() in {".xlsx", ".xls"}
            for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        files = [
            Path(url.toLocalFile()) for url in event.mimeData().urls()
            if Path(url.toLocalFile()).suffix.lower() in {".xlsx", ".xls"}
        ]
        if files:
            self._load_file(files[0])
            event.acceptProposedAction()

    def select_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Ham FOM müşteri listesini seçin", str(Path.home()), "Excel dosyaları (*.xlsx *.xls)"
        )
        if selected:
            self._load_file(Path(selected))

    def _load_file(self, path: Path) -> None:
        try:
            if ReportEditingEngine.classify_file(path) != "customer":
                raise ValueError("Bu dosya ham FOM müşteri listesi olarak tanınamadı.")
        except Exception as error:
            self.source_path = None
            self.start_button.setEnabled(False)
            QMessageBox.warning(self, "Müşteri listesi tanınamadı", str(error))
            return
        self.source_path = path
        self.drop_title.setText(path.name)
        self.drop_detail.setText("Ham FOM müşteri listesi tanındı ve işleme hazır.")
        self.drop_frame.setProperty("hasFiles", "true")
        self.drop_frame.style().unpolish(self.drop_frame)
        self.drop_frame.style().polish(self.drop_frame)
        self.clear_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.progress.setValue(20)

    def clear_file(self) -> None:
        self.source_path = None
        self.drop_title.setText("Müşteri listesini buraya sürükleyin")
        self.drop_detail.setText("Dosya henüz seçilmedi")
        self.drop_frame.setProperty("hasFiles", "false")
        self.drop_frame.style().unpolish(self.drop_frame)
        self.drop_frame.style().polish(self.drop_frame)
        self.clear_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.progress.setValue(0)
        self.log.clear()

    def start_import(self) -> None:
        if not self.source_path:
            return
        self.start_button.setEnabled(False)
        self.select_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.progress.setValue(45)
        operation_id = self.history.start(MODULE_ID, MODULE_NAME, [self.source_path])
        try:
            result = CustomerListImportEngine(self.source_path, APP_PATHS.data_root).run()
            self.history.complete(operation_id, [result.cached_path], result.summary())
            self.log.clear()
            for line in result.logs:
                self.log.append(line)
            self.cache_status.setText(self._cache_status_text())
            self.progress.setValue(100)
        except Exception as error:
            self.history.fail(operation_id, str(error))
            self.progress.setValue(0)
            self.log.append(f"HATA: {error}")
            QMessageBox.critical(self, "Müşteri listesi içe aktarma hatası", str(error))
        finally:
            self.start_button.setEnabled(self.source_path is not None)
            self.select_button.setEnabled(True)
            self.clear_button.setEnabled(self.source_path is not None)

    @staticmethod
    def _cache_status_text() -> str:
        cache = CustomerListCache(APP_PATHS.data_root)
        metadata = cache.metadata() or {}
        if cache.get():
            return (
                f"{metadata.get('orijinal_ad', 'Müşteri listesi')} • "
                f"{metadata.get('kaydedilme_tarihi', 'tarih bilinmiyor')} tarihinde güncellendi"
            )
        return "Henüz müşteri listesi içe aktarılmadı."
