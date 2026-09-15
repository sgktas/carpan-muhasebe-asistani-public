"""Lightweight landing pages used while legacy workflows migrate screen by screen."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.ui.common import add_page_header
from app.ui.components import ConnectionState, LockedModuleState, SecondaryButton, SectionHeader
from app.ui.design_system import TOKENS
from app.ui.product_registry import ACTIVE, COMING_SOON, LOCKED, UNCONFIGURED, ProductModule, PRODUCT_MODULES


class ProductStatePage(QWidget):
    """Safe product module surface; it never claims an unconnected integration exists."""

    open_requested = Signal(str)

    def __init__(self, module: ProductModule, *, state: str, parent=None):
        super().__init__(parent)
        self.module = module
        self.state = state
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(TOKENS.space_6, TOKENS.space_6, TOKENS.space_6, TOKENS.space_6)
        layout.setSpacing(TOKENS.space_6)
        add_page_header(layout, module.display_name, module.description)
        if module.module_id == "dashboard":
            layout.addWidget(SectionHeader("Finansal operasyonlar", "İşlemlerinizi başlatın, çalışma araçlarınıza tek yerden ulaşın."))
            grid = QGridLayout()
            grid.setSpacing(TOKENS.space_4)
            for index, target_id in enumerate(("accounting_automation", "reconciliation", "operations", "reports")):
                definition = next(item for item in PRODUCT_MODULES if item.module_id == target_id)
                card = QFrame()
                card.setObjectName("surfaceCard")
                column = QVBoxLayout(card)
                column.setContentsMargins(24, 20, 24, 20)
                column.setSpacing(12)
                heading = QLabel(definition.display_name)
                heading.setObjectName("panelTitle")
                detail = QLabel(definition.description)
                detail.setObjectName("cardSubtitle")
                detail.setWordWrap(True)
                column.addWidget(heading)
                column.addWidget(detail, 1)
                button = SecondaryButton("Çalışma alanını aç  →")
                button.clicked.connect(lambda _checked=False, target=target_id: self.open_requested.emit(target))
                column.addWidget(button, 0, Qt.AlignLeft)
                grid.addWidget(card, index // 2, index % 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            layout.addLayout(grid)
            notice = QLabel("Yerel çalışma alanı · Dosyalarınız ve mevcut işlem araçlarınız bu uygulamada yönetilir.")
            notice.setWordWrap(True)
            notice.setObjectName("automationNotice")
            layout.addWidget(notice)
        elif state == LOCKED:
            layout.addWidget(LockedModuleState("Ek modül", module.description))
        elif state == UNCONFIGURED:
            layout.addWidget(ConnectionState("Bağlantı yapılandırılmadı", module.description))
        elif state == COMING_SOON:
            layout.addWidget(ConnectionState("Yakında", module.description))
        else:
            layout.addWidget(ConnectionState("Çalışma alanı hazır", module.description))
        layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll)


class AutomationHubPage(QWidget):
    """Product-level entry point that keeps legacy adapter pages accessible."""

    open_requested = Signal(str)

    def __init__(
        self,
        module: ProductModule,
        targets: tuple[tuple[str, str, str], ...],
        parent=None,
    ):
        super().__init__(parent)
        self.module = module
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(TOKENS.space_6, TOKENS.space_6, TOKENS.space_6, TOKENS.space_6)
        layout.setSpacing(TOKENS.space_6)
        add_page_header(
            layout,
            module.display_name,
            module.description,
            "AKTİF",
        )
        notice = QLabel(self._notice_text(module.module_id))
        notice.setObjectName("automationNotice")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        section = QLabel("Çalışma araçları")
        section.setObjectName("sectionTitle")
        layout.addWidget(section)
        for target_id, title, detail in targets:
            row = QFrame()
            row.setObjectName("toolRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(TOKENS.space_5, TOKENS.space_4, TOKENS.space_5, TOKENS.space_4)
            text = QVBoxLayout()
            heading = QLabel(title)
            heading.setObjectName("panelTitle")
            caption = QLabel(detail)
            caption.setObjectName("cardSubtitle")
            caption.setWordWrap(True)
            text.addWidget(heading)
            text.addWidget(caption)
            row_layout.addLayout(text, 1)
            button = SecondaryButton("Aç")
            button.setAccessibleName(f"{title} çalışma aracını aç")
            button.clicked.connect(lambda _checked=False, item=target_id: self.open_requested.emit(item))
            row_layout.addWidget(button, 0, Qt.AlignVCenter)
            layout.addWidget(row)
        layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll)

    @staticmethod
    def _notice_text(module_id: str) -> str:
        if module_id == "accounting_automation":
            return (
                "Bugünkü üretim akışı yerel ve dosya tabanlıdır. Banka veya e-fatura "
                "API bağlantısı yapılandırılmadan canlı veri gösterilmez."
            )
        return "Bu ürün alanındaki mevcut çalışma araçları aşağıda listelenir."
