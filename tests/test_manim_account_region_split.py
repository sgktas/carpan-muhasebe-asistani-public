from __future__ import annotations

import pandas as pd
import xlrd

from app.core.processing_engine import ProcessingEngine


class _FakeNetsisWriter:
    def __init__(self, *_args, **_kwargs):
        pass

    def write(self, rows, output_path):
        output_path.write_bytes(f"{len(rows)} rows".encode("ascii"))
        return output_path

    def close(self):
        pass


def test_aydin_dosyasi_kod_sube_ile_uc_akisi_nazilliden_ayirir(
    synthetic_project,
    monkeypatch,
):
    manim_path, tahsilat_path, customer_path, project_root = synthetic_project
    manim_path = manim_path.with_name("TEST_AYDIN_Manim.xlsx")
    rows = [
        {
            "Banka": "Garanti", "Kod - Şube": "TEST-HESAP-1007", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "AYDIN HAVALE", "Tutar": 1000.0, "Dekont Durumu": "Aktarıldı",
            "Karşı Hesap Adı": "XYZ FIRMASI", "Karşı Hesap Kodu": "XYZ999",
        },
        {
            "Banka": "Garanti", "Kod - Şube": "TEST-HESAP-1008", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "NAZILLI HAVALE", "Tutar": 1100.0, "Dekont Durumu": "Aktarıldı",
            "Karşı Hesap Adı": "XYZ FIRMASI", "Karşı Hesap Kodu": "XYZ999",
        },
        {
            "Banka": "YapıKredi", "Kod - Şube": "TEST-HESAP-2007", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "AYDIN ODEME", "Tutar": 1200.0, "Dekont Durumu": "Ödeme Onaylandı",
            "Karşı Hesap Adı": "", "Karşı Hesap Kodu": "",
        },
        {
            "Banka": "YapıKredi", "Kod - Şube": "TEST-HESAP-2008", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "NAZILLI ODEME", "Tutar": 1300.0, "Dekont Durumu": "Ödeme Onaylandı",
            "Karşı Hesap Adı": "", "Karşı Hesap Kodu": "",
        },
        {
            "Banka": "Ziraat", "Kod - Şube": "TEST-HESAP-3007", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "AYDIN REFERANSLI", "Tutar": 1400.0, "Dekont Durumu": "Referanslı",
            "Karşı Hesap Adı": "", "Karşı Hesap Kodu": "",
        },
        {
            "Banka": "Ziraat", "Kod - Şube": "TEST-HESAP-3008", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "NAZILLI REFERANSLI", "Tutar": 1500.0, "Dekont Durumu": "Referanslı",
            "Karşı Hesap Adı": "", "Karşı Hesap Kodu": "",
        },
    ]
    pd.DataFrame(rows).to_excel(manim_path, index=False)
    monkeypatch.setattr("app.core.processing_engine.NetsisWriter", _FakeNetsisWriter)

    result = ProcessingEngine(
        [manim_path, tahsilat_path, customer_path],
        project_root,
    ).run()
    names = {path.name for path in result.created_files}
    assert "07_AYDIN_GARANTI_15072026.xls" in names
    assert "08_NAZILLI_GARANTI_15072026.xls" in names
    assert "09_ODEME_ONAYLANDI_15072026.xls" in names
    assert "10_REFERANSLI_15072026.xls" in names

    payment = xlrd.open_workbook(result.output_dir / "09_ODEME_ONAYLANDI_15072026.xls")
    payment_sheet = payment.sheet_by_index(0)
    assert [payment_sheet.cell_value(row, 5) for row in range(1, payment_sheet.nrows)] == [
        "AYDIN ODEME", "NAZILLI ODEME"
    ]
    assert [int(payment_sheet.cell_value(row, 0)) for row in range(1, payment_sheet.nrows)] == [
        1007, 1008
    ]
    assert [payment_sheet.cell_value(row, 7) for row in range(1, payment_sheet.nrows)] == [
        "BANK-Y-07", "BANK-Y-08"
    ]

    referenced = xlrd.open_workbook(result.output_dir / "10_REFERANSLI_15072026.xls")
    assert referenced.sheet_by_name("AYDIN").cell_value(1, 2) == "AYDIN REFERANSLI"
    assert referenced.sheet_by_name("NAZILLI").cell_value(1, 2) == "NAZILLI REFERANSLI"
    assert any("AYDIN: 3" in line and "NAZILLI: 3" in line for line in result.logs)


def test_hesap_bulunamazsa_guncel_musteri_kodu_ve_adi_bolgeyi_ayirir(
    synthetic_project,
    monkeypatch,
):
    manim_path, tahsilat_path, customer_path, project_root = synthetic_project
    manim_path = manim_path.with_name("TEST_AYDIN_Manim.xlsx")
    pd.DataFrame([
        {
            "Müşteri Kodu": "AYD001", "Ünvan": "AYDIN TEST MARKET",
            "Vergi No": "1111111111", "Şube": "SIMSEK-AYDIN",
        },
        {
            "Müşteri Kodu": "NAZ001", "Ünvan": "NAZILLI TEST MARKET",
            "Vergi No": "2222222222", "Şube": "SIMSEK-NAZILLI",
        },
    ]).to_excel(customer_path, index=False)
    pd.DataFrame([
        {
            "Banka": "Garanti", "Kod - Şube": "BILINMEYEN", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "KODDAN NAZILLI", "Tutar": 1000.0, "Dekont Durumu": "Aktarıldı",
            "Karşı Hesap Adı": "NAZILLI TEST MARKET", "Karşı Hesap Kodu": "NAZ001",
        },
        {
            "Banka": "Garanti", "Kod - Şube": "BILINMEYEN", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "ISIMDEN AYDIN", "Tutar": 1100.0, "Dekont Durumu": "Ödeme Onaylandı",
            "Karşı Hesap Adı": "AYDIN TEST MARKET", "Karşı Hesap Kodu": "",
        },
        {
            "Banka": "Garanti", "Kod - Şube": "BILINMEYEN", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "ISIMDEN NAZILLI", "Tutar": 1200.0, "Dekont Durumu": "Referanslı",
            "Karşı Hesap Adı": "NAZILLI TEST MARKET", "Karşı Hesap Kodu": "",
        },
        {
            "Banka": "Garanti", "Kod - Şube": "TEST-HESAP-1007", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "HESAP ONCELIKLI AYDIN", "Tutar": 1300.0, "Dekont Durumu": "Ödeme Onaylandı",
            "Karşı Hesap Adı": "NAZILLI TEST MARKET", "Karşı Hesap Kodu": "NAZ001",
        },
    ]).to_excel(manim_path, index=False)
    monkeypatch.setattr("app.core.processing_engine.NetsisWriter", _FakeNetsisWriter)

    result = ProcessingEngine(
        [manim_path, tahsilat_path, customer_path],
        project_root,
    ).run()
    names = {path.name for path in result.created_files}
    assert "08_NAZILLI_GARANTI_15072026.xls" in names

    payment = xlrd.open_workbook(result.output_dir / "09_ODEME_ONAYLANDI_15072026.xls")
    payment_sheet = payment.sheet_by_index(0)
    assert [payment_sheet.cell_value(row, 5) for row in range(1, payment_sheet.nrows)] == [
        "ISIMDEN AYDIN", "HESAP ONCELIKLI AYDIN"
    ]
    assert [int(payment_sheet.cell_value(row, 0)) for row in range(1, payment_sheet.nrows)] == [
        1007, 1007
    ]

    referenced = xlrd.open_workbook(result.output_dir / "10_REFERANSLI_15072026.xls")
    assert referenced.sheet_by_name("NAZILLI").cell_value(1, 2) == "ISIMDEN NAZILLI"
