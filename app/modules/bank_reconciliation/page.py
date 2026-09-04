from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.app_paths import APP_PATHS
from app.core.bank_statement_metadata import find_bank_logo_path
from app.core.bank_statement_parser import BankStatementParser
from app.core.bank_statement_profile import BankStatementProfileStore
from app.core.excel_header_finder import extract_letterhead_text, find_header_row, read_excel_raw
from app.core.netsis_report_parser import NetsisReportParser
from app.core.netsis_report_profile import NetsisReportProfileStore
from app.core.operation_history import OperationHistory
from app.core.output_location import resolve_output_dir
from app.core.reconciliation_engine import ReconciliationEngine, ReconciliationResult
from app.core.region_config import RegionConfig, active_region_config_path
from app.ui.common import add_page_header
from app.ui.theme import asset_icon, crisp_pixmap
from app.writers.reconciliation_writer import ReconciliationReportWriter

MODULE_ID = "bank_reconciliation"
MODULE_NAME = "Banka Mutabakatı"


def _classify_reconciliation_file(path: Path) -> str | None:
    """Sürüklenen/seçilen dosyanın banka ekstresi mi yoksa Netsis raporu mu
    olduğunu, gerçek başlık satırındaki sütun adlarına bakarak otomatik
    anlar (MANİM Aktarma modülündeki dosya sınıflandırmasıyla aynı mantık).
    """
    try:
        raw = read_excel_raw(path)
    except Exception:
        return None

    netsis_profile = NetsisReportProfileStore(APP_PATHS.config_dir).get_or_default(None)
    if find_header_row(raw, set(netsis_profile.columns.keys())) is not None:
        return "netsis"

    bank_profile = BankStatementProfileStore(APP_PATHS.config_dir).get_or_default(None)
    if find_header_row(raw, set(bank_profile.columns.keys())) is not None:
        return "bank"

    return None


def _detect_region(bank_path: Path, netsis_path: Path) -> str | None:
    """Aktif bölgelerden hangisine ait olduğunu, her iki dosyanın da antet
    bloğundan (banka hesap kodu, müşteri şube etiketi vb.) otomatik anlar.

    ÖNEMLİ: iki dosyanın antet metinleri BİRLEŞTİRİLİP tek seferde aranır.
    Aksi halde banka ekstresindeki 'Şube' alanı (bankanın hizmet verdiği
    fiziksel şube, örn. 'ANTALYA TİCARİ') şirketin gerçek bölgesinden önce
    yanlışlıkla eşleşebilir — oysa Netsis'teki kesin banka hesap kodu
    (örn. 'BANK-G-01') doğru bölgeyi gösterir. Kodlar isimlerden önce
    arandığı için, iki metni birleştirmek doğru önceliği garantiler.
    """
    region_config = RegionConfig(
        active_region_config_path(APP_PATHS.config_dir, APP_PATHS.data_root)
    )

    combined_parts: list[str] = []
    for path, profile_store, get_profile in (
        (bank_path, BankStatementProfileStore(APP_PATHS.config_dir), lambda s: s.get_or_default(None)),
        (netsis_path, NetsisReportProfileStore(APP_PATHS.config_dir), lambda s: s.get_or_default(None)),
    ):
        try:
            raw = read_excel_raw(path)
            profile = get_profile(profile_store)
            header_row = find_header_row(raw, set(profile.columns.keys()))
            combined_parts.append(extract_letterhead_text(path, header_row))
        except Exception:
            continue

    return region_config.find_region_in_text(" ".join(combined_parts))


class BankReconciliationPage(QWidget):
    """Modül 03: banka ekstresi ile Netsis ay sonu raporunu karşılaştırıp
    ay sonu bakiyesinin tutup tutmadığını, tutmuyorsa hangi işlemlerin
    uyuşmadığını bulur.
    """

    def __init__(self, history: OperationHistory, parent=None):
        super().__init__(parent)
        self.history = history
        self.bank_file: Path | None = None
        self.netsis_file: Path | None = None
        self.last_output_path: Path | None = None
        self.setAcceptDrops(True)
        self._build_ui()

    # ------------------------------------------------------------------ #
    # Genel iskelet
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(34, 30, 34, 0)
        add_page_header(
            header_layout,
            MODULE_NAME,
            "Banka ekstresi ile Netsis'ten aldığınız ay sonu raporunu karşılaştırır; "
            "ay sonu bakiyesi tutmuyorsa hangi işlemlerin eksik/fazla olduğunu bulur.",
            badge_text="MODÜL 03",
        )
        root.addWidget(header_container)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_run_tab(), "Mutabakat Yap")
        self.tabs.addTab(self._build_log_tab(), "Geçmiş Mutabakatlar")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs)

    def _on_tab_changed(self, index: int) -> None:
        if self.tabs.tabText(index) == "Geçmiş Mutabakatlar":
            self._refresh_log_tab()

    # ------------------------------------------------------------------ #
    # Sekme 1: Mutabakat Yap
    # ------------------------------------------------------------------ #
    def _build_run_tab(self) -> QWidget:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 20, 34, 30)
        layout.setSpacing(18)

        # --- Girdi dosyaları: surukle-birak alani ---
        upload_card = QFrame()
        upload_card.setObjectName("surfaceCard")
        upload_layout = QVBoxLayout(upload_card)
        upload_layout.setContentsMargins(22, 20, 22, 20)
        upload_layout.setSpacing(14)

        upload_header = QHBoxLayout()
        upload_header.setSpacing(12)
        upload_header_col = QVBoxLayout()
        upload_header_col.setSpacing(3)
        upload_title = QLabel("Girdi dosyaları")
        upload_title.setObjectName("cardTitle")
        upload_subtitle = QLabel("Banka ekstresi + Netsis ay sonu raporu (ikisini birden sürükleyebilirsiniz)")
        upload_subtitle.setObjectName("cardSubtitle")
        upload_header_col.addWidget(upload_title)
        upload_header_col.addWidget(upload_subtitle)
        upload_header.addLayout(upload_header_col, 1)

        self.file_status = QLabel("Dosya bekleniyor")
        self.file_status.setObjectName("statusPill")
        self.file_status.setProperty("ready", "false")
        upload_header.addWidget(self.file_status, 0, Qt.AlignTop)
        upload_layout.addLayout(upload_header)

        self.drop_frame = QFrame()
        self.drop_frame.setObjectName("dropArea")
        self.drop_frame.setProperty("hasFiles", "false")
        self.drop_frame.setMinimumHeight(150)
        self.drop_frame.setMaximumHeight(200)
        drop_layout = QVBoxLayout(self.drop_frame)
        drop_layout.setContentsMargins(18, 16, 18, 16)
        drop_layout.setSpacing(8)

        self.drop_hint_container = QWidget()
        hint_layout = QVBoxLayout(self.drop_hint_container)
        hint_layout.setContentsMargins(0, 0, 0, 0)
        hint_layout.setSpacing(7)
        hint_layout.setAlignment(Qt.AlignCenter)

        upload_icon = QLabel()
        upload_icon_path = APP_PATHS.assets_dir / "icons" / "upload-default.png"
        if upload_icon_path.is_file():
            upload_icon.setPixmap(crisp_pixmap(self, upload_icon_path, 34))
        upload_icon.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(upload_icon)

        drop_title = QLabel("Excel dosyalarını buraya sürükleyin")
        drop_title.setObjectName("dropTitle")
        drop_title.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(drop_title)

        drop_detail = QLabel("Banka ekstresi ve Netsis raporu otomatik tanınır")
        drop_detail.setObjectName("dropDetail")
        drop_detail.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(drop_detail)
        drop_layout.addWidget(self.drop_hint_container, 1)

        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setVisible(False)
        self.file_list.setMaximumHeight(150)
        drop_layout.addWidget(self.file_list, 1)
        upload_layout.addWidget(self.drop_frame)

        file_actions = QHBoxLayout()
        file_actions.setSpacing(8)
        self.loaded_files_label = QLabel("Henüz dosya seçilmedi")
        self.loaded_files_label.setObjectName("cardSubtitle")
        file_actions.addWidget(self.loaded_files_label, 1)

        self.clear_button = QPushButton("Temizle")
        self.clear_button.setObjectName("ghost")
        self.clear_button.setIcon(asset_icon(APP_PATHS.assets_dir, "trash"))
        self.clear_button.setIconSize(QSize(15, 15))
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self._clear_files)
        file_actions.addWidget(self.clear_button)

        self.select_button = QPushButton("Dosya seç")
        self.select_button.setObjectName("secondary")
        self.select_button.setIcon(asset_icon(APP_PATHS.assets_dir, "folder"))
        self.select_button.setIconSize(QSize(16, 16))
        self.select_button.clicked.connect(self._select_files)
        file_actions.addWidget(self.select_button)
        upload_layout.addLayout(file_actions)
        layout.addWidget(upload_card)

        # --- Mutabakat Yap butonu ---
        self.run_button = QPushButton("Mutabakat Yap")
        self.run_button.setObjectName("primary")
        self.run_button.setMinimumHeight(42)
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self._run_reconciliation)
        layout.addWidget(self.run_button)

        # --- İşlem günlüğü ---
        log_card = QFrame()
        log_card.setObjectName("surfaceCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 18, 20, 20)
        log_layout.setSpacing(10)

        log_header_col = QVBoxLayout()
        log_header_col.setSpacing(3)
        log_title = QLabel("İşlem günlüğü")
        log_title.setObjectName("cardTitle")
        log_subtitle = QLabel("Mutabakat sonucu ve doğrulamalar")
        log_subtitle.setObjectName("cardSubtitle")
        log_header_col.addWidget(log_title)
        log_header_col.addWidget(log_subtitle)
        log_layout.addLayout(log_header_col)

        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Mutabakat sonucu burada görüntülenecek.")
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log.setMinimumHeight(120)
        self.log.setMaximumHeight(220)
        log_layout.addWidget(self.log)
        layout.addWidget(log_card)

        # --- Zengin sonuc karti (logo + istatistikler) ---
        self.result_card_container = QVBoxLayout()
        layout.addLayout(self.result_card_container)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    # ------------------------------------------------------------------ #
    # Dosya yukleme: surukle-birak + otomatik siniflandirma
    # ------------------------------------------------------------------ #
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(
            Path(url.toLocalFile()).suffix.lower() in {".xlsx", ".xls"}
            for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        files = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if Path(url.toLocalFile()).suffix.lower() in {".xlsx", ".xls"}
        ]
        if files:
            self._load_files(files)
            event.acceptProposedAction()

    def _select_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Banka ekstresi ve Netsis raporu dosyalarını seçin",
            str(Path.home()),
            "Excel dosyaları (*.xlsx *.xls)",
        )
        if selected:
            self._load_files([Path(path) for path in selected])

    def _load_files(self, files: list[Path]) -> None:
        unrecognized: list[Path] = []
        for path in files:
            kind = _classify_reconciliation_file(path)
            if kind == "bank":
                self.bank_file = path
            elif kind == "netsis":
                self.netsis_file = path
            else:
                unrecognized.append(path)

        self._refresh_file_list()
        self.run_button.setEnabled(self.bank_file is not None and self.netsis_file is not None)

        if unrecognized:
            names = ", ".join(p.name for p in unrecognized)
            QMessageBox.warning(
                self,
                "Dosya tanınamadı",
                f"Şu dosya(lar) banka ekstresi ya da Netsis raporu olarak tanınamadı:\n\n{names}\n\n"
                "Sütun başlıklarını kontrol edin ya da Ayarlar ekranından profil ekleyin.",
            )

    def _refresh_file_list(self) -> None:
        self.file_list.clear()
        items = []
        if self.bank_file:
            items.append(f"🏦 Banka Ekstresi: {self.bank_file.name}")
        if self.netsis_file:
            items.append(f"🧾 Netsis Raporu: {self.netsis_file.name}")

        has_files = bool(items)
        self.drop_hint_container.setVisible(not has_files)
        self.file_list.setVisible(has_files)
        self.file_list.addItems(items)
        self.drop_frame.setProperty("hasFiles", "true" if has_files else "false")
        self.drop_frame.style().unpolish(self.drop_frame)
        self.drop_frame.style().polish(self.drop_frame)

        self.clear_button.setEnabled(has_files)
        if self.bank_file and self.netsis_file:
            self.loaded_files_label.setText("İki dosya da hazır — Mutabakat Yap'a basabilirsiniz")
            self.file_status.setProperty("ready", "true")
        elif has_files:
            eksik = "Netsis raporu" if self.bank_file else "banka ekstresi"
            self.loaded_files_label.setText(f"1 dosya yüklendi, eksik: {eksik}")
            self.file_status.setProperty("ready", "false")
        else:
            self.loaded_files_label.setText("Henüz dosya seçilmedi")
            self.file_status.setProperty("ready", "false")
        self.file_status.setText("Hazır" if (self.bank_file and self.netsis_file) else "Dosya bekleniyor")
        self.file_status.style().unpolish(self.file_status)
        self.file_status.style().polish(self.file_status)

    def _clear_files(self) -> None:
        self.bank_file = None
        self.netsis_file = None
        self.run_button.setEnabled(False)
        self._refresh_file_list()
        self.log.clear()
        self._clear_result_card()

    # ------------------------------------------------------------------ #
    # Mutabakat calistirma
    # ------------------------------------------------------------------ #
    def _run_reconciliation(self) -> None:
        self.log.clear()
        self.log.append("Mutabakat işlemi başlatıldı...")
        operation_id = self.history.start(MODULE_ID, MODULE_NAME, [self.bank_file, self.netsis_file])
        try:
            bank_parser = BankStatementParser(self.bank_file)
            bank_records = bank_parser.load()
            metadata = bank_parser.load_metadata()
            self.log.append(f"Banka ekstresi okundu: {len(bank_records)} işlem ({metadata.banka_adi or 'banka adı okunamadı'})")

            netsis_records = NetsisReportParser(self.netsis_file).load()
            self.log.append(f"Netsis raporu okundu: {len(netsis_records)} işlem")

            bolge = _detect_region(self.bank_file, self.netsis_file)
            self.log.append(f"Bölge: {bolge or 'tanınamadı'}")

            result = ReconciliationEngine().reconcile(bank_records, netsis_records)
            self.log.append(f"Eşleşen işlem sayısı: {result.eslesen_sayisi}")
            self.log.append(f"Bölünmüş fiş olarak tanınan grup sayısı: {result.bolunmus_grup_sayisi}")
            self.log.append(f"Sadece bankada: {len(result.sadece_bankada)} | Sadece Netsis'te: {len(result.sadece_netposte)}")

            output_dir = resolve_output_dir(APP_PATHS) / "Banka Mutabakati"
            timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
            output_path = output_dir / f"Mutabakat_Raporu_{timestamp}.xlsx"
            ReconciliationReportWriter().write(result, output_path)
            self.last_output_path = output_path
            self.log.append(f"Rapor kaydedildi: {output_path}")

            toplam_alinan = sum(r.tutar for r in bank_records if r.tutar > 0)
            toplam_gonderilen = sum(-r.tutar for r in bank_records if r.tutar < 0)
            kalan_sayisi = len(result.sadece_bankada) + len(result.sadece_netposte)
            durum = (
                "TAM MUTABIK" if (result.mutabik and kalan_sayisi == 0)
                else "BAKİYE TUTUYOR AMA AÇIKLANAMAYAN KAYIT VAR" if result.mutabik
                else "MUTABIK DEĞİL"
            )
            self.log.append(f"Durum: {durum}")

            devir_bakiyesi = None
            if bank_records:
                _, first_record = min(
                    enumerate(bank_records),
                    key=lambda item: (item[1].tarih or datetime.max, item[0]),
                )
                if first_record.bakiye is not None:
                    devir_bakiyesi = round(first_record.bakiye - first_record.tutar, 2)
            self.log.append(
                f"Önceki aydan devreden bakiye: {devir_bakiyesi:,.2f} TL" if devir_bakiyesi is not None
                else "Önceki aydan devreden bakiye bulunamadı"
            )
            self.log.append(f"Yeni aya devredecek bakiye: {result.banka_bakiyesi:,.2f} TL" if result.banka_bakiyesi is not None else "-")

            en_buyuk_hareketler = sorted(bank_records, key=lambda r: abs(r.tutar), reverse=True)[:3]
            en_buyuk_hareketler_veri = [
                {
                    "tarih": r.tarih.strftime("%d.%m.%Y") if r.tarih else "-",
                    "tutar": r.tutar,
                    "aciklama": r.aciklama,
                }
                for r in en_buyuk_hareketler
            ]
            if en_buyuk_hareketler_veri:
                self.log.append("Bu dönemin en büyük hareketleri (giren/çıkan farkını en çok etkileyenler):")
                for hareket in en_buyuk_hareketler_veri:
                    self.log.append(f"  {hareket['tarih']} | {hareket['tutar']:,.2f} TL | {hareket['aciklama']}")

            summary = {
                "bolge": bolge,
                "banka_adi": metadata.banka_adi,
                "sirket_unvani": metadata.sirket_unvani,
                "sube": metadata.sube,
                "iban": metadata.iban,
                "donem_baslangic": metadata.donem_baslangic,
                "donem_bitis": metadata.donem_bitis,
                "islem_sayisi": len(bank_records),
                "toplam_alinan_tutar": toplam_alinan,
                "toplam_gonderilen_tutar": toplam_gonderilen,
                "devir_bakiyesi": devir_bakiyesi,
                "banka_bakiyesi": result.banka_bakiyesi,
                "netsis_bakiyesi": result.netsis_bakiyesi,
                "fark": result.fark,
                "eslesen_sayisi": result.eslesen_sayisi,
                "bolunmus_grup_sayisi": result.bolunmus_grup_sayisi,
                "sadece_bankada": len(result.sadece_bankada),
                "sadece_netposte": len(result.sadece_netposte),
                "mutabik": result.mutabik,
                "durum": durum,
                "en_buyuk_hareketler": en_buyuk_hareketler_veri,
            }
            self.history.complete(operation_id, [output_path], summary=summary)

            self._show_result_card(summary, str(output_path), datetime.now().strftime("%d.%m.%Y %H:%M"))
            self._refresh_log_tab()
        except Exception as error:
            self.history.fail(operation_id, str(error))
            self.log.append(f"HATA: {error}")
            QMessageBox.critical(self, "Hata", f"Mutabakat sırasında bir sorun oluştu:\n\n{error}")

    def _clear_result_card(self) -> None:
        while self.result_card_container.count():
            item = self.result_card_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _show_result_card(self, summary: dict, output_path: str, tarih_text: str) -> None:
        self._clear_result_card()
        self.result_card_container.addWidget(_build_summary_card(summary, output_path, tarih_text))

    # ------------------------------------------------------------------ #
    # Sekme 2: Geçmiş Mutabakatlar (log ekranı)
    # ------------------------------------------------------------------ #
    def _build_log_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        self._log_layout = QVBoxLayout(content)
        self._log_layout.setContentsMargins(34, 20, 34, 30)
        self._log_layout.setSpacing(14)
        self._log_layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        return page

    def _refresh_log_tab(self) -> None:
        while self._log_layout.count() > 1:
            item = self._log_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        records = [r for r in self.history.recent(200) if r.module_id == MODULE_ID and r.status == "SUCCESS"]
        if not records:
            empty_label = QLabel("Henüz kaydedilmiş bir mutabakat işlemi yok.")
            empty_label.setStyleSheet("color: #5b6472;")
            self._log_layout.insertWidget(0, empty_label)
            return

        for record in records:
            output_path = record.output_files[0] if record.output_files else None
            tarih_text = record.completed_at or record.started_at
            card = _build_summary_card(record.summary or {}, output_path, tarih_text)
            self._log_layout.insertWidget(self._log_layout.count() - 1, card)


# ---------------------------------------------------------------------- #
# Paylaşılan kurumsal özet kartı (hem anlık sonuç hem geçmiş sekmesi kullanır)
# ---------------------------------------------------------------------- #
def _build_summary_card(summary: dict, output_path: str | None, tarih_text: str) -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(22, 18, 22, 18)
    layout.setSpacing(10)

    header_row = QHBoxLayout()
    header_row.setSpacing(12)

    banka_adi = summary.get("banka_adi") or "Banka adı okunamadı"
    logo_path = find_bank_logo_path(summary.get("banka_adi"), APP_PATHS.assets_dir)
    if logo_path:
        logo_label = QLabel()
        pixmap = QPixmap(str(logo_path))
        logo_label.setPixmap(pixmap.scaled(QSize(40, 40), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header_row.addWidget(logo_label)

    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    bolge = summary.get("bolge")
    baslik_metni = f"{bolge} — {banka_adi}" if bolge else f"{banka_adi} (bölge tanınamadı)"
    title_label = QLabel(baslik_metni)
    title_label.setStyleSheet("font-size: 15px; font-weight: 700;")
    title_col.addWidget(title_label)

    alt_bilgi_parcalari = []
    if summary.get("sirket_unvani"):
        alt_bilgi_parcalari.append(summary["sirket_unvani"])
    if summary.get("sube"):
        alt_bilgi_parcalari.append(f"Şube: {summary['sube']}")
    if summary.get("donem_baslangic") and summary.get("donem_bitis"):
        alt_bilgi_parcalari.append(f"Dönem: {summary['donem_baslangic']} – {summary['donem_bitis']}")
    if alt_bilgi_parcalari:
        subtitle_label = QLabel(" · ".join(alt_bilgi_parcalari))
        subtitle_label.setStyleSheet("color: #5b6472; font-size: 12px;")
        title_col.addWidget(subtitle_label)
    header_row.addLayout(title_col, 1)

    durum = summary.get("durum", "-")
    durum_renk = "#1a7a3c" if durum == "TAM MUTABIK" else "#b3261e"
    durum_label = QLabel(durum)
    durum_label.setStyleSheet(
        f"background-color: {durum_renk}; color: white; font-weight: 700; "
        "padding: 4px 10px; border-radius: 10px; font-size: 11px;"
    )
    header_row.addWidget(durum_label, 0, Qt.AlignTop)
    layout.addLayout(header_row)

    grid = QGridLayout()
    grid.setHorizontalSpacing(28)
    grid.setVerticalSpacing(4)

    def fmt(value):
        return f"{value:,.2f} TL" if isinstance(value, (int, float)) else "-"

    stats = [
        ("Toplam Alınan Tutar", fmt(summary.get("toplam_alinan_tutar"))),
        ("Toplam Gönderilen Tutar", fmt(summary.get("toplam_gonderilen_tutar"))),
        ("İşlem Sayısı", str(summary.get("islem_sayisi", "-"))),
        ("Devreden Bakiye (önceki ay)", fmt(summary.get("devir_bakiyesi"))),
        ("Yeni Aya Devredecek Bakiye", fmt(summary.get("banka_bakiyesi"))),
        ("Netsis Bakiyesi", fmt(summary.get("netsis_bakiyesi"))),
        ("Fark", fmt(summary.get("fark"))),
        ("Eşleşen İşlem", str(summary.get("eslesen_sayisi", "-"))),
        ("Bölünmüş Fiş Grubu", str(summary.get("bolunmus_grup_sayisi", "-"))),
        ("Açıklanamayan Kayıt", str(summary.get("sadece_bankada", 0) + summary.get("sadece_netposte", 0))),
    ]
    for index, (label, value) in enumerate(stats):
        row, col = divmod(index, 3)
        cell = QVBoxLayout()
        label_widget = QLabel(label)
        label_widget.setStyleSheet("color: #8a93a1; font-size: 11px;")
        value_widget = QLabel(value)
        value_widget.setStyleSheet("font-weight: 600; font-size: 13px;")
        cell.addWidget(label_widget)
        cell.addWidget(value_widget)
        grid.addLayout(cell, row, col)
    layout.addLayout(grid)

    en_buyuk_hareketler = summary.get("en_buyuk_hareketler") or []
    if en_buyuk_hareketler:
        buyuk_title = QLabel("Bu dönemin en büyük hareketleri")
        buyuk_title.setStyleSheet("color: #8a93a1; font-size: 11px; margin-top: 4px;")
        layout.addWidget(buyuk_title)
        for hareket in en_buyuk_hareketler:
            satir = QLabel(f"{hareket.get('tarih', '-')} · {fmt(hareket.get('tutar'))} · {hareket.get('aciklama', '')}")
            satir.setStyleSheet("font-size: 12px; color: #333;")
            satir.setWordWrap(True)
            layout.addWidget(satir)

    tarih_label = QLabel(f"İşlem tarihi: {tarih_text}")
    tarih_label.setStyleSheet("color: #8a93a1; font-size: 11px;")
    layout.addWidget(tarih_label)

    if output_path:
        open_button = QPushButton("Raporu Aç")
        open_button.clicked.connect(
            lambda checked=False, path=output_path: QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        )
        layout.addWidget(open_button, 0, Qt.AlignLeft)

    return card
