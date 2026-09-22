"""Read-only presentation of current/historical operation totals.

Net accounting totals are never replaced by gross movement volumes.
Optional presentation evidence augments future history; old history stays honest.
"""
from decimal import Decimal

CATEGORIES = (
    ('normal', 'Havale'), ('branch', 'Şubeli'), ('payment', 'Ödeme onaylandı'),
    ('reference', 'Referanslı'), ('virman', 'Virman'), ('review', 'İncelemede'),
)
OUTCOMES = {'payment': {'ODEME_ONAYLANDI'}, 'reference': {'REFERANSLI'},
            'virman': {'VIRMAN', 'SAME_BANK_VIRMAN'}, 'review': {'REVIEW'}}
FIELDS = ('netsis_total', 'payment_total', 'reference_total', 'virman_total',
          'rule_total', 'review_total', 'pending_total')


def presentation_evidence(summary):
    if summary is None:
        return {}
    branches = {(r, b): value for r, b, value in summary.branch_output_buckets}
    rows = []
    for bucket in summary.buckets:
        complete = len(bucket.details) == bucket.record_count
        gross = {key: str(sum((abs(d.amount) for d in bucket.details if d.outcome in outcomes), Decimal(0)))
                 for key, outcomes in OUTCOMES.items()} if complete else {}
        branch = branches.get((bucket.region, bucket.bank))
        rows.append({'region': bucket.region, 'bank': bucket.bank,
                     'branch': str(branch) if branch is not None else None, 'gross': gross})
    return {'version': 1, 'buckets': rows}


def _decimal(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (ArithmeticError, ValueError, TypeError):
        return None



def bank_breakdown(summary, evidence=None):
    """Return presentation-safe category facts for each region/bank bucket.

    This is the bank-granular counterpart of :func:`regional_breakdown`.  It
    preserves the same evidence rules: a missing gross/branch proof stays
    ``None`` instead of being inferred from a net amount.
    """
    if summary is None:
        return []
    evidence = presentation_evidence(summary) if evidence is None else evidence
    extra = {}
    if isinstance(evidence, dict) and evidence.get('version') == 1 and isinstance(evidence.get('buckets'), list):
        for row in evidence.get('buckets', []):
            if isinstance(row, dict):
                extra[(row.get('region'), row.get('bank'))] = row
    rows = []
    for bucket in summary.buckets:
        proof = extra.get((bucket.region, bucket.bank), {})
        branch = _decimal(proof.get('branch'))
        if branch is not None and not Decimal(0) <= branch <= max(bucket.netsis_total, Decimal(0)):
            branch = None
        values = {
            'branch': branch,
            'normal': bucket.netsis_total - branch if branch is not None else None,
        }
        gross = proof.get('gross', {})
        for key in OUTCOMES:
            value = _decimal(gross.get(key)) if isinstance(gross, dict) else None
            if value is not None and value < abs(getattr(bucket, key + '_total')):
                value = None
            values[key] = value
        distributed = sum((getattr(bucket, name) for name in FIELDS), Decimal(0))
        rows.append({
            'region': bucket.region,
            'bank': bucket.bank,
            'record_count': bucket.record_count,
            **values,
            'source': bucket.manim_total,
            'distributed': distributed,
            'difference': bucket.manim_total - distributed,
            'netsis_net': bucket.netsis_total,
            'payment_net': bucket.payment_total,
            'reference_net': bucket.reference_total,
            'virman_net': bucket.virman_total,
            'review_net': bucket.review_total,
        })
    return rows

def regional_breakdown(summary, evidence=None):
    """Return region/category facts. Missing evidence remains None, not zero."""
    if summary is None:
        return []
    evidence = presentation_evidence(summary) if evidence is None else evidence
    extra = {}
    if isinstance(evidence, dict) and evidence.get('version') == 1 and isinstance(evidence.get('buckets'), list):
        for row in evidence.get('buckets', []):
            if isinstance(row, dict):
                extra[(row.get('region'), row.get('bank'))] = row
    regions = {}
    for bucket in summary.buckets:
        row = regions.setdefault(bucket.region, {key: Decimal(0) for key in
            ('normal', 'branch', 'payment', 'reference', 'virman', 'review', 'source', 'distributed', 'difference',
             'netsis_net', 'payment_net', 'reference_net', 'virman_net', 'review_net')})
        proof = extra.get((bucket.region, bucket.bank), {})
        branch = _decimal(proof.get('branch'))
        if branch is not None and not Decimal(0) <= branch <= max(bucket.netsis_total, Decimal(0)):
            branch = None
        values = {'branch': branch, 'normal': bucket.netsis_total - branch if branch is not None else None}
        gross = proof.get('gross', {})
        for key in OUTCOMES:
            values[key] = _decimal(gross.get(key)) if isinstance(gross, dict) else None
            if values[key] is not None and values[key] < abs(getattr(bucket, key + '_total')):
                values[key] = None
        # Old snapshots lack gross evidence: expose only explicitly labelled net
        # fields in the detail view, never abs(net) as a fabricated gross total.
        for key, value in values.items():
            row[key] = row[key] + value if row[key] is not None and value is not None else None
        row['source'] += bucket.manim_total
        row['netsis_net'] += bucket.netsis_total
        for key in OUTCOMES:
            row[key + '_net'] += getattr(bucket, key + '_total')
        distributed = sum((getattr(bucket, name) for name in FIELDS), Decimal(0))
        row['distributed'] += distributed
        row['difference'] += bucket.manim_total - distributed
    return [dict(region=region, **values) for region, values in sorted(regions.items())]
