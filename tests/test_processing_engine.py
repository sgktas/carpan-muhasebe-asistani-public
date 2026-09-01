import xlrd
import pytest

from app.core.processing_engine import ManualResolution, ProcessingEngine
from app.models.records import TahsilatRecord


def _files(project):
    manim_path, tahsilat_path, customer_path, _ = project
    return [manim_path, tahsilat_path, customer_path]


def test_normal_kayit_netsis_dosyasina_yaziliyor(synthetic_project):
    manim_path, tahsilat_path, customer_path, project_root = synthetic_project
    engine = ProcessingEngine(_files(synthetic_project), project_root)
    result = engine.run()

    assert result.produced_netsis_records == 1
    netsis_files = [f for f in result.created_files if "BODRUM_GARANTI" in f.name]
    assert len(netsis_files) == 1


def test_odeme_onaylandi_ve_referansli_ayriliyor(synthetic_project):
    engine = ProcessingEngine(_files(synthetic_project), synthetic_project[3])
    result = engine.run()

    assert result.skipped_payment == 1
    assert result.skipped_reference == 1
    assert result.unresolved == 0

    odeme_files = [f for f in result.created_files if "ODEME_ONAYLANDI" in f.name]
    referansli_files = [f for f in result.created_files if "REFERANSLI" in f.name]
    assert len(odeme_files) == 1
    assert len(referansli_files) == 1

    book = xlrd.open_workbook(odeme_files[0], formatting_info=True)
    sheet = book.sheet_by_index(0)
    assert sheet.row_values(0) == [
        "KasaKodu", "Tarih", "Fisno", "GC", "Tip", "Aciklama", "Tutar",
        "Kod", "DovizTut", "Kur", "Plasiyer", "ProjeKodu", "RefKodu",
    ]
    row = sheet.row_values(1)
    assert row[0] == 1001  # Public örnek Bodrum KasaKodu
    assert row[2] == "1"    # Fisno sabit
    assert row[3] == "C"
    assert row[4] == "B"
    assert row[7] == "BANK-G-01"  # Public örnek Bodrum + Garanti kodu
    assert row[10] == "TEST"     # Public örnek plasiyer kodu
    xf = book.xf_list[sheet.cell_xf_index(1, 6)]
    assert book.format_map[xf.format_key].format_str == "#,##0.00"


def test_ayni_dosya_ikinci_kez_islenmiyor(synthetic_project):
    project_root = synthetic_project[3]
    files = _files(synthetic_project)

    engine1 = ProcessingEngine(files, project_root)
    result1 = engine1.run()
    assert result1.duplicate_files == []

    engine2 = ProcessingEngine(files, project_root)
    duplicates = engine2.find_duplicate_manim_files()
    assert len(duplicates) == 1

    result2 = engine2.run()
    assert result2.duplicate_files == [files[0].name]
    assert result2.produced_netsis_records == 0
    assert result2.skipped_payment == 0


def test_kullanici_izin_verirse_mukerrer_dosya_yine_islenir(synthetic_project):
    project_root = synthetic_project[3]
    files = _files(synthetic_project)

    engine1 = ProcessingEngine(files, project_root)
    engine1.run()

    engine2 = ProcessingEngine(files, project_root)
    duplicates = engine2.find_duplicate_manim_files()
    allow = {info["hash"] for info in duplicates.values()}

    result2 = engine2.run(allow_duplicate_files=allow)
    assert result2.duplicate_files == []
    assert result2.produced_netsis_records == 1


def test_manuel_eslestirme_resolver_cagriliyor_ve_hafizaya_yaziliyor(synthetic_project):
    manim_path, tahsilat_path, customer_path, project_root = synthetic_project

    # Eslesmeyecek bir MANIM kaydi ekleyelim
    import pandas as pd
    df = pd.read_excel(manim_path)
    df = pd.concat([df, pd.DataFrame([{
        "Banka": "Garanti", "Kod - Şube": "123", "İşlem Tarihi": pd.Timestamp("2026-07-17"),
        "Açıklama": "TAMAMEN BILINMEYEN KAYIT", "Tutar": 4242.0,
        "Dekont Durumu": "Aktarıldı", "Karşı Hesap Adı": "", "Karşı Hesap Kodu": "",
    }])], ignore_index=True)
    df.to_excel(manim_path, index=False)

    called = {}

    def resolver(pending, customers, tahsilat):
        called["count"] = len(pending)
        rows = [TahsilatRecord(musteri_kodu="XYZ999", musteri_ismi="manuel", belge_tarihi=None, tutar=pending[0].record.tutar)]
        return {0: ManualResolution(route="HAVALE", rows=rows)}

    engine = ProcessingEngine([manim_path, tahsilat_path, customer_path], project_root)
    result = engine.run(resolver=resolver)

    assert called["count"] == 1
    assert result.unresolved == 0
    assert result.produced_netsis_records == 2  # ABC001 (normal) + XYZ999 (elle)

    # Hafizaya yazildi mi?
    from app.core.mapping_store import MappingStore
    store = MappingStore(project_root / "data" / "customer_mappings.json")
    assert store.get("TAMAMEN BILINMEYEN KAYIT") == [{"musteri_kodu": "XYZ999", "tutar": 4242.0}]


def test_manuel_olarak_odeme_onaylandiya_tasinabiliyor(synthetic_project):
    """Dekont durumu otomatik taninamayan bir kayit, kullanici tarafindan
    manuel olarak Odeme Onaylandi dosyasina yonlendirilebilmeli (musteri
    kodu aranmadan)."""
    manim_path, tahsilat_path, customer_path, project_root = synthetic_project

    import pandas as pd
    df = pd.read_excel(manim_path)
    df = pd.concat([df, pd.DataFrame([{
        "Banka": "Ziraat Bankası", "Kod - Şube": "123", "İşlem Tarihi": pd.Timestamp("2026-07-17"),
        "Açıklama": "TEMMUZ AYI KIRA ODEMESI", "Tutar": 172666.0,
        "Dekont Durumu": "Beklemede", "Karşı Hesap Adı": "", "Karşı Hesap Kodu": "",
    }])], ignore_index=True)
    df.to_excel(manim_path, index=False)

    def resolver(pending, customers, tahsilat):
        assert len(pending) == 1
        return {0: ManualResolution(route="REFERANSLI", rows=None)}

    engine = ProcessingEngine([manim_path, tahsilat_path, customer_path], project_root)
    result = engine.run(resolver=resolver)

    assert result.unresolved == 0
    assert result.skipped_reference == 2  # senkron testteki mevcut REFERANSLI kaydi + bu manuel tasinan
    referansli_files = [f for f in result.created_files if "REFERANSLI" in f.name]
    assert len(referansli_files) == 1


def test_cikti_klasoru_modul_adi_ve_islem_tarihini_tasir(synthetic_project):
    engine = ProcessingEngine(_files(synthetic_project), synthetic_project[3])
    result = engine.run()
    for created_file in result.created_files:
        assert created_file.parent.parent.name == "output"
        assert created_file.parent.name == "MANİM AKTARMA - 15-16.07.2026"


def test_dosya_adlari_ve_klasor_islem_tarihini_kullaniyor_bugunu_degil(synthetic_project):
    """Sistem tarihi ne olursa olsun çıktı adı MANİM içindeki ilk ve son
    işlem tarihlerini taşımalıdır."""
    engine = ProcessingEngine(_files(synthetic_project), synthetic_project[3])
    result = engine.run()

    assert result.created_files, "en az bir dosya olusturulmus olmali"
    for created_file in result.created_files:
        assert created_file.parent.name == "MANİM AKTARMA - 15-16.07.2026"
        assert "15-16.07.2026" in created_file.name



def test_gecersiz_manim_satiri_eslestirmeye_girmez_ve_raporlanir(synthetic_project):
    import pandas as pd

    manim_path, tahsilat_path, customer_path, project_root = synthetic_project
    df = pd.read_excel(manim_path)
    df = pd.concat([df, pd.DataFrame([{
        "Banka": "Garanti",
        "Kod - Şube": "123",
        "İşlem Tarihi": pd.Timestamp("2026-07-15"),
        "Açıklama": "BOZUK KAYNAK SATIRI",
        "Tutar": None,
        "Dekont Durumu": None,
        "Karşı Hesap Adı": "",
        "Karşı Hesap Kodu": "",
    }])], ignore_index=True)
    df.to_excel(manim_path, index=False)

    engine = ProcessingEngine([manim_path, tahsilat_path, customer_path], project_root)
    result = engine.run()

    assert result.total_manim_records == 4
    assert result.invalid_manim_records == 1
    assert result.unresolved == 0
    assert result.invalid_file is not None and result.invalid_file.is_file()

    invalid_df = pd.read_excel(result.invalid_file)
    assert len(invalid_df) == 1
    assert "Tutar" in invalid_df.loc[0, "Neden"]
    assert "Dekont durumu" in invalid_df.loc[0, "Neden"]


def test_writer_hatasi_dosyayi_islenmis_olarak_isaretlemez(synthetic_project, monkeypatch):
    import pytest

    manim_path, tahsilat_path, customer_path, project_root = synthetic_project
    engine = ProcessingEngine([manim_path, tahsilat_path, customer_path], project_root)

    def fail_write(*_args, **_kwargs):
        raise OSError("disk yazma testi")

    monkeypatch.setattr("app.core.processing_engine.NetsisWriter.write", fail_write)

    with pytest.raises(OSError, match="disk yazma testi"):
        engine.run()

    assert engine.find_duplicate_manim_files() == {}
    output_root = project_root / "output"
    assert not list(output_root.glob("20*")) if output_root.exists() else True


def test_manuel_eslestirmede_pasif_cari_kod_kabul_edilir(synthetic_project):
    import pandas as pd

    manim_path, tahsilat_path, customer_path, project_root = synthetic_project
    df = pd.read_excel(manim_path)
    df = pd.concat([df, pd.DataFrame([{
        "Banka": "Garanti",
        "Kod - Şube": "123",
        "İşlem Tarihi": pd.Timestamp("2026-07-17"),
        "Açıklama": "BILINMEYEN CARI TESTI",
        "Tutar": 4242.0,
        "Dekont Durumu": "Aktarıldı",
        "Karşı Hesap Adı": "",
        "Karşı Hesap Kodu": "",
    }])], ignore_index=True)
    df.to_excel(manim_path, index=False)

    def resolver(pending, customers, tahsilat):
        rows = [TahsilatRecord(
            musteri_kodu="LISTEDE_YOK",
            musteri_ismi="manuel",
            belge_tarihi=None,
            tutar=pending[0].record.tutar,
        )]
        return {0: ManualResolution(route="HAVALE", rows=rows)}

    engine = ProcessingEngine([manim_path, tahsilat_path, customer_path], project_root)
    result = engine.run(resolver=resolver)

    assert result.unresolved == 0
    assert result.produced_netsis_records == 2

    from app.core.mapping_store import MappingStore
    store = MappingStore(project_root / "data" / "customer_mappings.json")
    assert store.get("BILINMEYEN CARI TESTI") == [
        {"musteri_kodu": "LISTEDE_YOK", "tutar": 4242.0}
    ]


def test_kaynaklar_ile_kalici_veri_klasoru_ayri_kullanilabilir(synthetic_project, tmp_path):
    manim_path, tahsilat_path, customer_path, resource_root = synthetic_project
    data_root = tmp_path / "kalici_kullanici_verisi"

    engine = ProcessingEngine(
        [manim_path, tahsilat_path, customer_path],
        project_root=resource_root,
        data_root=data_root,
    )
    result = engine.run()

    assert result.output_dir is not None
    assert result.output_dir.parent == data_root / "output"
    assert (data_root / "data" / "processed_files.json").is_file()
    assert engine.find_duplicate_manim_files()


def test_tum_uretilen_excel_dosyalari_xls_ve_yazilabilir(synthetic_project):
    import os
    import stat

    engine = ProcessingEngine(_files(synthetic_project), synthetic_project[3])
    result = engine.run()
    all_files = list(result.created_files)
    if result.review_file:
        all_files.append(result.review_file)
    if result.invalid_file and result.invalid_file not in all_files:
        all_files.append(result.invalid_file)

    assert all_files
    for file_path in all_files:
        assert file_path.suffix.lower() == ".xls"
        assert file_path.read_bytes()[:8] == bytes.fromhex("D0CF11E0A1B11AE1")
        assert file_path.stat().st_mode & stat.S_IWUSR
        assert os.access(file_path, os.W_OK)


def test_iki_gunluk_aktarim_dosya_adi_tarih_araligi_ve_satir_sirasi(synthetic_project):
    import pandas as pd
    import xlrd

    manim_path, tahsilat_path, customer_path, project_root = synthetic_project
    pd.DataFrame([
        {
            "Banka": "Garanti", "Kod - Şube": "123",
            "İşlem Tarihi": pd.Timestamp("2026-07-19 08:15:00"),
            "Açıklama": "PAZAR KAYDI", "Tutar": 1900.0,
            "Dekont Durumu": "Aktarıldı", "Karşı Hesap Adı": "", "Karşı Hesap Kodu": "C1900",
        },
        {
            "Banka": "Garanti", "Kod - Şube": "123",
            "İşlem Tarihi": pd.Timestamp("2026-07-18 23:45:00"),
            "Açıklama": "CUMARTESI KAYDI", "Tutar": 1800.0,
            "Dekont Durumu": "Aktarıldı", "Karşı Hesap Adı": "", "Karşı Hesap Kodu": "C1800",
        },
    ]).to_excel(manim_path, index=False)
    pd.DataFrame([
        {"Müşteri Kodu": "C1800", "Ünvan": "CUMARTESI MUSTERI", "Vergi No": "1800", "Şube": "BODRUM"},
        {"Müşteri Kodu": "C1900", "Ünvan": "PAZAR MUSTERI", "Vergi No": "1900", "Şube": "BODRUM"},
    ]).to_excel(customer_path, index=False)

    engine = ProcessingEngine([manim_path, tahsilat_path, customer_path], project_root)
    result = engine.run()

    netsis_file = next(file for file in result.created_files if "BODRUM_GARANTI" in file.name)
    assert netsis_file.name == "01_BODRUM_GARANTI_18-19.07.2026.xls"
    assert netsis_file.parent.name == "MANİM AKTARMA - 18-19.07.2026"

    book = xlrd.open_workbook(netsis_file, formatting_info=True)
    sheet = book.sheet_by_index(0)
    dates = [
        xlrd.xldate_as_datetime(sheet.cell_value(row, 1), book.datemode).date()
        for row in range(1, sheet.nrows)
    ]
    assert dates == [pd.Timestamp("2026-07-18").date(), pd.Timestamp("2026-07-19").date()]
    assert sheet.cell_value(1, 13) == "CUMARTESI KAYDI"
    assert sheet.cell_value(2, 13) == "PAZAR KAYDI"


def test_musteri_listesi_verilmezse_hafizadaki_son_liste_kullanilir(synthetic_project, tmp_path):
    import pandas as pd

    manim_path, tahsilat_path, customer_path, project_root = synthetic_project

    engine1 = ProcessingEngine([manim_path, tahsilat_path, customer_path], project_root)
    result1 = engine1.run()
    assert result1.produced_netsis_records == 1

    # ikinci turda farkli bir MANIM dosyasi kullanilir ki mukerrer dosya
    # tespitiyle karismasin; asil test edilen sey musteri listesinin
    # verilmeden hafizadan kullanilabilmesi.
    manim_path_2 = tmp_path / "input" / "TEST_BODRUM_Manim_2.xlsx"
    pd.DataFrame([
        {
            "Banka": "Garanti", "Kod - Şube": "123", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "IKINCI TUR ODEME", "Tutar": 1500.0,
            "Dekont Durumu": "Aktarıldı", "Karşı Hesap Adı": "ABC LTD", "Karşı Hesap Kodu": "ABC001",
        },
    ]).to_excel(manim_path_2, index=False)

    engine2 = ProcessingEngine([manim_path_2, tahsilat_path], project_root)
    result2 = engine2.run()
    assert result2.produced_netsis_records == 1
    assert any("hafızadaki son liste kullanıldı" in log for log in result2.logs)


def test_hic_hafiza_yokken_musteri_listesi_verilmezse_hata_verir(synthetic_project):
    manim_path, tahsilat_path, _customer_path, project_root = synthetic_project

    engine = ProcessingEngine([manim_path, tahsilat_path], project_root)
    try:
        engine.run()
        assert False, "ValueError bekleniyordu"
    except ValueError as exc:
        assert "Musteri listesi bulunamadi" in str(exc)


def test_hafizadaki_listede_yeni_musteri_yoksa_islem_durmaz_ve_yenisi_saklanir(
    synthetic_project,
    tmp_path,
):
    import pandas as pd

    manim_path, tahsilat_path, customer_path, project_root = synthetic_project
    ProcessingEngine([manim_path, tahsilat_path, customer_path], project_root).run()

    new_manim = tmp_path / "input" / "TEST_BODRUM_YENI_MUSTERI_Manim.xlsx"
    pd.DataFrame([{
        "Banka": "Garanti", "Kod - Şube": "123",
        "İşlem Tarihi": pd.Timestamp("2026-07-17"),
        "Açıklama": "YENI MUSTERI ODEMESI", "Tutar": 1700.0,
        "Dekont Durumu": "Aktarıldı", "Karşı Hesap Adı": "YENI MUSTERI",
        "Karşı Hesap Kodu": "NEW001",
    }]).to_excel(new_manim, index=False)

    unresolved_result = ProcessingEngine([new_manim, tahsilat_path], project_root).run()
    assert unresolved_result.unresolved == 1
    assert unresolved_result.output_dir is not None
    assert any("manuel eşleştirme ekranına gönderildi" in log for log in unresolved_result.logs)

    updated_customers = tmp_path / "input" / "guncel_musteri_listesi.xlsx"
    pd.DataFrame([
        {"Müşteri Kodu": "ABC001", "Ünvan": "ABC LTD", "Vergi No": "2222222222", "Şube": "BODRUM"},
        {"Müşteri Kodu": "XYZ999", "Ünvan": "XYZ FIRMASI", "Vergi No": "1111111111", "Şube": "BODRUM"},
        {"Müşteri Kodu": "NEW001", "Ünvan": "YENI MUSTERI", "Vergi No": "3333333333", "Şube": "BODRUM"},
    ]).to_excel(updated_customers, index=False)
    updated_manim = tmp_path / "input" / "TEST_BODRUM_YENI_MUSTERI_GUNCEL_Manim.xlsx"
    pd.DataFrame([{
        "Banka": "Garanti", "Kod - Şube": "123",
        "İşlem Tarihi": pd.Timestamp("2026-07-17"),
        "Açıklama": "YENI MUSTERI IKINCI ODEMESI", "Tutar": 1700.0,
        "Dekont Durumu": "Aktarıldı", "Karşı Hesap Adı": "YENI MUSTERI",
        "Karşı Hesap Kodu": "NEW001",
    }]).to_excel(updated_manim, index=False)
    updated_result = ProcessingEngine(
        [updated_manim, tahsilat_path, updated_customers],
        project_root,
    ).run()
    assert updated_result.produced_netsis_records == 1

    another_manim = tmp_path / "input" / "TEST_BODRUM_YENI_MUSTERI_2_Manim.xlsx"
    pd.DataFrame([{
        "Banka": "Garanti", "Kod - Şube": "123",
        "İşlem Tarihi": pd.Timestamp("2026-07-18"),
        "Açıklama": "YENI MUSTERI IKINCI ODEME", "Tutar": 1800.0,
        "Dekont Durumu": "Aktarıldı", "Karşı Hesap Adı": "YENI MUSTERI",
        "Karşı Hesap Kodu": "NEW001",
    }]).to_excel(another_manim, index=False)
    cached_result = ProcessingEngine([another_manim, tahsilat_path], project_root).run()
    assert cached_result.produced_netsis_records == 1
    assert any("hafızadaki son liste kullanıldı" in log for log in cached_result.logs)
