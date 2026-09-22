"""Current-run and historical output inspection within the product shell."""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app.core.operation_simulation import simulation_summary_from_payload
from app.ui.accounting_view import money_text
from app.ui.operation_breakdown import CATEGORIES, regional_breakdown


def amount(value):
    return money_text(value).replace(' TL', ' ₺')


def output_table(headers):
    table = QTableWidget(0, len(headers))
    table.setObjectName('operationBreakdownTable')
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(30)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    return table


class AccountingOutputsPage(QWidget):
    settings_requested = Signal()
    history_requested = Signal()

    def __init__(self, workspace, history, *, allow_history=True, parent=None):
        super().__init__(parent)
        self.workspace, self.history = workspace, history
        self.allow_history = allow_history
        self._operations = {}
        self._files = ()
        self.setObjectName('accountingOutputsPage')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        top = QHBoxLayout()
        title = QLabel('Çıktılar ve işlem sonuçları')
        title.setObjectName('automationPageTitle')
        top.addWidget(title, 1)
        for text, signal in (('Çıktı ayarları', self.settings_requested), ('Geçmiş & Audit', self.history_requested)):
            button = QPushButton(text)
            button.setObjectName('secondary')
            button.clicked.connect(signal.emit)
            button.setVisible(text != 'Geçmiş & Audit' or allow_history)
            top.addWidget(button)
        layout.addLayout(top)
        self.operation = QComboBox()
        self.operation.setObjectName('operationSelector')
        self.operation.currentIndexChanged.connect(self.render)
        layout.addWidget(self.operation)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setObjectName('cardSubtitle')
        layout.addWidget(self.note)
        self.regions = output_table(['Bölge', *[label for _, label in CATEGORIES], 'Kaynak net', 'Dağıtılan net', 'Fark'])
        self.regions.horizontalHeader().setStretchLastSection(False)
        self.regions.horizontalHeader().setMinimumSectionSize(105)
        self.regions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.regions, 2)
        self.net_note = QLabel()
        self.net_note.setWordWrap(True)
        self.net_note.setObjectName('cardSubtitle')
        layout.addWidget(self.net_note)
        file_heading = QHBoxLayout()
        file_heading.addWidget(QLabel('Üretilen çıktı dosyaları'), 1)
        self.open_file = QPushButton('Dosyayı aç')
        self.open_folder = QPushButton('Klasörünü aç')
        self.open_file.setObjectName('secondary')
        self.open_folder.setObjectName('primary')
        self.open_file.clicked.connect(lambda: self.open_selected(False))
        self.open_folder.clicked.connect(lambda: self.open_selected(True))
        file_heading.addWidget(self.open_file)
        file_heading.addWidget(self.open_folder)
        layout.addLayout(file_heading)
        self.files = output_table(['Dosya', 'Durum', 'Konum'])
        self.files.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.files.itemSelectionChanged.connect(self.update_actions)
        layout.addWidget(self.files, 1)
        self.refresh()

    def refresh(self):
        selected = self.operation.currentData()
        self.operation.blockSignals(True)
        self.operation.clear()
        self.operation.addItem('Mevcut çalışma', None)
        self._operations = {}
        if self.allow_history:
            company = getattr(self.history, 'company_id', None)
            for record in self.history.recent(None):
                if record.company_id != company or record.module_id not in {'manim_transfer', 'report_editing'}:
                    continue
                self._operations[record.id] = record
                try:
                    date = datetime.fromisoformat(record.started_at.replace('Z', '+00:00')).astimezone().strftime('%d.%m.%Y %H:%M')
                except (ValueError, TypeError):
                    date = record.started_at
                state = {'SUCCESS': 'Başarılı', 'PARTIAL': 'Kısmi', 'FAILED': 'Hatalı', 'RUNNING': 'Devam ediyor', 'INTERRUPTED': 'Yarım kaldı'}.get(record.status, record.status)
                self.operation.addItem(f'{date} · {record.module_name} · {state}', record.id)
        self.operation.setCurrentIndex(max(0, self.operation.findData(selected)))
        self.operation.blockSignals(False)
        self.render()

    def render(self):
        record = self._operations.get(self.operation.currentData())
        if record is None:
            summary = self.workspace.summary
            evidence = None
            self._files = self.workspace._last_created_files if self.workspace._output_done else ()
            self.note.setText('Mevcut çalışma · ' + ('Çıktılar üretildi; ERP kabulü ayrıca doğrulanır.' if self.workspace._output_done else 'Önizleme / hazırlık · Henüz çıktı üretilmedi.'))
        else:
            summary = simulation_summary_from_payload(record.summary.get('operation_result'))
            evidence = record.summary.get('operation_presentation', {})
            self._files = tuple(Path(path) for path in record.output_files)
            self.note.setText(f'Geçmiş kayıt · {len(self._files)} dosya · Çıktı üretimi, ERP kabulü anlamına gelmez.')
        rows = regional_breakdown(summary, evidence)
        self.regions.setRowCount(len(rows))
        for n, row in enumerate(rows):
            categories = []
            for key, _ in CATEGORIES:
                value = amount(row[key])
                if row[key] is None and key == 'normal':
                    value = amount(row['netsis_net']) + ' (toplam)'
                elif row[key] is None and key != 'branch':
                    value = amount(row[key + '_net']) + ' (net)'
                categories.append(value)
            values = [row['region'], *categories,
                      amount(row['source']), amount(row['distributed']), amount(row['difference'])]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if col:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.regions.setItem(n, col, item)
        if summary is None:
            self.net_note.setText('Bu işlem için bölge / kategori özeti mevcut değil. Kayıtlı dosyalar aşağıdadır.')
        else:
            net = ' · '.join(f'{label}: {amount(summary.total(field))}' for label, field in
                (('Havale (şubeli dahil)', 'netsis_total'), ('Ödeme', 'payment_total'), ('Referanslı', 'reference_total'), ('Virman', 'virman_total'), ('İnceleme', 'review_total')))
            self.net_note.setText('Kategoriler hareket hacmi; kaynak/dağıtılan/fark net. —: ayrıntı kaydedilmemiş.\nKayıtlı işaretli net toplamlar: ' + net)
            if any(b.unaccounted_total for b in summary.buckets):
                self.net_note.setText('Dikkat: banka/bölge bazında açıklanamayan fark var; net farklar birbirini götürebilir.\n' + self.net_note.text())
        self.files.setRowCount(len(self._files))
        for n, path in enumerate(self._files):
            for col, value in enumerate((path.name, 'Mevcut' if path.is_file() else 'Dosya bulunamadı', str(path.parent))):
                item = QTableWidgetItem(value)
                item.setToolTip(str(path))
                self.files.setItem(n, col, item)
        if self._files:
            self.files.selectRow(0)
        self.update_actions()

    def update_actions(self):
        row = self.files.currentRow()
        path = self._files[row] if 0 <= row < len(self._files) else None
        self.open_file.setEnabled(path is not None and path.is_file())
        self.open_folder.setEnabled(path is not None and path.parent.is_dir())

    def open_selected(self, folder):
        row = self.files.currentRow()
        if 0 <= row < len(self._files):
            path = self._files[row].parent if folder else self._files[row]
            if (path.is_dir() if folder else path.is_file()):
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            else:
                self.note.setText('Seçili dosya veya klasör artık bu konumda değil.')
                self.update_actions()
