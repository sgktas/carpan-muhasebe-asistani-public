from collections import defaultdict
from datetime import datetime

from app.core.output_profile import OutputProfileStore
from app.core.processing_engine import ProcessingEngine, ProcessingResult, UnresolvedItem
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


def test_multiple_bank_movements_with_difference_become_one_manual_group(synthetic_project):
    project_root = synthetic_project[3]
    engine = ProcessingEngine([], project_root)
    profile = OutputProfileStore(project_root / "config").get("netsis")
    suggestions = [TahsilatRecord("C001", "TEST", None, 600)]

    remaining = engine._match_combined_bank_movements(
        _pending([100, 200, 250], suggestions),
        defaultdict(list),
        ProcessingResult(),
        profile,
        _Processor(),
    )

    assert len(remaining) == 1
    assert len(remaining[0].group_records) == 3
    assert remaining[0].group_target_amount == 600


def test_one_cent_difference_is_not_combined_automatically(synthetic_project):
    project_root = synthetic_project[3]
    engine = ProcessingEngine([], project_root)
    profile = OutputProfileStore(project_root / "config").get("netsis")
    suggestions = [TahsilatRecord("C001", "TEST", None, 600.01)]

    remaining = engine._match_combined_bank_movements(
        _pending([100, 200, 300], suggestions),
        defaultdict(list),
        ProcessingResult(),
        profile,
        _Processor(),
    )

    assert len(remaining) == 1
    assert len(remaining[0].group_records) == 3
