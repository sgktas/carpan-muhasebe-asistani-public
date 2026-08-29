from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.core.region_config import RegionConfigStore


class RegionEditorDialog(QDialog):
    def __init__(
        self,
        store: RegionConfigStore,
        region_name: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.store = store
        self.original_name = region_name
        self.saved_region: str | None = None
        self.setWindowTitle("Bölgeyi Düzenle" if region_name else "Yeni Bölge Ekle")
        self.setMinimumWidth(520)
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        info = QLabel(
            "Bu bilgiler MANİM aktarım dosyalarında ve Ödeme Onaylandı çıktısında "
            "kullanılır. Sıra değeri dosya ve satır sırasını belirler."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Örn. ANTALYA")
        self.active_check = QCheckBox("Aktarımlarda kullan")
        self.active_check.setChecked(True)
        self.order_spin = QSpinBox()
        self.order_spin.setRange(1, 999)
        self.kasa_spin = QSpinBox()
        self.kasa_spin.setRange(0, 99_999_999)
        self.proje_spin = QSpinBox()
        self.proje_spin.setRange(0, 99_999_999)
        self.ref_edit = QLineEdit()
        self.aliases_edit = QLineEdit()
        self.aliases_edit.setPlaceholderText("Virgülle ayırın: ANTALYA, ANTALYA TEMİNATSIZ")
        self.garanti_edit = QLineEdit()
        self.ykb_edit = QLineEdit()
        self.ziraat_edit = QLineEdit()
        self.manim_garanti_edit = QLineEdit()
        self.manim_ykb_edit = QLineEdit()
        self.manim_ziraat_edit = QLineEdit()

        form.addRow("Bölge adı", self.name_edit)
        form.addRow("Durum", self.active_check)
        form.addRow("Çıktı sırası", self.order_spin)
        form.addRow("Kasa kodu", self.kasa_spin)
        form.addRow("Proje kodu", self.proje_spin)
        form.addRow("Referans kodu", self.ref_edit)
        form.addRow("Müşteri şube etiketleri", self.aliases_edit)
        form.addRow("Garanti çıktı banka kodu", self.garanti_edit)
        form.addRow("Yapı Kredi çıktı banka kodu", self.ykb_edit)
        form.addRow("Ziraat çıktı banka kodu", self.ziraat_edit)
        form.addRow("MANİM Garanti hesap/IBAN sonu", self.manim_garanti_edit)
        form.addRow("MANİM Yapı Kredi hesap/IBAN sonu", self.manim_ykb_edit)
        form.addRow("MANİM Ziraat hesap/IBAN sonu", self.manim_ziraat_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Kaydet")
        buttons.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_values(self) -> None:
        self.order_spin.setValue(self.store.next_order())
        if not self.original_name:
            return
        entry = self.store.config().entry(self.original_name)
        self.name_edit.setText(self.original_name)
        self.active_check.setChecked(bool(entry.get("aktif", True)))
        self.order_spin.setValue(int(entry.get("sira", self.store.next_order())))
        self.kasa_spin.setValue(int(entry.get("kasa_kodu") or 0))
        self.proje_spin.setValue(int(entry.get("proje_kodu") or 0))
        self.ref_edit.setText(str(entry.get("ref_kodu") or ""))
        self.aliases_edit.setText(", ".join(entry.get("musteri_sube_etiketleri", [])))
        banks = entry.get("banka_kodlari", {})
        self.garanti_edit.setText(str(banks.get("GARANTI") or ""))
        self.ykb_edit.setText(str(banks.get("YKB") or ""))
        self.ziraat_edit.setText(str(banks.get("ZIRAAT") or ""))
        manim_accounts = entry.get("manim_hesap_kodlari", {})
        self.manim_garanti_edit.setText(str(manim_accounts.get("GARANTI") or ""))
        self.manim_ykb_edit.setText(str(manim_accounts.get("YKB") or ""))
        self.manim_ziraat_edit.setText(str(manim_accounts.get("ZIRAAT") or ""))

    def _save(self) -> None:
        region = self.store.normalize_name(self.name_edit.text())
        if not region:
            QMessageBox.warning(self, "Eksik bilgi", "Bölge adını yazın.")
            return
        if not self.original_name and region in self.store.config().regions(include_inactive=True):
            QMessageBox.warning(self, "Bölge zaten var", "Bu bölgeyi listeden seçip düzenleyin.")
            return
        if self.kasa_spin.value() == 0 or self.proje_spin.value() == 0:
            QMessageBox.warning(self, "Eksik bilgi", "Kasa kodu ve proje kodu sıfır olamaz.")
            return

        aliases = [item.strip() for item in self.aliases_edit.text().split(",") if item.strip()]
        values = {
            "aktif": self.active_check.isChecked(),
            "sira": self.order_spin.value(),
            "kasa_kodu": self.kasa_spin.value(),
            "proje_kodu": self.proje_spin.value(),
            "ref_kodu": self.ref_edit.text().strip().upper(),
            "banka_kodlari": {
                "GARANTI": self.garanti_edit.text(),
                "YKB": self.ykb_edit.text(),
                "ZIRAAT": self.ziraat_edit.text(),
            },
            "manim_hesap_kodlari": {
                "GARANTI": self.manim_garanti_edit.text(),
                "YKB": self.manim_ykb_edit.text(),
                "ZIRAAT": self.manim_ziraat_edit.text(),
            },
            "musteri_sube_etiketleri": aliases or [region],
        }
        try:
            self.saved_region = self.store.save_region(
                region,
                values,
                original_name=self.original_name,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Kaydedilemedi", str(error))
            return
        self.accept()


class RegionManagementDialog(QDialog):
    def __init__(self, store: RegionConfigStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Bölge Yönetimi")
        self.resize(930, 500)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        info = QLabel(
            "Aktif bölgeler MANİM, Referanslı ve Ödeme Onaylandı çıktılarında burada "
            "belirlenen sırayla kullanılır. Yeni bölge eklemek için kod değişikliği gerekmez."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            [
                "Sıra", "Bölge", "Durum", "Kasa", "Proje",
                "Garanti çıktı", "YKB çıktı", "Ziraat çıktı",
                "Garanti hesap sonu", "YKB hesap sonu", "Ziraat hesap sonu",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._edit_selected)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        add_button = QPushButton("Yeni Bölge Ekle")
        add_button.clicked.connect(self._add_region)
        edit_button = QPushButton("Seçili Bölgeyi Düzenle")
        edit_button.clicked.connect(self._edit_selected)
        close_button = QPushButton("Kapat")
        close_button.clicked.connect(self.accept)
        actions.addWidget(add_button)
        actions.addWidget(edit_button)
        actions.addStretch(1)
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def _refresh(self) -> None:
        config = self.store.config()
        regions = config.regions(include_inactive=True)
        self.table.setRowCount(len(regions))
        for row, region in enumerate(regions):
            entry = config.entry(region)
            banks = entry.get("banka_kodlari", {})
            manim_accounts = entry.get("manim_hesap_kodlari", {})
            values = [
                entry.get("sira", row + 1),
                region,
                "Aktif" if entry.get("aktif", True) else "Pasif",
                entry.get("kasa_kodu", ""),
                entry.get("proje_kodu", ""),
                banks.get("GARANTI", ""),
                banks.get("YKB", ""),
                banks.get("ZIRAAT", ""),
                manim_accounts.get("GARANTI", ""),
                manim_accounts.get("YKB", ""),
                manim_accounts.get("ZIRAAT", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column in (0, 2, 3, 4):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, item)
        if regions:
            self.table.selectRow(0)

    def _selected_region(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 1)
        return item.text() if item else None

    def _add_region(self) -> None:
        if RegionEditorDialog(self.store, parent=self).exec():
            self._refresh()

    def _edit_selected(self, *_args) -> None:
        region = self._selected_region()
        if not region:
            QMessageBox.information(self, "Bölge seçin", "Düzenlemek istediğiniz bölgeyi seçin.")
            return
        if RegionEditorDialog(self.store, region, self).exec():
            self._refresh()
