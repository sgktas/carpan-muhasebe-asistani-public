from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.active_profile_store import ActiveProfileStore
from app.core.app_paths import APP_PATHS
from app.core.backup_service import BackupError, create_local_backup
from app.core.customer_list_profile import CustomerListProfileStore
from app.core.input_profile import InputProfileStore
from app.core.output_location import OutputLocationStore, resolve_output_dir
from app.core.output_profile import OutputProfileStore
from app.core.region_config import RegionConfigStore, active_region_config_path
from app.ui.common import add_page_header
from app.ui.profile_editor_dialogs import (
    CustomerListProfileEditorDialog,
    InputProfileEditorDialog,
    OutputProfileEditorDialog,
)
from app.ui.region_management_dialog import RegionManagementDialog


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_profiles = ActiveProfileStore(APP_PATHS.data_root)
        self._user_config_dir = APP_PATHS.data_root / "config"
        self._user_templates_dir = APP_PATHS.data_root / "templates"
        self._input_profile_store = InputProfileStore(APP_PATHS.config_dir, self._user_config_dir)
        self._output_profile_store = OutputProfileStore(APP_PATHS.config_dir, self._user_config_dir)
        self._customer_list_profile_store = CustomerListProfileStore(
            APP_PATHS.config_dir, self._user_config_dir
        )
        self._output_location_store = OutputLocationStore(APP_PATHS.data_root)
        self._region_store = RegionConfigStore(
            active_region_config_path(APP_PATHS.config_dir, APP_PATHS.data_root)
        )
        self._profile_row_widgets: list[QWidget] = []
        self._build_ui()

    # ------------------------------------------------------------------ #
    # Dosya konumları
    # ------------------------------------------------------------------ #
    def _path_row(self, title: str, value: str, callback) -> QFrame:
        frame = QFrame()
        frame.setObjectName("settingsRow")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(12)

        col = QVBoxLayout()
        col.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("miniInfoTitle")
        value_label = QLabel(value)
        value_label.setObjectName("miniInfoText")
        value_label.setWordWrap(True)
        col.addWidget(title_label)
        col.addWidget(value_label)
        layout.addLayout(col, 1)

        button = QPushButton("Klasörü aç")
        button.setObjectName("secondary")
        button.clicked.connect(callback)
        layout.addWidget(button)
        return frame

    @staticmethod
    def _open_directory(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _output_folder_row(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("settingsRow")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(8)

        title_label = QLabel("Çıktı klasörü")
        title_label.setObjectName("miniInfoTitle")
        layout.addWidget(title_label)

        self._output_value_label = QLabel(str(resolve_output_dir(APP_PATHS)))
        self._output_value_label.setObjectName("miniInfoText")
        self._output_value_label.setWordWrap(True)
        layout.addWidget(self._output_value_label)

        button_row = QHBoxLayout()
        open_button = QPushButton("Klasörü aç")
        open_button.setObjectName("secondary")
        open_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolve_output_dir(APP_PATHS))))
        )
        change_button = QPushButton("Klasörü değiştir...")
        change_button.setObjectName("secondary")
        change_button.clicked.connect(self._change_output_folder)
        reset_button = QPushButton("Varsayılana döndür")
        reset_button.setObjectName("secondary")
        reset_button.clicked.connect(self._reset_output_folder)
        button_row.addWidget(open_button)
        button_row.addWidget(change_button)
        button_row.addWidget(reset_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        return frame

    def _change_output_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Çıktıların kaydedileceği klasörü seçin", str(resolve_output_dir(APP_PATHS))
        )
        if not chosen:
            return
        self._output_location_store.set_override(chosen)
        self._output_value_label.setText(chosen)

    def _reset_output_folder(self) -> None:
        self._output_location_store.clear_override()
        self._output_value_label.setText(str(resolve_output_dir(APP_PATHS)))

    def _create_backup(self) -> None:
        default_name = f"carpan-muhasebe-yedek-{datetime.now():%Y%m%d-%H%M}.zip"
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            "Yerel veri yedeğini kaydet",
            str(Path.home() / "Documents" / default_name),
            "ZIP arşivi (*.zip)",
        )
        if not selected:
            return
        destination = Path(selected)
        if destination.suffix.casefold() != ".zip":
            destination = destination.with_suffix(".zip")
        try:
            created = create_local_backup(APP_PATHS.data_root, destination)
        except BackupError as error:
            QMessageBox.critical(self, "Yedek oluşturulamadı", str(error))
            return
        QMessageBox.information(
            self,
            "Yedek oluşturuldu",
            f"Yerel ayarlar, eşleştirme hafızası ve işlem geçmişi yedeklendi.\n\n{created}",
        )

    def _region_management_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("surfaceCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(10)

        title = QLabel("Bölge Yönetimi")
        title.setObjectName("cardTitle")
        subtitle = QLabel(
            "MANİM, Referanslı ve Ödeme Onaylandı çıktılarında kullanılacak bölgeleri, "
            "muhasebe kodlarını ve çıktı sırasını buradan yönetin."
        )
        subtitle.setObjectName("cardSubtitle")
        subtitle.setWordWrap(True)
        self._region_summary_label = QLabel()
        self._region_summary_label.setObjectName("miniInfoText")
        self._refresh_region_summary()

        button = QPushButton("Bölgeleri Yönet...")
        button.setObjectName("secondary")
        button.clicked.connect(self._open_region_management)

        row = QHBoxLayout()
        row.addWidget(self._region_summary_label, 1)
        row.addWidget(button)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(row)
        return card

    def _refresh_region_summary(self) -> None:
        regions = self._region_store.config().regions()
        self._region_summary_label.setText(
            f"{len(regions)} aktif bölge: " + ", ".join(regions)
        )

    def _open_region_management(self) -> None:
        RegionManagementDialog(self._region_store, self).exec()
        self._refresh_region_summary()

    # ------------------------------------------------------------------ #
    # Girdi / Çıktı / Müşteri listesi profilleri
    # ------------------------------------------------------------------ #
    def _profile_row(
        self,
        title: str,
        profiles: list,
        active_id: str,
        on_change,
        folder_path,
        kind: str,
    ) -> QFrame:
        frame = QFrame()
        frame.setObjectName("settingsRow")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(16, 13, 16, 13)
        outer.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        col = QVBoxLayout()
        col.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("miniInfoTitle")
        col.addWidget(title_label)

        combo = QComboBox()
        active_index = 0
        for index, profile in enumerate(profiles):
            combo.addItem(profile.name, profile.profile_id)
            if profile.profile_id == active_id:
                active_index = index
        if profiles:
            combo.setCurrentIndex(active_index)
        col.addWidget(combo)

        description_label = QLabel(profiles[active_index].description if profiles else "Henüz profil yok.")
        description_label.setObjectName("miniInfoText")
        description_label.setWordWrap(True)
        col.addWidget(description_label)
        top_row.addLayout(col, 1)

        button_col = QVBoxLayout()
        button_col.setSpacing(6)
        edit_button = QPushButton("Düzenle")
        edit_button.setObjectName("secondary")
        edit_button.setEnabled(bool(profiles))
        edit_button.clicked.connect(lambda: self._open_editor(kind, edit=True, combo=combo, profiles_ref=profiles))
        new_button = QPushButton("Yeni Profil Ekle")
        new_button.setObjectName("secondary")
        new_button.clicked.connect(lambda: self._open_editor(kind, edit=False, combo=combo, profiles_ref=profiles))
        open_folder_button = QPushButton("Profil klasörünü aç")
        open_folder_button.setObjectName("secondary")
        open_folder_button.clicked.connect(
            lambda: self._open_directory(Path(folder_path))
        )
        button_col.addWidget(edit_button)
        button_col.addWidget(new_button)
        button_col.addWidget(open_folder_button)
        top_row.addLayout(button_col)
        outer.addLayout(top_row)

        def _handle_change(index: int) -> None:
            if index < 0 or index >= len(profiles):
                return
            description_label.setText(profiles[index].description)
            protected = kind == "output" and bool(getattr(profiles[index], "protected", False))
            edit_button.setEnabled(not protected)
            edit_button.setText("Onaylı profil • Kilitli" if protected else "Düzenle")
            edit_button.setToolTip(
                "Onaylı Netsis profilleri değiştirilemez. Farklı bir şablon için yeni profil ekleyin."
                if protected else ""
            )
            on_change(combo.itemData(index))

        combo.currentIndexChanged.connect(_handle_change)
        _handle_change(active_index if profiles else -1)
        return frame

    def _open_editor(self, kind: str, edit: bool, combo: QComboBox, profiles_ref: list) -> None:
        selected_profile = None
        if edit:
            if not profiles_ref:
                return
            index = combo.currentIndex()
            selected_profile = profiles_ref[index] if 0 <= index < len(profiles_ref) else None
            if kind == "output" and bool(getattr(selected_profile, "protected", False)):
                QMessageBox.information(
                    self,
                    "Onaylı profil kilitli",
                    "Bu profil onaylı Netsis şablonuna bağlıdır ve değiştirilemez. "
                    "Farklı bir şablon için Yeni Profil Ekle'yi kullanın.",
                )
                return

        if kind == "input":
            dialog = InputProfileEditorDialog(self._user_config_dir, selected_profile, self)
        elif kind == "output":
            dialog = OutputProfileEditorDialog(
                self._user_config_dir, self._user_templates_dir, selected_profile, self
            )
        elif kind == "customer_list":
            dialog = CustomerListProfileEditorDialog(self._user_config_dir, selected_profile, self)
        else:
            return

        if dialog.exec():
            saved_id = getattr(dialog, "saved_profile_id", None)
            if saved_id:
                if kind == "input":
                    self._active_profiles.set_input_profile_id(saved_id)
                elif kind == "output":
                    self._active_profiles.set_output_profile_id(saved_id)
                elif kind == "customer_list":
                    self._active_profiles.set_customer_list_profile_id(saved_id)
            QMessageBox.information(self, "Kaydedildi", "Profil kaydedildi ve aktif profil olarak seçildi.")
            self._rebuild_profile_rows()

    def _rebuild_profile_rows(self) -> None:
        for widget in self._profile_row_widgets:
            self._profile_layout.removeWidget(widget)
            widget.deleteLater()
        self._profile_row_widgets.clear()

        input_profiles = self._input_profile_store.list_profiles()
        output_profiles = [
            profile for profile in self._output_profile_store.list_profiles()
            if profile.category == "havale"
        ]
        customer_list_profiles = self._customer_list_profile_store.list_profiles()

        rows = [
            self._profile_row(
                "Girdi profili (banka hareket raporu formatı)",
                input_profiles,
                self._active_profiles.get_input_profile_id(),
                self._active_profiles.set_input_profile_id,
                self._user_config_dir / "input_profiles",
                kind="input",
            ),
            self._profile_row(
                "Çıktı profili (muhasebe programı şablonu)",
                output_profiles,
                self._active_profiles.get_output_profile_id(),
                self._active_profiles.set_output_profile_id,
                self._user_config_dir / "output_profiles",
                kind="output",
            ),
            self._profile_row(
                "Müşteri listesi profili (cari/müşteri veritabanı dışa aktarımı)",
                customer_list_profiles,
                self._active_profiles.get_customer_list_profile_id(),
                self._active_profiles.set_customer_list_profile_id,
                self._user_config_dir / "customer_list_profiles",
                kind="customer_list",
            ),
        ]
        for row in rows:
            self._profile_layout.addWidget(row)
            self._profile_row_widgets.append(row)

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(scroll.horizontalScrollBarPolicy())

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(18)

        add_page_header(
            layout,
            "Ayarlar",
            "Uygulamanın kalıcı veri ve görünür çıktı konumlarını yönetin.",
        )

        card = QFrame()
        card.setObjectName("surfaceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(10)

        title = QLabel("Dosya konumları")
        title.setObjectName("cardTitle")
        subtitle = QLabel(
            "Çıktılar varsayılan olarak Belgeler altında görünür; isterseniz başka bir klasöre "
            "değiştirebilirsiniz. Uygulama veri klasörü ise eşleştirme hafızası ve işlem geçmişi "
            "gibi programın kendi kullandığı, normalde dokunmanız gerekmeyen dosyaları tutar — "
            "bir sorun yaşandığında destek için paylaşmanız istenebilir."
        )
        subtitle.setObjectName("cardSubtitle")
        subtitle.setWordWrap(True)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        card_layout.addWidget(self._output_folder_row())
        card_layout.addWidget(
            self._path_row(
                "Uygulama veri klasörü (eşleştirme hafızası, işlem geçmişi — normalde dokunmanız gerekmez)",
                str(APP_PATHS.data_root),
                lambda: QDesktopServices.openUrl(
                    QUrl.fromLocalFile(str(APP_PATHS.data_root))
                ),
            )
        )

        backup_row = QFrame()
        backup_row.setObjectName("settingsRow")
        backup_layout = QHBoxLayout(backup_row)
        backup_layout.setContentsMargins(16, 13, 16, 13)
        backup_text = QVBoxLayout()
        backup_title = QLabel("Yerel veri yedeği")
        backup_title.setObjectName("miniInfoTitle")
        backup_description = QLabel(
            "Eşleştirme hafızasını, işlem geçmişini, bölge ayarlarını ve kullanıcı profillerini "
            "tek bir ZIP dosyasında saklar. Çıktı Excel dosyaları ve günlükler yedeğe alınmaz."
        )
        backup_description.setObjectName("miniInfoText")
        backup_description.setWordWrap(True)
        backup_text.addWidget(backup_title)
        backup_text.addWidget(backup_description)
        backup_button = QPushButton("Yedek oluştur...")
        backup_button.setObjectName("secondary")
        backup_button.clicked.connect(self._create_backup)
        backup_layout.addLayout(backup_text, 1)
        backup_layout.addWidget(backup_button)
        card_layout.addWidget(backup_row)
        layout.addWidget(card)

        layout.addWidget(self._region_management_card())

        profile_card = QFrame()
        profile_card.setObjectName("surfaceCard")
        self._profile_layout = QVBoxLayout(profile_card)
        self._profile_layout.setContentsMargins(20, 18, 20, 20)
        self._profile_layout.setSpacing(10)

        profile_title = QLabel("Girdi / Çıktı Profilleri")
        profile_title.setObjectName("cardTitle")
        profile_subtitle = QLabel(
            "Banka raporu formatı, muhasebe programı şablonu ve müşteri listesi formatı burada "
            "seçilir ve düzenlenir. 'Düzenle' ile mevcut bir profili değiştirebilir, 'Yeni Profil "
            "Ekle' ile sıfırdan bir tane oluşturabilirsiniz — JSON dosyası ile uğraşmanıza gerek "
            "yok. Seçim hemen etkili olur, yeniden başlatmaya gerek yok."
        )
        profile_subtitle.setObjectName("cardSubtitle")
        profile_subtitle.setWordWrap(True)
        self._profile_layout.addWidget(profile_title)
        self._profile_layout.addWidget(profile_subtitle)

        layout.addWidget(profile_card)
        layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

        self._rebuild_profile_rows()
