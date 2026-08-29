from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.app_paths import APP_PATHS
from app.ui.theme import crisp_pixmap


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
