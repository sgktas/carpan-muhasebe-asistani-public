"""Side-effect-free preflight totals for MANİM operations."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from app.core.text_keys import bank_key, compact_key


def _money(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SimulationDetail:
    source_file: str
    source_row: int
    amount: Decimal
    outcome: str
    rule_code: str


@dataclass(frozen=True)
class SimulationBucket:
    region: str
    bank: str
    manim_total: Decimal
    netsis_total: Decimal
    payment_total: Decimal
    reference_total: Decimal
    virman_total: Decimal
    rule_total: Decimal
    review_total: Decimal
    record_count: int
    details: tuple[SimulationDetail, ...] = field(default_factory=tuple)
    pending_total: Decimal = Decimal("0.00")
    unaccounted_total: Decimal = Decimal("0.00")
    incoming_total_snapshot: Decimal | None = None
    outgoing_total_snapshot: Decimal | None = None

    @property
    def incoming_total(self) -> Decimal:
        if self.incoming_total_snapshot is not None:
            return self.incoming_total_snapshot
        return sum((d.amount for d in self.details if d.amount > 0), Decimal("0.00"))

    @property
    def outgoing_total(self) -> Decimal:
        if self.outgoing_total_snapshot is not None:
            return self.outgoing_total_snapshot
        return -sum((d.amount for d in self.details if d.amount < 0), Decimal("0.00"))

    @property
    def difference(self) -> Decimal:
        return (self.manim_total - self.netsis_total).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class SimulationSummary:
    buckets: tuple[SimulationBucket, ...] = field(default_factory=tuple)
    ignored_records: int = 0

    @property
    def manim_total(self) -> Decimal:
        return sum((bucket.manim_total for bucket in self.buckets), Decimal("0.00"))

    @property
    def netsis_total(self) -> Decimal:
        return sum((bucket.netsis_total for bucket in self.buckets), Decimal("0.00"))

    @property
    def difference(self) -> Decimal:
        return (self.manim_total - self.netsis_total).quantize(Decimal("0.01"))

    def total(self, field_name: str) -> Decimal:
        return sum((getattr(b, field_name) for b in self.buckets), Decimal("0.00"))

    @property
    def needs_attention(self) -> bool:
        return bool(self.ignored_records or any(
            b.pending_total or b.unaccounted_total or b.review_total
            or any(d.outcome == "REVIEW" for d in b.details)
            for b in self.buckets
        ))

    def matches(self, other: SimulationSummary) -> bool:
        # Bölge/banka veya karar değişimini genel toplamların birbirini
        # götürmesi gizlememeli. Bu bir kaynak/config snapshot kanıtı değildir.
        return not (self.ignored_records or other.ignored_records) and self == other


class OperationSimulation:
    """Builds an explainable summary without touching persistent state."""

    _NETSIS_OUTCOMES = {"HAVALE", "MATCH", "MANUAL_HAVALE"}
    _CATEGORIES = {
        "ODEME_ONAYLANDI": "payment_total",
        "REFERANSLI": "reference_total",
        "VIRMAN": "virman_total",
        "SAME_BANK_VIRMAN": "virman_total",
        "KURAL_CALISTI": "rule_total",
        "REVIEW": "review_total",
    }

    def summarize(self, decision_audits: Iterable[dict], *, netsis_records=None) -> SimulationSummary:
        buckets: dict[tuple[str, str], dict[str, object]] = {}
        ignored = 0
        final_decisions = {}
        for index, audit in enumerate(decision_audits):
            source = str(audit.get("source_file", ""))
            row = int(audit.get("source_row", 0) or 0)
            identity = (source, row, compact_key(audit.get("region", "")), bank_key(audit.get("bank", "")))
            # Kimliği olmayan sentetik/eski kayıtları birbirine birleştirme.
            final_decisions[identity if source and row else (index,)] = audit
        for audit in final_decisions.values():
            # Aynı banka/bölge adı farklı Türkçe karakter veya yazımıyla
            # gelirse simülasyonda ayrı satır oluşturmamalı.
            region = compact_key(audit.get("region", ""))
            bank = bank_key(audit.get("bank", ""))
            if not region:
                ignored += 1
                continue
            key = (region, bank)
            entry = buckets.setdefault(
                key,
                {
                    "manim_total": Decimal("0.00"), "netsis_total": Decimal("0.00"),
                    "payment_total": Decimal("0.00"), "reference_total": Decimal("0.00"),
                    "virman_total": Decimal("0.00"), "rule_total": Decimal("0.00"),
                    "review_total": Decimal("0.00"), "record_count": 0, "details": [],
                },
            )
            amount = _money(audit.get("amount"))
            entry["manim_total"] += amount
            entry["record_count"] += 1
            outcome = str(audit.get("outcome", "")).strip().upper()
            if outcome == "SKIPPED":
                outcome = "REVIEW"
            entry["details"].append(SimulationDetail(
                source_file=str(audit.get("source_file", "")),
                source_row=int(audit.get("source_row", 0) or 0),
                amount=amount,
                outcome=outcome,
                rule_code=str(audit.get("rule_code", "")),
            ))
            if outcome in self._NETSIS_OUTCOMES:
                entry["netsis_total"] += amount
            category = self._CATEGORIES.get(outcome)
            if category:
                entry[category] += amount
        if netsis_records is not None:
            for entry in buckets.values():
                entry["netsis_total"] = Decimal("0.00")
            for record in netsis_records:
                key = (compact_key(record.bolge), bank_key(record.banka))
                if key not in buckets:
                    # Çıktının kaynağı bulunamıyorsa bunu sessizce doğrulama.
                    ignored += 1
                    continue
                buckets[key]["netsis_total"] += _money(record.tutar)
        for entry in buckets.values():
            matched_source = sum((d.amount for d in entry["details"] if d.outcome in self._NETSIS_OUTCOMES), Decimal("0.00"))
            retained = matched_source - entry["netsis_total"]
            entry["pending_total"] = max(retained, Decimal("0.00"))
            entry["unaccounted_total"] = entry["manim_total"] - sum(
                (entry[name] for name in ("netsis_total", "payment_total", "reference_total", "virman_total", "rule_total", "review_total", "pending_total")), Decimal("0.00")
            )
            entry["details"] = tuple(entry["details"])
        result = tuple(
            SimulationBucket(region=region, bank=bank, **values)
            for (region, bank), values in sorted(buckets.items())
        )
        return SimulationSummary(buckets=result, ignored_records=ignored)


def simulation_summary_payload(summary: SimulationSummary | None) -> dict:
    """Persist a non-sensitive, exact post-operation distribution snapshot."""
    if summary is None:
        return {"version": 1, "ignored_records": 0, "buckets": []}
    return {
        "version": 1,
        "ignored_records": int(summary.ignored_records),
        "buckets": [
            {
                "region": bucket.region,
                "bank": bucket.bank,
                "manim_total": str(bucket.manim_total),
                "netsis_total": str(bucket.netsis_total),
                "payment_total": str(bucket.payment_total),
                "reference_total": str(bucket.reference_total),
                "virman_total": str(bucket.virman_total),
                "rule_total": str(bucket.rule_total),
                "review_total": str(bucket.review_total),
                "pending_total": str(bucket.pending_total),
                "unaccounted_total": str(bucket.unaccounted_total),
                "incoming_total": str(bucket.incoming_total),
                "outgoing_total": str(bucket.outgoing_total),
                "record_count": int(bucket.record_count),
            }
            for bucket in summary.buckets
        ],
    }


def simulation_summary_from_payload(payload: object) -> SimulationSummary | None:
    """Read a persisted distribution defensively; corrupted history stays visible."""
    if not isinstance(payload, dict) or payload.get("version") != 1:
        return None
    raw_buckets = payload.get("buckets")
    if not isinstance(raw_buckets, list):
        return None
    try:
        buckets = []
        for raw in raw_buckets:
            if not isinstance(raw, dict):
                return None
            buckets.append(
                SimulationBucket(
                    region=str(raw["region"]),
                    bank=str(raw["bank"]),
                    manim_total=_money(raw["manim_total"]),
                    netsis_total=_money(raw["netsis_total"]),
                    payment_total=_money(raw["payment_total"]),
                    reference_total=_money(raw["reference_total"]),
                    virman_total=_money(raw["virman_total"]),
                    rule_total=_money(raw["rule_total"]),
                    review_total=_money(raw["review_total"]),
                    pending_total=_money(raw["pending_total"]),
                    unaccounted_total=_money(raw["unaccounted_total"]),
                    record_count=max(0, int(raw["record_count"])),
                    details=(),
                    incoming_total_snapshot=_money(raw["incoming_total"]),
                    outgoing_total_snapshot=_money(raw["outgoing_total"]),
                )
            )
        ignored = max(0, int(payload.get("ignored_records", 0)))
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return None
    return SimulationSummary(tuple(buckets), ignored_records=ignored)


def attach_simulation_details(
    summary: SimulationSummary,
    decision_audits: Iterable[dict],
) -> SimulationSummary:
    """Attach drill-down rows from the ledger without changing exact totals."""
    detail_summary = OperationSimulation().summarize(decision_audits)
    details_by_key = {
        (bucket.region, bucket.bank): bucket.details
        for bucket in detail_summary.buckets
    }
    return SimulationSummary(
        tuple(
            replace(
                bucket,
                details=details_by_key.get((bucket.region, bucket.bank), ()),
            )
            for bucket in summary.buckets
        ),
        ignored_records=summary.ignored_records,
    )
