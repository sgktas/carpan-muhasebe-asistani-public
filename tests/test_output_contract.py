from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
import xlwt

from app.core.output_contract import (
    FOM_COLLECTION_OUTPUT_BASENAME,
    FOM_SALES_OUTPUT_BASENAME,
    OutputContractError,
    validate_fom_integration_output,
    validate_netsis_output,
)
from app.core.output_profile import OutputProfileStore
from app.models.records import NetsisRecord


TEST_COLLECTION_CUSTOMER_ID = "8" * 12
TEST_COLLECTION_DOCUMENT_ID = "7" * 13
TEST_SALES_CUSTOMER_ID = "6" * 10
TEST_SALES_DOCUMENT_ID = "B" + "4" * 14
TEST_VIRMAN_SOURCE_BANK_CODE = "BM" + "21402"
TEST_VIRMAN_TARGET_BANK_CODE = "BM" + "21204"


def _write_contract_file(path: Path, profile, bank_format: str) -> None:
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Sheet1")
    for column, header in enumerate(profile.headers()):
        sheet.write(0, column, header)
    bank_style = xlwt.easyxf(num_format_str=bank_format)
    sheet.write(1, 0, "SENTETIK-BANKA", bank_style)
    date_style = xlwt.easyxf(num_format_str="m/d/yy")
    amount_style = xlwt.easyxf(num_format_str="#,##0.00")
    for column, definition in enumerate(profile.columns):
        if definition.source_kind == "const" and definition.value is not None:
            style = amount_style if definition.style == "amount" else xlwt.Style.default_style
            sheet.write(1, column, definition.value, style)
    sheet.write(1, 3, datetime(2026, 9, 5), date_style)
    sheet.write(1, 4, datetime(2026, 9, 5), date_style)
    sheet.write(1, 7, "TEST001")
    sheet.write(1, 14, 1250.50, amount_style)
    workbook.save(str(path))


def _write_fom_contract_file(
    path: Path,
    *,
    sheet_name: str = "SATIS_FATURALARI",
    headers: list[str] | None = None,
    row_count: int = 1,
    amount_format: str = "General",
) -> None:
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet(sheet_name)
    headers = headers or ["MusteriKodu", "Tutar"]
    for column, header in enumerate(headers):
        sheet.write(0, column, header)
    for row in range(1, row_count + 1):
        sheet.write(row, 0, f"TEST{row}")
        sheet.write(row, 1, 100.0, xlwt.easyxf(num_format_str=amount_format))
    workbook.save(str(path))


def _write_collection_contract_file(path: Path, *, numeric_keys: bool) -> None:
    headers = [
        "MusteriKodu", "Musteriİsmi", "BelgeNo", "BelgeTarihi", "TahsilatTipi",
        "TahsilatTuru", "SatisElemani", "Pesin/Diger", "Personel", "Rota",
        "MusteriKayitTipi", "MusteriTipi", "SahiplikTipi", "AltTip",
        "FiyatListesi", "BANKA", "Tutar", "BÖLGE",
    ]
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("TAHSILATLAR")
    for column, header in enumerate(headers):
        sheet.write(0, column, header)
    keys = [int(TEST_COLLECTION_CUSTOMER_ID), int(TEST_COLLECTION_DOCUMENT_ID), 1, 164] if numeric_keys else [
        TEST_COLLECTION_CUSTOMER_ID, "B" + TEST_COLLECTION_DOCUMENT_ID, "1", "000000164"
    ]
    row = [keys[0], "TEST", keys[1], "09.09.2026", "N", keys[2], keys[3],
           1, "TEST", "ANTALYA-DD-01", "Müşteri", "Müşteri", "Bağımsız",
           "Market", "Liste", "GARANTI", 100.0, "ANTALYA"]
    for column, value in enumerate(row):
        sheet.write(1, column, value)
    workbook.save(str(path))


def test_fom_contract_accepts_exact_psoft_sales_name(tmp_path):
    output = tmp_path / f"{FOM_SALES_OUTPUT_BASENAME}.xls"
    _write_fom_contract_file(output, row_count=2)

    validate_fom_integration_output(
        output,
        expected_basename=FOM_SALES_OUTPUT_BASENAME,
        expected_sheet_name="SATIS_FATURALARI",
        expected_headers=["MusteriKodu", "Tutar"],
        expected_data_rows=2,
    )


def test_fom_contract_rejects_unapproved_integration_name(tmp_path):
    output = tmp_path / "ENT_SATIS_FATURALARI.xls"
    _write_fom_contract_file(output)

    with pytest.raises(OutputContractError, match="onaylı satış veya tahsilat"):
        validate_fom_integration_output(
            output,
            expected_basename=output.stem,
            expected_sheet_name="SATIS_FATURALARI",
            expected_headers=["MusteriKodu", "Tutar"],
            expected_data_rows=1,
        )


def test_fom_contract_rejects_wrong_sheet_or_row_count(tmp_path):
    output = tmp_path / f"{FOM_COLLECTION_OUTPUT_BASENAME}.xls"
    _write_fom_contract_file(
        output,
        sheet_name="YANLIS_SAYFA",
        row_count=1,
    )

    with pytest.raises(OutputContractError, match="sayfa adı değişmiş"):
        validate_fom_integration_output(
            output,
            expected_basename=FOM_COLLECTION_OUTPUT_BASENAME,
            expected_sheet_name="TAHSILATLAR",
            expected_headers=["MusteriKodu", "Tutar"],
            expected_data_rows=2,
        )


def test_fom_contract_allows_original_template_sheet_name(tmp_path):
    sheet_name = "ENT-Muhasebe_Entegrasyon(Satis"
    template = tmp_path / "template.xls"
    output = tmp_path / f"{FOM_COLLECTION_OUTPUT_BASENAME}.xls"
    _write_fom_contract_file(template, sheet_name=sheet_name)
    _write_fom_contract_file(output, sheet_name=sheet_name)

    validate_fom_integration_output(
        output,
        expected_basename=FOM_COLLECTION_OUTPUT_BASENAME,
        expected_sheet_name=sheet_name,
        expected_headers=["MusteriKodu", "Tutar"],
        expected_data_rows=1,
        template_path=template,
    )


def test_collection_contract_rejects_numeric_identifier_cells(tmp_path):
    output = tmp_path / f"{FOM_COLLECTION_OUTPUT_BASENAME}.xls"
    _write_collection_contract_file(output, numeric_keys=True)

    with pytest.raises(OutputContractError, match="kimlik alanları metin"):
        validate_fom_integration_output(
            output,
            expected_basename=FOM_COLLECTION_OUTPUT_BASENAME,
            expected_sheet_name="TAHSILATLAR",
            expected_headers=[
                "MusteriKodu", "Musteriİsmi", "BelgeNo", "BelgeTarihi", "TahsilatTipi",
                "TahsilatTuru", "SatisElemani", "Pesin/Diger", "Personel", "Rota",
                "MusteriKayitTipi", "MusteriTipi", "SahiplikTipi", "AltTip",
                "FiyatListesi", "BANKA", "Tutar", "BÖLGE",
            ],
            expected_data_rows=1,
        )


def test_sales_contract_rejects_numeric_identifier_cells(tmp_path):
    output = tmp_path / f"{FOM_SALES_OUTPUT_BASENAME}.xls"
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("SATIS_FATURALARI")
    headers = ["MüşteriKodu", "FaturaNo", "Tutar"]
    for column, header in enumerate(headers):
        sheet.write(0, column, header)
    sheet.write(1, 0, int(TEST_SALES_CUSTOMER_ID))
    sheet.write(1, 1, TEST_SALES_DOCUMENT_ID)
    sheet.write(1, 2, 100.0)
    workbook.save(str(output))

    with pytest.raises(OutputContractError, match="kimlik alanları metin"):
        validate_fom_integration_output(
            output,
            expected_basename=FOM_SALES_OUTPUT_BASENAME,
            expected_sheet_name="SATIS_FATURALARI",
            expected_headers=headers,
            expected_data_rows=1,
        )


def test_fom_contract_rejects_changed_template_number_format(tmp_path):
    template = tmp_path / "template.xls"
    output = tmp_path / f"{FOM_SALES_OUTPUT_BASENAME}.xls"
    headers = ["MüşteriKodu", "Tutar"]
    _write_fom_contract_file(
        template,
        headers=headers,
        amount_format="#,##0.00",
    )
    _write_fom_contract_file(
        output,
        headers=headers,
        amount_format="General",
    )

    with pytest.raises(OutputContractError, match="hücre biçimleri"):
        validate_fom_integration_output(
            output,
            expected_basename=FOM_SALES_OUTPUT_BASENAME,
            expected_sheet_name="SATIS_FATURALARI",
            expected_headers=headers,
            expected_data_rows=1,
            template_path=template,
        )


def test_toplu_output_contract_rejects_changed_bank_code_cell_format(tmp_path):
    profile = OutputProfileStore(Path(__file__).resolve().parents[1] / "config").get("netsis_toplu")
    template = tmp_path / "template.xls"
    output = tmp_path / "output.xls"
    _write_contract_file(template, profile, "0.00")
    _write_contract_file(output, profile, "@")
    records = [
        NetsisRecord(
            islem_tarihi=datetime(2026, 9, 5),
            cari_kodu="TEST001",
            tutar=1250.50,
            aciklama="TEST",
            banka="Garanti",
            bolge="BODRUM",
            kaynak="TEST",
            banka_hesap_kodu="SENTETIK-BANKA",
        )
    ]

    with pytest.raises(OutputContractError, match="hücre biçimi"):
        validate_netsis_output(output, profile, records, template)


def test_output_contract_rejects_amount_difference(tmp_path):
    profile = OutputProfileStore(Path(__file__).resolve().parents[1] / "config").get("netsis_toplu")
    output = tmp_path / "output.xls"
    _write_contract_file(output, profile, "0.00")
    records = [
        NetsisRecord(
            islem_tarihi=datetime(2026, 9, 5),
            cari_kodu="TEST001",
            tutar=1200,
            aciklama="TEST",
            banka="Garanti",
            bolge="BODRUM",
            kaynak="TEST",
            banka_hesap_kodu="SENTETIK-BANKA",
        )
    ]

    with pytest.raises(OutputContractError, match="toplamı uyuşmuyor"):
        validate_netsis_output(output, profile, records)


def test_toplu_output_contract_rejects_changed_profile_constant(tmp_path):
    profile = OutputProfileStore(Path(__file__).resolve().parents[1] / "config").get(
        "netsis_toplu"
    )
    output = tmp_path / "output.xls"
    # Değeri değiştirmek için aynı yapıyı tekrar ve hatalı yön sabitiyle yaz.
    replacement = xlwt.Workbook()
    sheet = replacement.add_sheet("Sheet1")
    for column, header in enumerate(profile.headers()):
        sheet.write(0, column, header)
    for column, definition in enumerate(profile.columns):
        if (
            definition.source_kind == "const"
            and definition.value is not None
            and column != 1
        ):
            style = (
                xlwt.easyxf(num_format_str="#,##0.00")
                if definition.style == "amount"
                else xlwt.Style.default_style
            )
            sheet.write(1, column, definition.value, style)
    sheet.write(1, 0, "SENTETIK-BANKA")
    sheet.write(1, 1, 1)
    sheet.write(1, 3, datetime(2026, 9, 5), xlwt.easyxf(num_format_str="m/d/yy"))
    sheet.write(1, 4, datetime(2026, 9, 5), xlwt.easyxf(num_format_str="m/d/yy"))
    sheet.write(1, 7, "TEST001")
    sheet.write(1, 14, 1250.50, xlwt.easyxf(num_format_str="#,##0.00"))
    replacement.save(str(output))
    records = [
        NetsisRecord(
            islem_tarihi=datetime(2026, 9, 5),
            cari_kodu="TEST001",
            tutar=1250.50,
            aciklama="TEST",
            banka="Garanti",
            bolge="BODRUM",
            kaynak="TEST",
            banka_hesap_kodu="SENTETIK-BANKA",
        )
    ]

    with pytest.raises(OutputContractError, match="sabit alanları"):
        validate_netsis_output(output, profile, records)


def test_profile_loader_honors_explicit_non_amount_styles():
    store = OutputProfileStore(Path(__file__).resolve().parents[1] / "config")
    profile = store.get("netsis")
    styles = {column.header: column.style for column in profile.columns}

    assert styles["Tutar"] == "amount"
    assert styles["Döviz Tutar"] == "amount"
    assert styles["İşlem Masrafı Tutar"] == "text"
    assert styles["BSMV Tutar"] == "text"


def test_xlsx_contract_preserves_template_sheet_set_and_two_bank_codes(tmp_path):
    profile = OutputProfileStore(Path(__file__).resolve().parents[1] / "config").get(
        "netsis_virman_toplu"
    )
    template = tmp_path / "template.xlsx"
    output = tmp_path / "output.xlsx"

    for path in (template, output):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Sheet1"
        sheet.append(profile.headers())
        sheet.append([
            "BANK-SOURCE", 1, None, "06.09.2026", "06.09.2026", None, None,
            "BANK-TARGET", None, None, None, None, 0, None, 1250, "TEST",
            None, None, "R00", 101, "TEST", None, None, None, None, None,
            None, None, None, None, None, None,
        ])
        sheet.cell(2, 15).number_format = "#,##0.00"
        workbook.create_sheet("Sayfa2")
        workbook.create_sheet("Sheet3")
        workbook.save(path)

    records = [
        type("Record", (), {"tutar": 1250})()
    ]
    validate_netsis_output(output, profile, records, template)


def test_xlsx_contract_rejects_removed_template_sheet(tmp_path):
    profile = OutputProfileStore(Path(__file__).resolve().parents[1] / "config").get(
        "netsis_virman_toplu"
    )
    template = tmp_path / "template.xlsx"
    output = tmp_path / "output.xlsx"
    for path, extra_sheet in ((template, True), (output, False)):
        workbook = Workbook()
        workbook.active.append(profile.headers())
        if extra_sheet:
            workbook.create_sheet("Sayfa2")
        workbook.save(path)

    with pytest.raises(OutputContractError, match="sayfaları"):
        validate_netsis_output(output, profile, [], template)


def _write_virman_contract_pair(tmp_path: Path) -> tuple[Path, Path, object]:
    profile = OutputProfileStore(Path(__file__).resolve().parents[1] / "config").get(
        "netsis_virman_toplu"
    )
    template = tmp_path / "virman-template.xlsx"
    output = tmp_path / "virman-output.xlsx"
    values = [
        TEST_VIRMAN_SOURCE_BANK_CODE, 1, None, "11.09.2026", "11.09.2026", None, None,
        TEST_VIRMAN_TARGET_BANK_CODE, None, None, None, None, 0, None, 2_000_000, "TEST",
        None, None, "G01", 210, "00", None, None, None, None, None,
        None, None, None, None, None, None,
    ]
    for path in (template, output):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(profile.headers())
        sheet.append(values)
        for column in (14, 15, 26, 27, 31, 32):
            sheet.cell(2, column).number_format = "#,##0.00"
        sheet.cell(2, 21).number_format = "@"
        workbook.save(path)
    record = type("Record", (), {"tutar": 2_000_000})()
    return template, output, (profile, [record])


def test_virman_contract_rejects_any_changed_template_cell_format(tmp_path):
    template, output, (profile, records) = _write_virman_contract_pair(tmp_path)
    workbook = load_workbook(output)
    workbook.active.cell(2, 26).number_format = "General"
    workbook.save(output)

    with pytest.raises(OutputContractError, match="virman hücre biçimleri"):
        validate_netsis_output(output, profile, records, template)


def test_virman_contract_rejects_numeric_plasiyer_code(tmp_path):
    template, output, (profile, records) = _write_virman_contract_pair(tmp_path)
    workbook = load_workbook(output)
    workbook.active.cell(2, 21, 0).number_format = "@"
    workbook.save(output)

    with pytest.raises(OutputContractError, match="metin alanları sayıya"):
        validate_netsis_output(output, profile, records, template)
