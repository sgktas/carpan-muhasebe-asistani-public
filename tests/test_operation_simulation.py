from decimal import Decimal
from types import SimpleNamespace

from app.core.operation_simulation import (
    OperationSimulation,
    attach_simulation_details,
    simulation_summary_from_payload,
    simulation_summary_payload,
)


def test_simulation_groups_regions_banks_and_separates_netsis_total():
    summary = OperationSimulation().summarize([
        {"region": "Antalya", "bank": "Garanti", "amount": 100, "outcome": "HAVALE"},
        {"region": "ANTALYA", "bank": "GARANTİ", "amount": 25.5, "outcome": "REVIEW"},
        {"region": "Aydın", "bank": "Ziraat", "amount": 40, "outcome": "ODEME_ONAYLANDI"},
    ])
    assert len(summary.buckets) == 2
    antalya = next(item for item in summary.buckets if item.region == "ANTALYA")
    assert antalya.manim_total == Decimal("125.50")
    assert antalya.netsis_total == Decimal("100.00")
    assert antalya.review_total == Decimal("25.50")
    assert antalya.difference == Decimal("25.50")
    assert summary.manim_total == Decimal("165.50")


def test_simulation_is_read_only_and_ignores_missing_region():
    audits = [{"region": "", "bank": "Garanti", "amount": 10, "outcome": "HAVALE"}]
    summary = OperationSimulation().summarize(audits)
    assert summary.buckets == ()
    assert summary.ignored_records == 1


def audit(row, amount, outcome, **extra):
    return {"source_file": "bank.xlsx", "source_row": row, "region": "ANTALYA",
            "bank": "Garanti", "amount": amount, "outcome": outcome, **extra}


def test_final_decision_is_counted_once_for_each_combined_member():
    audits = [audit(2, 70978, "REVIEW"), audit(3, 77000, "REVIEW"),
              audit(2, 70978, "HAVALE"), audit(3, 77000, "HAVALE")]
    summary = OperationSimulation().summarize(audits)
    assert summary.manim_total == summary.netsis_total == Decimal("147978.00")
    assert summary.buckets[0].record_count == 2
    assert summary.buckets[0].review_total == 0
    assert isinstance(summary.buckets[0].details, tuple)
    assert audits[0]["outcome"] == "REVIEW"


def test_separate_routes_are_not_a_false_financial_difference():
    summary = OperationSimulation().summarize([
        audit(1, 100, "HAVALE"), audit(2, 50, "ODEME_ONAYLANDI"),
        audit(3, -20, "SAME_BANK_VIRMAN"), audit(4, -10, "REFERANSLI"),
        audit(5, 30, "KURAL_CALISTI"),
    ])
    bucket = summary.buckets[0]
    assert bucket.incoming_total == 180
    assert bucket.outgoing_total == 30
    assert bucket.virman_total == -20
    assert bucket.unaccounted_total == 0
    assert bucket.difference == 50
    assert not summary.needs_attention


def test_partial_approval_uses_actual_planned_output_not_whole_source_amount():
    summary = OperationSimulation().summarize(
        [audit(2, 100, "REVIEW"), audit(2, 100, "HAVALE")],
        netsis_records=[SimpleNamespace(bolge="ANTALYA", banka="Garanti", tutar=60)],
    )
    bucket = summary.buckets[0]
    assert bucket.netsis_total == 60
    assert bucket.pending_total == 40
    assert bucket.unaccounted_total == 0
    assert summary.needs_attention


def test_output_larger_than_source_is_an_unaccounted_difference():
    summary = OperationSimulation().summarize(
        [audit(2, 100, "HAVALE")],
        netsis_records=[SimpleNamespace(bolge="ANTALYA", banka="Garanti", tutar=110)],
    )
    assert summary.buckets[0].unaccounted_total == -10
    assert summary.needs_attention


def test_equal_grand_totals_do_not_hide_region_or_route_changes():
    before = OperationSimulation().summarize([audit(2, 100, "HAVALE")])
    after = OperationSimulation().summarize([audit(2, 100, "HAVALE", region="BODRUM")])
    assert before.netsis_total == after.netsis_total
    assert not before.matches(after)


def test_positive_and_negative_review_do_not_cancel_attention():
    summary = OperationSimulation().summarize([audit(2, 100, "REVIEW"), audit(3, -100, "SKIPPED")])
    assert summary.buckets[0].review_total == 0
    assert summary.needs_attention


def test_unknown_route_and_unattributed_output_are_visible():
    summary = OperationSimulation().summarize([audit(2, 100, "UNKNOWN")], netsis_records=[
        SimpleNamespace(bolge="BODRUM", banka="Garanti", tutar=100)
    ])
    assert summary.buckets[0].unaccounted_total == 100
    assert summary.ignored_records == 1
    assert not summary.matches(summary)


def test_persisted_operation_result_preserves_exact_partial_output_total():
    summary = OperationSimulation().summarize(
        [audit(2, 100, "HAVALE")],
        netsis_records=[SimpleNamespace(bolge="ANTALYA", banka="Garanti", tutar=60)],
    )

    restored = simulation_summary_from_payload(simulation_summary_payload(summary))

    assert restored.manim_total == summary.manim_total
    assert restored.buckets[0].netsis_total == Decimal("60.00")
    assert restored.buckets[0].pending_total == Decimal("40.00")
    assert restored.buckets[0].incoming_total == Decimal("100.00")
    assert restored.buckets[0].details == ()

    hydrated = attach_simulation_details(restored, [audit(2, 100, "HAVALE")])
    assert len(hydrated.buckets[0].details) == 1
    assert hydrated.buckets[0].netsis_total == Decimal("60.00")


def test_corrupted_persisted_operation_result_is_not_presented_as_valid():
    assert simulation_summary_from_payload({"version": 1, "buckets": None}) is None
    assert simulation_summary_from_payload({"version": 99, "buckets": []}) is None
