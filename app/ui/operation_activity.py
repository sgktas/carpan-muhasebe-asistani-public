"""Shared, read-only activity view for desktop operation pages.

Presentation only: severity is not a financial decision or success inference.
Legacy append/clear/toPlainText callers retain their full original messages.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QTableView, QVBoxLayout, QWidget,
    QAbstractItemView,
)


class ActivityModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries: list[tuple[str, str, str]] = []
        self.error_count = 0
        self.warning_count = 0

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 3

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return ("Saat", "Seviye", "İşlem açıklaması")[section]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        timestamp, level, message = self.entries[index.row()]
        if role == Qt.DisplayRole:
            return (timestamp, level, message.replace("\n", " · "))[index.column()]
        if role == Qt.ToolTipRole:
            return message
        if role == Qt.ForegroundRole and index.column() == 1:
            return QColor({"Hata": "#B42318", "Uyarı": "#9B5A12", "Bilgi": "#356180"}[level])

    def append(self, message: str):
        self.append_many([message])

    def append_many(self, messages):
        now = datetime.now().strftime("%H:%M:%S")
        entries = []
        for message in messages:
            message = str(message)
            stripped = message.lstrip().upper()
            level = "Hata" if stripped.startswith("HATA:") else "Uyarı" if stripped.startswith("UYARI:") else "Bilgi"
            entries.append((now, level, message))
        if not entries:
            return
        row = len(self.entries)
        self.beginInsertRows(QModelIndex(), row, row + len(entries) - 1)
        self.entries.extend(entries)
        self.error_count += sum(e[1] == "Hata" for e in entries)
        self.warning_count += sum(e[1] == "Uyarı" for e in entries)
        self.endInsertRows()

    def clear(self):
        self.beginResetModel()
        self.entries.clear()
        self.error_count = self.warning_count = 0
        self.endResetModel()


class ActivityFilter(QSortFilterProxyModel):
    level = ""
    query = ""

    def filterAcceptsRow(self, row, parent):
        _time, level, message = self.sourceModel().entries[row]
        return (not self.level or self.level == level) and self.query in message.casefold()


class OperationActivity(QWidget):
    """Searchable activity, explicit errors, selectable detail and local copy."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(250)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("İşlem açıklamalarında ara…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("İşlem günlüğünde ara")
        self.level = QComboBox()
        self.level.addItems(["Tüm kayıtlar", "Uyarı", "Hata", "Bilgi"])
        self.level.setAccessibleName("Günlük seviyesi")
        self.copy_button = QPushButton("Günlüğü kopyala")
        self.copy_button.setObjectName("secondary")
        self.copy_button.setToolTip("Tüm kayıtları panoya kopyalar. Paylaşmadan önce müşteri bilgilerini kontrol edin.")
        self.copy_button.clicked.connect(lambda: QApplication.clipboard().setText(self.toPlainText()))
        tools.addWidget(self.search, 1)
        tools.addWidget(self.level)
        tools.addWidget(self.copy_button)
        layout.addLayout(tools)
        self.model = ActivityModel(self)
        self.proxy = ActivityFilter(self)
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setObjectName("activityTable")
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setColumnWidth(0, 82)
        self.table.setColumnWidth(1, 82)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setAccessibleName("İşlem günlüğü kayıtları")
        layout.addWidget(self.table, 1)
        self.empty = QLabel("Henüz işlem kaydı yok. Dosyalarınızı seçerek başlayın.")
        self.empty.setObjectName("activityEmpty")
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)
        footer = QHBoxLayout()
        self.counts = QLabel()
        self.counts.setObjectName("cardSubtitle")
        self.counts.setWordWrap(True)
        self.details_toggle = QCheckBox("Seçili kaydın ayrıntısı")
        footer.addWidget(self.counts, 1)
        footer.addWidget(self.details_toggle)
        layout.addLayout(footer)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(120)
        self.details.setPlaceholderText("Üstteki listeden bir kayıt seçin.")
        self.details.hide()
        layout.addWidget(self.details)
        self.details_toggle.toggled.connect(self.details.setVisible)
        self.table.selectionModel().currentRowChanged.connect(self._select)
        self.table.doubleClicked.connect(lambda _index: self.details_toggle.setChecked(True))
        self.search.textChanged.connect(self._filter)
        self.level.currentIndexChanged.connect(self._filter)
        self._refresh()

    def _select(self, current, _previous):
        source = self.proxy.mapToSource(current)
        self.details.setPlainText(self.model.entries[source.row()][2] if source.isValid() else "")

    def _filter(self):
        modern = hasattr(self.proxy, "beginFilterChange") and hasattr(self.proxy, "endFilterChange")
        if modern:
            self.proxy.beginFilterChange()
        self.proxy.query = self.search.text().strip().casefold()
        self.proxy.level = self.level.currentText() if self.level.currentIndex() else ""
        if modern:
            self.proxy.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        else:
            self.proxy.invalidateFilter()
        self._refresh()

    def _refresh(self):
        entries = self.model.entries
        errors = self.model.error_count
        warnings = self.model.warning_count
        self.counts.setText(f"{self.proxy.rowCount():,} / {len(entries):,} kayıt  ·  {warnings:,} uyarı  ·  {errors:,} hata")
        self.copy_button.setEnabled(bool(entries))
        self.empty.setVisible(not self.proxy.rowCount())
        if entries:
            self.empty.setText("Bu filtrelere uygun kayıt bulunamadı. Aramayı veya seviye filtresini değiştirin.")
        else:
            self.empty.setText(getattr(self, "_placeholder", "Henüz işlem kaydı yok. Dosyalarınızı seçerek başlayın."))

    def append(self, message: str):
        self.append_many([message])

    def append_many(self, messages):
        scroll = self.table.verticalScrollBar()
        follow = scroll.value() >= scroll.maximum() - 2
        self.model.append_many(messages)
        self._refresh()
        if follow:
            self.table.scrollToBottom()

    def clear(self):
        self.model.clear()
        self.search.clear()
        self.level.setCurrentIndex(0)
        self.details.clear()
        self.details_toggle.setChecked(False)
        self._refresh()

    def toPlainText(self):
        return "\n".join(message for _time, _level, message in self.model.entries)

    def setPlaceholderText(self, text):
        self._placeholder = text
        self._refresh()
