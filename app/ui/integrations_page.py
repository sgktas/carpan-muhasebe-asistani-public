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
from app.core.app_paths import APP_PATHS
from app.core.template_integrity import verify_approved_templates
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

        self.readiness_card = QFrame()
        self.readiness_card.setObjectName("surfaceCard")
        readiness_layout = QHBoxLayout(self.readiness_card)
        readiness_layout.setContentsMargins(20, 16, 20, 16)
        readiness_col = QVBoxLayout()
        readiness_title = QLabel("Çalışmaya hazır")
        readiness_title.setObjectName("cardTitle")
        self.readiness_text = QLabel()
        self.readiness_text.setObjectName("cardSubtitle")
        self.readiness_text.setWordWrap(True)
        readiness_col.addWidget(readiness_title)
        readiness_col.addWidget(self.readiness_text)
        readiness_layout.addLayout(readiness_col, 1)
        self.readiness_badge = QLabel()
        self.readiness_badge.setObjectName("moduleBadge")
        self.readiness_badge.setAlignment(Qt.AlignCenter)
        readiness_layout.addWidget(self.readiness_badge)
        layout.addWidget(self.readiness_card)

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
        self.table.setHorizontalHeaderLabels(["Bağlantı", "Kategori", "Yöntem", "Durum", "Ne yapabilirsiniz?"])
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
        template_snapshot = verify_approved_templates(APP_PATHS.resource_root)
        templates_ready = template_snapshot.is_valid
        self.readiness_badge.setText("HAZIR" if templates_ready else "KONTROL GEREKLİ")
        self.readiness_text.setText(
            "Onaylı Netsis ve FOM şablonları doğrulandı. Aktarım işlemlerine güvenle başlayabilirsiniz."
            if templates_ready
            else "Bir veya daha fazla onaylı şablon doğrulanamadı. Aktarıma başlamadan önce Ayarlar > Onaylı Şablon Kontrolü alanını açın."
        )
        integrations = self.registry.all()
        self.table.setRowCount(len(integrations))
        for row, item in enumerate(integrations):
            is_template_export = item.integration_id in {"netsis_approved_export", "psoft_fom_approved_export"}
            status = "Hazır" if (not is_template_export or templates_ready) else "Kontrol gerekli"
            next_step = (
                "Aktarıma başlayabilirsiniz."
                if status == "Hazır"
                else "Ayarlar'dan onaylı şablon kontrolünü çalıştırın."
            )
            values = (item.name, item.category, item.transport, status, next_step)
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if column == 3:
                    cell.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, cell)
