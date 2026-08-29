from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class _PasteableTableWidget(QTableWidget):
    """Tek tıkla yazmaya/yapıştırmaya izin veren, Excel'den kopyala-yapıştırı
    destekleyen tablo. Ctrl+V ile panodaki (tek hücre veya sekme ile ayrılmış
    çok hücreli) veriyi, düzenleme moduna girmeye gerek kalmadan doğrudan
    seçili hücreden başlayarak yapıştırır. Ctrl+C ile de seçili hücreleri
    panoya kopyalar.
    """

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override ismi)
        if event.matches(QKeySequence.StandardKey.Paste):
            self._paste_from_clipboard()
            return
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_to_clipboard()
            return
        super().keyPressEvent(event)

    def _paste_from_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication

        text = QApplication.clipboard().text()
        if not text:
            return
        current = self.currentItem()
        start_row = self.currentRow() if current else 0
        start_col = self.currentColumn() if current else 0
        if start_row < 0:
            start_row = 0
        if start_col < 0:
            start_col = 0

        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        lines = [line for line in lines if line != ""] or [""]
        for row_offset, line in enumerate(lines):
            cells = line.split("\t")
            for col_offset, cell_text in enumerate(cells):
                row = start_row + row_offset
                col = start_col + col_offset
                if row >= self.rowCount() or col >= self.columnCount():
                    continue
                item = self.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.setItem(row, col, item)
                item.setText(cell_text.strip())

    def _copy_to_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication

        selected = self.selectedRanges()
        if not selected:
            return
        sel = selected[0]
        rows = []
        for row in range(sel.topRow(), sel.bottomRow() + 1):
            cells = []
            for col in range(sel.leftColumn(), sel.rightColumn() + 1):
                item = self.item(row, col)
                cells.append(item.text() if item else "")
            rows.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(rows))


class ManualMatchDialog(QDialog):
    """Otomatik eşleşmeyen MANİM kayıtları için manuel eşleştirme ekranı.

    Kullanıcı önce bu kaydın GERÇEKTE ne olduğuna karar verir:
      - Netsis Havale Aktarımı: müşteri kodu + tutar girilir (şubeli/bölünmüş
        kayıtlar için birden fazla satır eklenebilir; toplam tutar kaydın
        MANİM tutarına tam eşit olmalı).
      - Ödeme Onaylandı dosyasına taşı: müşteri kodu aranmadan doğrudan o
        dosyaya eklenir (örn. dekont durumu otomatik tanınamamışsa).
      - Referanslı kayıt dosyasına taşı: aynı şekilde doğrudan taşınır.
      - Atla: İnceleme Gerekenler listesinde kalsın.

    "Netsis Havale Aktarımı" seçilip kaydedildiğinde eşleştirme hafızaya
    (mapping_store.json) yazılır; aynı açıklama bir daha geldiğinde program
    otomatik uygular, bir daha sormaz.
    """

    ROUTES = [
        ("HAVALE", "Netsis Havale Aktarımı"),
        ("ODEME_ONAYLANDI", "Ödeme Onaylandı dosyasına taşı"),
        ("REFERANSLI", "Referanslı kayıt dosyasına taşı"),
        ("ATLA", "Atla (İnceleme listesinde kalsın)"),
    ]

    def __init__(self, pending_items, customers, parent=None):
        super().__init__(parent)
        self.pending_items = pending_items
        self.customers = customers
        self.customer_codes = {self._code_key(row.cari_kodu): row.cari_kodu for row in customers}
        # index -> (route, rows|None)  rows: [(musteri_kodu, tutar), ...] (sadece HAVALE icin)
        self.resolutions: dict[int, tuple[str, list[tuple[str, float]] | None]] = {}
        self._current_index: int | None = None

        self.setWindowTitle("Eşleştirme Gerekiyor")
        self.resize(1050, 640)
        self._build_ui()
        if self.pending_items:
            self.list_widget.setCurrentRow(0)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel(f"Otomatik eşleşmeyen kayıt sayısı: {len(self.pending_items)}"))
        self.list_widget = QListWidget()
        for item in self.pending_items:
            self.list_widget.addItem(QListWidgetItem(self._list_label(item)))
        self.list_widget.currentRowChanged.connect(self._on_select_row)
        left_layout.addWidget(self.list_widget)
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        layout.addWidget(left_widget, 1)

        right_layout = QVBoxLayout()
        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.detail_label.setCursor(Qt.CursorShape.IBeamCursor)
        right_layout.addWidget(self.detail_label)

        right_layout.addWidget(QLabel("Bu kayıt aslında:"))
        self.route_group = QButtonGroup(self)
        self.route_buttons: dict[str, QRadioButton] = {}
        for route_key, route_label in self.ROUTES:
            button = QRadioButton(route_label)
            self.route_group.addButton(button)
            self.route_buttons[route_key] = button
            button.toggled.connect(self._on_route_changed)
            right_layout.addWidget(button)

        self.table = _PasteableTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Müşteri Kodu", "Tutar"])
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.CurrentChanged
            | QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.itemChanged.connect(self._update_total_label)
        right_layout.addWidget(self.table)

        row_buttons = QHBoxLayout()
        self.add_row_button = QPushButton("+ Satır Ekle")
        self.add_row_button.clicked.connect(self._add_empty_row)
        self.remove_row_button = QPushButton("Satır Sil")
        self.remove_row_button.clicked.connect(self._remove_selected_row)
        row_buttons.addWidget(self.add_row_button)
        row_buttons.addWidget(self.remove_row_button)
        right_layout.addLayout(row_buttons)

        self.total_label = QLabel("")
        right_layout.addWidget(self.total_label)

        action_buttons = QHBoxLayout()
        save_button = QPushButton("Bu Kaydı Onayla ve Kaydet")
        save_button.clicked.connect(self._save_current)
        skip_button = QPushButton("Atla (İnceleme listesinde kalsın)")
        skip_button.clicked.connect(self._skip_current)
        action_buttons.addWidget(save_button)
        action_buttons.addWidget(skip_button)
        right_layout.addLayout(action_buttons)

        finish_button = QPushButton("Bitti / Kapat")
        finish_button.clicked.connect(self.accept)
        right_layout.addWidget(finish_button)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        layout.addWidget(right_widget, 2)

    @staticmethod
    def _code_key(value: str) -> str:
        return "".join(str(value).strip().upper().split())

    @staticmethod
    def _list_label(item) -> str:
        return f"{item.region} | {item.record.banka} | {item.record.tutar:,.2f} TL"

    def _on_select_row(self, index: int) -> None:
        if index < 0 or index >= len(self.pending_items):
            self._current_index = None
            return
        self._current_index = index
        item = self.pending_items[index]
        tarih_saat = (
            item.record.islem_tarihi.strftime("%d.%m.%Y %H:%M:%S")
            if item.record.islem_tarihi
            else "-"
        )
        self.detail_label.setText(
            f"<b>Bölge:</b> {item.region} &nbsp;&nbsp; <b>Banka:</b> {item.record.banka} "
            f"&nbsp;&nbsp; <b>Tarih/Saat:</b> {tarih_saat}<br>"
            f"<b>Tutar:</b> {item.record.tutar:,.2f} TL<br>"
            f"<b>Açıklama:</b> {item.record.aciklama}<br>"
            f"<b>Dekont Durumu:</b> {item.record.dekont_durumu}<br>"
            f"<b>Neden eşleşmedi:</b> {item.reason}"
        )

        existing = self.resolutions.get(index)
        route = existing[0] if existing else "HAVALE"
        self.route_buttons[route].blockSignals(True)
        self.route_buttons[route].setChecked(True)
        self.route_buttons[route].blockSignals(False)
        self._apply_route_visibility(route)

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if existing and existing[1]:
            for code, amount in existing[1]:
                self._append_row(code, f"{amount:.2f}")
        else:
            self._append_row("", f"{item.record.tutar:.2f}")
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
        is_havale = route == "HAVALE"
        self.table.setVisible(is_havale)
        self.add_row_button.setVisible(is_havale)
        self.remove_row_button.setVisible(is_havale)
        self.total_label.setVisible(is_havale)

    def _append_row(self, code: str = "", amount: str = "") -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(code))
        self.table.setItem(row, 1, QTableWidgetItem(amount))

    def _add_empty_row(self) -> None:
        self._append_row()

    def _remove_selected_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
        self._update_total_label()

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
            if amount is None:
                continue
            rows.append((code, amount))
        return rows

    @staticmethod
    def _parse_amount(text: str) -> float | None:
        """'7.831,00' (Türkçe: nokta binlik ayraç, virgül kuruş) ve '7831.00'
        (düz ondalık) biçimlerinin ikisini de doğru okur. Önceki hali sadece
        virgülü noktaya çeviriyordu; bu da '7.831,00' -> '7.831.00' gibi
        geçersiz bir metin üretip satırı sessizce siliyordu.
        """
        text = text.strip()
        if not text:
            return None
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None

    def _update_total_label(self, *_args) -> None:
        if self._current_index is None or self._current_route() != "HAVALE":
            self.total_label.setText("")
            return
        target = self.pending_items[self._current_index].record.tutar
        total = sum(amount for _, amount in self._current_table_rows())
        matches = abs(round(total, 2) - round(target, 2)) <= 0.01
        color = "green" if matches else "red"
        self.total_label.setText(
            f"<span style='color:{color}; font-weight:bold'>"
            f"Girilen toplam: {total:,.2f} TL &nbsp;/&nbsp; Hedef: {target:,.2f} TL</span>"
        )

    def _save_current(self) -> None:
        if self._current_index is None:
            return
        route = self._current_route()

        if route in ("ODEME_ONAYLANDI", "REFERANSLI", "ATLA"):
            self.resolutions[self._current_index] = (route, None)
            self._mark_done(route)
            self._go_to_next_unresolved()
            return

        # route == "HAVALE"
        rows = self._current_table_rows()
        if not rows:
            QMessageBox.warning(self, "Eksik bilgi", "En az bir müşteri kodu ve tutar girin.")
            return

        canonical_rows: list[tuple[str, float]] = []
        unknown_codes: list[str] = []
        for code, amount in rows:
            canonical_code = self.customer_codes.get(self._code_key(code))
            if not canonical_code:
                unknown_codes.append(code)
                continue
            if amount <= 0:
                QMessageBox.warning(self, "Geçersiz tutar", "Tutar sıfırdan büyük olmalıdır.")
                return
            canonical_rows.append((canonical_code, amount))

        if unknown_codes:
            QMessageBox.warning(
                self,
                "Cari kod bulunamadı",
                "Şu cari kod(lar) müşteri listesinde yok:\n\n"
                + "\n".join(sorted(set(unknown_codes)))
                + "\n\nMüşteri listesindeki geçerli cari kodu girin.",
            )
            return

        rows = canonical_rows
        target = self.pending_items[self._current_index].record.tutar
        total = sum(amount for _, amount in rows)
        if abs(round(total, 2) - round(target, 2)) > 0.01:
            QMessageBox.warning(
                self,
                "Tutar tutmuyor",
                f"Girilen tutarların toplamı ({total:,.2f} TL) kayıt tutarıyla "
                f"({target:,.2f} TL) eşleşmiyor. Lütfen kontrol edin.",
            )
            return
        self.resolutions[self._current_index] = ("HAVALE", rows)
        self._mark_done("HAVALE")
        self._go_to_next_unresolved()

    def _mark_done(self, route: str) -> None:
        labels = dict(self.ROUTES)
        current_item = self.list_widget.item(self._current_index)
        base_label = self._list_label(self.pending_items[self._current_index])
        current_item.setText(f"{base_label}  ✓ {labels[route]}")

    def _skip_current(self) -> None:
        if self._current_index is None:
            return
        self.resolutions[self._current_index] = ("ATLA", None)
        self._mark_done("ATLA")
        self._go_to_next_unresolved()

    def _go_to_next_unresolved(self) -> None:
        for index in range(len(self.pending_items)):
            if index not in self.resolutions:
                self.list_widget.setCurrentRow(index)
                return

    def get_resolutions(self) -> dict[int, tuple[str, list[tuple[str, float]] | None]]:
        """{pending_items indeksi: (route, rows|None)} biçiminde onaylanan kararları döndürür."""
        return self.resolutions
