import datetime as dt

import xlrd

from app.core.region_config import RegionConfig
from app.models.records import ManimRecord
from app.writers.referansli_writer import ReferansliWriter


def _record(region_note: str = ""):
    return ManimRecord(
        banka="Ziraat Bankası",
        sube="123",
        islem_tarihi=dt.datetime(2026, 7, 16, 11, 0, 0),
        aciklama=f"Referanslı Gelen Havale ALİ VELİ {region_note}".strip(),
        tutar=-1234.56,
        dekont_durumu="Referanslı Kayıt",
        karsi_hesap_adi="",
        karsi_hesap_kodu="",
        kaynak_dosya="test.xlsx",
        kaynak_satir=5,
        ham_veri={
            "Banka": "Ziraat Bankası",
            "Kod - Şube": "123",
            "İşlem Tarihi": dt.datetime(2026, 7, 16, 11, 0, 0),
            "Açıklama": "Referanslı Gelen Havale ALİ VELİ",
            "Tutar": -1234.56,
            "Dekont Durumu": "Referanslı Kayıt",
            "Karşı Hesap Adı": "",
            "Karşı Hesap Kodu": "",
            "Ekstra Sütun": "çıktıya gelmemeli",
        },
    )


def test_yalniz_bes_gerekli_sutun_yaziliyor(tmp_path):
    output_path = ReferansliWriter().write(
        {"FETHIYE": [_record()]},
        tmp_path / "referansli.xls",
    )
    book = xlrd.open_workbook(output_path, formatting_info=True)
    sheet = book.sheet_by_name("FETHIYE")
    assert sheet.row_values(0) == [
        "Banka", "İşlem Tarihi", "Açıklama", "Tutar", "Dekont Durumu"
    ]
    row = sheet.row_values(1)
    assert row[0] == "Ziraat Bankası"
    assert row[2] == "Referanslı Gelen Havale ALİ VELİ"
    assert row[3] == -1234.56
    assert row[4] == "Referanslı Kayıt"
    assert sheet.ncols == 5


def test_tarih_sutunu_saatsiz_formatlaniyor(tmp_path):
    output_path = ReferansliWriter().write(
        {"FETHIYE": [_record()]},
        tmp_path / "referansli.xls",
    )
    book = xlrd.open_workbook(output_path, formatting_info=True)
    sheet = book.sheet_by_name("FETHIYE")
    value = xlrd.xldate_as_datetime(sheet.cell_value(1, 1), book.datemode)
    assert value.hour == 0 and value.minute == 0
    xf = book.xf_list[sheet.cell_xf_index(1, 1)]
    assert book.format_map[xf.format_key].format_str.upper() == "DD.MM.YYYY"


def test_dort_bolge_sayfasi_her_zaman_onayli_sirada_olusturuluyor(tmp_path):
    output_path = ReferansliWriter().write(
        {
            "MUGLA": [_record("MUGLA")],
            "FETHIYE": [_record("FETHIYE")],
        },
        tmp_path / "referansli.xls",
    )
    book = xlrd.open_workbook(output_path)
    assert book.sheet_names() == ["BODRUM", "FETHIYE", "SOKE", "MUGLA"]
    assert book.sheet_by_name("BODRUM").nrows == 1
    assert book.sheet_by_name("SOKE").nrows == 1
    assert book.sheet_by_name("FETHIYE").nrows == 2
    assert book.sheet_by_name("MUGLA").nrows == 2


def test_tanimsiz_bolge_icin_fazladan_sayfa_olusturulmuyor(tmp_path):
    output_path = ReferansliWriter().write(
        {
            "BODRUM": [_record()],
            "DENIZLI": [_record()],
        },
        tmp_path / "referansli.xls",
    )
    book = xlrd.open_workbook(output_path)
    assert book.sheet_names() == ["BODRUM", "FETHIYE", "SOKE", "MUGLA"]


def test_hicbir_onayli_bolgede_kayit_yoksa_none_doner(tmp_path):
    assert ReferansliWriter().write(
        {"FETHIYE": [], "DENIZLI": [_record()]},
        tmp_path / "referansli.xls",
    ) is None


def test_aktif_yeni_bolgeler_ayar_sirasiyla_sayfa_olur(tmp_path):
    config = RegionConfig("config/bolge_kodlari.json")
    output_path = ReferansliWriter(config).write(
        {
            "ANTALYA": [_record("ANTALYA")],
            "DENIZLI": [_record("DENIZLI")],
            "AYDIN": [_record("AYDIN")],
            "NAZILLI": [_record("NAZILLI")],
        },
        tmp_path / "referansli-yeni-bolgeler.xls",
    )
    book = xlrd.open_workbook(output_path)
    assert book.sheet_names() == [
        "BODRUM", "FETHIYE", "SOKE", "MUGLA", "ANTALYA", "DENIZLI", "AYDIN", "NAZILLI"
    ]
