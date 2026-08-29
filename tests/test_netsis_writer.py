from datetime import datetime
import os
import stat
from pathlib import Path

import xlrd

from app.models.records import NetsisRecord
from app.writers.netsis_writer import NetsisWriter


def _record(tutar=1000.0):
    return NetsisRecord(
        islem_tarihi=datetime(2026, 7, 16, 14, 30, 0),
        cari_kodu="C001",
        tutar=tutar,
        aciklama="TEST ACIKLAMA",
        banka="Garanti",
        bolge="BODRUM",
        kaynak="TEST",
    )


def _open(path):
    return xlrd.open_workbook(path, formatting_info=True)


def test_gercek_excel_97_2003_biff8_ve_xls_uzantisi(tmp_path):
    output_path = NetsisWriter().write([_record()], tmp_path / "test.xlsx")
    assert output_path.suffix == ".xls"
    assert output_path.read_bytes()[:8] == bytes.fromhex("D0CF11E0A1B11AE1")
    assert _open(output_path).sheet_names() == ["Sheet1"]


def test_dosya_salt_okunur_degil(tmp_path):
    output_path = NetsisWriter().write([_record()], tmp_path / "test.xls")
    assert output_path.stat().st_mode & stat.S_IWUSR
    assert os.access(output_path, os.W_OK)


def test_veri_basligin_hemen_altindan_baslar_bosluk_yok(tmp_path):
    output_path = NetsisWriter().write(
        [_record(), _record(2000.0)], tmp_path / "test.xls"
    )
    sheet = _open(output_path).sheet_by_index(0)
    assert sheet.cell_value(1, 12) == 1000.0
    assert sheet.cell_value(2, 12) == 2000.0


def test_tarih_saatsiz_ve_dd_mm_yyyy_formatinda_yaziliyor(tmp_path):
    output_path = NetsisWriter().write([_record()], tmp_path / "test.xls")
    book = _open(output_path)
    sheet = book.sheet_by_index(0)
    tarih = xlrd.xldate_as_datetime(sheet.cell_value(1, 1), book.datemode)
    assert tarih.hour == 0 and tarih.minute == 0
    xf = book.xf_list[sheet.cell_xf_index(1, 1)]
    assert book.format_map[xf.format_key].format_str.upper() == "DD.MM.YYYY"


def test_gercek_27_sutunlu_netsis_basliklari_yaziliyor(tmp_path):
    output_path = NetsisWriter().write([_record()], tmp_path / "test.xls")
    sheet = _open(output_path).sheet_by_index(0)
    assert sheet.ncols == 27
    assert sheet.row_values(0) == NetsisWriter.HEADERS
    assert sheet.cell_value(1, 5) == "C001"
    assert sheet.cell_value(1, 6) == 0
    assert sheet.cell_value(1, 7) == 0
    assert sheet.cell_value(1, 8) == 0
    assert sheet.cell_value(1, 17) == "HV"


def test_writer_kayitlari_islem_tarihine_gore_kucukten_buyuge_siralar(tmp_path):
    records = [
        NetsisRecord(
            islem_tarihi=datetime(2026, 7, 19, 9, 0), cari_kodu="C19", tutar=19,
            aciklama="19 TEMMUZ", banka="Garanti", bolge="BODRUM", kaynak="TEST",
        ),
        NetsisRecord(
            islem_tarihi=datetime(2026, 7, 18, 23, 0), cari_kodu="C18", tutar=18,
            aciklama="18 TEMMUZ", banka="Garanti", bolge="BODRUM", kaynak="TEST",
        ),
    ]
    output_path = NetsisWriter().write(records, tmp_path / "sirali.xls")
    book = _open(output_path)
    sheet = book.sheet_by_index(0)
    assert sheet.cell_value(1, 13) == "18 TEMMUZ"
    assert sheet.cell_value(2, 13) == "19 TEMMUZ"


def test_excel_com_kayit_yolu_xlexcel8_ve_orijinal_sablonu_kullanir(tmp_path, monkeypatch):
    template = tmp_path / "netsis_template.xlsx"
    template.write_bytes(b"template")
    output = tmp_path / "netsis.xls"

    class FakeRange:
        def __init__(self, address):
            self.address = address
            self.NumberFormat = None
            if address == "A1:AA1":
                self.Value = (tuple(NetsisWriter.HEADERS),)
            else:
                self.Value = None

        def ClearContents(self):
            return None

    class FakeRows:
        Count = 15

    class FakeUsedRange:
        Rows = FakeRows()

    class FakeWorksheet:
        UsedRange = FakeUsedRange()

        def __init__(self):
            self.ranges = {}

        def Range(self, address):
            self.ranges.setdefault(address, FakeRange(address))
            return self.ranges[address]

    class FakeWorksheets:
        def __init__(self, sheet):
            self.sheet = sheet

        def __call__(self, index):
            assert index == 1
            return self.sheet

    class FakeWorkbook:
        def __init__(self):
            self.sheet = FakeWorksheet()
            self.Worksheets = FakeWorksheets(self.sheet)
            self.CheckCompatibility = True
            self.saved = None
            self.closed = False

        def SaveAs(self, filename, **kwargs):
            self.saved = (filename, kwargs)
            Path(filename).write_bytes(bytes.fromhex("D0CF11E0A1B11AE1"))

        def Close(self, SaveChanges=False):
            self.closed = True

    class FakeWorkbooks:
        def __init__(self, workbook):
            self.workbook = workbook
            self.opened = None

        def Open(self, filename, **kwargs):
            self.opened = (filename, kwargs)
            return self.workbook

    class FakeExcel:
        def __init__(self, workbook):
            self.Workbooks = FakeWorkbooks(workbook)

    fake_workbook = FakeWorkbook()
    writer = NetsisWriter(template)
    monkeypatch.setattr(writer, "_get_excel_application", lambda: FakeExcel(fake_workbook))

    result = writer._write_with_microsoft_excel([_record()], output)

    assert result == output
    assert fake_workbook.saved[1]["FileFormat"] == 56
    assert fake_workbook.CheckCompatibility is False
    assert fake_workbook.closed
    assert fake_workbook.sheet.ranges["F2:F2"].NumberFormat == "@"
    assert fake_workbook.sheet.ranges["B2:C2"].NumberFormatLocal == "gg.aa.yyyy"
    written = fake_workbook.sheet.ranges["A2:AA2"].Value2
    assert written[0][5] == "C001"
    assert written[0][12] == 1000.0
