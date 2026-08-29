from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QWidget

BRAND_NAVY = "#214866"
BRAND_NAVY_DARK = "#17364D"
BRAND_ORANGE = "#CF642D"
BRAND_ORANGE_DARK = "#A84A20"
BRAND_ORANGE_SOFT = "#FFF1E8"

TEXT_PRIMARY = "#17212B"
TEXT_SECONDARY = "#667584"
TEXT_MUTED = "#8B98A5"
BORDER = "#DDE4EA"
BORDER_STRONG = "#C7D2DC"
APP_BACKGROUND = "#F4F6F8"
SURFACE = "#FFFFFF"
SIDEBAR_BACKGROUND = "#FFFFFF"

MAIN_STYLE = f"""
QWidget#mainRoot {{
    background-color: {APP_BACKGROUND};
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT_PRIMARY};
}}
QFrame#sidebar {{
    background-color: {SIDEBAR_BACKGROUND};
    border-right: 1px solid {BORDER};
}}
QFrame#brandArea {{
    background-color: {SURFACE};
    border: none;
}}
QLabel#brandDescriptor {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel#navSection {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    padding: 0 10px;
}}
QPushButton.navItem {{
    background-color: transparent;
    color: #405261;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 11px 12px;
    text-align: left;
    font-size: 13px;
}}
QPushButton.navItem:hover {{
    background-color: #F4F7F9;
    color: {BRAND_NAVY};
}}
QPushButton.navItem[active="true"] {{
    background-color: {BRAND_ORANGE_SOFT};
    color: {BRAND_ORANGE_DARK};
    border: 1px solid #F3C9B3;
    font-weight: 650;
}}
QFrame#userCard {{
    background-color: #F7F9FA;
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLabel#userName {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#userStatus {{
    color: {TEXT_MUTED};
    font-size: 10px;
}}
QPushButton#logoutButton {{
    background: transparent;
    border: none;
    color: {TEXT_SECONDARY};
    font-size: 11px;
    text-align: left;
    padding: 0;
}}
QPushButton#logoutButton:hover {{
    color: {BRAND_ORANGE_DARK};
}}
QLabel#pageTitle {{
    font-size: 24px;
    font-weight: 650;
    color: {TEXT_PRIMARY};
}}
QLabel#pageSubtitle {{
    font-size: 13px;
    color: {TEXT_SECONDARY};
}}
QLabel#moduleBadge {{
    background-color: #EAF0F4;
    border: 1px solid #D5E0E8;
    border-radius: 10px;
    color: {BRAND_NAVY};
    font-size: 10px;
    font-weight: 700;
    padding: 6px 10px;
}}
QFrame#surfaceCard {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QLabel#cardTitle {{
    color: {TEXT_PRIMARY};
    font-size: 14px;
    font-weight: 650;
}}
QLabel#cardSubtitle {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel#statusPill {{
    background-color: #F1F4F6;
    border: 1px solid {BORDER};
    border-radius: 9px;
    color: {TEXT_SECONDARY};
    font-size: 11px;
    padding: 5px 9px;
}}
QLabel#statusPill[ready="true"] {{
    background-color: #EAF7EF;
    border: 1px solid #BFE3CB;
    color: #287244;
}}
QFrame#dropArea {{
    background-color: #FBFCFD;
    border: 2px dashed {BORDER_STRONG};
    border-radius: 12px;
}}
QFrame#dropArea:hover {{
    background-color: #F8FAFB;
    border-color: #AEBCC8;
}}
QFrame#dropArea[hasFiles="true"] {{
    background-color: #FFFBF8;
    border: 2px solid {BRAND_ORANGE};
}}
QLabel#dropTitle {{
    color: {TEXT_PRIMARY};
    font-size: 15px;
    font-weight: 650;
}}
QLabel#dropDetail {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QListWidget#fileList {{
    background-color: transparent;
    border: none;
    outline: none;
    color: #405261;
    font-size: 12px;
}}
QListWidget#fileList::item {{
    background-color: #FFFFFF;
    border: 1px solid #E7ECEF;
    border-radius: 7px;
    padding: 7px 9px;
    margin: 2px 0;
}}
QListWidget#fileList::item:selected {{
    background-color: {BRAND_ORANGE_SOFT};
    border-color: #F1C5AE;
    color: {TEXT_PRIMARY};
}}
QPushButton#primary {{
    background-color: {BRAND_NAVY};
    color: #FFFFFF;
    border: 1px solid {BRAND_NAVY};
    border-radius: 9px;
    padding: 11px 20px;
    font-weight: 650;
    min-width: 118px;
}}
QPushButton#primary:hover:!disabled {{
    background-color: {BRAND_NAVY_DARK};
    border-color: {BRAND_NAVY_DARK};
}}
QPushButton#primary:pressed:!disabled {{
    background-color: #102B3D;
}}
QPushButton#primary:disabled {{
    background-color: #DCE3E8;
    border-color: #DCE3E8;
    color: #929EA8;
}}
QPushButton#secondary {{
    background-color: #FFFFFF;
    color: {BRAND_NAVY};
    border: 1px solid #C7D3DC;
    border-radius: 9px;
    padding: 9px 14px;
    font-weight: 600;
}}
QPushButton#secondary:hover {{
    background-color: #F3F7F9;
    border-color: #A8BAC7;
}}
QPushButton#ghost {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 8px 10px;
}}
QPushButton#ghost:hover {{
    background-color: #F3F5F7;
    color: {BRAND_ORANGE_DARK};
}}
QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: #E8EDF1;
    height: 8px;
}}
QProgressBar::chunk {{
    background-color: {BRAND_ORANGE};
    border-radius: 4px;
}}
QTextEdit#log {{
    background-color: #FBFCFD;
    border: 1px solid #E3E8EC;
    border-radius: 10px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
    color: #465563;
    padding: 10px;
    selection-background-color: #DCE8F0;
}}
QFrame#placeholderCard {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QLabel#placeholderTitle {{
    color: {TEXT_PRIMARY};
    font-size: 17px;
    font-weight: 650;
}}
QLabel#placeholderText {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
}}
QLabel#comingSoonBadge {{
    background-color: {BRAND_ORANGE_SOFT};
    border: 1px solid #F2C9B4;
    border-radius: 9px;
    color: {BRAND_ORANGE_DARK};
    font-size: 10px;
    font-weight: 700;
    padding: 5px 9px;
}}

QFrame#miniInfoCard {{
    background-color: #F8FAFB;
    border: 1px solid #E4E9ED;
    border-radius: 10px;
}}
QLabel#miniInfoTitle {{
    color: #17212B;
    font-size: 12px;
    font-weight: 650;
}}
QLabel#miniInfoText {{
    color: #667584;
    font-size: 11px;
}}
QFrame#settingsRow {{
    background-color: #FBFCFD;
    border: 1px solid #E3E8EC;
    border-radius: 10px;
}}
QTableWidget#historyTable {{
    background-color: #FFFFFF;
    alternate-background-color: #F8FAFB;
    border: 1px solid #E3E8EC;
    border-radius: 10px;
    gridline-color: #E7ECEF;
    selection-background-color: #FFF1E8;
    selection-color: #17212B;
}}
QTableWidget#historyTable::item {{
    padding: 7px;
}}
QHeaderView::section {{
    background-color: #F3F6F8;
    color: #405261;
    border: none;
    border-right: 1px solid #DDE4EA;
    border-bottom: 1px solid #DDE4EA;
    padding: 8px;
    font-weight: 650;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #C8D1D8;
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: #AEBAC3;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""

LOGIN_STYLE = f"""
QWidget#loginRoot {{
    background-color: {APP_BACKGROUND};
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
    color: {TEXT_PRIMARY};
}}
QFrame#loginCard {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QFrame#accentLine {{
    background-color: {BRAND_ORANGE};
    border: none;
    border-radius: 2px;
}}
QLabel#loginEyebrow {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#loginTitle {{
    color: {TEXT_PRIMARY};
    font-size: 21px;
    font-weight: 650;
}}
QLabel#loginSubtitle {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel.fieldLabel {{
    color: #405261;
    font-size: 12px;
    font-weight: 600;
}}
QLineEdit {{
    background-color: #FBFCFD;
    border: 1px solid #D6DEE4;
    border-radius: 9px;
    padding: 10px 12px;
    font-size: 13px;
    color: {TEXT_PRIMARY};
}}
QLineEdit:hover {{
    border-color: #BECAD3;
}}
QLineEdit:focus {{
    border: 1px solid {BRAND_NAVY};
    background-color: #FFFFFF;
}}
QPushButton#loginButton {{
    background-color: {BRAND_NAVY};
    color: #FFFFFF;
    border: none;
    border-radius: 9px;
    font-weight: 650;
    font-size: 14px;
    padding: 12px;
}}
QPushButton#loginButton:hover {{
    background-color: {BRAND_NAVY_DARK};
}}
QLabel#versionLabel {{
    color: {TEXT_MUTED};
    font-size: 10px;
}}
"""


def crisp_pixmap(widget: QWidget, path: Path, target_width: int) -> QPixmap:
    """Return a high-DPI-aware pixmap without changing the original asset."""
    ratio = widget.devicePixelRatioF() or 1.0
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return pixmap
    scaled = pixmap.scaledToWidth(
        max(1, int(target_width * ratio)),
        Qt.SmoothTransformation,
    )
    scaled.setDevicePixelRatio(ratio)
    return scaled


def asset_icon(assets_dir: Path, name: str, active: bool = False) -> QIcon:
    state = "active" if active else "default"
    path = assets_dir / "icons" / f"{name}-{state}.png"
    return QIcon(str(path)) if path.is_file() else QIcon()
