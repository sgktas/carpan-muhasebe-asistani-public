from datetime import datetime
import json

import pytest

from app.core.movement_classifier import MovementRoute
from app.core.movement_router import MovementRouter
from app.core.region_config import RegionConfig
from app.models.records import ManimRecord


def _config(tmp_path) -> RegionConfig:
    path = tmp_path / "regions.json"
    path.write_text(
        json.dumps(
            {
                "_plasiyer_kodu": "TEST",
                "_genel_ref_kodu": "R00",
                "BODRUM": {
                    "aktif": True,
                    "sira": 1,
                    "proje_kodu": 101,
                    "banka_kodlari": {
                        "GARANTI": "BANK-G-01",
                        "YKB": "BANK-Y-01",
                    },
                    "manim_hesap_kodlari": {
                        "GARANTI": "1001",
                        "YKB": "2001",
                    },
                },
                "ANTALYA": {
                    "aktif": True,
                    "sira": 2,
                    "proje_kodu": 105,
                    "banka_kodlari": {
                        "GARANTI": "BANK-G-05",
                        "YKB": "BANK-Y-05",
                    },
                    "manim_hesap_kodlari": {
                        "GARANTI": "1005",
                        "YKB": "2005",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return RegionConfig(path)


def _record(
    status: str,
    *,
    amount: float = 100,
    description: str = "TEST",
    bank: str = "Garanti",
) -> ManimRecord:
    return ManimRecord(
        banka=bank,
        sube="TEST-1001",
        islem_tarihi=datetime(2026, 9, 6),
        aciklama=description,
        tutar=amount,
        dekont_durumu=status,
        karsi_hesap_adi="",
        karsi_hesap_kodu="",
        kaynak_dosya="test.xlsx",
        kaynak_satir=2,
    )


@pytest.mark.parametrize(
    ("record", "expected_route", "expected_code"),
    [
        (
            _record("Ödeme Onaylandı"),
            MovementRoute.ODEME_ONAYLANDI,
            "PAYMENT_APPROVED",
        ),
        (
            _record("Ödeme Onaylandı", amount=-100),
            MovementRoute.REVIEW,
            "NEGATIVE_PAYMENT_APPROVAL",
        ),
        (
            _record("Kural Çalıştı"),
            MovementRoute.KURAL_CALISTI,
            "RULE_TRIGGERED",
        ),
        (
            _record("Referanslı", description="ROTA104 YATAN PARA"),
            MovementRoute.REVIEW,
            "AMBIGUOUS_STAFF_DEPOSIT",
        ),
        (
            _record("Aktarıldı"),
            MovementRoute.HAVALE,
            "TRANSFER",
        ),
    ],
)
def test_router_preserves_status_priority(
    tmp_path,
    record,
    expected_route,
    expected_code,
):
    decision = MovementRouter(_config(tmp_path)).route(record, "BODRUM")
    assert decision.route == expected_route
    assert decision.code == expected_code


def test_router_extracts_only_same_bank_reference_virman(tmp_path):
    router = MovementRouter(_config(tmp_path))
    same_bank = router.route(
        _record(
            "Referanslı",
            amount=-1250,
            description="INT-HVL-1001 DEN 1005 HES VIRMAN",
        ),
        "BODRUM",
    )
    different_bank = router.route(
        _record(
            "Referanslı",
            amount=-1250,
            description="GIDEN HAVALE SIRKET HESABI TRTESTTESTTESTTESTTEST2005",
        ),
        "BODRUM",
    )

    assert same_bank.route == MovementRoute.SAME_BANK_VIRMAN
    assert same_bank.code == "SAME_BANK_INTERNAL_TRANSFER"
    assert same_bank.virman_record is not None
    assert same_bank.virman_record.kaynak_banka == "GARANTI"
    assert same_bank.virman_record.hedef_banka == "GARANTI"
    assert different_bank.route == MovementRoute.REFERANSLI
    assert different_bank.code == "REFERENCE"
    assert different_bank.virman_record is None


def test_router_keeps_uncertain_virman_in_reference_with_reason(tmp_path):
    decision = MovementRouter(_config(tmp_path)).route(
        _record(
            "Referanslı",
            amount=-1250,
            description="BILINMEYEN 9999 HES VIRMAN",
        ),
        "BODRUM",
    )

    assert decision.route == MovementRoute.REFERANSLI
    assert decision.code == "VIRMAN_REVIEW_REQUIRED"
    assert decision.candidate is True
    assert "hedef hesap" in decision.reason
