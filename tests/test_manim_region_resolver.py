from datetime import datetime

from app.core.manim_region_resolver import ManimRegionResolver
from app.models.records import CustomerRecord, ManimRecord


class FakeRegionConfig:
    def find_region_by_manim_account(self, bank, account):
        if (bank, account) == ("GARANTI", "506"):
            return "NAZILLI"
        return None

    def find_region_in_text(self, value):
        text = str(value).upper()
        return next(
            (region for region in ("AYDIN", "NAZILLI", "ANTALYA") if region in text),
            None,
        )


def _record(**changes):
    values = {
        "banka": "Garanti",
        "sube": "",
        "islem_tarihi": datetime(2026, 9, 1),
        "aciklama": "test",
        "tutar": 100.0,
        "dekont_durumu": "Aktarıldı",
        "karsi_hesap_adi": "Örnek Müşteri",
        "karsi_hesap_kodu": "123",
        "kaynak_dosya": "AYDIN MANIM.xlsx",
        "kaynak_satir": 2,
    }
    values.update(changes)
    return ManimRecord(**values)


def test_account_code_has_priority_over_file_region():
    resolver = ManimRegionResolver(
        FakeRegionConfig(),
        ("AYDIN", "NAZILLI", "ANTALYA"),
    )

    assert resolver.for_record(_record(sube="506"), "AYDIN") == "NAZILLI"


def test_unique_customer_region_is_used_when_account_does_not_resolve():
    resolver = ManimRegionResolver(
        FakeRegionConfig(),
        ("AYDIN", "NAZILLI", "ANTALYA"),
    )
    customers = [
        CustomerRecord("123", "Örnek Müşteri", "1", "BAT-ANTALYA"),
    ]
    code_index, name_index = resolver.customer_indexes(customers)

    assert resolver.for_record(
        _record(), "AYDIN", code_index, name_index
    ) == "ANTALYA"


def test_ambiguous_customer_name_is_not_used_as_region_evidence():
    resolver = ManimRegionResolver(
        FakeRegionConfig(),
        ("AYDIN", "NAZILLI", "ANTALYA"),
    )
    customers = [
        CustomerRecord("1", "Zincir Mağaza", "1", "BAT-AYDIN"),
        CustomerRecord("2", "Zincir Mağaza", "1", "BAT-ANTALYA"),
    ]
    code_index, name_index = resolver.customer_indexes(customers)

    assert "ZINCIRMAGAZA" not in name_index
    assert resolver.for_record(
        _record(karsi_hesap_kodu="", karsi_hesap_adi="Zincir Mağaza"),
        "NAZILLI",
        code_index,
        name_index,
    ) == "NAZILLI"


def test_file_name_normalization_handles_turkish_letters():
    resolver = ManimRegionResolver(FakeRegionConfig(), ("MUGLA", "FETHIYE"))

    assert resolver.from_file_name("MUĞLA05.09.2026 - Manim.xlsx") == "MUGLA"
