from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.operation_center import (
    build_operation_center_snapshot,
    operation_attention_text,
)
from app.core.operation_history import OperationHistory
from app.ui.common import add_page_header


class OperationCenterPage(QWidget):
    """Yerel işlemlerden türetilen günlük finans operasyon görünümü."""

    def __init__(self, history: OperationHistory, parent=None):
        super().__init__(parent)
        self.history = history
        self._attention_records = ()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(18)
        add_page_header(
            layout,
            "Operasyon Merkezi",
            "Günlük finans işlemlerinin durumunu, inceleme bekleyen kayıtları ve üretilen çıktıları tek yerde takip edin.",
        )

        metrics = QGridLayout()
        metrics.setSpacing(12)
        self._metric_values: dict[str, QLabel] = {}
        for index, (key, title, subtitle) in enumerate(
            (
                ("total", "Toplam işlem", "Son 100 kayıt"),
                ("success", "Başarılı", "Tamamlanan işlemler"),
                ("attention", "Dikkat gerekiyor", "Kısmi, hatalı veya yarım"),
                ("unresolved", "İnceleme kaydı", "Manuel karar bekleyenler"),
                ("files", "Üretilen dosya", "İşlem geçmişindeki çıktılar"),
            )
        ):
            metrics.addWidget(self._metric_card(key, title, subtitle), index // 3, index % 3)
        layout.addLayout(metrics)

        card = QFrame()
        card.setObjectName("surfaceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(12)
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title = QLabel("Öncelikli takip listesi")
        title.setObjectName("cardTitle")
        subtitle = QLabel("Bu liste otomatik karar vermez; kontrol edilmesi gereken işlemleri görünür kılar.")
        subtitle.setObjectName("cardSubtitle")
        subtitle.setWordWrap(True)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col, 1)
        refresh_button = QPushButton("Yenile")
        refresh_button.setObjectName("secondary")
        refresh_button.clicked.connect(self.refresh)
        header.addWidget(refresh_button)
        card_layout.addLayout(header)

        filters = QHBoxLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItem("Tüm dikkat kayıtları", "")
        self.status_filter.addItem("Kısmi işlemler", "PARTIAL")
        self.status_filter.addItem("Hatalı işlemler", "FAILED")
        self.status_filter.addItem("Yarım kalanlar", "INTERRUPTED")
        self.status_filter.currentIndexChanged.connect(self._render_attention_records)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Modül, kullanıcı veya kontrol nedeni ara")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._render_attention_records)
        filters.addWidget(self.status_filter)
        filters.addWidget(self.search_input, 1)
        card_layout.addLayout(filters)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("historyTable")
        self.table.setHorizontalHeaderLabels(["Tarih", "Modül", "Durum", "Kontrol nedeni", "Kullanıcı"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 145)
        self.table.setColumnWidth(1, 165)
        self.table.setColumnWidth(2, 115)
        self.table.setColumnWidth(3, 440)
        card_layout.addWidget(self.table)
        layout.addWidget(card)
        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    def _metric_card(self, key: str, title_text: str, subtitle_text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("surfaceCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(17, 15, 17, 15)
        layout.setSpacing(4)
        title = QLabel(title_text)
        title.setObjectName("miniInfoTitle")
        value = QLabel("0")
        value.setStyleSheet("font-size:28px; font-weight:700; color:#214866;")
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("miniInfoText")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(subtitle)
        self._metric_values[key] = value
        return card

    def refresh(self) -> None:
        snapshot = build_operation_center_snapshot(self.history.recent(100))
        values = {
            "total": snapshot.total_operations,
            "success": snapshot.successful_operations,
            "attention": snapshot.attention_operations,
            "unresolved": snapshot.unresolved_items,
            "files": snapshot.generated_files,
        }
        for key, value in values.items():
            self._metric_values[key].setText(str(value))
        self._attention_records = snapshot.attention_records
        self._render_attention_records()

    def _render_attention_records(self) -> None:
        status = self.status_filter.currentData() if hasattr(self, "status_filter") else ""
        needle = self.search_input.text().strip().casefold() if hasattr(self, "search_input") else ""
        records = [
            record for record in self._attention_records
            if (not status or record.status == status)
            and (not needle or needle in " ".join((record.module_name, record.actor, operation_attention_text(record))).casefold())
        ]
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = (
                self._display_date(record.started_at),
                record.module_name,
                self._status_text(record.status),
                operation_attention_text(record),
                record.actor or "-",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 2:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, item)

    @staticmethod
    def _display_date(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone().strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return value

    @staticmethod
    def _status_text(status: str) -> str:
        return {
            "PARTIAL": "Kısmi",
            "FAILED": "Hatalı",
            "INTERRUPTED": "Yarım kaldı",
        }.get(status, status)
