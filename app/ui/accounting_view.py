"""Immutable presentation of parser and engine facts; no routing decisions."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from collections import Counter

from app.core.manim_parser import ManimParser
from app.core.manim_input_classifier import ManimInputClassifier
from app.core.manim_region_resolver import ManimRegionResolver
from app.core.input_profile import InputProfileStore
from app.core.active_profile_store import ActiveProfileStore
from app.core.region_config import RegionConfig, active_region_config_path
from app.core.operation_simulation import simulation_summary_from_payload


def money(value):
    try:
        result = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def money_text(value):
    if value is None:
        return '—'
    return f'{value:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.') + ' TL'


@dataclass(frozen=True)
class RecordView:
    source: str
    row: int
    region: str
    bank: str
    date: str
    description: str
    amount: Decimal | None
    receipt: str
    issue: str = ''
    outcome: str = ''
    rule: str = ''
    reason: str = ''

    @property
    def priority(self):
        if self.issue:
            return 0
        if self.outcome in ('REVIEW', 'SKIPPED'):
            return 1
        # MANUAL_HAVALE is a genuine user/manual accounting decision.
        # REFERANSLI and ODEME_ONAYLANDI are already deterministic routed
        # outcomes; presenting them as pending review makes a completed
        # operation look unfinished.
        if self.outcome == 'MANUAL_HAVALE':
            return 2
        return 3 if not self.outcome else 4


@dataclass(frozen=True)
class SourceView:
    path: str
    adapter: str
    records: tuple[RecordView, ...] = ()
    error: str = ''

    @property
    def total(self):
        if self.error or any(r.amount is None for r in self.records):
            return None
        return sum((r.amount for r in self.records), Decimal('0.00'))

    @property
    def receipt_summary(self):
        counts = Counter(r.receipt or 'Boş' for r in self.records)
        return ' · '.join(f'{key}: {value}' for key, value in sorted(counts.items()))


@dataclass(frozen=True)
class AccountingView:
    sources: tuple[SourceView, ...] = ()

    @property
    def records(self):
        return tuple(r for s in self.sources for r in s.records)

    @property
    def regions(self):
        return tuple(sorted({r.region for r in self.records if r.region != 'BILINMEYEN_BOLGE'}))

    @property
    def total(self):
        sources = [s for s in self.sources if s.adapter == 'MANİM Excel']
        if not sources or any(s.total is None for s in sources):
            return None
        return sum((s.total for s in sources), Decimal('0.00'))


def load_sources(paths, resource_root, data_root):
    """Read selected sources using the same active parser profile as the engine.

    Regions before execution use account/file evidence only; customer-dependent
    resolution is deferred to the engine's decision audits.
    """
    config = RegionConfig(active_region_config_path(resource_root / 'config', data_root))
    resolver = ManimRegionResolver(config, config.regions())
    selection = ActiveProfileStore(data_root).selection_snapshot()
    profile = InputProfileStore(resource_root / 'config', data_root / 'config').get_or_default(selection['input_profile_id'])
    result = []
    for path in dict.fromkeys(Path(p).resolve() for p in paths):
        try:
            bundle = ManimInputClassifier().classify([path])
            if not bundle.manim_files:
                adapter = 'FOM / tahsilat' if bundle.tahsilat_file else 'Müşteri listesi' if bundle.customer_file else 'Tanımlanamadı'
                result.append(SourceView(str(path), adapter))
                continue
            parsed = ManimParser(path, profile).load_with_issues()
            region = resolver.from_file_name(path.stem)
            rows = [RecordView(str(path), r.kaynak_satir, resolver.for_record(r, region), r.banka,
                               str(r.islem_tarihi or ''), r.aciklama, money(r.tutar), r.dekont_durumu)
                    for r in parsed.records]
            headers = {field: header for header, field in profile.columns.items()}
            for invalid in parsed.invalid_rows:
                raw = invalid.ham_veri
                def text(field):
                    return ManimParser._text(raw.get(headers[field], ''))
                rows.append(RecordView(str(path), invalid.kaynak_satir, region, text('banka'),
                                       text('islem_tarihi'), text('aciklama'),
                                       money(ManimParser._amount(raw.get(headers['tutar']))),
                                       text('dekont_durumu'), '; '.join(invalid.nedenler)))
            result.append(SourceView(str(path), 'MANİM Excel', tuple(sorted(rows, key=lambda r: r.row))))
        except Exception as error:
            result.append(SourceView(str(path), 'MANİM Excel', error=str(error)))
    return AccountingView(tuple(result))


def detail_rows(view, audits=()):
    """Join only unambiguous source identities. Later audit replaces earlier one."""
    from dataclasses import replace
    names = Counter(Path(s.path).name for s in view.sources)
    decisions = {}
    for audit in audits:
        key = (audit.get('source_file'), audit.get('source_row'))
        decisions[key] = audit
    rows = []
    for record in view.records:
        name = Path(record.source).name
        audit = decisions.get((name, record.row), {}) if names[name] == 1 else {}
        rows.append(replace(record, outcome=str(audit.get('outcome', '')),
                            rule=str(audit.get('rule_code', '')), reason=str(audit.get('reason', '')),
                            region=str(audit.get('region') or record.region)))
    return tuple(sorted(rows, key=lambda r: (r.priority, r.source, r.row)))


@dataclass(frozen=True)
class ReconciliationView:
    source_total: Decimal | None
    distributed: Decimal | None
    difference: Decimal | None
    limitation: str


def reconcile(view, summary):
    if summary is None:
        return ReconciliationView(view.total, None, None, 'Motor önizlemesi sonrası kullanılabilir.')
    details = [d for b in summary.buckets for d in b.details]
    keys = [(d.source_file, d.source_row) for d in details]
    source_keys = [(Path(r.source).name, r.row) for r in view.records]
    amounts = {(Path(r.source).name, r.row): r.amount for r in view.records}
    complete = (view.total is not None and bool(source_keys) and not summary.ignored_records
                and not any(r.issue for r in view.records)
                and len(set(source_keys)) == len(source_keys)
                and len(set(keys)) == len(keys) and set(keys) == set(source_keys)
                and all(amounts.get((d.source_file, d.source_row)) == d.amount for d in details)
                and view.total == summary.manim_total)
    fields = ('netsis_total', 'payment_total', 'reference_total', 'virman_total', 'rule_total', 'review_total', 'pending_total')
    distributed = sum((summary.total(f) for f in fields), Decimal('0.00'))
    if not complete:
        return ReconciliationView(view.total, distributed, None, 'Kaynak kapsamı doğrulanamadı: eksik, geçersiz veya çakışan kayıt. Dağıtım yalnız motor kapsamıdır.')
    if any(b.unaccounted_total for b in summary.buckets):
        return ReconciliationView(view.total, distributed, view.total-distributed, 'Bölge/banka bazında açıklanamayan fark var; toplamlar birbirini götürebilir.')
    return ReconciliationView(view.total, distributed, view.total-distributed, 'Kaynak → motor dağılımı. ERP kabulü ve çıktı yayın durumu ayrıca doğrulanır.')


def previous_operation(history, current_id=None):
    for record in history.recent(None):
        if (record.company_id == history.company_id and record.module_id == 'manim_transfer'
                and record.status == 'SUCCESS' and record.id != current_id):
            summary = simulation_summary_from_payload(record.summary.get('operation_result'))
            if summary is not None:
                return record, summary
    return None
