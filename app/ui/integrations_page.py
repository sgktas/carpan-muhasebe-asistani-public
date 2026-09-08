from __future__ import annotations

from PySide6.QtCore import Qt
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

from app.integrations.registry import IntegrationRegistry, build_default_integration_registry
from app.ui.common import add_page_header


class IntegrationsPage(QWidget):
    """Dış sistem adaptörlerinin görünür, güvenli ürün envanteri."""

    def __init__(self, registry: IntegrationRegistry | None = None, parent=None):
        super().__init__(parent)
        self.registry = registry or build_default_integration_registry()
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
            "Entegrasyonlar",
            "Muhasebe, raporlama ve banka bağlantılarının durumunu buradan takip edin. Finansal dosyalar bu ekrandan merkezi platforma gönderilmez.",
        )

        notice = QFrame()
        notice.setObjectName("surfaceCard")
        notice_layout = QVBoxLayout(notice)
        notice_layout.setContentsMargins(20, 16, 20, 16)
        notice_title = QLabel("Güvenli bağlantı yaklaşımı")
        notice_title.setObjectName("cardTitle")
        notice_text = QLabel(
            "Bugünkü bağlantılar onaylı yerel dosya akışlarıdır. Canlı banka ve ERP API bağlantıları eklendiğinde erişim anahtarları işletim sistemi korumalı depoda tutulacak; şablonlar ve müşteri verileri merkezi platforma taşınmayacaktır."
        )
        notice_text.setObjectName("cardSubtitle")
        notice_text.setWordWrap(True)
        notice_layout.addWidget(notice_title)
        notice_layout.addWidget(notice_text)
        layout.addWidget(notice)

        card = QFrame()
        card.setObjectName("surfaceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Bağlantı envanteri")
        title.setObjectName("cardTitle")
        header.addWidget(title, 1)
        refresh_button = QPushButton("Yenile")
        refresh_button.setObjectName("secondary")
        refresh_button.clicked.connect(self.refresh)
        header.addWidget(refresh_button)
        card_layout.addLayout(header)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("historyTable")
        self.table.setHorizontalHeaderLabels(["Bağlantı", "Kategori", "Yöntem", "Durum", "Açıklama"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 225)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 175)
        self.table.setColumnWidth(3, 130)
        card_layout.addWidget(self.table)
        layout.addWidget(card)
        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    def refresh(self) -> None:
        integrations = self.registry.all()
        self.table.setRowCount(len(integrations))
        for row, item in enumerate(integrations):
            values = (item.name, item.category, item.transport, item.maturity, item.description)
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if column == 3:
                    cell.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, cell)
