from app.models.records import CustomerRecord, ManimRecord
from app.processors.havale_processor import HavaleProcessor


def _manim(description: str, amount: float = 1000.0) -> ManimRecord:
    return ManimRecord(
        banka="Garanti",
        sube="123",
        islem_tarihi=None,
        aciklama=description,
        tutar=amount,
        dekont_durumu="Aktarıldı",
        karsi_hesap_adi="",
        karsi_hesap_kodu="",
        kaynak_dosya="test.xlsx",
        kaynak_satir=2,
    )


def test_aciklamadaki_tek_yildizli_maskeli_musteri_kodu_eslesir():
    customers = [CustomerRecord("111211111111", "TEST MARKET", "1111111111", "SIMSEK-SOKE")]
    processor = HavaleProcessor([], customers)

    rows, reason = processor.process(_manim("GELEN HAVALE 111*11111111 TEST ODEMESI"), "SOKE")

    assert reason is None
    assert len(rows) == 1
    assert rows[0].cari_kodu == "111211111111"
    assert rows[0].kaynak == "ACIKLAMA_KODU"


def test_aciklamadaki_tire_ile_ayrilmis_musteri_kodu_eslesir():
    customers = [CustomerRecord("222333333333", "ORNEK TEDARIK LTD", "2222222222", "SIMSEK-BODRUM")]
    processor = HavaleProcessor([], customers)

    rows, reason = processor.process(_manim("ORNEK TEDARIK LTD 222-333333333 22222222222"), "BODRUM")

    assert reason is None
    assert rows[0].cari_kodu == "222333333333"
    assert rows[0].kaynak == "ACIKLAMA_KODU"


def test_maskeli_kod_birden_fazla_musteriye_uyarsa_otomatik_secmez():
    customers = [
        CustomerRecord("111211111111", "TEST A", "1111111111", "SIMSEK-SOKE"),
        CustomerRecord("111311111111", "TEST B", "2222222222", "SIMSEK-SOKE"),
    ]
    processor = HavaleProcessor([], customers)

    rows, reason = processor.process(_manim("GELEN HAVALE 111*11111111"), "SOKE")

    assert rows == []
    assert reason is not None


def test_subeli_bir_kurus_fark_netsis_toplaminda_dengelenir():
    from app.models.records import TahsilatRecord

    customers = [
        CustomerRecord("C001", "ORNEK AKARYAKIT 1", "3333333333", "SIMSEK-KUSADASI"),
        CustomerRecord("C002", "ORNEK AKARYAKIT 2", "3333333333", "SIMSEK-KUSADASI"),
    ]
    tahsilat = [
        TahsilatRecord("C001", "ORNEK AKARYAKIT 1", None, 68616.75),
        TahsilatRecord("C002", "ORNEK AKARYAKIT 2", None, 83371.50),
    ]
    processor = HavaleProcessor(
        tahsilat,
        customers,
        region_branch_aliases={"SOKE": ("KUSADASI",)},
    )

    rows, reason = processor.process(
        _manim("ORNEK AKARYAKIT 3333333333", 151988.24),
        "SOKE",
    )

    assert reason is None
    assert round(sum(row.tutar for row in rows), 2) == 151988.24
    assert sorted(row.tutar for row in rows) == [68616.75, 83371.49]


def test_aciklamadaki_x_ayiricili_harfli_musteri_kodu_eslesir():
    customers = [
        CustomerRecord("M11111111111", "ORNEK MARKET", "22222222222", "SIMSEK-BODRUM")
    ]
    processor = HavaleProcessor([], customers)

    rows, reason = processor.process(
        _manim("talimata istinaden teslimat MX11111111111 33333333333", 13000.0),
        "BODRUM",
    )

    assert reason is None
    assert len(rows) == 1
    assert rows[0].cari_kodu == "M11111111111"
    assert rows[0].kaynak == "ACIKLAMA_KODU"


def test_gercek_x_iceren_cari_kodu_ayirici_sanilmaz():
    customers = [
        CustomerRecord("MX11111111111", "X KODLU TEST MARKET", "22222222222", "SIMSEK-BODRUM"),
        CustomerRecord("M11111111111", "DIGER TEST MARKET", "33333333333", "SIMSEK-BODRUM"),
    ]
    processor = HavaleProcessor([], customers)

    rows, reason = processor.process(_manim("ODEME MX11111111111", 13000.0), "BODRUM")

    assert reason is None
    assert rows[0].cari_kodu == "MX11111111111"
