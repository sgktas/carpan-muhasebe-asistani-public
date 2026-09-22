from decimal import Decimal
from types import SimpleNamespace
from pathlib import Path

import pandas as pd
import pytest
from app.ui.accounting_view import (AccountingView, SourceView, RecordView, detail_rows,
    reconcile, previous_operation, money, money_text, load_sources)
from app.core.operation_simulation import OperationSimulation, simulation_summary_payload


def record(source='synthetic_manim.xlsx', row=2, region='SYNTHETIC_REGION', amount='123.45', **kwargs):
    return RecordView(source, row, region, 'SYNTHETIC_BANK', '2026-01-01', 'Synthetic transaction',
                      money(amount), kwargs.pop('receipt', 'Aktarıldı'), **kwargs)


def audit(r, outcome='HAVALE'):
    return dict(source_file=Path(r.source).name, source_row=r.row, region=r.region,
                bank=r.bank, amount=str(r.amount), outcome=outcome, rule_code='SYNTHETIC_RULE')


@pytest.mark.parametrize('count', [0, 1, 7, 19])
def test_arbitrary_source_counts(count):
    view = AccountingView(tuple(SourceView(f'synthetic_{i}.xlsx', 'MANİM Excel',
                           (record(f'synthetic_{i}.xlsx', region=f'SYNTHETIC_{i % 3}'),)) for i in range(count)))
    assert len(view.sources) == count
    assert len(view.records) == count
    assert len(view.regions) == min(count, 3)
    assert view.total == (Decimal('123.45') * count if count else None)


def test_one_file_can_have_multiple_regions_and_unknowns():
    view = AccountingView((SourceView('synthetic.xlsx', 'MANİM Excel',
                                     (record(region='SYNTHETIC_A'), record(row=3,region='SYNTHETIC_B'),
                                      record(row=4,region='BILINMEYEN_BOLGE'))),))
    assert view.regions == ('SYNTHETIC_A', 'SYNTHETIC_B')


def test_receipt_counts_preserve_source_labels():
    source = SourceView('synthetic.xlsx', 'MANİM Excel', tuple(record(row=i+2,receipt=status) for i,status in
                         enumerate(['Otomatik Olarak Aktarıldı','Aktarıldı','', 'Aktarıldı'])))
    assert 'Otomatik Olarak Aktarıldı: 1' in source.receipt_summary
    assert 'Boş: 1' in source.receipt_summary
    assert 'Aktarıldı: 2' in source.receipt_summary


def test_unknown_amount_is_not_zero():
    view = AccountingView((SourceView('synthetic.xlsx','MANİM Excel',(record(amount=None),)),))
    assert view.total is None
    assert money_text(None) == '—'
    assert money_text(Decimal('1234567.89')) == '1.234.567,89 TL'


def test_engine_partition_conservation():
    r = record()
    view = AccountingView((SourceView(r.source,'MANİM Excel',(r,)),))
    summary = OperationSimulation().summarize([audit(r)])
    result = reconcile(view,summary)
    assert result.source_total == result.distributed == Decimal('123.45')
    assert result.difference == 0


@pytest.mark.parametrize('case', ['missing', 'invalid', 'duplicate', 'no_summary'])
def test_unprovable_partitions_never_claim_zero(case):
    r = record(issue='Invalid' if case=='invalid' else '')
    rows = (r,r) if case=='duplicate' else (r,)
    view = AccountingView((SourceView(r.source,'MANİM Excel',rows),))
    summary = OperationSimulation().summarize([] if case=='missing' else [audit(r)])
    assert reconcile(view,None if case=='no_summary' else summary).difference is None


def test_unknown_engine_outcome_exposes_unallocated_amount():
    r=record()
    view=AccountingView((SourceView(r.source,'MANİM Excel',(r,)),))
    summary=OperationSimulation().summarize([audit(r,'UNKNOWN')])
    assert reconcile(view,summary).difference == r.amount


def test_exception_priority_and_detail_join():
    rows=(record(row=2),record(row=3),record(row=4,issue='Dekont durumu eksik',receipt=''))
    view=AccountingView((SourceView('synthetic_manim.xlsx','MANİM Excel',rows),))
    audits=[audit(rows[0]), dict(audit(rows[1],'REVIEW'), reason='Synthetic review reason')]
    details=detail_rows(view,audits)
    assert [r.row for r in details]==[4,3,2]
    assert details[1].reason=='Synthetic review reason'
    assert details[1].rule=='SYNTHETIC_RULE'


def test_duplicate_basenames_do_not_receive_ambiguous_audits():
    a=record('synthetic_a/same.xlsx')
    b=record('synthetic_b/same.xlsx')
    view=AccountingView(tuple(SourceView(r.source,'MANİM Excel',(r,)) for r in (a,b)))
    assert all(not r.outcome for r in detail_rows(view,[audit(a)]))


def test_long_filename_preserved():
    r=record('synthetic_'+'x'*180+'.xlsx')
    view=AccountingView((SourceView(r.source,'MANİM Excel',(r,)),))
    assert detail_rows(view)[0].source==r.source


def test_previous_operation_company_isolation_and_empty():
    payload=simulation_summary_payload(OperationSimulation().summarize([audit(record())]))
    foreign=SimpleNamespace(id=8,company_id=2,module_id='manim_transfer',status='SUCCESS',summary={'operation_result':payload})
    own=SimpleNamespace(id=7,company_id=1,module_id='manim_transfer',status='SUCCESS',summary={'operation_result':payload})
    history=SimpleNamespace(company_id=1,recent=lambda limit:[foreign])
    assert previous_operation(history) is None
    history.recent=lambda limit:[foreign,own]
    assert previous_operation(history)[0].id==7
    assert previous_operation(history,7) is None


def test_actual_parser_reports_blank_status_without_reclassifying(tmp_path):
    from app.core.input_profile import InputProfileStore
    root=Path(__file__).resolve().parents[1]
    profile=InputProfileStore(root/'config').get('manim')
    rows=[]
    for status in ('Otomatik Olarak Aktarıldı','Aktarıldı',''):
        values=dict(banka='SYNTHETIC_BANK',sube='SYNTHETIC_BRANCH',islem_tarihi='2026-01-01',aciklama='Synthetic transaction',
                    tutar=10.25,dekont_durumu=status,karsi_hesap_adi='Synthetic account',karsi_hesap_kodu='SYNTHETIC')
        rows.append({header:values[field] for header,field in profile.columns.items()})
    source=tmp_path/'synthetic_manim.xlsx'
    pd.DataFrame(rows).to_excel(source,index=False)
    view=load_sources([source],root,tmp_path)
    assert len(view.records)==3
    assert view.total==Decimal('30.75')
    assert len([r for r in view.records if r.issue])==1
    assert not any(r.outcome for r in view.records)


def test_completed_routed_outcomes_are_not_presented_as_pending_review():
    payment = record(row=20)
    reference = record(row=21)
    manual = record(row=22)
    view = AccountingView((SourceView('synthetic_manim.xlsx', 'MANİM Excel', (payment, reference, manual)),))
    rows = detail_rows(view, [
        audit(payment, 'ODEME_ONAYLANDI'),
        audit(reference, 'REFERANSLI'),
        audit(manual, 'MANUAL_HAVALE'),
    ])
    by_row = {row.row: row for row in rows}
    assert by_row[20].priority == 4
    assert by_row[21].priority == 4
    assert by_row[22].priority == 2
