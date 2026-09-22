"""Small, concrete PySide primitives shared by the new product shell."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.design_system import STATUS_TOKENS, TOKENS


class StatusBadge(QLabel):
    """Textual status indicator; colour only supports the spoken state."""

    def __init__(self, text: str, *, tone: str = "info", parent=None):
        super().__init__(text, parent)
        palette = {
            "success": (TOKENS.success, TOKENS.success_soft),
            "warning": (TOKENS.warning, TOKENS.warning_soft),
            "critical": (TOKENS.critical, TOKENS.critical_soft),
            "info": (TOKENS.info, TOKENS.info_soft),
            "neutral": (TOKENS.text_secondary, TOKENS.surface_secondary),
        }
        foreground, background = palette.get(tone, palette["neutral"])
        self.setObjectName("statusBadge")
        self.setAlignment(Qt.AlignCenter)
        self.setAccessibleName(f"Durum: {text}")
        self.setStyleSheet(
            f"background:{background}; color:{foreground}; border:none; "
            f"border-radius:{TOKENS.radius_small}px; padding:4px 8px; font-size:11px; font-weight:600;"
        )


class ModuleStatusBadge(StatusBadge):
    def __init__(self, state: str, parent=None):
        foreground, background, label = STATUS_TOKENS[state]
        super().__init__(label, tone="neutral", parent=parent)
        self.state = state
        self.setAccessibleName(f"Modül durumu: {label}")
        self.setStyleSheet(
            f"background:{background}; color:{foreground}; border:1px solid {foreground}; "
            f"border-radius:{TOKENS.radius_small}px; padding:2px 6px; font-size:10px; font-weight:600;"
        )


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("primary")


class SecondaryButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("secondary")


class DangerButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("danger")


class IconButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("iconButton")


class SectionHeader(QFrame):
    def __init__(self, title: str, subtitle: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("sectionHeader")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TOKENS.space_1)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        if subtitle:
            detail = QLabel(subtitle)
            detail.setObjectName("sectionSubtitle")
            detail.setWordWrap(True)
            layout.addWidget(detail)


class EmptyState(QFrame):
    def __init__(self, title: str, detail: str, parent=None):
        super().__init__(parent)
        self.setObjectName("emptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(TOKENS.space_7, TOKENS.space_7, TOKENS.space_7, TOKENS.space_7)
        layout.setSpacing(TOKENS.space_2)
        heading = QLabel(title)
        heading.setObjectName("emptyStateTitle")
        heading.setAlignment(Qt.AlignCenter)
        detail_label = QLabel(detail)
        detail_label.setObjectName("emptyStateDetail")
        detail_label.setAlignment(Qt.AlignCenter)
        detail_label.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(detail_label)


class ConnectionState(EmptyState):
    pass


class LockedModuleState(EmptyState):
    pass


class MetricTile(QFrame):
    def __init__(self, label: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metricTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(TOKENS.space_4, TOKENS.space_3, TOKENS.space_4, TOKENS.space_3)
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        label_widget = QLabel(label)
        label_widget.setObjectName("metricLabel")
        layout.addWidget(value_label)
        layout.addWidget(label_widget)


class SidebarItem(QFrame):
    """Navigation title with a secondary status line and a separate chevron."""

    def __init__(self, label: str, state: str, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarItem")
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 1)
        layout.setHorizontalSpacing(0)
        layout.setVerticalSpacing(0)
        layout.setAlignment(Qt.AlignTop)
        self.button = QPushButton(label)
        self.button.setProperty("class", "navItem")
        self.button.setProperty("active", "false")
        self.button.setAccessibleName(label)
        self.button.setCursor(Qt.PointingHandCursor)
        self.status = ModuleStatusBadge(state)
        self.status.setProperty("moduleState", state)
        tone = {
            "ACTIVE": "#58C99A",
            "UNCONFIGURED": "#E9B44C",
            "COMING_SOON": "#8FB3FF",
            "LOCKED": "#9AA9BC",
        }.get(state, "#9AA9BC")
        self.status.setText(f"●  {self.status.text()}")
        self.status.setStyleSheet(
            f"background:transparent; color:{tone}; border:none; "
            "padding:0px; font-size:9px; font-weight:500;"
        )
        self.status.setFixedWidth(self.status.sizeHint().width())
        self.status.setFixedHeight(11)
        self.status.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.status.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.button, 0, 0)
        layout.addWidget(self.status, 1, 0, Qt.AlignLeft)
        layout.setColumnStretch(0, 1)
        # Keep the state visually attached to the title instead of letting it
        # drift toward the next module row.
        self.status.setContentsMargins(27, 0, 0, 0)
        self.status.setFixedWidth(self.status.sizeHint().width() + 27)
        self.chevron = QPushButton("⌃")
        self.chevron.setObjectName("sidebarChevron")
        self.chevron.setFixedSize(20, 20)
        self.chevron.setAccessibleName("Alt menüyü daralt")
        layout.addWidget(self.chevron, 0, 1)
        self.chevron.hide()
        self.expandable = False
        self.show_status = True

    def set_collapsed(self, collapsed: bool) -> None:
        label = self.button.accessibleName()
        self.button.setText("" if collapsed else label)
        self.button.setToolTip(label)
        self.status.setVisible(self.show_status and not collapsed)
        self.chevron.setVisible(self.expandable and not collapsed)


class SidebarSection(QFrame):
    """A small grouped navigation container for product-family sections."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarSection")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("navSection")
        self.layout.addWidget(self.title_label)

    def add_item(self, widget: QWidget) -> None:
        self.layout.addWidget(widget)

    def set_collapsed(self, collapsed: bool) -> None:
        self.title_label.setVisible(not collapsed)
