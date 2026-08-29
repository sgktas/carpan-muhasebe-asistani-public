from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.operation_history import OperationHistory
from app.ui.common import add_page_header


class HistoryPage(QWidget):
    def __init__(self, history: OperationHistory, parent=None):
        super().__init__(parent)
        self.history = history
        self._records = []
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
        content.setMinimumHeight(620)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(18)

        add_page_header(
            layout,
            "Geçmiş İşlemler",
            "MANİM Aktarma ve FOM Rapor Düzenleme modüllerinde tamamlanan işlemleri, durumları ve çıktı klasörlerini görüntüleyin.",
        )

        card = QFrame()
        card.setObjectName("surfaceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(12)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title = QLabel("İşlem kayıtları")
        title.setObjectName("cardTitle")
        subtitle = QLabel("Son 100 işlem SQLite veritabanından okunur.")
        subtitle.setObjectName("cardSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col, 1)

        refresh_button = QPushButton("Yenile")
        refresh_button.setObjectName("secondary")
        refresh_button.clicked.connect(self.refresh)
        header.addWidget(refresh_button)

        self.open_button = QPushButton("Çıktı klasörünü aç")
        self.open_button.setObjectName("primary")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_selected_output)
        header.addWidget(self.open_button)
        card_layout.addLayout(header)

        self.table = QTableWidget(0, 6)
        self.table.setObjectName("historyTable")
        self.table.setHorizontalHeaderLabels(
            ["Tarih", "Modül", "Durum", "Girdi", "Çıktı", "Özet"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 155)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 70)
        card_layout.addWidget(self.table, 1)

        layout.addWidget(card, 1)
        scroll.setWidget(content)
        root.addWidget(scroll)

    @staticmethod
    def _display_date(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone().strftime("%d.%m.%Y %H:%M")
        except Exception:
            return value

    @staticmethod
    def _status_text(status: str) -> str:
        return {
            "SUCCESS": "Başarılı",
            "PARTIAL": "Kısmi",
            "FAILED": "Hatalı",
            "RUNNING": "Devam ediyor",
        }.get(status, status)

    @staticmethod
    def _summary_text(summary: dict) -> str:
        if not summary:
            return "-"
        preferred = [
            ("produced_netsis_records", "Netsis"),
            ("unresolved", "İnceleme"),
            ("customer_rows", "Müşteri"),
            ("sales_rows", "Satış"),
            ("collection_rows", "Tahsilat"),
            ("created_file_count", "Dosya"),
            ("bolge", "Bölge"),
            ("banka_adi", "Banka"),
            ("islem_sayisi", "İşlem"),
            ("durum", "Durum"),
        ]
        parts = [
            f"{label}: {summary[key]}"
            for key, label in preferred
            if key in summary
        ]
        return " • ".join(parts) or "-"

    def refresh(self) -> None:
        self._records = self.history.recent(100)
        self.table.setRowCount(len(self._records))
        for row_index, record in enumerate(self._records):
            values = [
                self._display_date(record.started_at),
                record.module_name,
                self._status_text(record.status),
                str(len(record.input_files)),
                str(len(record.output_files)),
                self._summary_text(record.summary),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (2, 3, 4):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_index, column, item)
        self._update_actions()

    def _update_actions(self) -> None:
        row = self.table.currentRow()
        enabled = (
            0 <= row < len(self._records)
            and bool(self._records[row].output_files)
        )
        self.open_button.setEnabled(enabled)

    def open_selected_output(self) -> None:
        row = self.table.currentRow()
        if not (0 <= row < len(self._records)):
            return
        outputs = self._records[row].output_files
        if not outputs:
            return
        first = Path(outputs[0])
        folder = first if first.is_dir() else first.parent
        if folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
