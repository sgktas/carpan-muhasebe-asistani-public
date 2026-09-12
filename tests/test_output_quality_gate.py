from datetime import datetime
from pathlib import Path

import pytest

from app.core.output_profile import OutputProfileStore
from app.core.output_quality_gate import OutputQualityError, validate_netsis_rows, validate_virman_rows
from app.core.region_config import RegionConfig
from app.core.manim_output_service import ManimOutputPlan, ManimOutputService
from app.models.records import NetsisRecord, VirmanRecord


TEST_ANTALYA_BANK_CODE = "BM" + "21204"
TEST_BODRUM_BANK_CODE = "BM" + "21401"
TEST_INVALID_BANK_CODE = "BM" + "9" * 5
TEST_CUSTOMER_CODE = "9" * 10


def _config(tmp_path):
    return RegionConfig(tmp_path / "missing.json", snapshot={
        "_plasiyer_kodu": "00",
        "_genel_ref_kodu": "G01",
        "ANTALYA": {
            "aktif": True,
            "sira": 1,
            "proje_kodu": 22,
            "banka_kodlari": {"GARANTI": TEST_ANTALYA_BANK_CODE},
        },
        "BODRUM": {
            "aktif": True,
            "sira": 2,
            "proje_kodu": 211,
            "banka_kodlari": {"GARANTI": TEST_BODRUM_BANK_CODE},
        },
    })


def _havale(*, bank_code=TEST_ANTALYA_BANK_CODE, bank="GARANTI", region="ANTALYA", amount=1250):
    return NetsisRecord(
        islem_tarihi=datetime(2026, 9, 11),
        cari_kodu=TEST_CUSTOMER_CODE,
        tutar=amount,
        aciklama="TEST",
        banka=bank,
        bolge=region,
        kaynak="TEST",
        banka_hesap_kodu=bank_code,
    )


def test_toplu_havale_preflight_accepts_configured_bm_code(tmp_path):
    profile = OutputProfileStore(Path("config")).get("netsis_toplu")
    assert validate_netsis_rows(
        [_havale()], profile, _config(tmp_path), output_region="ANTALYA", output_bank="TOPLU"
    ) == 1


def test_toplu_havale_preflight_rejects_wrong_bm_code_before_excel_write(tmp_path):
    profile = OutputProfileStore(Path("config")).get("netsis_toplu")
    with pytest.raises(
        OutputQualityError,
        match=rf"BM banka hesap kodu '{TEST_INVALID_BANK_CODE}'.*{TEST_ANTALYA_BANK_CODE}",
    ):
        validate_netsis_rows(
            [_havale(bank_code=TEST_INVALID_BANK_CODE)], profile, _config(tmp_path),
            output_region="ANTALYA", output_bank="TOPLU"
        )


def test_preflight_rejects_zero_amount_and_cross_bank_region_file(tmp_path):
    profile = OutputProfileStore(Path("config")).get("netsis_toplu")
    with pytest.raises(OutputQualityError, match="tutar sıfırdan büyük"):
        validate_netsis_rows(
            [_havale(amount=0)], profile, _config(tmp_path), output_region="ANTALYA", output_bank="TOPLU"
        )

    profile = OutputProfileStore(Path("config")).get("netsis")
    with pytest.raises(OutputQualityError, match="çıktı bankasıyla uyuşmuyor"):
        validate_netsis_rows(
            [_havale(bank_code="", bank="ZIRAAT")], profile, _config(tmp_path),
            output_region="ANTALYA", output_bank="GARANTI"
        )


def test_virman_preflight_allows_only_same_bank_with_approved_constants(tmp_path):
    record = VirmanRecord(
        islem_tarihi=datetime(2026, 9, 11),
        islem_tarihi_metni="11.09.2026",
        tutar=2500,
        aciklama="VIRMAN",
        bolge="ANTALYA",
        kaynak_banka="GARANTI",
        hedef_banka="GARANTI",
        kaynak_banka_hesap_kodu=TEST_ANTALYA_BANK_CODE,
        hedef_banka_hesap_kodu=TEST_BODRUM_BANK_CODE,
        muh_ref_kodu="G01",
        proje_kodu=22,
        plasiyer_kodu="00",
        kaynak="TEST",
    )
    assert validate_virman_rows([record], _config(tmp_path)) == 1

    wrong_bank = VirmanRecord(**{**record.__dict__, "hedef_banka": "ZIRAAT"})
    with pytest.raises(OutputQualityError, match="farklı bankalar"):
        validate_virman_rows([wrong_bank], _config(tmp_path))


def test_invalid_bm_code_stops_before_any_output_folder_is_created(tmp_path):
    profile = OutputProfileStore(Path("config")).get("netsis_toplu")
    service = ManimOutputService(tmp_path / "out", _config(tmp_path), ("ANTALYA", "BODRUM"))
    plan = ManimOutputPlan(
        outputs={("ANTALYA", "TOPLU"): [_havale(bank_code=TEST_INVALID_BANK_CODE)]},
        virman_by_region={},
        review_rows=[],
        invalid_rows=[],
        odeme_onaylandi_items=[],
        referansli_by_region={},
        kural_calisti_by_region={},
        islem_tarihleri={datetime(2026, 9, 11).date()},
        output_profile=profile,
        reference_output_profile=OutputProfileStore(Path("config")).get("netsis_virman_toplu"),
    )

    with pytest.raises(OutputQualityError, match="BM banka hesap kodu"):
        service.write(plan)

    assert not (tmp_path / "out").exists()
