"""Read-only MANİM plan presentation. Never writes templates or ERP records."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QTabWidget, QSizePolicy,
)

from app.core.operation_simulation import SimulationSummary

OUTCOMES = {
    "HAVALE": "Netsis havale", "MATCH": "Netsis havale", "MANUAL_HAVALE": "Netsis havale",
    "ODEME_ONAYLANDI": "Ödeme onaylandı", "REFERANSLI": "Referanslı",
    "SAME_BANK_VIRMAN": "Aynı banka virmanı", "VIRMAN": "Aynı banka virmanı",
    "KURAL_CALISTI": "Kural çalıştı", "REVIEW": "Kontrol bekliyor",
}


def money_text(value):
    return f"{value:,.2f} TL"


def read_only_table(headers):
    table = QTableWidget(0, len(headers))
    table.setObjectName("planTable")
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(42)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    return table


class SimulationDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.summary = None
        self._visible_buckets = []
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)
        hero = QFrame()
        hero.setObjectName("planHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        self.heading = QLabel("Aktarımın tamamını, tek bakışta görün")
        self.heading.setObjectName("planHeroTitle")
        self.heading.setWordWrap(True)
        self.subtitle = QLabel("Önce simülasyon çalıştırın. Bölge, banka ve çıktı dağılımları burada görünecek.")
        self.subtitle.setObjectName("planHeroSubtitle")
        self.subtitle.setWordWrap(True)
        hero_layout.addWidget(self.heading)
        hero_layout.addWidget(self.subtitle)
        root.addWidget(hero)
        self.metrics = {}
        cards = QGridLayout()
        cards.setSpacing(10)
        for index, (key, title, hint) in enumerate([
            ("incoming_total", "MANİM · Gelen", "Pozitif kaynak hareketleri"),
            ("outgoing_total", "MANİM · Giden", "Negatif hareketlerin mutlak toplamı"),
            ("netsis_total", "Netsis · Havale", "Hazırlanan havale satırlarının toplamı"),
            ("pending_total", "Bekleyen bakiye", "Havale kaynağının aktarılmayan bölümü"),
        ]):
            card = QFrame()
            card.setObjectName("planMetric")
            col = QVBoxLayout(card)
            col.setContentsMargins(14, 12, 14, 12)
            label = QLabel(title)
            label.setObjectName("cardSubtitle")
            value = QLabel("—")
            value.setObjectName("planMetricValue")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            note = QLabel(hint)
            note.setObjectName("cardSubtitle")
            note.setWordWrap(True)
            col.addWidget(label)
            col.addWidget(value)
            col.addWidget(note)
            self.metrics[key] = value
            cards.addWidget(card, index // 2, index % 2)
        root.addLayout(cards)
        self.notice = QLabel("Simülasyon Excel dosyası üretmez ve Netsis'e kayıt göndermez.")
        self.notice.setObjectName("planNotice")
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)
        tools = QHBoxLayout()
        self.region = QComboBox()
        self.region.addItem("Tüm bölgeler", "")
        self.region.setAccessibleName("Simülasyon bölge filtresi")
        self.bank = QComboBox()
        self.bank.addItem("Tüm bankalar", "")
        self.bank.setAccessibleName("Simülasyon banka filtresi")
        self.attention = QComboBox()
        self.attention.addItem("Tüm durumlar", False)
        self.attention.addItem("Kontrol bekleyenler", True)
        for control in (self.region, self.bank, self.attention):
            control.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            control.setMinimumContentsLength(8)
            control.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tools.addWidget(self.region, 1)
        tools.addWidget(self.bank, 1)
        tools.addWidget(self.attention, 1)
        root.addLayout(tools)
        self.table = read_only_table(["Bölge / Banka", "Gelen", "Giden", "Netsis havale", "Durum"])
        self.table.setMinimumHeight(190)
        self.table.setAccessibleName("Bölge ve banka bazında aktarım planı")
        root.addWidget(self.table, 1)
        bottom = QHBoxLayout()
        self.row_count = QLabel("Henüz simülasyon yok")
        self.row_count.setObjectName("cardSubtitle")
        self.row_count.setWordWrap(True)
        self.detail_button = QPushButton("Seçili bölge / banka ayrıntısı →")
        self.detail_button.setObjectName("secondary")
        self.detail_button.setEnabled(False)
        bottom.addWidget(self.row_count, 1)
        bottom.addWidget(self.detail_button)
        root.addLayout(bottom)
        self.detail_button.clicked.connect(self.show_selected_detail)
        self.table.cellDoubleClicked.connect(lambda _r, _c: self.show_selected_detail())
        self.table.itemSelectionChanged.connect(lambda: self.detail_button.setEnabled(self.table.currentRow() >= 0))
        for control in (self.region, self.bank, self.attention):
            control.currentIndexChanged.connect(self._render)

    def set_summary(self, summary: SimulationSummary | None, *, preview: bool = True):
        self.summary = summary
        for control, title, values in (
            (self.region, "Tüm bölgeler", sorted({b.region for b in summary.buckets}) if summary else []),
            (self.bank, "Tüm bankalar", sorted({b.bank for b in summary.buckets}) if summary else []),
        ):
            control.blockSignals(True)
            control.clear()
            control.addItem(title, "")
            for value in values:
                control.addItem(value, value)
            control.blockSignals(False)
        self.attention.setCurrentIndex(0)
        self.heading.setText("Aktarım öncesi · Simülasyon" if preview else "Aktarım sonrası · Hazırlanan çıktı planı")
        self.subtitle.setText(
            "Henüz çıktı üretilmedi. Tahmini dağılımı inceleyip aktarım adımına geçebilirsiniz."
            if preview else "Bu ekran hazırlanan dosyaları özetler; Netsis'e başarıyla alındığını doğrulamaz."
        )
        self._render()

    def _render(self):
        summary = self.summary
        buckets = [b for b in summary.buckets if
            (not self.region.currentData() or b.region == self.region.currentData()) and
            (not self.bank.currentData() or b.bank == self.bank.currentData()) and
            (not self.attention.currentData() or SimulationSummary((b,)).needs_attention)
        ] if summary else []
        self._visible_buckets = buckets
        filtered = SimulationSummary(tuple(buckets))
        for key, label in self.metrics.items():
            label.setText(money_text(filtered.total(key)) if summary else "—")
        review_count = sum(d.outcome == "REVIEW" for b in buckets for d in b.details)
        if summary:
            problem = filtered.needs_attention or bool(summary.ignored_records)
            self.notice.setText(
                f"{review_count} kaynak hareketi kontrol bekliyor. "
                f"Bekleyen bakiye: {money_text(filtered.total('pending_total'))}. "
                f"Dağılım kontrol farkı (mutlak): {money_text(sum(abs(b.unaccounted_total) for b in buckets))}. "
                + (f"{summary.ignored_records} kayıt özete alınamadı; kaynak kontrolü gerekli. " if summary.ignored_records else "")
                + "Ödeme onaylandı, referanslı ve virman ayrı çıktı gruplarıdır; tek başına hata değildir."
            )
            self.notice.setProperty("attention", problem)
            self.notice.style().unpolish(self.notice)
            self.notice.style().polish(self.notice)
        else:
            self.notice.setText("Simülasyon Excel dosyası üretmez ve Netsis'e kayıt göndermez.")
            self.notice.setProperty("attention", False)
            self.notice.style().unpolish(self.notice)
            self.notice.style().polish(self.notice)
        self.table.setRowCount(len(buckets))
        for row, bucket in enumerate(buckets):
            needs = SimulationSummary((bucket,)).needs_attention
            values = [f"{bucket.region} / {bucket.bank}", money_text(bucket.incoming_total),
                      money_text(bucket.outgoing_total), money_text(bucket.netsis_total),
                      "Kontrol bekliyor" if needs else "Dağılım dengeli"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if 1 <= col <= 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 4:
                    item.setForeground(QColor("#9B5A12" if needs else "#197452"))
                self.table.setItem(row, col, item)
        self.row_count.setText(f"{len(buckets)} bölge / banka · {sum(b.record_count for b in buckets):,} kaynak hareketi · Kartlar filtreye göre hesaplanır" if summary else "Henüz simülasyon yok")
        self.row_count.setWordWrap(True)
        self.detail_button.setEnabled(bool(buckets))
        if buckets:
            self.table.selectRow(0)

    def show_selected_detail(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._visible_buckets):
            return
        bucket = self._visible_buckets[row]
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{bucket.region} / {bucket.bank} · Dağılım ve kaynaklar")
        dialog.resize(980, 620)
        layout = QVBoxLayout(dialog)
        title = QLabel(f"{bucket.region} / {bucket.bank}")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        note = QLabel("Tutarlar kaynak hareketinin işaretini korur. Kaynak satır tutarı, kısmi veya birleşik işlemlerde cari dağılım tutarı değildir.")
        note.setWordWrap(True)
        layout.addWidget(note)
        tabs = QTabWidget()
        distribution = read_only_table(["Dağılım", "Tutar"])
        rows = [
            ("MANİM net hareket (gelen − giden)", bucket.manim_total),
            ("Netsis havale çıktısı", bucket.netsis_total),
            ("Ödeme onaylandı", bucket.payment_total), ("Referanslı", bucket.reference_total),
            ("Aynı banka virmanı", bucket.virman_total), ("Kural çalıştı", bucket.rule_total),
            ("İncelemede kalan hareketler", bucket.review_total),
            ("Bekleyen / aktarılmayan bakiye", bucket.pending_total),
            ("Açıklanamayan dağılım farkı", bucket.unaccounted_total),
        ]
        distribution.setRowCount(len(rows))
        for row, (name, amount) in enumerate(rows):
            distribution.setItem(row, 0, QTableWidgetItem(name))
            item = QTableWidgetItem(money_text(amount))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            distribution.setItem(row, 1, item)
        tabs.addTab(distribution, "Tutar dağılımı")
        sources = read_only_table(["Kaynak dosya", "Satır", "Kaynak tutar", "Son karar", "Kural"])
        sources.setRowCount(len(bucket.details))
        for row, detail in enumerate(bucket.details):
            for col, text in enumerate((detail.source_file, str(detail.source_row), money_text(detail.amount), OUTCOMES.get(detail.outcome, detail.outcome), detail.rule_code)):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                sources.setItem(row, col, item)
        tabs.addTab(sources, f"Kaynak hareketler ({len(bucket.details)})")
        layout.addWidget(tabs, 1)
        close = QPushButton("Kapat")
        close.setObjectName("secondary")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, 0, Qt.AlignRight)
        dialog.exec()
