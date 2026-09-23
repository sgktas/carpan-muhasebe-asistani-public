from datetime import datetime
import pytest
from decimal import Decimal
from types import SimpleNamespace

from PySide6.QtCore import Qt, QAbstractAnimation
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QTableWidgetSelectionRange, QWidget,
)

from app.ui.accounting_resolution_page import AccountingResolutionPage
from app.ui.accounting_workspace import AccountingWorkspace
from app.ui.accounting_view import AccountingView, SourceView, RecordView
from app.ui.theme import MAIN_STYLE
from tests.test_accounting_view import record
from tests.test_accounting_view import audit
from app.core.operation_simulation import OperationSimulation, simulation_summary_payload, simulation_summary_from_payload
from app.ui.accounting_view import reconcile


APP = QApplication.instance() or QApplication([])


def test_source_table_active_editor_and_disabled_selection_remain_readable(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _: []), SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    page.setStyleSheet(MAIN_STYLE)
    row = record()
    page.view = AccountingView((SourceView(row.source, 'MANİM Excel', (row,)),))
    page.render()
    page.resize(1400, 850)
    page.show()
    APP.processEvents()
    table = page.dashboard_sources
    item = table.item(0, 0)
    table.setCurrentItem(item)
    table.editItem(item)  # Explicit edit exercises the delegate; user editing stays disabled.
    APP.processEvents()
    editor = table.findChild(QLineEdit)
    assert editor is not None
    assert editor.text() == row.region
    assert row.source in table.item(0, 0).toolTip()
    editor.selectAll()
    palette = editor.palette()
    assert palette.color(QPalette.Text).lightness() < palette.color(QPalette.Base).lightness() - 100
    assert abs(palette.color(QPalette.HighlightedText).lightness() - palette.color(QPalette.Highlight).lightness()) > 80
    QTest.keyClick(editor, Qt.Key_Escape)
    table.setEnabled(False)
    APP.processEvents()
    assert table.item(0, 0).text() == row.region
    palette = table.palette()
    assert palette.color(QPalette.Disabled, QPalette.Text).lightness() < palette.color(QPalette.Disabled, QPalette.Base).lightness() - 80
    page.close()


def test_reconciliation_separates_actual_branch_rows_and_gross_reference(tmp_path):
    rows = tuple(record(row=i + 2, amount=amount) for i, amount in enumerate(('100', '200', '-40', '10')))
    audits = [audit(r, 'HAVALE' if i < 2 else 'REFERANSLI') for i, r in enumerate(rows)]
    outputs = [SimpleNamespace(bolge=r.region, banka=r.bank, tutar=r.amount, kaynak=kind)
               for r, kind in zip(rows, ('MANIM_KOD', 'SUBELI_TAHSILAT'))]
    summary = OperationSimulation().summarize(audits, netsis_records=iter(outputs))
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _: []), SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    page.view = AccountingView((SourceView(rows[0].source, 'MANİM Excel', rows),))
    page.set_result(SimpleNamespace(simulation_summary=summary, decision_audits=audits, unresolved=0), preview=True)
    assert page.recon_normal.value.text() == '100,00 ₺'
    assert page.recon_branch.value.text() == '200,00 ₺'
    assert page.recon_reference.value.text() == '50,00 ₺'  # NOT abs(net) == 30.
    assert summary.total('reference_total') == Decimal('-30')
    assert reconcile(page.view, summary).difference == 0
    assert all(cell.label.text() != 'Dağıtılan toplam' for cell in page.recon_cells)
    assert page.recon_difference.value.text() == '0,00 ₺'
    persisted = simulation_summary_from_payload(simulation_summary_payload(summary))
    assert persisted.branch_output_total is None
    page.set_result(SimpleNamespace(simulation_summary=persisted, decision_audits=audits, unresolved=0), preview=True)
    assert page.recon_branch.value.text() == '—'
    assert page.recon_reference.value.text() == '—'
    page.close()


def test_output_breakdown_does_not_change_financial_gate_or_payload():
    rows = [record(amount='50'), record(row=3, amount='75')]
    audits = [audit(r) for r in rows]
    outputs = [SimpleNamespace(bolge=r.region, banka=r.bank, tutar=r.amount, kaynak=kind)
               for r, kind in zip(rows, ('BIRLESIK_BANKA_HAREKETI', 'MANUEL_ESLESTIRME'))]
    baseline = OperationSimulation().summarize(audits)
    actual = OperationSimulation().summarize(audits, netsis_records=outputs)
    assert actual.branch_output_total == Decimal('50')
    assert actual.matches(baseline)
    assert simulation_summary_payload(actual) == simulation_summary_payload(baseline)


def test_source_selection_contrast_and_inspector_stays_closed_on_refresh(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _: []), SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    page.setStyleSheet(MAIN_STYLE)
    row = record(issue='Sentetik inceleme')
    page.view = AccountingView((SourceView(row.source, 'MANİM Excel', (row,)),))
    page.render()
    page.resize(1380, 850)
    page.show()
    APP.processEvents()
    table = page.dashboard_sources
    QTest.mouseClick(table.viewport(), Qt.LeftButton, pos=table.visualItemRect(table.item(0, 0)).center())
    assert table.selectedItems()
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        assert table.palette().color(group, QPalette.Text) != table.palette().color(group, QPalette.Base)
        assert table.palette().color(group, QPalette.HighlightedText) != table.palette().color(group, QPalette.Highlight)
    page.records.selectRow(0)
    before = page.canvas_scroll.width()
    page.set_inspector_visible(False)
    QTest.qWait(240)
    page.render_records()
    APP.processEvents()
    assert not page._inspector_open
    assert page.inspector_frame.isHidden()
    assert page.canvas_scroll.width() > before
    page.detail_toggle.click()
    # Qt's animation clock can lag under full-suite load. Await completion,
    # with a bounded timeout, before checking the final layout contract.
    for _ in range(100):
        APP.processEvents()
        if page._inspector_animation.state() == QAbstractAnimation.Stopped:
            break
        QTest.qWait(20)
    assert page._inspector_animation.state() == QAbstractAnimation.Stopped
    APP.processEvents()
    assert page._inspector_open and not page.inspector_frame.isHidden()
    assert page.canvas_scroll.width() == before
    page.close()


def resolution_page():
    page = AccountingResolutionPage()
    page.setStyleSheet(MAIN_STYLE)
    item = SimpleNamespace(
        region="TEST", group_records=(), suggested_rows=(), reason="Sentetik tutar kontrolü",
        record=SimpleNamespace(banka="Test Bankası", tutar=Decimal("21583"),
            aciklama="Sentetik müşteri", islem_tarihi=datetime(2026, 9, 16), dekont_durumu="Aktarıldı"),
    )
    page.load_request([item], [])
    page.table.item(0, 0).setText("TEST-CARI")
    return page


def test_amount_editor_keeps_value_contrast_and_keyboard_commit():
    page = resolution_page()
    page.resize(1100, 700)
    page.show()
    APP.processEvents()
    item = page.table.item(0, 1)
    page.table.setCurrentItem(item)
    page.table.editItem(item)
    APP.processEvents()
    editor = page.table.findChild(QLineEdit, "allocationCellEditor")
    assert editor is not None
    assert editor.text() == "21.583,00"
    assert editor.alignment() & Qt.AlignRight
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        assert editor.palette().color(group, QPalette.Text) != editor.palette().color(group, QPalette.Base)
        assert editor.palette().color(group, QPalette.HighlightedText) != editor.palette().color(group, QPalette.Highlight)
    editor.selectAll()
    QTest.keyClicks(editor, "21.584,00")
    QTest.keyClick(editor, Qt.Key_Tab)
    APP.processEvents()
    assert page.table.item(0, 1).text() == "21.584,00"
    assert page._current_table_rows() == [("TEST-CARI", 21584.0)]
    assert page.total_label.property("tone") == "critical"
    assert "+1,00 TL" in page.total_label.text()
    page.close()


def test_totals_present_target_difference_and_keep_partial_decision():
    page = resolution_page()
    assert page.total_label.property("tone") == "success"
    assert "Tutarlar eşleşiyor" in page.total_label.text()
    page.table.item(0, 1).setText("20.583,00")
    assert page.total_label.property("tone") == "warning"
    assert "1.000,00 TL" in page.total_label.text()
    assert page.save_button.isEnabled()  # Existing partial-payment confirmation remains available.
    page.close()


def test_allocation_bulk_paste_expands_rows_and_copy_has_no_trailing_whitespace():
    page = resolution_page()
    page.table.setCurrentCell(0, 0)
    QApplication.clipboard().setText(
        "  C001  \t  100,00  \nC002\t200,00\nC003   \t300,00\n"
    )
    page.table._paste_from_clipboard()
    APP.processEvents()

    assert page.table.rowCount() >= 3
    assert page.table.item(0, 0).text() == "C001"
    assert page.table.item(1, 0).text() == "C002"
    assert page.table.item(2, 0).text() == "C003"
    assert page.table.item(2, 1).text() == "300,00"

    page.table.clearSelection()
    page.table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 2, 1), True)
    page.table._copy_to_clipboard()
    copied = QApplication.clipboard().text()
    assert copied == "C001\t100,00\nC002\t200,00\nC003\t300,00"
    assert not copied.endswith((" ", "\t", "\n", "\r"))
    page.close()


def test_allocation_editor_keeps_bulk_paste_shortcut_when_cell_editor_is_open():
    page = resolution_page()
    page.resize(900, 650)
    page.show()
    page.table.setCurrentCell(0, 0)
    page.table.editItem(page.table.item(0, 0))
    APP.processEvents()
    editor = page.table.findChild(QLineEdit, "allocationCellEditor")
    assert editor is not None

    QApplication.clipboard().setText("C101\t101,00\nC102\t102,00")
    QTest.keyClick(editor, Qt.Key_V, Qt.ControlModifier)
    APP.processEvents()

    assert page.table.item(0, 0).text() == "C101"
    assert page.table.item(0, 1).text() == "101,00"
    assert page.table.item(1, 0).text() == "C102"
    assert page.table.item(1, 1).text() == "102,00"
    page.close()


def test_grouped_manual_resolution_requires_full_bank_total(monkeypatch):
    page = AccountingResolutionPage()
    page.setStyleSheet(MAIN_STYLE)
    group_records = (
        SimpleNamespace(tutar=Decimal("100"), aciklama="A", islem_tarihi=datetime(2026, 9, 18)),
        SimpleNamespace(tutar=Decimal("200"), aciklama="B", islem_tarihi=datetime(2026, 9, 18)),
    )
    item = SimpleNamespace(
        region="BODRUM",
        group_records=group_records,
        group_target_amount=300.0,
        suggested_rows=(SimpleNamespace(musteri_kodu="C001", tutar=250.0),),
        reason="Tahsilat raporunda eksik müşteri",
        record=SimpleNamespace(
            banka="Garanti", tutar=Decimal("100"), aciklama="Toplu test",
            islem_tarihi=datetime(2026, 9, 18), dekont_durumu="Aktarıldı",
        ),
    )
    page.load_request([item], [])
    assert page._current_table_rows() == [("C001", 250.0)]

    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    page._save_current()

    assert 0 not in page.resolutions
    assert warnings and "50.00 TL" in warnings[0]
    assert "eksik müşteri" in warnings[0].casefold()
    page.close()


def test_inspector_tabs_and_operation_actions_are_independent(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    row = record(issue="Sentetik kontrol")
    page.view = AccountingView((SourceView(row.source, "MANİM Excel", (row,)),))
    page.render()
    page.resize(1366, 768)
    page.show()
    APP.processEvents()
    page.records.selectRow(0)
    page.inspector_tabs.setCurrentIndex(1)
    assert row.source in page.inspector.toPlainText()
    before = page.canvas_scroll.width()
    page.set_inspector_visible(False, animated=False)
    APP.processEvents()
    assert page.canvas_scroll.width() > before
    assert page.preview_button.isVisible()
    assert page.preview_button.parentWidget() is page.operation_actions
    assert not page.output_button.isEnabled()
    page.set_result(SimpleNamespace(simulation_summary=None, decision_audits=(), unresolved=1), preview=True)
    assert page.output_button.isEnabled()
    assert "1 karar" in page.output_button.text()
    page.set_inspector_visible(True, animated=False)
    APP.processEvents()
    assert page.canvas_scroll.width() == before
    page.close()


@pytest.mark.parametrize('size', [(1146, 650), (1380, 782), (1452, 823)])
def test_allocation_validation_never_overlays_rows(size):
    page = resolution_page()
    page.detail_title.setText('Sentetik uzun müşteri açıklaması ' * 6)
    for index in range(8):
        page._append_row(f'TEST-{index}', '100')
    page.resize(*size)
    page.show()
    APP.processEvents()
    assert page.table.parentWidget() is page.total_label.parentWidget()
    assert page.table.geometry().bottom() < page.total_label.geometry().top()
    assert page.table.height() >= 210
    assert page.total_label.height() >= page.total_label.heightForWidth(page.total_label.width())
    page.editor_scroll.ensureWidgetVisible(page.total_label)
    APP.processEvents()
    assert page.table.geometry().bottom() < page.total_label.geometry().top()
    page.close()


@pytest.mark.parametrize('size', [(1146, 650), (1380, 782), (1452, 823)])
def test_mockup_section_order_and_responsive_width(tmp_path, size):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    page.setStyleSheet(MAIN_STYLE)
    row = record(issue='Sentetik kontrol')
    page.view = AccountingView((SourceView(row.source, 'MANİM Excel', (row,)),))
    page.resize(*size)
    page.show()
    page.render()
    page.set_inspector_visible(True, animated=False)
    APP.processEvents()
    assert page.recon_panel.y() < page.source_panel.y() < page.records.y()
    assert page.source_panel.y() == page.breakdown_panel.y()
    assert page.canvas_scroll.widget().width() <= page.canvas_scroll.viewport().width()
    assert page.record_summary.y() < page.inspector_tabs.y()
    page.close()


@pytest.mark.parametrize('size', [(1146, 650), (1380, 782), (1452, 823), (1920, 1080)])
@pytest.mark.parametrize('value_text', ['—', '-7.066.349,25 ₺'])
def test_net_movement_financial_value_fits_without_ellipsis(tmp_path, size, value_text):
    from PySide6.QtGui import QFontMetricsF

    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    page.setStyleSheet(MAIN_STYLE)
    row = record(issue='Synthetic control')
    page.view = AccountingView((SourceView(row.source, 'MANİM Excel', (row,)),))
    page.resize(*size)
    page.show()
    page.render()
    page.set_inspector_visible(True, animated=False)
    page.metric_net.set_value(value_text, 'Net kaynak hareketi')
    APP.processEvents()

    value = page.metric_net.value
    assert value.text() == value_text
    assert value.toolTip() == value.text()
    assert QFontMetricsF(value.font()).horizontalAdvance(value.text()) <= value.contentsRect().width()
    text_column = page.metric_net.layout().itemAt(0).layout().itemAt(1).layout()
    title_rect = text_column.itemAt(0).widget().geometry()
    value_rect = value.geometry()
    detail_rect = text_column.itemAt(2).widget().geometry()
    assert title_rect.x() == value_rect.x() == detail_rect.x()
    icon_rect = page.metric_net.icon.geometry()
    assert icon_rect.right() < value_rect.left()
    assert page.metric_incoming.value.font().pixelSize() >= 16
    page.close()


@pytest.mark.parametrize('size', [(1146, 650), (1380, 782), (1452, 823), (1920, 1080)])
@pytest.mark.parametrize(('metric_name', 'value_text'), [
    ('metric_incoming', '11.206.585,41 ₺'),
    ('metric_outgoing', '22.170.000,00 ₺'),
    ('metric_net', '-7.066.349,25 ₺'),
])
def test_financial_kpi_values_fit_without_clipping(tmp_path, size, metric_name, value_text):
    from PySide6.QtGui import QFontMetricsF

    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    page.setStyleSheet(MAIN_STYLE)
    row = record(issue='Synthetic control')
    page.view = AccountingView((SourceView(row.source, 'MANİM Excel', (row,)),))
    page.resize(*size)
    page.show()
    page.render()
    page.set_inspector_visible(True, animated=False)
    tile = getattr(page, metric_name)
    tile.set_value(value_text, 'Kaynak hareketleri')
    APP.processEvents()

    value = tile.value
    assert value.text() == value_text
    assert value.toolTip() == value_text
    assert QFontMetricsF(value.font()).horizontalAdvance(value.text()) <= value.contentsRect().width()
    text_column = tile.layout().itemAt(0).layout().itemAt(1).layout()
    title_rect = text_column.itemAt(0).widget().geometry()
    value_rect = value.geometry()
    detail_rect = text_column.itemAt(2).widget().geometry()
    assert title_rect.x() == value_rect.x() == detail_rect.x()
    assert tile.icon.geometry().right() < value_rect.left()
    page.close()


def test_source_summary_uses_signed_source_values_and_real_filters(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    first = SourceView('synthetic_a.xlsx', 'MANİM Excel', (
        record(source='synthetic_a.xlsx', region='A', amount='200'),
        record(source='synthetic_a.xlsx', region='A', row=3, amount='-25'),
    ))
    second = SourceView('synthetic_b.xlsx', 'MANİM Excel', (
        record(source='synthetic_b.xlsx', region='B', amount='10'),
    ))
    page.view = AccountingView((first, second))
    page.render()
    assert page.dashboard_sources.columnCount() == 9
    assert page.dashboard_sources.item(0, 6).text() == '200,00 ₺'
    assert page.dashboard_sources.item(0, 7).text() == '25,00 ₺'
    assert page.dashboard_sources.item(0, 8).text() == '175,00 ₺'
    assert page.dashboard_sources.item(0, 1).text() == 'Synthetic Bank'
    assert 'synthetic_a.xlsx' in page.dashboard_sources.item(0, 0).toolTip()
    page.file_search.setText('synthetic_b')
    assert page.dashboard_sources.rowCount() == 1
    page.file_search.clear()
    page.file_region_filter.setCurrentIndex(page.file_region_filter.findData('A'))
    assert page.dashboard_sources.rowCount() == 1
    assert page.view.sources == (first, second)
    page.close()




def test_breakdown_uses_bank_badge_widgets(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    rows = (
        RecordView('synthetic.xlsx', 2, 'SYNTHETIC_REGION', 'Garanti', '2026-01-01', 'Synthetic transaction', Decimal('20'), 'Aktarıldı'),
        RecordView('synthetic.xlsx', 3, 'SYNTHETIC_REGION', 'YKB', '2026-01-01', 'Synthetic transaction', Decimal('30'), 'Aktarıldı'),
    )
    audits = [audit(r) for r in rows]
    outputs = [
        SimpleNamespace(bolge=r.region, banka=r.bank, tutar=r.amount, kaynak='MANIM_KOD')
        for r in rows
    ]
    summary = OperationSimulation().summarize(audits, netsis_records=outputs)
    page.view = AccountingView((SourceView(rows[0].source, 'MANİM Excel', rows),))
    page.set_result(SimpleNamespace(simulation_summary=summary, decision_audits=audits, unresolved=0), preview=True)
    page.render()
    page._render_current_breakdown()
    widget = page.breakdown_table.cellWidget(0, 0)
    assert widget is not None
    mark = widget.findChild(QLabel, 'automationBankMark')
    assert mark is not None
    assert mark.accessibleName() in {'Garanti logosu', 'Yapı Kredi logosu'}
    assert mark.pixmap() is not None and not mark.pixmap().isNull()
    assert page.breakdown_table.item(0, 0).text() == ''
    page.close()


def test_pass9_source_bank_summary_keeps_financial_columns_visible(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    rows = (
        RecordView('multi.xlsx', 2, 'BODRUM', 'Garanti', '2026-01-01', 'A', Decimal('10'), 'Aktarıldı'),
        RecordView('multi.xlsx', 3, 'BODRUM', 'YKB', '2026-01-01', 'B', Decimal('20'), 'Aktarıldı'),
        RecordView('multi.xlsx', 4, 'BODRUM', 'Ziraat Bankası', '2026-01-01', 'C', Decimal('-5'), 'Aktarıldı'),
    )
    page.view = AccountingView((SourceView('multi.xlsx', 'MANİM Excel', rows),))
    page.render()
    assert page.dashboard_sources.item(0, 1).text() == '3 banka'
    tooltip = page.dashboard_sources.item(0, 1).toolTip()
    assert all(name in tooltip for name in ('Garanti', 'Yapı Kredi', 'Ziraat'))
    assert page.dashboard_sources.horizontalHeader().sectionResizeMode(6) == QHeaderView.Stretch
    assert page.dashboard_sources.horizontalHeader().sectionResizeMode(7) == QHeaderView.Stretch
    assert page.dashboard_sources.horizontalHeader().sectionResizeMode(8) == QHeaderView.Stretch
    page.close()


def test_pass9_engine_codes_are_displayed_as_user_friendly_labels(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    row = record()
    decision = dict(audit(row), rule_code='AUTOMATIC_CUSTOMER_MATCH')
    page.view = AccountingView((SourceView(row.source, 'MANİM Excel', (row,)),))
    page.set_result(SimpleNamespace(simulation_summary=OperationSimulation().summarize([decision]), decision_audits=[decision], unresolved=0), preview=True)
    page.render()
    page._set_filter_mode('ready')
    page.records.selectRow(0)
    assert page.records.item(0, 6).text() == 'Otomatik müşteri eşleşmesi'
    assert page.evidence_values['rule'].text() == 'Otomatik müşteri eşleşmesi'
    assert page.target_values['rule'].text() == 'Otomatik müşteri eşleşmesi'
    assert page.reason_filter.itemText(page.reason_filter.findData('AUTOMATIC_CUSTOMER_MATCH')) == 'Otomatik müşteri eşleşmesi'
    page.close()


def test_pass9_missing_reason_is_neutral_not_success(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    row = record()
    decision = dict(audit(row), rule_code='AUTOMATIC_CUSTOMER_MATCH')
    page.view = AccountingView((SourceView(row.source, 'MANİM Excel', (row,)),))
    page.set_result(SimpleNamespace(simulation_summary=OperationSimulation().summarize([decision]), decision_audits=[decision], unresolved=0), preview=True)
    page.render()
    page._set_filter_mode('ready')
    page.records.selectRow(0)
    assert page.evidence_values['reason'].text() == 'Motor karar ayrıntısı henüz yok.'
    assert page.evidence_icons['reason'].property('tone') == 'neutral'
    assert page.evidence_icons['rule'].property('tone') == 'success'
    page.close()


def test_pass23_source_summary_omits_non_manim_empty_rows(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    manim = SourceView('bodrum.xlsx', 'MANİM Excel', (record(source='bodrum.xlsx', region='BODRUM', amount='100'),))
    customer = SourceView('customers.xlsx', 'Customer list', (RecordView('customers.xlsx', 2, '', '', '2026-01-01', 'Customer row', Decimal('0'), 'Aktarildi'),))
    page.view = AccountingView((manim, customer))
    page.render()
    assert page.source_count_badge.text() == '2 dosya'
    assert page.dashboard_sources.rowCount() == 1
    assert page.dashboard_sources.item(0, 0).text() == 'BODRUM'
    page.close()

def test_missing_source_amount_is_not_presented_as_zero(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    page.view = AccountingView((SourceView('synthetic.xlsx', 'MANİM Excel', (record(amount='invalid'),)),))
    page.render()
    assert [page.dashboard_sources.item(0, col).text() for col in (6, 7, 8)] == ['—'] * 3
    assert page.metric_auto.value.text() == '—'
    page.close()


def test_reason_filter_and_column_visibility_do_not_mutate_records(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    rows = (record(issue='Kontrol A'), record(row=3, issue='Kontrol B'))
    page.view = AccountingView((SourceView(rows[0].source, 'MANİM Excel', rows),))
    page.render()
    page.reason_filter.setCurrentIndex(page.reason_filter.findData('Kontrol B'))
    assert page.records.rowCount() == 1
    assert page.records.item(0, 6).text() == 'Kontrol B'
    page.column_menu.actions()[-1].setChecked(False)
    assert page.records.isColumnHidden(7)
    page._clear_record_filters()
    assert page.records.rowCount() == 2
    assert page.view.records == rows
    page.close()


def test_native_inspector_uses_real_evidence_and_existing_navigation(tmp_path):
    page = AccountingWorkspace(SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))
    row = record(issue='Bölge onayı gerekli')
    page.view = AccountingView((SourceView(row.source, 'MANİM Excel', (row,)),))
    page.render()
    page.records.selectRow(0)
    assert page.evidence_values['reason'].text() == row.issue
    assert page.target_values['account'].text() == '—'
    assert page.inspector_warning.text() == row.issue
    navigation = []
    page.matching_requested.connect(lambda: navigation.append(True))
    page.matching_button.click()
    assert navigation == [True]
    assert page.view.records == (row,)
    page.close()


def test_pass7a_dashboard_width_priorities_and_review_chips(tmp_path):
    page = AccountingWorkspace(
        SimpleNamespace(recent=lambda _limit: []),
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path),
    )
    page.setStyleSheet(MAIN_STYLE)
    row = record(issue='Sentetik kontrol')
    page.view = AccountingView((SourceView(row.source, 'MANİM Excel', (row,)),))
    page.resize(1380, 782)
    page.show()
    page.render()
    page.set_inspector_visible(True, animated=False)
    APP.processEvents()

    # Finance KPIs intentionally receive more width than status cards.
    assert page.metric_layout.columnStretch(0) > page.metric_layout.columnStretch(3)
    assert page.metric_layout.columnStretch(1) > page.metric_layout.columnStretch(4)
    assert page.metric_incoming.value.property('dense') == 'true'
    assert page.metric_outgoing.value.property('dense') == 'true'
    assert page.metric_outgoing.property('tone') == 'outflow'

    # The source table must never expose a horizontal scrollbar.  In the compact
    # dashboard view filenames are deliberately removed so the operational facts
    # keep priority without growing the card again.
    assert page.dashboard_sources.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert page.dashboard_sources.columnCount() == 9
    assert page.dashboard_sources.isColumnHidden(4)
    assert page.dashboard_sources.isColumnHidden(5)

    # The review tabs retain their semantic identity while being rendered as
    # count chips by the stylesheet.
    assert page.attention_tab.property('tone') == 'warning'
    assert page.ready_tab.property('tone') == 'success'
    assert page.all_tab.property('tone') == 'neutral'

    # At the narrow supported desktop boundary the two least-critical receipt
    # counters collapse instead of forcing the source table to overflow.
    page.resize(1146, 650)
    APP.processEvents()
    assert page.dashboard_sources.isColumnHidden(4)
    assert page.dashboard_sources.isColumnHidden(5)
    page.close()
