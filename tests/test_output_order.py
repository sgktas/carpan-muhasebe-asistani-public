import datetime as dt

import xlrd

from app.core.output_order import (
    bank_sort_key,
    region_file_prefix,
    region_sort_key,
    special_file_prefix,
)
from app.core.region_config import RegionConfig
from app.models.records import ManimRecord
from app.writers.odeme_onaylandi_writer import OdemeOnaylandiWriter


def _record(region: str, minute: int) -> ManimRecord:
    return ManimRecord(
        banka="Garanti",
        sube="123",
        islem_tarihi=dt.datetime(2026, 7, 20, 10, minute),
        aciklama=f"{region} TEST",
        tutar=1000 + minute,
        dekont_durumu="Ödeme Onaylandı",
        karsi_hesap_adi="",
        karsi_hesap_kodu="",
        kaynak_dosya=f"{region}.xlsx",
        kaynak_satir=minute + 2,
        ham_veri={},
    )


def test_region_ve_banka_siralama_anahtarlari():
    assert sorted(["MUGLA", "SOKE", "BODRUM", "FETHIYE"], key=region_sort_key) == [
        "BODRUM", "FETHIYE", "SOKE", "MUGLA"
    ]
    assert sorted(["ZIRAAT", "GARANTI", "YKB"], key=bank_sort_key) == [
        "GARANTI", "YKB", "ZIRAAT"
    ]


def test_yeni_bolgeler_ayar_sirasina_gore_siralanir():
    order = ("BODRUM", "FETHIYE", "SOKE", "MUGLA", "ANTALYA", "DENIZLI", "AYDIN", "NAZILLI")
    values = ["AYDIN", "MUGLA", "ANTALYA", "BODRUM", "DENIZLI"]
    assert sorted(values, key=lambda region: region_sort_key(region, order)) == [
        "BODRUM", "MUGLA", "ANTALYA", "DENIZLI", "AYDIN"
    ]
    assert region_file_prefix("ANTALYA", order) == "05"
    assert region_file_prefix("AYDIN", order) == "07"
    assert region_file_prefix("NAZILLI", order) == "08"
    assert special_file_prefix("ODEME_ONAYLANDI", order) == "09"
    assert special_file_prefix("REFERANSLI", order) == "10"
    assert special_file_prefix("KURAL_CALISTI", order) == "11"


def test_odeme_onaylandi_bolge_bolge_gruplu_yazilir(tmp_path):
    config = RegionConfig("config/bolge_kodlari.json")
    items = [
        (_record("MUGLA", 4), "MUGLA", "GARANTI"),
        (_record("BODRUM", 2), "BODRUM", "GARANTI"),
        (_record("SOKE", 3), "SOKE", "GARANTI"),
        (_record("FETHIYE", 2), "FETHIYE", "GARANTI"),
        (_record("BODRUM", 1), "BODRUM", "GARANTI"),
    ]

    output = OdemeOnaylandiWriter(config).write(items, tmp_path / "odeme.xls")
    book = xlrd.open_workbook(output)
    sheet = book.sheet_by_index(0)

    kasa_kodlari = [int(sheet.cell_value(row, 0)) for row in range(1, sheet.nrows)]
    assert kasa_kodlari == [1001, 1001, 1002, 1003, 1004]
    aciklamalar = [sheet.cell_value(row, 5) for row in range(1, sheet.nrows)]
    assert aciklamalar[:2] == ["BODRUM TEST", "BODRUM TEST"]


def test_odeme_onaylandi_yeni_bolgeleri_kodlariyla_yazar(tmp_path):
    config = RegionConfig("config/bolge_kodlari.json")
    items = [
        (_record("AYDIN", 3), "AYDIN", "GARANTI"),
        (_record("NAZILLI", 4), "NAZILLI", "GARANTI"),
        (_record("ANTALYA", 1), "ANTALYA", "GARANTI"),
        (_record("DENIZLI", 2), "DENIZLI", "GARANTI"),
    ]

    output = OdemeOnaylandiWriter(config).write(items, tmp_path / "yeni-bolgeler.xls")
    sheet = xlrd.open_workbook(output).sheet_by_index(0)
    assert [sheet.cell_value(row, 5) for row in range(1, sheet.nrows)] == [
        "ANTALYA TEST", "DENIZLI TEST", "AYDIN TEST", "NAZILLI TEST"
    ]
    assert [int(sheet.cell_value(row, 0)) for row in range(1, sheet.nrows)] == [
        1005, 1006, 1007, 1008
    ]
    assert [int(sheet.cell_value(row, 11)) for row in range(1, sheet.nrows)] == [
        105, 106, 107, 108
    ]
