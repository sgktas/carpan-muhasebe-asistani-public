"""Small, consistent outline symbols for the accounting work surface."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PATHS = {
    "files": '<path d="m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5"/>',
    "region": '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2.5"/>',
    "record": '<path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6"/>',
    "workflow": '<path d="M3 8h8v12H3zM13 3h8v12h-8zM7 5V3h6M17 18v3h-6M5 12h4M15 7h4"/>',
    "balance": '<path d="M12 3v17M6 21h12M4 7h16M6 7l-4 8h8zM18 7l-4 8h8z"/>',
    "calendar": '<rect x="4" y="5" width="16" height="16" rx="2"/><path d="M8 3v4M16 3v4M4 10h16M8 14h3M8 17h7"/>',
    "filter": '<path d="M3 4h18l-7 8v8l-4-2v-6z"/>',
    "columns": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/>',
    "kpi_down": '<path d="M12 5v12"/><path d="m8.7 13.5 3.3 3.5 3.3-3.5"/>',
    "kpi_up": '<path d="M12 19V7"/><path d="m8.7 10.5 3.3-3.5 3.3 3.5"/>',
    "kpi_net": '<path d="M6.5 19V13"/><path d="M10.5 19V10.5"/><path d="M14.5 19V8"/><path d="M18.5 19V5.5"/>',
}


def workspace_icon(name: str, size: int = 24, color: str = "#3653A3") -> QIcon:
    stroke_width = "1.85" if name.startswith("kpi_") else "1.65"
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round">{_PATHS[name]}</svg>'
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


_SIDEBAR_PATHS = {
    "dashboard": '<path d="M4 11.5 12 4l8 7.5V20H4z"/><path d="M9 20v-6h6v6"/>',
    "accounting_automation": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h4"/>',
    "tax_automation": '<path d="M7 4h10l3 4v12H4V8z"/><path d="M8 12h8M8 16h5"/>',
    "banking": '<path d="M3 9h18L12 3z"/><path d="M5 10v8M9 10v8M15 10v8M19 10v8M3 20h18"/>',
    "einvoice": '<path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4M9 11h6M9 15h6"/>',
    "reconciliation": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="m8 12 2.5 2.5L16 9"/>',
    "integrations": '<path d="M8 4v4M16 4v4M5 8h6v5H5zM13 11h6v5h-6zM8 13v5M16 16v4"/>',
    "operations": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>',
    "reports": '<path d="M5 20V10M10 20V6M15 20v-8M20 20V4"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.09A1.7 1.7 0 0 0 8.97 19.35a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1.03H3v-4h.09A1.7 1.7 0 0 0 4.65 8.94a1.7 1.7 0 0 0-.34-1.88L4.25 7l2.83-2.83.06.06A1.7 1.7 0 0 0 9.02 4.57 1.7 1.7 0 0 0 10.05 3H10V3h4v.09a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.88-.34l.06-.06L19.8 7.08l-.06.06a1.7 1.7 0 0 0-.34 1.88 1.7 1.7 0 0 0 1.56 1.03H21v4h-.09A1.7 1.7 0 0 0 19.4 15Z"/>',
}


def product_sidebar_icon(module_id: str, size: int = 18, *, active: bool = False) -> QIcon:
    """Crisp outline icon set for the product navigation rail."""
    path = _SIDEBAR_PATHS.get(module_id, _SIDEBAR_PATHS["operations"])
    color = "#FFFFFF" if active else "#B9C7DA"
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


_SHELL_PATHS = {
    "file": '<path d="M6 3h8l4 4v14H6zM14 3v5h4"/>',
    "history": '<path d="M4 12a8 8 0 1 0 2-5.3M4 4v5h5M12 8v5l3 2"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/>',
    "bell": '<path d="M6 16h12l-1.5-2.5V10a4.5 4.5 0 0 0-9 0v3.5zM10 19h4"/>',
    "panel": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M16 4v16"/>',
}


def shell_icon(name: str, size: int = 16, color: str = "#36527F") -> QIcon:
    """Crisp line icons for the finance-workspace top bar."""
    path = _SHELL_PATHS[name]
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
