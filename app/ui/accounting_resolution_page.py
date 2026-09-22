from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.money import money, money_sum
from app.ui.accounting_view import money_text
from app.ui.design_system import TOKENS


class _AllocationLineEdit(QLineEdit):
    """Table editor that keeps bulk Ctrl+C/Ctrl+V working while editing."""

    def __init__(self, table, parent=None):
        super().__init__(parent)
        self._allocation_table = table

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.matches(QKeySequence.StandardKey.Paste):
            self._allocation_table._paste_from_clipboard()
            # Delegate editor later commits its own text back to the model.
            # Keep it synchronized with the freshly pasted current cell so it
            # cannot overwrite the first pasted value when focus moves.
            item = self._allocation_table.item(
                self._allocation_table.currentRow(),
                self._allocation_table.currentColumn(),
            )
            if item is not None:
                self.setText(item.text())
                self.selectAll()
            return
        if event.matches(QKeySequence.StandardKey.Copy):
            self._allocation_table._copy_to_clipboard()
            return
        super().keyPressEvent(event)


class AllocationEditorDelegate(QStyledItemDelegate):
    """Explicit editor colours prevent native selected-cell palette leakage."""

    def __init__(self, table):
        super().__init__(table)
        self._table = table

    def createEditor(self, parent, option, index):
        editor = _AllocationLineEdit(self._table, parent)
        editor.setObjectName("allocationCellEditor")
        editor.setAlignment(Qt.AlignRight if index.column() == 1 else Qt.AlignLeft)
        palette = editor.palette()
        for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            for role, colour in (
                (QPalette.Base, TOKENS.surface),
                (QPalette.Text, TOKENS.text_primary),
                (QPalette.Highlight, TOKENS.brand),
                (QPalette.HighlightedText, TOKENS.surface),
            ):
                palette.setColor(group, role, QColor(colour))
        editor.setPalette(palette)
        editor.setStyleSheet(
            f"QLineEdit {{ background:{TOKENS.surface}; color:{TOKENS.text_primary};"
            f" selection-background-color:{TOKENS.brand}; selection-color:{TOKENS.surface};"
            f" border:1px solid {TOKENS.brand}; border-radius:4px; padding:2px 8px;"
            " font-family:'Segoe UI'; font-size:13px; }"
        )
        return editor

    def setEditorData(self, editor, index):
        editor.setText(str(index.data(Qt.EditRole) or ""))
        editor.selectAll()

    def setModelData(self, editor, model, index):
        model.setData(index, editor.text(), Qt.EditRole)


class _PasteableAllocationTable(QTableWidget):
    """Two-column allocation editor with Excel-friendly copy/paste."""

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.matches(QKeySequence.StandardKey.Paste):
            self._paste_from_clipboard()
            return
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_to_clipboard()
            return
        super().keyPressEvent(event)

    def _paste_from_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if not text:
            return
        start_row = self.currentRow() if self.currentRow() >= 0 else 0
        start_col = self.currentColumn() if self.currentColumn() >= 0 else 0
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        # Excel panosu çoğu zaman sonuna bir satır sonu ekler. Yalnız terminal
        # satır sonlarını temizle; ortadaki boş satırları silip satırları kaydırma.
        normalized = normalized.rstrip("\n")
        lines = normalized.split("\n") if normalized else [""]
        required_rows = start_row + len(lines)
        while self.rowCount() < required_rows:
            self.insertRow(self.rowCount())
        for row_offset, line in enumerate(lines):
            for col_offset, cell_text in enumerate(line.split("\t")):
                row = start_row + row_offset
                col = start_col + col_offset
                if col >= self.columnCount():
                    continue
                item = self.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.setItem(row, col, item)
                item.setText(cell_text.strip())

    def _copy_to_clipboard(self) -> None:
        ranges = self.selectedRanges()
        if not ranges:
            current = self.currentItem()
            if current is None:
                return
            text = current.text().strip()
            QApplication.clipboard().setText(text)
            return
        selected = ranges[0]
        lines: list[str] = []
        for row in range(selected.topRow(), selected.bottomRow() + 1):
            cells: list[str] = []
            for col in range(selected.leftColumn(), selected.rightColumn() + 1):
                item = self.item(row, col)
                cells.append(item.text().strip() if item else "")
            # Seçimin sağındaki boş hücreler panoya tab/boşluk olarak taşınmasın.
            while cells and not cells[-1]:
                cells.pop()
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines).rstrip(" \t\r\n"))


class AccountingResolutionPage(QWidget):
    """Integrated replacement for the legacy modal manual-match dialog.

    The page intentionally returns the same raw resolution contract used by the
    existing processing engine: ``index -> (route, rows, allow_partial)``.  It
    does not write mappings or accounting output itself; the running MANİM
    operation remains the single owner of those semantics.
    """

    resolutions_submitted = Signal(object)
    back_to_work_requested = Signal()

    ROUTES = (
        ("HAVALE", "Netsis havale"),
        ("ODEME_ONAYLANDI", "Ödeme onaylandı"),
        ("REFERANSLI", "Referanslı"),
        ("ATLA", "İncelemede bırak"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending_items: list = []
        self.customers: list = []
        self.customer_codes: dict[str, str] = {}
        self.resolutions: dict[int, tuple[str, list[tuple[str, float]] | None, bool]] = {}
        self._current_index: int | None = None
        self._build_ui()
        self._set_empty_state()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(3)
        title = QLabel("Eşleştirme & Kurallar")
        title.setObjectName("automationPageTitle")
        subtitle = QLabel(
            "Otomatik karara bağlanamayan hareketleri aynı çalışma içinde düzeltin; "
            "ayrı bir eski pencereye geçmeden muhasebe kararını tamamlayın."
        )
        subtitle.setObjectName("automationPageSubtitle")
        subtitle.setWordWrap(True)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)
        self.back_button = QPushButton("← Yeni çalışmaya dön")
        self.back_button.setObjectName("secondary")
        self.back_button.clicked.connect(self.back_to_work_requested.emit)
        header.addWidget(self.back_button, 0, Qt.AlignTop)
        root.addLayout(header)

        self.summary = QFrame()
        self.summary.setObjectName("automationMetricStrip")
        summary_layout = QHBoxLayout(self.summary)
        summary_layout.setContentsMargins(14, 9, 14, 9)
        summary_layout.setSpacing(18)
        self.pending_count = QLabel("0 bekleyen")
        self.pending_count.setObjectName("automationStatValue")
        self.resolved_count = QLabel("0 karar verildi")
        self.resolved_count.setObjectName("automationStatDetail")
        self.summary_hint = QLabel("Çıktı motoru bu kararlar tamamlanana kadar güvenli biçimde bekler.")
        self.summary_hint.setObjectName("automationStatDetail")
        summary_layout.addWidget(self.pending_count)
        summary_layout.addWidget(self.resolved_count)
        summary_layout.addStretch(1)
        summary_layout.addWidget(self.summary_hint)
        root.addWidget(self.summary)

        body = QHBoxLayout()
        body.setSpacing(12)

        queue_card = QFrame()
        queue_card.setObjectName("surfaceCard")
        queue_layout = QVBoxLayout(queue_card)
        queue_layout.setContentsMargins(0, 0, 0, 0)
        queue_layout.setSpacing(0)
        queue_header = QFrame()
        queue_header.setObjectName("resolutionQueueHeader")
        queue_header_layout = QVBoxLayout(queue_header)
        queue_header_layout.setContentsMargins(14, 12, 14, 10)
        queue_header_layout.setSpacing(2)
        queue_title = QLabel("Karar bekleyen kayıtlar")
        queue_title.setObjectName("panelTitle")
        self.queue_subtitle = QLabel("Henüz bekleyen kayıt yok")
        self.queue_subtitle.setObjectName("cardSubtitle")
        queue_header_layout.addWidget(queue_title)
        queue_header_layout.addWidget(self.queue_subtitle)
        queue_layout.addWidget(queue_header)
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("resolutionQueue")
        self.list_widget.currentRowChanged.connect(self._on_select_row)
        queue_layout.addWidget(self.list_widget, 1)
        queue_card.setMinimumWidth(280)
        queue_card.setMaximumWidth(360)
        body.addWidget(queue_card)

        editor = QFrame()
        editor.setObjectName("surfaceCard")
        editor_layout = QVBoxLayout(editor)
        editor_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        editor_layout.setContentsMargins(18, 16, 18, 16)
        editor_layout.setSpacing(12)

        self.detail_title = QLabel("Kayıt seçin")
        self.detail_title.setObjectName("resolutionRecordTitle")
        self.detail_title.setWordWrap(True)
        self.detail_meta = QLabel("Sol listeden karar bekleyen bir hareket seçin.")
        self.detail_meta.setObjectName("cardSubtitle")
        self.detail_meta.setWordWrap(True)
        self.detail_reason = QLabel("")
        self.detail_reason.setObjectName("resolutionReason")
        self.detail_reason.setWordWrap(True)
        editor_layout.addWidget(self.detail_title)
        editor_layout.addWidget(self.detail_meta)
        editor_layout.addWidget(self.detail_reason)

        route_title = QLabel("Muhasebe kararı")
        route_title.setObjectName("panelTitle")
        editor_layout.addWidget(route_title)
        route_row = QHBoxLayout()
        route_row.setSpacing(7)
        self.route_group = QButtonGroup(self)
        self.route_buttons: dict[str, QPushButton] = {}
        for route_key, route_label in self.ROUTES:
            button = QPushButton(route_label)
            button.setCheckable(True)
            button.setAccessibleName(route_label)
            button.setObjectName("resolutionRoute")
            button.setProperty("route", route_key)
            self.route_group.addButton(button)
            self.route_buttons[route_key] = button
            button.toggled.connect(self._on_route_changed)
            route_row.addWidget(button)
        route_row.addStretch(1)
        editor_layout.addLayout(route_row)

        self.allocation_panel = QFrame()
        self.allocation_panel.setObjectName("resolutionAllocationPanel")
        allocation_layout = QVBoxLayout(self.allocation_panel)
        allocation_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        allocation_layout.setContentsMargins(0, 0, 0, 0)
        allocation_layout.setSpacing(7)
        allocation_header = QHBoxLayout()
        allocation_title = QLabel("Cari dağılımı")
        allocation_title.setObjectName("panelTitle")
        allocation_header.addWidget(allocation_title)
        allocation_header.addStretch(1)
        self.add_row_button = QPushButton("+ Satır")
        self.add_row_button.setObjectName("ghost")
        self.add_row_button.clicked.connect(self._add_empty_row)
        self.remove_row_button = QPushButton("Satırı sil")
        self.remove_row_button.setObjectName("ghost")
        self.remove_row_button.clicked.connect(self._remove_selected_row)
        allocation_header.addWidget(self.add_row_button)
        allocation_header.addWidget(self.remove_row_button)
        allocation_layout.addLayout(allocation_header)

        self.table = _PasteableAllocationTable(0, 2)
        self.table.setObjectName("resolutionAllocationTable")
        self.table.setItemDelegate(AllocationEditorDelegate(self.table))
        self.table.setTabKeyNavigation(True)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setColumnWidth(0, 220)
        self.table.setHorizontalHeaderLabels(("Cari kod", "Tutar"))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.CurrentChanged
            | QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        self.table.itemChanged.connect(self._update_total_label)
        self.table.setMinimumHeight(210)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        allocation_layout.addWidget(self.table, 1)
        self.total_label = QLabel("")
        self.total_label.setObjectName("resolutionTotal")
        self.total_label.setWordWrap(True)
        self.total_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.total_label.setMinimumHeight(68)
        allocation_layout.addWidget(self.total_label)
        editor_layout.addWidget(self.allocation_panel, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.skip_button = QPushButton("İncelemede bırak")
        self.skip_button.setObjectName("secondary")
        self.skip_button.clicked.connect(self._skip_current)
        self.save_button = QPushButton("Kararı kaydet")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self._save_current)
        actions.addStretch(1)
        actions.addWidget(self.skip_button)
        actions.addWidget(self.save_button)
        editor_layout.addLayout(actions)
        self.editor_scroll = QScrollArea(self)
        self.editor_scroll.setObjectName("resolutionEditorScroll")
        self.editor_scroll.setFrameShape(QFrame.NoFrame)
        self.editor_scroll.setWidgetResizable(True)
        self.editor_scroll.setWidget(editor)
        body.addWidget(self.editor_scroll, 1)
        root.addLayout(body, 1)

        footer = QFrame()
        footer.setObjectName("resolutionFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 10, 14, 10)
        self.footer_text = QLabel("Karar bekleyen kayıt yok.")
        self.footer_text.setObjectName("automationRuntimeStatus")
        self.footer_text.setWordWrap(True)
        footer_layout.addWidget(self.footer_text, 1)
        self.finish_button = QPushButton("Kararları uygula ve işleme devam et")
        self.finish_button.setObjectName("primary")
        self.finish_button.clicked.connect(self._finish)
        footer_layout.addWidget(self.finish_button)
        root.addWidget(footer)

    def load_request(self, pending_items, customers) -> None:
        self.pending_items = list(pending_items or [])
        self.customers = list(customers or [])
        self.customer_codes = {
            self._code_key(row.cari_kodu): row.cari_kodu
            for row in self.customers
        }
        self.resolutions = {}
        self._current_index = None
        self.list_widget.clear()
        for item in self.pending_items:
            self.list_widget.addItem(QListWidgetItem(self._list_label(item)))
        self.queue_subtitle.setText(
            f"{len(self.pending_items)} kayıt motor kararı için kullanıcı onayı bekliyor"
            if self.pending_items else "Bekleyen kayıt yok"
        )
        self._update_summary()
        self._set_enabled(bool(self.pending_items))
        if self.pending_items:
            self.list_widget.setCurrentRow(0)
        else:
            self._set_empty_state()

    def _set_empty_state(self) -> None:
        self.detail_title.setText("Karar bekleyen kayıt yok")
        self.detail_meta.setText("Motor belirsiz bir kayıt gönderdiğinde burada düzenleyebilirsiniz.")
        self.detail_reason.clear()
        self.table.setRowCount(0)
        self.total_label.clear()
        self.footer_text.setText("Karar bekleyen kayıt yok.")
        self._set_enabled(False)
        self._update_summary()

    def _set_enabled(self, enabled: bool) -> None:
        for button in self.route_buttons.values():
            button.setEnabled(enabled)
        self.add_row_button.setEnabled(enabled)
        self.remove_row_button.setEnabled(enabled)
        self.skip_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.finish_button.setEnabled(enabled)
        self.table.setEnabled(enabled)

    @staticmethod
    def _code_key(value: str) -> str:
        return "".join(str(value).strip().upper().split())

    @staticmethod
    def _list_label(item) -> str:
        if item.group_records:
            return f"{item.region}  ·  {item.record.banka}  ·  TOPLU {len(item.group_records)} hareket"
        return f"{item.region} · {item.record.banka}\n{money_text(item.record.tutar)}  ·  Kontrol bekliyor"

    def _on_select_row(self, index: int) -> None:
        if index < 0 or index >= len(self.pending_items):
            self._current_index = None
            return
        self._current_index = index
        item = self.pending_items[index]
        title = str(item.record.aciklama or "Açıklamasız hareket").strip()
        self.detail_title.setText(title)
        tarih = item.record.islem_tarihi.strftime("%d.%m.%Y %H:%M:%S") if item.record.islem_tarihi else "—"
        self.detail_meta.setText(
            f"{item.region}  ·  {item.record.banka}  ·  {tarih}  ·  {money_text(item.record.tutar)}\n"
            f"Dekont durumu: {item.record.dekont_durumu or '—'}"
        )
        reason = str(item.reason or "Motor otomatik karar üretemedi.")
        if item.group_records:
            reason += (
                f"\n{len(item.group_records)} banka hareketi birlikte değerlendiriliyor · "
                f"Tahsilat hedefi {item.group_target_amount:,.2f} TL"
            )
        self.detail_reason.setText(f"Kontrol nedeni: {reason}")

        existing = self.resolutions.get(index)
        route = existing[0] if existing else "HAVALE"
        for key, button in self.route_buttons.items():
            button.blockSignals(True)
            button.setChecked(key == route)
            button.blockSignals(False)
        self._apply_route_visibility(route)

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if existing and existing[1]:
            for code, amount in existing[1]:
                self._append_row(code, f"{amount:.2f}")
        elif item.suggested_rows:
            for suggested in item.suggested_rows:
                self._append_row(suggested.musteri_kodu, f"{suggested.tutar:.2f}")
        else:
            target = item.group_target_amount if item.group_records else item.record.tutar
            self._append_row("", f"{target:.2f}")
        self.table.blockSignals(False)
        self._update_total_label()

    def _current_route(self) -> str:
        for route_key, button in self.route_buttons.items():
            if button.isChecked():
                return route_key
        return "HAVALE"

    def _on_route_changed(self, *_args) -> None:
        self._apply_route_visibility(self._current_route())

    def _apply_route_visibility(self, route: str) -> None:
        self.allocation_panel.setVisible(route == "HAVALE")

    def _append_row(self, code: str = "", amount: str = "") -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(code))
        parsed = self._parse_amount(amount)
        amount_item = QTableWidgetItem(money_text(parsed).removesuffix(" TL") if parsed is not None else amount)
        amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 1, amount_item)

    def _add_empty_row(self) -> None:
        self._append_row()

    def _remove_selected_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
        self._update_total_label()

    @staticmethod
    def _parse_amount(text: str) -> float | None:
        text = text.strip()
        if not text:
            return None
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None

    def _current_table_rows(self) -> list[tuple[str, float]]:
        rows: list[tuple[str, float]] = []
        for row_index in range(self.table.rowCount()):
            code_item = self.table.item(row_index, 0)
            amount_item = self.table.item(row_index, 1)
            code = code_item.text().strip() if code_item else ""
            amount_text = amount_item.text().strip() if amount_item else ""
            if not code or not amount_text:
                continue
            amount = self._parse_amount(amount_text)
            if amount is not None:
                rows.append((code, amount))
        return rows

    def _update_total_label(self, *_args) -> None:
        if self._current_index is None or self._current_route() != "HAVALE":
            self.total_label.clear()
            return
        item = self.pending_items[self._current_index]
        target = money(item.group_target_amount if item.group_records else item.record.tutar)
        total = money_sum(amount for _, amount in self._current_table_rows())
        difference = target - total
        comparison = (
            f"Girilen toplam {money_text(total)}  ·  Hedef {money_text(target)}\n"
            f"Fark {'+' if total > target else ''}{money_text(total - target)} · "
        )
        if difference == Decimal("0.00"):
            self.total_label.setText(comparison + "Tutarlar eşleşiyor")
            self.total_label.setProperty("tone", "success")
        elif difference > 0:
            self.total_label.setText(comparison + f"Bekleyen bakiye {money_text(difference)}")
            self.total_label.setProperty("tone", "warning")
        else:
            self.total_label.setText(comparison + "Hedef aşıldı; kaydetmeden önce fazla tutarı düzeltin.")
            self.total_label.setProperty("tone", "critical")
        self.total_label.style().unpolish(self.total_label)
        self.total_label.style().polish(self.total_label)

    def _save_current(self) -> None:
        if self._current_index is None:
            return
        route = self._current_route()
        item = self.pending_items[self._current_index]

        if route == "ODEME_ONAYLANDI" and item.record.tutar < 0:
            QMessageBox.warning(
                self,
                "Ödeme onaylandı olamaz",
                "Negatif tutarlı kayıt giden para işlemidir. Ödeme onaylandı yalnız gelen "
                "havale için kullanılabilir.",
            )
            return

        if route in {"ODEME_ONAYLANDI", "REFERANSLI", "ATLA"}:
            self.resolutions[self._current_index] = (route, None, False)
            self._mark_done(route)
            self._go_to_next_unresolved()
            self._update_summary()
            return

        rows = self._current_table_rows()
        if not rows:
            QMessageBox.warning(self, "Eksik bilgi", "En az bir cari kod ve tutar girin.")
            return

        canonical_rows: list[tuple[str, float]] = []
        for code, amount in rows:
            raw_code = code.strip()
            if not raw_code:
                QMessageBox.warning(self, "Eksik bilgi", "Cari kod boş bırakılamaz.")
                return
            if amount <= 0:
                QMessageBox.warning(self, "Geçersiz tutar", "Tutar sıfırdan büyük olmalıdır.")
                return
            canonical_code = self.customer_codes.get(self._code_key(raw_code), raw_code)
            canonical_rows.append((canonical_code, amount))

        target = money(item.group_target_amount if item.group_records else item.record.tutar)
        total = money_sum(amount for _, amount in canonical_rows)
        if total > target:
            QMessageBox.warning(
                self,
                "Tutar tutmuyor",
                f"Girilen tutarların toplamı ({total:,.2f} TL) banka hareketini "
                f"({target:,.2f} TL) aşamaz.",
            )
            return
        allow_partial = total < target
        if allow_partial and item.group_records:
            remaining = target - total
            QMessageBox.warning(
                self,
                "Toplu havale eksik",
                f"Toplu banka hareketlerinin {remaining:,.2f} TL tutarı henüz cari dağılımına "
                "eklenmedi. Tahsilat raporunda eksik müşteri varsa cari kodunu ve tutarını "
                "yeni satır olarak ekleyin; toplu havale banka toplamıyla tamamen eşleşmeden "
                "rapor hazırlanamaz.",
            )
            return
        if allow_partial:
            remaining = target - total
            answer = QMessageBox.question(
                self,
                "Bekleyen bakiye",
                f"{remaining:,.2f} TL bu aktarımda bekleyen bakiye olarak bırakılacak; "
                "yalnız girdiğiniz tutar Netsis'e yazılacak. Devam edilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.resolutions[self._current_index] = ("HAVALE", canonical_rows, allow_partial)
        self._mark_done("HAVALE")
        self._go_to_next_unresolved()
        self._update_summary()

    def _skip_current(self) -> None:
        if self._current_index is None:
            return
        self.resolutions[self._current_index] = ("ATLA", None, False)
        self._mark_done("ATLA")
        self._go_to_next_unresolved()
        self._update_summary()

    def _mark_done(self, route: str) -> None:
        if self._current_index is None:
            return
        labels = dict(self.ROUTES)
        list_item = self.list_widget.item(self._current_index)
        list_item.setText(f"{self._list_label(self.pending_items[self._current_index])}   ✓ {labels[route]}")
        list_item.setData(Qt.UserRole, route)

    def _go_to_next_unresolved(self) -> None:
        for index in range(len(self.pending_items)):
            if index not in self.resolutions:
                self.list_widget.setCurrentRow(index)
                return

    def _update_summary(self) -> None:
        total = len(self.pending_items)
        resolved = len(self.resolutions)
        self.pending_count.setText(f"{max(0, total - resolved)} bekleyen")
        self.resolved_count.setText(f"{resolved} karar verildi")
        if total:
            self.footer_text.setText(
                f"{resolved}/{total} kayıt için karar verildi. Kararsız kalanlar inceleme listesinde kalabilir."
            )
        else:
            self.footer_text.setText("Karar bekleyen kayıt yok.")

    def _finish(self) -> None:
        total = len(self.pending_items)
        unresolved = total - len(self.resolutions)
        if unresolved:
            answer = QMessageBox.question(
                self,
                "Kararsız kayıtlar",
                f"{unresolved} kayıt için karar verilmedi. Bu kayıtlar inceleme listesinde bırakılarak "
                "işleme devam edilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        payload = dict(self.resolutions)
        self.resolutions_submitted.emit(payload)
        self.footer_text.setText("Kararlar motora aktarıldı · Muhasebe işlemi devam ediyor…")
        self._set_enabled(False)
