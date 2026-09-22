from collections import defaultdict
from datetime import datetime
from decimal import Decimal

import pytest

from app.core.output_profile import OutputProfileStore
from app.core.processing_engine import ProcessingEngine, ProcessingResult, UnresolvedItem
from app.core.manim_resolution import CombinedBankMovementMatcher, ManualResolution, ManualResolutionService
from app.core.tahsilat_consumption_ledger import TahsilatConsumptionError, TahsilatConsumptionLedger
from app.models.records import ManimRecord, NetsisRecord, TahsilatRecord


def _movement(amount: float, row: int) -> ManimRecord:
    return ManimRecord(
        banka="Garanti",
        sube="TEST",
        islem_tarihi=datetime(2026, 9, 5, 10, row),
        aciklama=f"AYNI MUSTERI PARCA {row}",
        tutar=amount,
        dekont_durumu="Aktarıldı",
        karsi_hesap_adi="ZINCIR TEST",
        karsi_hesap_kodu="",
        kaynak_dosya="test.xlsx",
        kaynak_satir=row,
    )


class _Processor:
    @staticmethod
    def _netsis_record(source, customer_code, amount, source_type):
        return NetsisRecord(
            islem_tarihi=source.islem_tarihi,
            cari_kodu=customer_code,
            tutar=amount,
            aciklama=source.aciklama,
            banka=source.banka,
            bolge="",
            kaynak=source_type,
        )


def _pending(amounts, suggestions):
    return [
        UnresolvedItem(
            record=_movement(amount, index + 2),
            region="BODRUM",
            reason="Tutar farkı",
            suggested_rows=list(suggestions),
        )
        for index, amount in enumerate(amounts)
    ]


def test_three_matching_bank_movements_are_combined_automatically(synthetic_project):
    project_root = synthetic_project[3]
    engine = ProcessingEngine([], project_root)
    profile = OutputProfileStore(project_root / "config").get("netsis")
    suggestions = [
        TahsilatRecord("C001", "TEST 1", None, 250),
        TahsilatRecord("C002", "TEST 2", None, 350),
    ]
    outputs = defaultdict(list)
    result = ProcessingResult()

    remaining = engine._match_combined_bank_movements(
        _pending([100, 200, 300], suggestions),
        outputs,
        result,
        profile,
        _Processor(),
    )

    assert remaining == []
    assert result.produced_netsis_records == 2
    assert sum(row.tutar for rows in outputs.values() for row in rows) == 600
    assert any("3 banka hareketi" in log for log in result.logs)
    assert len(result.decision_audits) == 3
    assert {
        audit["rule_code"] for audit in result.decision_audits
    } == {"COMBINED_BANK_MOVEMENTS_EXACT"}
    assert {audit["outcome"] for audit in result.decision_audits} == {"HAVALE"}


def test_multiple_bank_movements_with_difference_become_one_manual_group(synthetic_project):
    project_root = synthetic_project[3]
    engine = ProcessingEngine([], project_root)
    profile = OutputProfileStore(project_root / "config").get("netsis")
    suggestions = [TahsilatRecord("C001", "TEST", None, 600)]

    result = ProcessingResult()
    remaining = engine._match_combined_bank_movements(
        _pending([100, 200, 250], suggestions),
        defaultdict(list),
        result,
        profile,
        _Processor(),
    )

    assert len(remaining) == 1
    assert len(remaining[0].group_records) == 3
    # Manuel hedef tahsilat önerisi değil gerçek banka hareketleri toplamıdır.
    assert remaining[0].group_target_amount == 550
    assert len(result.decision_audits) == 3
    assert {audit["outcome"] for audit in result.decision_audits} == {"REVIEW"}
    assert {
        audit["rule_code"] for audit in result.decision_audits
    } == {"COMBINED_BANK_MOVEMENTS_DIFFERENCE"}


def test_one_cent_difference_is_balanced_automatically(synthetic_project):
    project_root = synthetic_project[3]
    engine = ProcessingEngine([], project_root)
    profile = OutputProfileStore(project_root / "config").get("netsis")
    suggestions = [TahsilatRecord("C001", "TEST", None, 600.01)]
    outputs = defaultdict(list)
    result = ProcessingResult()

    remaining = engine._match_combined_bank_movements(
        _pending([100, 200, 300], suggestions),
        outputs,
        result,
        profile,
        _Processor(),
    )

    assert remaining == []
    assert sum(row.tutar for rows in outputs.values() for row in rows) == 600
    assert {audit["rule_code"] for audit in result.decision_audits} == {
        "COMBINED_BANK_MOVEMENTS_CENT_BALANCED"
    }


def test_manual_combined_group_accepts_missing_collection_completed_by_user(synthetic_project):
    project_root = synthetic_project[3]
    engine = ProcessingEngine([], project_root)
    profile = OutputProfileStore(project_root / "config").get("netsis")
    suggestions = [TahsilatRecord("C001", "RAPORDA VAR", None, 500)]
    result = ProcessingResult()
    pending = engine._match_combined_bank_movements(
        _pending([100, 200, 250], suggestions),
        defaultdict(list),
        result,
        profile,
        _Processor(),
    )
    assert len(pending) == 1
    assert pending[0].group_target_amount == 550

    outputs = defaultdict(list)
    manual = ManualResolution(
        route="HAVALE",
        rows=[
            TahsilatRecord("C001", "RAPORDA VAR", None, 500),
            TahsilatRecord("C002", "MANUEL EKLENEN", None, 50),
        ],
    )
    outcome = ManualResolutionService(engine.region_config).apply(
        pending=pending,
        resolutions={0: manual},
        outputs=outputs,
        output_profile=profile,
        processor=_Processor(),
        movement_router=object(),
        virman_by_region=defaultdict(list),
        referansli_by_region=defaultdict(list),
        odeme_onaylandi_items=[],
    )

    assert outcome.pending == []
    assert outcome.produced_netsis_records == 2
    assert sum(row.tutar for rows in outputs.values() for row in rows) == 550
    assert any("Toplu havale manuel onaylandı" in line for line in outcome.logs)


@pytest.mark.parametrize('bank_total', ['599.99', '600.00', '600.01'])
def test_combined_rounding_preserves_source_consumption_and_retry(synthetic_project, tmp_path, bank_total):
    engine = ProcessingEngine([], synthetic_project[3])
    profile = OutputProfileStore(synthetic_project[3] / 'config').get('netsis')
    sources = [
        TahsilatRecord('TEST-A', 'Synthetic A', None, 250, 'synthetic-source', 'Sheet1', 2, 250),
        TahsilatRecord('TEST-B', 'Synthetic B', None, 350, 'synthetic-source', 'Sheet1', 3, 350),
    ]
    ledger = TahsilatConsumptionLedger(tmp_path / 'rounding.sqlite3', company_id=1)
    matcher = CombinedBankMovementMatcher(engine.region_config)
    outputs = defaultdict(list)
    result = matcher.match(
        _pending([100, float(Decimal(bank_total) - 100)], sources), outputs, profile, _Processor(),
    )
    assert result.pending == []
    assert sum(Decimal(str(row.tutar)) for rows in outputs.values() for row in rows) == Decimal(bank_total)
    assert result.consumption_rows == sources
    ledger.assert_can_consume(result.consumption_rows)
    ledger.consume(result.consumption_rows, operation_id=10)
    assert ledger.available_rows(sources) == []
    assert all(balance.remaining_amount == 0 for balance in ledger.balances(sources))
    with pytest.raises(TahsilatConsumptionError):
        ledger.assert_can_consume(result.consumption_rows)
    retry_rows = ledger.available_rows(sources, reusable_operation_ids=[10])
    retry = matcher.match(
        _pending([100, float(Decimal(bank_total) - 100)], retry_rows),
        defaultdict(list), profile, _Processor(),
    )
    ledger.assert_can_consume(retry.consumption_rows, reusable_operation_ids=[10])
    ledger.replace_for_retry(retry.consumption_rows, operation_id=11, reusable_operation_ids=[10])
    assert ledger.available_rows(sources) == []
    assert [balance.consumed_amount for balance in ledger.balances(sources)] == [250, 350]


@pytest.mark.parametrize('bank_total', [599.98, 600.02])
def test_combined_rounding_does_not_consume_larger_differences(synthetic_project, bank_total):
    engine = ProcessingEngine([], synthetic_project[3])
    profile = OutputProfileStore(synthetic_project[3] / 'config').get('netsis')
    sources = [TahsilatRecord('TEST', 'Synthetic', None, 600, 'source', 'Sheet1', 2, 600)]
    outputs = defaultdict(list)
    result = CombinedBankMovementMatcher(engine.region_config).match(
        _pending([100, bank_total - 100], sources), outputs, profile, _Processor(),
    )
    assert len(result.pending) == 1
    assert result.consumption_rows == []
    assert not outputs


def test_same_customer_group_key_combines_chain_movements(
    synthetic_project,
):
    """Aynı zincir anahtarı, banka hareketlerini güvenle birleştirir."""
    project_root = synthetic_project[3]
    engine = ProcessingEngine([], project_root)
    profile = OutputProfileStore(project_root / "config").get("netsis")
    chain_rows = [
        TahsilatRecord("C001", "ZINCIR 1", None, 250),
        TahsilatRecord("C002", "ZINCIR 2", None, 350),
    ]
    pending = [
        UnresolvedItem(
            record=_movement(amount, index + 2),
            region="BODRUM",
            reason="Tutar farkı",
            # Bu anahtar, tek hareketin miktarına göre oluşan aday imzasının
            # yerine aynı hukuki müşteri grubunu temsil eder.
            suggested_rows=chain_rows,
            combined_group_key="VKN:TEST-ZINCIR",
        )
        for index, amount in enumerate([100, 200, 300])
    ]
    remaining = engine._match_combined_bank_movements(
        pending,
        defaultdict(list),
        ProcessingResult(),
        profile,
        _Processor(),
    )

    assert remaining == []
