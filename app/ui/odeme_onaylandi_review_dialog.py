from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.core.personnel_list import PersonnelList
from app.core.personnel_list_cache import PersonnelListCache
from app.core.region_config import RegionConfig
from app.writers.odeme_onaylandi_writer import OdemeOnaylandiWriter

_MISMATCH_COLOR = QColor("#fdebec")

COL_TARIH = 0
COL_BANKA = 1
COL_ACIKLAMA = 2
COL_TUTAR = 3
COL_BOLGE = 4
COL_KASA_KODU = 5
COL_PROJE_KODU = 6
COL_ONERI = 7


class OdemeOnaylandiReviewDialog(QDialog):
    """Bankacının işlemi yanlış bölgenin hesabına yatırdığı durumlar için:
    her 'Ödeme Onaylandı' kaydının Kasa Kodu ve Proje Kodu'nu tek tek gözden
    geçirip düzeltmeyi ve dosyayı yeniden oluşturmayı sağlar.

    Bölge seçimi yalnızca bir kolaylık — Kasa Kodu ve Proje Kodu, seçilen
    bölgeye göre otomatik doldurulur, ama ikisi de doğrudan elle
    değiştirilebilir (bölgeye bağlı kalmadan). Asıl müdahale edilen ve
    Netsis'e giden değerler bunlardır.

    Personel listesi yüklüyse, açıklamadaki personel adından bölge otomatik
    önerilir ve mevcut bölgeyle uyuşmuyorsa satır işaretlenir — bankacı
    hatasını gözle taramaya gerek kalmadan hemen görünür.

    Banka (hangi banka hesabına yattığı) değişmez.
    """

    def __init__(
        self,
        items: list[tuple],
        output_path: Path,
        region_config: RegionConfig,
        personnel_cache: PersonnelListCache,
        parent=None,
    ):
        super().__init__(parent)
        self.items = list(items)
        self.output_path = output_path
        self.region_config = region_config
        self.personnel_cache = personnel_cache
        self.personnel_list: PersonnelList | None = None
        self._region_combos: list[QComboBox] = []
        self.setWindowTitle("Ödeme Onaylandı Kayıtlarını Gözden Geçir")
        self.resize(1200, 560)
        self._load_personnel_list_from_cache()
        self._build_ui()
        self._populate_table()

    def _load_personnel_list_from_cache(self) -> None:
        cached_path = self.personnel_cache.get()
        if cached_path:
            try:
                self.personnel_list = PersonnelList.from_excel(cached_path, self.region_config)
            except Exception:
                self.personnel_list = None

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Kasa Kodu ve Proje Kodu, seçtiğiniz bölgeye göre otomatik doluyor — "
            "ama ikisini de doğrudan buradan değiştirebilirsiniz. Netsis'e giden "
            "değerler bunlardır; bölge seçimi sadece kolaylık amaçlı bir öndolgu."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        personnel_row = QHBoxLayout()
        self.personnel_status_label = QLabel("")
        self.personnel_status_label.setStyleSheet("color: #5b6472;")
        personnel_row.addWidget(self.personnel_status_label, 1)

        load_personnel_button = QPushButton("Personel Listesi Yükle...")
        load_personnel_button.clicked.connect(self._load_personnel_list)
        personnel_row.addWidget(load_personnel_button)
        layout.addLayout(personnel_row)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Tarih", "Banka", "Açıklama", "Tutar", "Bölge (öndolgu için)",
             "Kasa Kodu", "Proje Kodu", "Önerilen Bölge (Personel)"]
        )
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        save_button = QPushButton("Düzelt ve Dosyayı Yeniden Oluştur")
        save_button.clicked.connect(self._save)
        cancel_button = QPushButton("Kapat")
        cancel_button.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

    def _update_personnel_status_label(self) -> None:
        if self.personnel_list:
            meta = self.personnel_cache.metadata() or {}
            self.personnel_status_label.setText(
                f"Personel listesi yüklü: {meta.get('orijinal_ad', '-')} "
                f"({len(self.personnel_list.entries)} kişi)"
            )
        else:
            self.personnel_status_label.setText(
                "Personel listesi henüz yüklenmedi — açıklamadan bölge önerisi için yükleyin."
            )

    def _populate_table(self) -> None:
        self._update_personnel_status_label()

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
            | QTableWidget.EditTrigger.AnyKeyPressed
        )
        self.table.setRowCount(len(self.items))
        self._region_combos = []
        regions = self.region_config.regions()

        for row, (record, region, bank_key) in enumerate(self.items):
            tarih_text = record.islem_tarihi.strftime("%d.%m.%Y") if record.islem_tarihi else "-"
            self._set_readonly(row, COL_TARIH, tarih_text)
            self._set_readonly(row, COL_BANKA, record.banka)
            self._set_readonly(row, COL_ACIKLAMA, record.aciklama)
            self._set_readonly(row, COL_TUTAR, f"{record.tutar:,.2f}")

            combo = QComboBox()
            combo.addItems(regions)
            if region in regions:
                combo.setCurrentText(region)
            combo.currentTextChanged.connect(lambda text, r=row: self._apply_region_defaults(r, text))
            self.table.setCellWidget(row, COL_BOLGE, combo)
            self._region_combos.append(combo)

            kasa_kodu = self.region_config.kasa_kodu(region)
            proje_kodu = self.region_config.proje_kodu(region)
            self.table.setItem(row, COL_KASA_KODU, QTableWidgetItem(str(kasa_kodu) if kasa_kodu is not None else ""))
            self.table.setItem(row, COL_PROJE_KODU, QTableWidgetItem(str(proje_kodu) if proje_kodu is not None else ""))

            oneri_text = "-"
            mismatch = False
            if self.personnel_list:
                matches = self.personnel_list.find_matches(record.aciklama)
                if len(matches) == 1:
                    oneri = matches[0]
                    oneri_text = f"{oneri.bolge} ({oneri.ad_gorunen})"
                    mismatch = oneri.bolge != region
                elif len(matches) > 1:
                    oneri_text = "Birden fazla personel eşleşti — elle kontrol edin"
            self._set_readonly(row, COL_ONERI, oneri_text)

            if mismatch:
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(_MISMATCH_COLOR)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(False)

    def _set_readonly(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~item.flags().__class__(2))  # Qt.ItemIsEditable = 2
        self.table.setItem(row, col, item)

    def _apply_region_defaults(self, row: int, region: str) -> None:
        kasa_kodu = self.region_config.kasa_kodu(region)
        proje_kodu = self.region_config.proje_kodu(region)
        self.table.setItem(row, COL_KASA_KODU, QTableWidgetItem(str(kasa_kodu) if kasa_kodu is not None else ""))
        self.table.setItem(row, COL_PROJE_KODU, QTableWidgetItem(str(proje_kodu) if proje_kodu is not None else ""))

    def _load_personnel_list(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Personel listesi dosyasını seç", "", "Excel dosyaları (*.xlsx *.xls)"
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            personnel_list = PersonnelList.from_excel(path, self.region_config)
        except Exception as error:
            QMessageBox.warning(self, "Dosya okunamadı", f"Personel listesi okunurken bir sorun oluştu:\n\n{error}")
            return

        self.personnel_cache.save(path)
        self.personnel_list = personnel_list
        self._populate_table()

    def _save(self) -> None:
        corrected_items = []
        degisen_sayisi = 0
        for row, (record, original_region, bank_key) in enumerate(self.items):
            new_region = self._region_combos[row].currentText()

            kasa_text = self.table.item(row, COL_KASA_KODU).text().strip()
            proje_text = self.table.item(row, COL_PROJE_KODU).text().strip()
            try:
                kasa_kodu = int(kasa_text) if kasa_text else None
            except ValueError:
                QMessageBox.warning(self, "Geçersiz Kasa Kodu", f"{row + 1}. satırdaki Kasa Kodu sayısal olmalı.")
                return
            try:
                proje_kodu = int(proje_text) if proje_text else None
            except ValueError:
                QMessageBox.warning(self, "Geçersiz Proje Kodu", f"{row + 1}. satırdaki Proje Kodu sayısal olmalı.")
                return

            original_kasa = self.region_config.kasa_kodu(original_region)
            original_proje = self.region_config.proje_kodu(original_region)
            if kasa_kodu != original_kasa or proje_kodu != original_proje:
                degisen_sayisi += 1

            overrides = {"kasa_kodu": kasa_kodu, "proje_kodu": proje_kodu}
            corrected_items.append((record, new_region, bank_key, overrides))

        if degisen_sayisi == 0:
            QMessageBox.information(self, "Değişiklik yok", "Hiçbir kaydın Kasa Kodu / Proje Kodu değeri değiştirilmedi.")
            return

        try:
            OdemeOnaylandiWriter(self.region_config).write(corrected_items, self.output_path)
        except Exception as error:
            QMessageBox.critical(self, "Hata", f"Dosya yeniden oluşturulurken bir sorun oluştu:\n\n{error}")
            return

        QMessageBox.information(
            self,
            "Kaydedildi",
            f"{degisen_sayisi} kaydın Kasa Kodu/Proje Kodu değeri düzeltildi ve dosya yeniden oluşturuldu:\n\n{self.output_path}",
        )
        self.accept()
