from datetime import datetime
import os
import stat
from pathlib import Path

import xlrd
import pytest

from app.core.output_profile import OutputProfile, OutputProfileStore
from app.models.records import NetsisRecord
from app.writers.netsis_writer import NetsisWriter, _default_template_path


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


def test_excel_yazicisi_onayli_kaynak_sablonu_gecici_kopyada_korur(tmp_path, monkeypatch):
    template = tmp_path / "approved_template.xls"
    template.write_bytes(b"approved original bytes")
    writer = NetsisWriter(template_path=template)
    captured = {}

    def fake_working_copy(_records, output_path, working_template):
        captured["working_template"] = working_template
        assert working_template != template
        assert working_template.read_bytes() == template.read_bytes()
        working_template.write_bytes(b"excel changed working copy")
        output = Path(output_path)
        output.write_bytes(b"output")
        return output

    monkeypatch.setattr(writer, "_write_with_microsoft_excel_working_copy", fake_working_copy)
    writer._write_with_microsoft_excel([], tmp_path / "output.xls")

    assert template.read_bytes() == b"approved original bytes"
    assert not captured["working_template"].exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows production writer")
def test_kaynak_paket_sablonsuzsa_sessizce_genel_excel_uretmez(tmp_path, monkeypatch):
    monkeypatch.delenv("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG", raising=False)
    monkeypatch.setattr("app.writers.netsis_writer.sys.frozen", False, raising=False)
    output = tmp_path / "missing.xls"
    with pytest.raises(FileNotFoundError, match="Genel Excel çıktısı üretilmedi"):
        NetsisWriter(template_path=tmp_path / "olmayan_sablon.xls").write([_record()], output)
    assert not output.exists()


def test_paketli_uygulama_sablonu_meipass_altindan_bulur(tmp_path, monkeypatch):
    template_dir = tmp_path / "templates" / "local"
    template_dir.mkdir(parents=True)
    (template_dir / "netsis_template.xlsx").write_bytes(b"template")
    profile = OutputProfile(
        profile_id="netsis",
        name="Netsis",
        description="",
        template_file="netsis_template.xlsx",
        columns=(),
    )

    monkeypatch.delenv("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG", raising=False)
    monkeypatch.setattr("app.writers.netsis_writer.sys.frozen", True, raising=False)
    monkeypatch.setattr("app.writers.netsis_writer.sys._MEIPASS", str(tmp_path), raising=False)

    assert _default_template_path(profile) == template_dir / "netsis_template.xlsx"


def test_orijinal_netsis_biff8_sablonu_profilde_kullanilabilir(tmp_path, monkeypatch):
    template_dir = tmp_path / "templates" / "local"
    template_dir.mkdir(parents=True)
    template = template_dir / "netsis_template.xls"
    template.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1"))
    profile = OutputProfile(
        profile_id="netsis",
        name="Netsis",
        description="",
        template_file="netsis_template.xls",
        columns=(),
    )

    monkeypatch.delenv("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG", raising=False)
    monkeypatch.setattr("app.writers.netsis_writer.sys.frozen", True, raising=False)
    monkeypatch.setattr("app.writers.netsis_writer.sys._MEIPASS", str(tmp_path), raising=False)

    assert _default_template_path(profile) == template


def test_xlsx_profile_preserves_xlsx_output_extension(tmp_path):
    profile = OutputProfileStore(Path(__file__).resolve().parents[1] / "config").get(
        "netsis_virman_toplu"
    )
    writer = NetsisWriter(template_path=tmp_path / "template.xlsx", profile=profile)
    assert writer._prepare_output_path(tmp_path / "virman.xls").suffix == ".xlsx"


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


def test_netsis_tutar_sutunlari_binlik_ayracli_yazilir(tmp_path):
    output_path = NetsisWriter().write([_record(1234567.89)], tmp_path / "test.xls")
    book = _open(output_path)
    sheet = book.sheet_by_index(0)

    doviz_xf = book.xf_list[sheet.cell_xf_index(1, 11)]
    tutar_xf = book.xf_list[sheet.cell_xf_index(1, 12)]
    assert book.format_map[doviz_xf.format_key].format_str == "#,##0.00"
    assert book.format_map[tutar_xf.format_key].format_str == "#,##0.00"


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


def test_orijinal_xls_sablonu_donusturmeden_kopyalanir(tmp_path):
    template = tmp_path / "netsis_template.xls"
    template.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1"))
    output = tmp_path / "netsis.xls"

    class FakeWorkbook:
        def __init__(self):
            self.copy_path = None
            self.save_as_called = False

        def SaveCopyAs(self, filename):
            self.copy_path = filename

        def SaveAs(self, *_args, **_kwargs):
            self.save_as_called = True

    workbook = FakeWorkbook()
    NetsisWriter(template)._save_workbook_as_netsis_xls(workbook, template, output)

    assert workbook.copy_path == str(output)
    assert not workbook.save_as_called


def test_orijinal_xls_sablonuna_hucre_hucre_yazilir(tmp_path):
    template = tmp_path / "netsis_template.xls"

    class FakeCell:
        def __init__(self):
            self.Value2 = None

    class FakeWorksheet:
        def __init__(self):
            self.cells = {}

        def Cells(self, row, column):
            return self.cells.setdefault((row, column), FakeCell())

        def Range(self, _address):
            raise AssertionError("Eski XLS şablonunda toplu Range.Value2 yazımı kullanılmamalı")

    worksheet = FakeWorksheet()
    NetsisWriter._write_excel_values(
        worksheet,
        [("C001", 1250.0), ("C002", 2500.0)],
        template,
        "B",
    )

    assert worksheet.cells[(2, 1)].Value2 == "C001"
    assert worksheet.cells[(2, 2)].Value2 == 1250.0
    assert worksheet.cells[(3, 1)].Value2 == "C002"


def test_virman_xlsx_bastaki_sifiri_korumak_icin_hucre_hucre_yazilir(tmp_path):
    template = tmp_path / "netsis_virman_toplu_template.xlsx"

    class FakeCell:
        def __init__(self):
            self.Value2 = None

    class FakeWorksheet:
        def __init__(self):
            self.cells = {}

        def Cells(self, row, column):
            return self.cells.setdefault((row, column), FakeCell())

        def Range(self, _address):
            raise AssertionError("Virman XLSX dosyasında toplu Value2 yazımı kullanılmamalı")

    worksheet = FakeWorksheet()
    NetsisWriter._write_excel_values(
        worksheet,
        [("BM-KAYNAK", "00")],
        template,
        "B",
        cell_by_cell=True,
    )

    assert worksheet.cells[(2, 1)].Value2 == "BM-KAYNAK"
    assert worksheet.cells[(2, 2)].Value2 == "00"


def test_toplu_banka_kodu_sablon_biciminde_kalir():
    profile = OutputProfileStore(Path(__file__).resolve().parents[1] / "config").get("netsis_toplu")
    columns = list(profile.columns)
    bank_column = columns[0]
    columns[0] = type(bank_column)(
        header=bank_column.header,
        width=bank_column.width,
        style=bank_column.style,
        source_kind=bank_column.source_kind,
        field=bank_column.field,
        value=bank_column.value,
        force_text=True,
    )
    defensive_profile = OutputProfile(
        profile_id=profile.profile_id,
        name=profile.name,
        description=profile.description,
        template_file=profile.template_file,
        columns=tuple(columns),
        category=profile.category,
        grouping=profile.grouping,
    )

    force_text_columns = NetsisWriter(profile=defensive_profile)._force_text_column_indexes()

    assert 0 not in force_text_columns
    assert 7 in force_text_columns
