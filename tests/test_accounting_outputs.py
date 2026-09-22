from decimal import Decimal
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication
from app.core.operation_simulation import OperationSimulation, simulation_summary_payload, simulation_summary_from_payload
from app.ui.accounting_view import AccountingView, SourceView, reconcile
from app.ui.accounting_workspace import AccountingWorkspace
from app.ui.accounting_outputs_page import AccountingOutputsPage
from app.ui.operation_breakdown import bank_breakdown, regional_breakdown, presentation_evidence
from tests.test_accounting_view import record, audit

APP = QApplication.instance() or QApplication([])


def example():
    rows = tuple(record(row=i + 2, amount=value) for i, value in enumerate(('100', '200', '-50', '70', '-300', '25')))
    outcomes = ('HAVALE', 'HAVALE', 'REFERANSLI', 'REFERANSLI', 'SAME_BANK_VIRMAN', 'REVIEW')
    audits = [audit(row, outcome) for row, outcome in zip(rows, outcomes)]
    outputs = [SimpleNamespace(bolge=r.region, banka=r.bank, tutar=r.amount, kaynak=kind)
               for r, kind in zip(rows, ('MANIM_KOD', 'SUBELI_TAHSILAT'))]
    return rows, audits, OperationSimulation().summarize(audits, netsis_records=outputs)


def workspace(tmp_path):
    return AccountingWorkspace(SimpleNamespace(recent=lambda _: []), SimpleNamespace(resource_root=tmp_path, data_root=tmp_path))


def test_region_categories_keep_gross_and_net_distinct_and_do_not_double_count_branch():
    rows, audits, summary = example()
    region = regional_breakdown(summary)[0]
    bank = bank_breakdown(summary)[0]
    assert bank['bank'] == summary.buckets[0].bank
    assert bank['record_count'] == summary.buckets[0].record_count
    assert bank['normal'] == 100
    assert bank['branch'] == 200
    assert bank['reference'] == 120
    assert bank['virman'] == 300
    assert region['normal'] == 100
    assert region['branch'] == 200
    assert region['reference'] == 120
    assert region['reference_net'] == 20
    assert region['virman'] == 300
    assert region['virman_net'] == -300
    assert region['source'] == region['distributed'] == 45
    assert region['difference'] == 0
    view = AccountingView((SourceView(rows[0].source, 'MANİM Excel', rows),))
    assert reconcile(view, summary).difference == 0
    payload = simulation_summary_payload(summary)
    restored = simulation_summary_from_payload(payload)
    assert regional_breakdown(restored, presentation_evidence(summary)) == regional_breakdown(summary)
    old = regional_breakdown(restored, {})[0]
    assert old['branch'] is None and old['reference'] is None
    assert old['reference_net'] == 20 and old['netsis_net'] == 300
    assert simulation_summary_payload(summary) == payload


def test_breakdown_keeps_unassigned_difference_and_variable_regions():
    rows = [record(source=f'synthetic_{i}.xlsx', region=f'ZONE{i}', amount='15') for i in range(11)]
    summary = OperationSimulation().summarize([audit(row, 'UNKNOWN') for row in rows], netsis_records=[])
    result = regional_breakdown(summary)
    assert len(result) == 11
    assert all(row['difference'] == 15 and row['distributed'] == 0 for row in result)


def test_current_breakdown_filter_does_not_mutate_summary(tmp_path):
    page = workspace(tmp_path)
    rows, audits, summary = example()
    page.view = AccountingView((SourceView(rows[0].source, 'MANİM Excel', rows),))
    page.set_result(SimpleNamespace(simulation_summary=summary, decision_audits=audits, unresolved=1), preview=True)
    page.breakdown_region.setCurrentIndex(1)
    assert page.breakdown_category.currentData() == 'normal'
    assert page.breakdown_bank.currentIndex() == 0
    assert page.breakdown_bank.currentText() == 'Tüm bankalar'
    assert page.breakdown_table.columnCount() == 4
    assert page.breakdown_table.rowCount() == 1
    assert page.breakdown_table.item(0, 1).text() == str(summary.buckets[0].record_count)
    assert page.breakdown_table.item(0, 3).text() == '100,00 ₺'
    page.breakdown_category.setCurrentIndex(page.breakdown_category.findData('virman'))
    assert page.breakdown_table.item(0, 3).text() == '300,00 ₺'
    assert page.breakdown_total.text() == '300,00 ₺'
    assert page.summary is summary
    assert page.recon_difference.value.text() == '0,00 ₺'
    assert page.recon_virman.value.text() == '300,00 ₺'
    assert page.recon_cells[5] is page.recon_virman
    assert all(cell.label.text() != 'Dağıtılan toplam' for cell in page.recon_cells)
    page.close()


def test_outputs_preserve_history_company_scope_and_open_exact_selected_file(tmp_path, monkeypatch):
    from app.ui import accounting_outputs_page as outputs_module
    page = workspace(tmp_path)
    rows, audits, summary = example()
    output = tmp_path / 'synthetic.txt'
    output.write_text('test', encoding='utf-8')
    page.summary = summary
    page._output_done = True
    page._last_created_files = (output,)
    operation = SimpleNamespace(id=1, company_id=1, module_id='manim_transfer', module_name='Muhasebe Otomasyonu',
        started_at='2026-09-17T10:00:00+00:00', status='SUCCESS', output_files=[str(output)],
        summary={'operation_result': simulation_summary_payload(summary), 'operation_presentation': presentation_evidence(summary)})
    foreign = SimpleNamespace(id=2, company_id=2, module_id='manim_transfer')
    history = SimpleNamespace(company_id=1, recent=lambda _: [operation, foreign])
    panel = AccountingOutputsPage(page, history)
    assert panel.operation.count() == 2
    assert panel.regions.item(0, 2).text() == '200,00 ₺'
    panel.operation.setCurrentIndex(1)
    assert '17.09.2026' in panel.operation.currentText()
    assert panel.files.rowCount() == 1
    opened = []
    monkeypatch.setattr(outputs_module.QDesktopServices, 'openUrl', lambda url: opened.append(url.toLocalFile()))
    panel.open_file.click()
    assert opened == [str(output).replace('\\', '/')]
    operation.summary.pop('operation_presentation')
    panel.refresh()
    assert panel.regions.item(0, 2).text() == '—'
    assert panel.regions.item(0, 1).text() == '300,00 ₺ (toplam)'
    assert panel.regions.item(0, 4).text() == '20,00 ₺ (net)'
    hidden = AccountingOutputsPage(page, history, allow_history=False)
    assert hidden.operation.count() == 1
    output.unlink()
    panel.refresh()
    assert not panel.open_file.isEnabled()
    assert panel.files.item(0, 1).text() == 'Dosya bulunamadı'
    hidden.close()
    panel.close()
    page.close()


def test_output_navigation_preserves_settings_and_source_tabs(tmp_path, monkeypatch):
    from tests.test_ui_design_system import _window
    window = _window(tmp_path, monkeypatch)
    window._open_accounting_mode('outputs')
    module = window._pages_by_id['accounting_automation']
    assert module.tabs.currentWidget() is window.accounting_outputs_page
    window.accounting_outputs_page.settings_requested.emit()
    assert module.tabs.currentIndex() == 1
    window._open_accounting_mode('sources')
    assert module.tabs.currentWidget() is window.accounting_sources_page
    window._open_accounting_mode('rules')
    assert module.tabs.currentWidget() is window.accounting_resolution_page
    for (key, _), item in zip(window.nav_items, window.nav_item_widgets):
        if key in {'dashboard', 'operations', 'settings', 'integrations', 'reports'}:
            assert item.status.isHidden()
    window.close()


def test_corrupt_optional_history_evidence_does_not_fabricate_amounts():
    rows, audits, summary = example()
    assert regional_breakdown(summary, {'version': 1, 'buckets': None})[0]['branch'] is None
    proof = presentation_evidence(summary)
    proof['buckets'][0]['branch'] = 'NaN'
    proof['buckets'][0]['gross']['virman'] = '-1'
    result = regional_breakdown(summary, proof)[0]
    assert result['branch'] is None and result['virman'] is None
    assert result['virman_net'] == -300 and result['difference'] == 0
