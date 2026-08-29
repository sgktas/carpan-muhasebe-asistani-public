from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.customer_list_profile import CustomerListProfile
from app.core.input_profile import InputProfile
from app.core.output_profile import OutputColumn, OutputProfile
from app.ui.manual_match_dialog import _PasteableTableWidget


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = (
        text.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
        .replace("ü", "u").replace("ö", "o").replace("ç", "c")
    )
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "profil"


class _ProfileMetaRow(QWidget):
    """Her profil düzenleyicinin üstünde tekrar eden kimlik/ad/açıklama alanları."""

    def __init__(self, profile_id: str, name: str, description: str, id_editable: bool, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(8)

        id_row = QHBoxLayout()
        id_row.addWidget(QLabel("Profil kimliği (dosya adı):"))
        self.id_edit = QLineEdit(profile_id)
        self.id_edit.setEnabled(id_editable)
        if not id_editable:
            self.id_edit.setToolTip("Var olan bir profili düzenlerken kimlik değiştirilemez.")
        id_row.addWidget(self.id_edit)
        layout.addLayout(id_row)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Görünen ad:"))
        self.name_edit = QLineEdit(name)
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        desc_row = QHBoxLayout()
        desc_row.addWidget(QLabel("Açıklama:"))
        self.description_edit = QLineEdit(description)
        desc_row.addWidget(self.description_edit)
        layout.addLayout(desc_row)


class InputProfileEditorDialog(QDialog):
    """Banka hareket raporu (girdi) profilini JSON'a hiç dokunmadan düzenler.

    Solda program içindeki sabit alan adları, sağda kullanıcının kendi banka
    raporundaki gerçek sütun başlığını yazacağı tek bir tablo gösterilir.
    """

    FIELD_LABELS = {
        "banka": "Banka",
        "sube": "Şube / Hesap",
        "islem_tarihi": "İşlem Tarihi",
        "aciklama": "Açıklama",
        "tutar": "Tutar",
        "dekont_durumu": "Dekont Durumu",
        "karsi_hesap_adi": "Karşı Hesap Adı",
        "karsi_hesap_kodu": "Karşı Hesap Kodu",
    }

    def __init__(self, config_dir: Path, profile: InputProfile | None, parent=None):
        super().__init__(parent)
        self.config_dir = config_dir
        self.is_new = profile is None
        self._detected_headers: list[str] = []
        self.setWindowTitle("Yeni Girdi Profili" if self.is_new else f"Girdi Profilini Düzenle — {profile.name}")
        self.resize(760, 520)
        self._build_ui(profile)

    def _build_ui(self, profile: InputProfile | None) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Banka hareket raporunuzda her satır için hangi sütun başlığının "
            "hangi bilgiyi taşıdığını belirtin. En kolayı: aşağıdan örnek bir "
            "rapor dosyası yükleyin, sütun başlıklarını sizin için otomatik "
            "bulup listeden seçmenizi sağlayalım. İsterseniz elle de yazabilirsiniz."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.meta = _ProfileMetaRow(
            profile.profile_id if profile else _slugify("yeni_girdi_profili"),
            profile.name if profile else "",
            profile.description if profile else "",
            id_editable=self.is_new,
        )
        layout.addWidget(self.meta)

        sample_row = QHBoxLayout()
        self.sample_label = QLabel("Örnek dosya: (henüz yüklenmedi — sütun başlıklarını elle yazabilirsiniz)")
        sample_row.addWidget(self.sample_label, 1)
        sample_button = QPushButton("Örnek rapor dosyası yükle...")
        sample_button.clicked.connect(self._load_sample_file)
        sample_row.addWidget(sample_button)
        layout.addLayout(sample_row)

        self.table = _PasteableTableWidget(len(self.FIELD_LABELS), 2)
        self.table.setHorizontalHeaderLabels(["Programın anladığı bilgi", "Sizin dosyanızdaki sütun başlığı"])
        self._existing_header_for = {}
        if profile:
            self._existing_header_for = {field: header for header, field in profile.columns.items()}
        for row, (field, label) in enumerate(self.FIELD_LABELS.items()):
            label_item = QTableWidgetItem(label)
            label_item.setFlags(label_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, label_item)
            self.table.setItem(row, 1, QTableWidgetItem(self._existing_header_for.get(field, "")))
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        save_button = QPushButton("Kaydet")
        save_button.clicked.connect(self._save)
        cancel_button = QPushButton("Vazgeç")
        cancel_button.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

    def _load_sample_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Örnek rapor dosyasını seç", "", "Excel dosyaları (*.xlsx *.xls)"
        )
        if not path_str:
            return
        try:
            import pandas as pd
            headers = [str(column).strip() for column in pd.read_excel(path_str, nrows=0).columns]
        except Exception as error:
            QMessageBox.warning(self, "Dosya okunamadı", f"Örnek dosya okunurken bir sorun oluştu: {error}")
            return

        self._detected_headers = headers
        self.sample_label.setText(f"Örnek dosya: {Path(path_str).name} — {len(headers)} sütun bulundu")

        for row, field in enumerate(self.FIELD_LABELS.keys()):
            current_text = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
            combo = QComboBox()
            combo.addItem("")
            combo.addItems(headers)
            preselect = current_text if current_text in headers else self._existing_header_for.get(field, "")
            if preselect in headers:
                combo.setCurrentText(preselect)
            self.table.setCellWidget(row, 1, combo)

    def _save(self) -> None:
        profile_id = _slugify(self.meta.id_edit.text())
        name = self.meta.name_edit.text().strip() or profile_id
        description = self.meta.description_edit.text().strip()

        columns: dict[str, str] = {}
        missing_fields = []
        for row, field in enumerate(self.FIELD_LABELS.keys()):
            combo = self.table.cellWidget(row, 1)
            if isinstance(combo, QComboBox):
                header_text = combo.currentText().strip()
            else:
                header_item = self.table.item(row, 1)
                header_text = header_item.text().strip() if header_item else ""
            if not header_text:
                missing_fields.append(self.FIELD_LABELS[field])
                continue
            columns[header_text] = field

        if missing_fields:
            QMessageBox.warning(
                self,
                "Eksik bilgi",
                "Şu bilgiler için sütun başlığı girmediniz:\n\n" + "\n".join(missing_fields),
            )
            return

        target_dir = self.config_dir / "input_profiles"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{profile_id}.json"
        if self.is_new and target_path.exists():
            QMessageBox.warning(self, "Zaten var", f"'{profile_id}' kimlikli bir profil zaten var. Farklı bir kimlik seçin.")
            return

        target_path.write_text(
            json.dumps(
                {"id": profile_id, "name": name, "description": description, "columns": columns},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.saved_profile_id = profile_id
        self.accept()


class CustomerListProfileEditorDialog(QDialog):
    """Müşteri listesi profilini JSON'a dokunmadan düzenler.

    Her bilgi için birden fazla olası sütun adı girilebilir (virgülle ayrılmış);
    dosyada bulunan ilk eşleşme kullanılır.
    """

    FIELD_LABELS = {
        "cari_kodu": "Müşteri/Cari Kodu (zorunlu)",
        "unvan": "Ünvan (zorunlu)",
        "tabela_adi": "Tabela Adı",
        "vergi_no": "Vergi No / T.C. Kimlik No",
        "sube": "Şube",
    }

    def __init__(self, config_dir: Path, profile: CustomerListProfile | None, parent=None):
        super().__init__(parent)
        self.config_dir = config_dir
        self.is_new = profile is None
        self.setWindowTitle("Yeni Müşteri Listesi Profili" if self.is_new else f"Müşteri Listesi Profilini Düzenle — {profile.name}")
        self.resize(760, 460)
        self._build_ui(profile)

    def _build_ui(self, profile: CustomerListProfile | None) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Müşteri listesi dosyanızda her bilgi için sütun başlığını yazın. "
            "Dosyanızda o bilgi birden fazla farklı isimle geçebiliyorsa (örn. "
            "hem 'Müşteri Kodu' hem 'Cari Kod'), virgülle ayırarak hepsini yazabilirsiniz — "
            "programınız dosyada bulduğu ilkini kullanır."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.meta = _ProfileMetaRow(
            profile.profile_id if profile else _slugify("yeni_musteri_listesi_profili"),
            profile.name if profile else "",
            profile.description if profile else "",
            id_editable=self.is_new,
        )
        layout.addWidget(self.meta)

        self.table = _PasteableTableWidget(len(self.FIELD_LABELS), 2)
        self.table.setHorizontalHeaderLabels(["Bilgi", "Sizin dosyanızdaki sütun başlığı/başlıkları (virgülle ayırın)"])
        existing_aliases = profile.aliases if profile else {}
        for row, (field, label) in enumerate(self.FIELD_LABELS.items()):
            label_item = QTableWidgetItem(label)
            label_item.setFlags(label_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, label_item)
            aliases_text = ", ".join(existing_aliases.get(field, ()))
            self.table.setItem(row, 1, QTableWidgetItem(aliases_text))
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        save_button = QPushButton("Kaydet")
        save_button.clicked.connect(self._save)
        cancel_button = QPushButton("Vazgeç")
        cancel_button.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

    def _save(self) -> None:
        profile_id = _slugify(self.meta.id_edit.text())
        name = self.meta.name_edit.text().strip() or profile_id
        description = self.meta.description_edit.text().strip()

        aliases: dict[str, list[str]] = {}
        for row, field in enumerate(self.FIELD_LABELS.keys()):
            item = self.table.item(row, 1)
            text = item.text().strip() if item else ""
            values = [part.strip() for part in text.split(",") if part.strip()]
            aliases[field] = values

        if not aliases.get("cari_kodu") or not aliases.get("unvan"):
            QMessageBox.warning(
                self,
                "Eksik bilgi",
                "Müşteri/Cari Kodu ve Ünvan için en az bir sütun adı girmelisiniz.",
            )
            return

        target_dir = self.config_dir / "customer_list_profiles"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{profile_id}.json"
        if self.is_new and target_path.exists():
            QMessageBox.warning(self, "Zaten var", f"'{profile_id}' kimlikli bir profil zaten var. Farklı bir kimlik seçin.")
            return

        target_path.write_text(
            json.dumps(
                {"id": profile_id, "name": name, "description": description, "aliases": aliases},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.saved_profile_id = profile_id
        self.accept()


class OutputProfileEditorDialog(QDialog):
    """Çıktı (muhasebe programı) profilini JSON'a dokunmadan düzenler.

    Her satır bir çıktı sütununu temsil eder: sütun başlığı, genişliği,
    kaynağı (her satırda hep aynı sabit değer mi, yoksa kayıttaki bir alan mı)
    ve görünüm biçimi. Sütun sayısı serbesttir (+ Satır Ekle / Satır Sil ile
    değişir) — böylece Netsis dışında farklı sayıda sütunlu bir program
    şablonu da tanımlanabilir.
    """

    FIELD_OPTIONS = ["islem_tarihi", "cari_kodu", "tutar", "aciklama", "banka", "bolge", "kaynak"]
    STYLE_OPTIONS = ["text", "date", "amount", "integer", "centered"]
    SOURCE_OPTIONS = ["Sabit değer", "Alan"]

    COL_HEADER = 0
    COL_WIDTH = 1
    COL_SOURCE = 2
    COL_VALUE = 3
    COL_STYLE = 4
    COL_FORCE_TEXT = 5

    def __init__(self, config_dir: Path, templates_dir: Path, profile: OutputProfile | None, parent=None):
        super().__init__(parent)
        self.config_dir = config_dir
        self.templates_dir = templates_dir
        self.is_new = profile is None
        self._selected_template_source: Path | None = None
        self._existing_template_file = profile.template_file if profile else ""
        self.setWindowTitle("Yeni Çıktı Profili" if self.is_new else f"Çıktı Profilini Düzenle — {profile.name}")
        self.resize(920, 560)
        self._build_ui(profile)

    def _build_ui(self, profile: OutputProfile | None) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Muhasebe programınızın beklediği Excel şablonundaki her sütunu bir "
            "satır olarak tanımlayın. 'Sabit değer' seçilen sütunlarda her "
            "satıra aynı değer yazılır (örn. banka kodu); 'Alan' seçilirse "
            "işlemdeki gerçek bilgi (tutar, tarih, açıklama, müşteri kodu vb.) yazılır."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.meta = _ProfileMetaRow(
            profile.profile_id if profile else _slugify("yeni_cikti_profili"),
            profile.name if profile else "",
            profile.description if profile else "",
            id_editable=self.is_new,
        )
        layout.addWidget(self.meta)

        template_row = QHBoxLayout()
        self.template_label = QLabel(
            f"Şablon dosyası: {self._existing_template_file or '(henüz seçilmedi)'}"
        )
        template_row.addWidget(self.template_label, 1)
        template_button = QPushButton("Şablon Excel dosyasını seç...")
        template_button.clicked.connect(self._choose_template)
        template_row.addWidget(template_button)
        layout.addLayout(template_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Sütun Başlığı", "Genişlik", "Kaynak", "Alan / Sabit Değer", "Biçim", "Metin Olarak Zorla"]
        )
        if profile:
            for column in profile.columns:
                self._append_row(column)
        else:
            self._append_row()
        layout.addWidget(self.table)

        row_buttons = QHBoxLayout()
        add_button = QPushButton("+ Sütun Ekle")
        add_button.clicked.connect(lambda: self._append_row())
        remove_button = QPushButton("Seçili Sütunu Sil")
        remove_button.clicked.connect(self._remove_selected_row)
        row_buttons.addWidget(add_button)
        row_buttons.addWidget(remove_button)
        layout.addLayout(row_buttons)

        buttons = QHBoxLayout()
        save_button = QPushButton("Kaydet")
        save_button.clicked.connect(self._save)
        cancel_button = QPushButton("Vazgeç")
        cancel_button.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

    def _append_row(self, column: OutputColumn | None = None) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, self.COL_HEADER, QTableWidgetItem(column.header if column else ""))
        self.table.setItem(row, self.COL_WIDTH, QTableWidgetItem(str(column.width if column else 15)))

        source_combo = QComboBox()
        source_combo.addItems(self.SOURCE_OPTIONS)
        source_combo.setCurrentIndex(1 if column and column.source_kind == "field" else 0)
        self.table.setCellWidget(row, self.COL_SOURCE, source_combo)

        value_text = ""
        if column:
            value_text = column.field if column.source_kind == "field" else ("" if column.value is None else str(column.value))
        self.table.setItem(row, self.COL_VALUE, QTableWidgetItem(value_text))

        style_combo = QComboBox()
        style_combo.addItems(self.STYLE_OPTIONS)
        style_combo.setCurrentText(column.style if column else "text")
        self.table.setCellWidget(row, self.COL_STYLE, style_combo)

        force_text_checkbox = QCheckBox()
        force_text_checkbox.setChecked(bool(column.force_text) if column else False)
        checkbox_holder = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_holder)
        checkbox_layout.addWidget(force_text_checkbox)
        checkbox_layout.setAlignment(force_text_checkbox, checkbox_layout.alignment())
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, self.COL_FORCE_TEXT, checkbox_holder)

    def _remove_selected_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _choose_template(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Şablon Excel dosyasını seç", "", "Excel dosyaları (*.xlsx *.xls)"
        )
        if path_str:
            self._selected_template_source = Path(path_str)
            self.template_label.setText(f"Şablon dosyası: {self._selected_template_source.name} (kaydedince kopyalanacak)")

    def _save(self) -> None:
        profile_id = _slugify(self.meta.id_edit.text())
        name = self.meta.name_edit.text().strip() or profile_id
        description = self.meta.description_edit.text().strip()

        if not self._selected_template_source and not self._existing_template_file:
            QMessageBox.warning(self, "Şablon eksik", "Lütfen bu profil için bir şablon Excel dosyası seçin.")
            return

        columns = []
        for row in range(self.table.rowCount()):
            header_item = self.table.item(row, self.COL_HEADER)
            header_text = header_item.text().strip() if header_item else ""
            if not header_text:
                QMessageBox.warning(self, "Eksik başlık", f"{row + 1}. satırın sütun başlığı boş olamaz.")
                return
            width_item = self.table.item(row, self.COL_WIDTH)
            try:
                width = int(width_item.text().strip()) if width_item and width_item.text().strip() else 15
            except ValueError:
                width = 15

            source_combo: QComboBox = self.table.cellWidget(row, self.COL_SOURCE)
            is_field = source_combo.currentIndex() == 1
            value_item = self.table.item(row, self.COL_VALUE)
            value_text = value_item.text().strip() if value_item else ""

            style_combo: QComboBox = self.table.cellWidget(row, self.COL_STYLE)
            style = style_combo.currentText()

            checkbox_holder = self.table.cellWidget(row, self.COL_FORCE_TEXT)
            force_text = False
            if checkbox_holder is not None:
                checkbox = checkbox_holder.findChild(QCheckBox)
                force_text = checkbox.isChecked() if checkbox else False

            if is_field:
                if value_text not in self.FIELD_OPTIONS:
                    QMessageBox.warning(
                        self,
                        "Geçersiz alan",
                        f"{row + 1}. satır: '{value_text}' tanınan bir alan değil. "
                        f"Geçerli alanlar: {', '.join(self.FIELD_OPTIONS)}",
                    )
                    return
                columns.append({
                    "header": header_text, "width": width, "style": style,
                    "source": "field", "field": value_text, "force_text": force_text,
                })
            else:
                const_value: object = None
                if value_text != "":
                    try:
                        const_value = int(value_text)
                    except ValueError:
                        const_value = value_text
                columns.append({
                    "header": header_text, "width": width, "style": style,
                    "source": "const", "value": const_value, "force_text": force_text,
                })

        target_dir = self.config_dir / "output_profiles"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{profile_id}.json"
        if self.is_new and target_path.exists():
            QMessageBox.warning(self, "Zaten var", f"'{profile_id}' kimlikli bir profil zaten var. Farklı bir kimlik seçin.")
            return

        template_file = self._existing_template_file
        if self._selected_template_source:
            self.templates_dir.mkdir(parents=True, exist_ok=True)
            template_file = f"{profile_id}_template{self._selected_template_source.suffix}"
            shutil.copy2(self._selected_template_source, self.templates_dir / template_file)

        target_path.write_text(
            json.dumps(
                {
                    "id": profile_id, "name": name, "description": description,
                    "template_file": template_file, "columns": columns,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.saved_profile_id = profile_id
        self.accept()
