from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.operation_history import OperationHistory
from app.ui.common import add_page_header

MODULE_ID = "cari_reconciliation"
MODULE_NAME = "Cari Mutabakat"


class CariReconciliationPage(QWidget):
    """Modül 04 iskeleti.

    Amaç (planlanan): müşteri (cari) bazında, Netsis'teki güncel bakiye ile
    müşterinin kendi kayıtları/ekstresi arasındaki farkı karşılaştırıp
    mutabakat mektubu/raporu hazırlamak.

    Şu an yalnız iskelet: modül kaydı, menü yeri ve sayfa kabuğu hazır;
    iş mantığı (girdi formatı, karşılaştırma kuralları, çıktı raporu)
    henüz tanımlanmadı.
    """

    def __init__(self, history: OperationHistory, parent=None):
        super().__init__(parent)
        self.history = history
        self._build_ui()

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
            MODULE_NAME,
            "Müşteri bazında Netsis bakiyesi ile müşteri kayıtlarını karşılaştırıp mutabakat raporu hazırlar.",
            badge_text="MODÜL 04",
        )

        placeholder = QFrame()
        placeholder.setObjectName("card")
        placeholder_layout = QVBoxLayout(placeholder)
        placeholder_layout.setContentsMargins(24, 24, 24, 24)
        placeholder_layout.setSpacing(8)

        title = QLabel("Bu modül geliştirme aşamasında")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        placeholder_layout.addWidget(title)

        detail = QLabel(
            "Planlanan akış: Netsis cari ekstresi + müşterinin kendi kayıtları "
            "karşılaştırılıp fark tespit edilecek, mutabakat mektubu/raporu "
            "üretilecek. Girdi/çıktı formatı, diğer modüllerdeki gibi kullanıcı "
            "tarafından düzenlenebilir profil dosyalarıyla tanımlanacak."
        )
        detail.setWordWrap(True)
        detail.setStyleSheet("color: #5b6472;")
        placeholder_layout.addWidget(detail)

        layout.addWidget(placeholder)
        layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll)
