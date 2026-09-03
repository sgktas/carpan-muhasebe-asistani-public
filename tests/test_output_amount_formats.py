from openpyxl import load_workbook

from app.modules.report_editing.engine import _write_clean_xlsx


def test_fom_tutarlar_iki_sayfada_sayisal_ve_binlik_ayracli(tmp_path):
    target = tmp_path / "collections.xlsx"
    _write_clean_xlsx(target, [
        ("Tahsilatlar", ["Müşteri Kodu", "Tutar"], [["000123", 12345.67]], False),
        ("ŞUBELİLER", ["Müşteri Kodu", "Tutar"], [["000456", -4321.25]], True),
    ])
    book = load_workbook(target)
    for sheet in book:
        assert sheet["B2"].number_format == "#,##0.00"
        assert sheet["B2"].data_type == "n"
        assert sheet["A2"].number_format == "General"
        assert sheet["A2"].value.startswith("000")
    assert book["Tahsilatlar"]["B2"].value == 12345.67
    assert book["ŞUBELİLER"]["B2"].value == -4321.25
    book.close()
