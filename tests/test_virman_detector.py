from datetime import datetime
import json

from app.core.region_config import RegionConfig
from app.core.virman_detector import VirmanDetector
from app.models.records import ManimRecord


def _config(tmp_path):
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
                    "banka_kodlari": {"GARANTI": "BANK-G-01", "YKB": "BANK-Y-01"},
                    "manim_hesap_kodlari": {"GARANTI": "1001", "YKB": "2001"},
                },
                "ANTALYA": {
                    "aktif": True,
                    "sira": 2,
                    "proje_kodu": 105,
                    "banka_kodlari": {"GARANTI": "BANK-G-05", "YKB": "BANK-Y-05"},
                    "manim_hesap_kodlari": {"GARANTI": "1005", "YKB": "2005"},
                },
            }
        ),
        encoding="utf-8",
    )
    return RegionConfig(path)


def _record(description: str, amount: float = -1250, bank: str = "Garanti"):
    return ManimRecord(
        banka=bank,
        sube="TEST-1001",
        islem_tarihi=datetime(2026, 9, 6, 10, 15),
        aciklama=description,
        tutar=amount,
        dekont_durumu="Referanslı",
        karsi_hesap_adi="",
        karsi_hesap_kodu="",
        kaynak_dosya="test.xlsx",
        kaynak_satir=2,
    )


def test_negative_internal_virman_uses_source_and_target_bank_codes(tmp_path):
    detector = VirmanDetector(_config(tmp_path))

    result = detector.detect(
        _record("INT-HVL-1001 DEN 1005 HES VIRMAN"),
        "BODRUM",
    )

    assert result.record is not None
    assert result.record.kaynak_banka_hesap_kodu == "BANK-G-01"
    assert result.record.hedef_banka_hesap_kodu == "BANK-G-05"
    assert result.record.tutar == 1250
    assert result.record.islem_tarihi_metni == "06.09.2026"
    assert result.record.proje_kodu == 101
    assert result.record.muh_ref_kodu == "R00"
    assert result.record.plasiyer_kodu == "TEST"


def test_positive_reference_is_not_virman_output(tmp_path):
    detector = VirmanDetector(_config(tmp_path))
    result = detector.detect(_record("1005 HES VIRMAN", amount=1250), "BODRUM")
    assert result.record is None
    assert result.candidate is False


def test_unrelated_negative_payment_stays_in_reference_output(tmp_path):
    detector = VirmanDetector(_config(tmp_path))
    result = detector.detect(_record("TEDARIKCI FATURA ODEMESI TRTEST9999"), "BODRUM")
    assert result.record is None
    assert result.candidate is False


def test_unknown_virman_target_is_flagged_but_not_exported(tmp_path):
    detector = VirmanDetector(_config(tmp_path))
    result = detector.detect(_record("BILINMEYEN 9999 HES VIRMAN"), "BODRUM")
    assert result.record is None
    assert result.candidate is True
    assert "hedef hesap" in result.reason


def test_outgoing_transfer_to_known_own_account_is_detected(tmp_path):
    detector = VirmanDetector(_config(tmp_path))
    result = detector.detect(
        _record("GIDEN HAVALE SIRKET HESABI TRTESTTESTTESTTESTTEST2005", bank="YapıKredi"),
        "BODRUM",
    )
    assert result.record is not None
    assert result.record.kaynak_banka_hesap_kodu == "BANK-Y-01"
    assert result.record.hedef_banka_hesap_kodu == "BANK-Y-05"


def test_reference_number_suffix_alone_does_not_create_false_virman(tmp_path):
    detector = VirmanDetector(_config(tmp_path))
    result = detector.detect(
        _record("VIRMAN REFERANS X98765A41005"),
        "BODRUM",
    )

    assert result.record is None
    assert result.candidate is True
