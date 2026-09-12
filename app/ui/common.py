from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.app_paths import APP_PATHS
from app.ui.theme import crisp_pixmap


class WorkflowSteps(QFrame):
    """Ana operasyon ekranları için sakin, adım odaklı iş akışı göstergesi."""

    def __init__(self, steps: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setObjectName("workflowSteps")
        self._cards: list[QFrame] = []
        self._numbers: list[QLabel] = []
        layout = QGridLayout(self)
        self._grid = layout
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        for index, (title_text, subtitle_text) in enumerate(steps):
            card = QFrame()
            card.setObjectName("workflowStep")
            card.setProperty("stepState", "pending")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(8)
            number = QLabel(str(index + 1))
            number.setObjectName("workflowNumber")
            number.setAlignment(Qt.AlignCenter)
            number.setFixedSize(24, 24)
            title = QLabel(title_text)
            title.setWordWrap(True)
            title.setObjectName("workflowTitle")
            subtitle = QLabel(subtitle_text)
            subtitle.setObjectName("workflowSubtitle")
            subtitle.setWordWrap(True)
            text = QVBoxLayout()
            text.setSpacing(1)
            text.addWidget(title)
            text.addWidget(subtitle)
            card_layout.addWidget(number, 0, Qt.AlignTop)
            card_layout.addLayout(text, 1)
            layout.addWidget(card, 0, index)
            self._cards.append(card)
            self._numbers.append(number)
        self.set_active(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = 2 if self.width() < 850 else 4
        for index, card in enumerate(self._cards):
            self._grid.addWidget(card, index // columns, index % columns)



    def reset(self) -> None:
        for index in range(len(self._cards)):
            self.set_state(index, "pending")
        if self._cards:
            self.set_state(0, "active")

    def set_active(self, index: int) -> None:
        for position in range(len(self._cards)):
            self.set_state(position, "complete" if position < index else "active" if position == index else "pending")

    def set_state(self, index: int, state: str) -> None:
        if not (0 <= index < len(self._cards)):
            return
        normalized = state if state in {"pending", "active", "complete", "attention"} else "pending"
        card = self._cards[index]
        card.setProperty("stepState", normalized)
        number = self._numbers[index]
        number.setProperty("stepState", normalized)
        for widget in (card, number):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        labels = {"pending": "Bekliyor", "active": "Sıradaki / sürüyor", "complete": "Tamamlandı", "attention": "Kontrol gerekli"}
        number.setText("✓" if normalized == "complete" else "!" if normalized == "attention" else str(index + 1))
        card.setAccessibleName(f"Adım {index + 1}: {labels[normalized]}")
        card.setToolTip(labels[normalized])


class Disclosure(QFrame):
    """Keep optional inputs and technical details within reach without dominating results."""
    def __init__(self, title, content, *, expanded=False, parent=None):
        super().__init__(parent)
        self.setObjectName("disclosure")
        self.content = content
        self.toggle = QPushButton()
        self.toggle.setObjectName("disclosureToggle")
        self.toggle.setCheckable(True)
        self._title = title
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.toggle)
        layout.addWidget(content)
        self.toggle.toggled.connect(self.set_expanded)
        self.set_expanded(expanded)

    def set_expanded(self, expanded):
        self.toggle.setChecked(expanded)
        self.content.setVisible(expanded)
        self.toggle.setText(("−  " if expanded else "+  ") + self._title)


def add_page_header(
    layout: QVBoxLayout,
    title_text: str,
    subtitle_text: str,
    badge_text: str | None = None,
) -> None:
    row = QHBoxLayout()
    row.setSpacing(16)

    title_col = QVBoxLayout()
    title_col.setSpacing(5)
    title = QLabel(title_text)
    title.setObjectName("pageTitle")
    subtitle = QLabel(subtitle_text)
    subtitle.setObjectName("pageSubtitle")
    subtitle.setWordWrap(True)
    title_col.addWidget(title)
    title_col.addWidget(subtitle)
    row.addLayout(title_col, 1)

    if badge_text:
        badge = QLabel(badge_text)
        badge.setObjectName("moduleBadge")
        badge.setAlignment(Qt.AlignCenter)
        row.addWidget(badge, 0, Qt.AlignTop)

    layout.addLayout(row)


def placeholder_page(title: str, message: str, icon_name: str) -> QWidget:
    page = QScrollArea()
    page.setWidgetResizable(True)
    page.setFrameShape(QFrame.NoFrame)
    page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    content = QWidget()
    content.setMinimumHeight(600)
    layout = QVBoxLayout(content)
    layout.setContentsMargins(34, 30, 34, 30)
    layout.setSpacing(20)
    add_page_header(layout, title, message)

    card = QFrame()
    card.setObjectName("placeholderCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(34, 34, 34, 34)
    card_layout.setSpacing(12)
    card_layout.setAlignment(Qt.AlignCenter)

    icon = QLabel()
    icon_path = APP_PATHS.assets_dir / "icons" / f"{icon_name}-default.png"
    if icon_path.is_file():
        icon.setPixmap(crisp_pixmap(content, icon_path, target_width=46))
    icon.setAlignment(Qt.AlignCenter)
    card_layout.addWidget(icon)

    badge = QLabel("YAKINDA")
    badge.setObjectName("comingSoonBadge")
    badge.setAlignment(Qt.AlignCenter)
    card_layout.addWidget(badge, 0, Qt.AlignHCenter)

    title_label = QLabel(f"{title} altyapısı hazırlanıyor")
    title_label.setObjectName("placeholderTitle")
    title_label.setAlignment(Qt.AlignCenter)
    card_layout.addWidget(title_label)

    text = QLabel(
        "Bu alan modüler çekirdek üzerinde geliştirilecek. "
        "Mevcut modüller bağımsız şekilde çalışmaya devam eder."
    )
    text.setObjectName("placeholderText")
    text.setAlignment(Qt.AlignCenter)
    text.setWordWrap(True)
    text.setMaximumWidth(520)
    card_layout.addWidget(text)

    layout.addWidget(card, 1)
    page.setWidget(content)
    return page
