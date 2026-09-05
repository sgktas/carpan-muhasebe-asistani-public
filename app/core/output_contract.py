from __future__ import annotations

from pathlib import Path

import xlrd

from app.core.money import money_sum
from app.core.output_profile import OutputProfile
from app.models.records import NetsisRecord


class OutputContractError(ValueError):
    """Oluşan Excel dosyası seçili muhasebe profiliyle uyuşmadığında."""


def validate_netsis_output(
    output_path: str | Path,
    profile: OutputProfile,
    records: list[NetsisRecord],
    template_path: str | Path | None = None,
) -> None:
    """Netsis'e verilmeden önce başlık, satır, tutar ve kritik biçimi denetler."""
    output_path = Path(output_path)
    try:
        book = xlrd.open_workbook(str(output_path), formatting_info=True)
    except Exception as error:
        raise OutputContractError(f"Çıktı Excel 97-2003 olarak doğrulanamadı: {error}") from error

    if book.sheet_names() != ["Sheet1"]:
        raise OutputContractError(
            f"Netsis çıktısı yalnız Sheet1 içermeli; bulunan sayfalar: {book.sheet_names()}"
        )
    sheet = book.sheet_by_index(0)
    expected_headers = profile.headers()
    actual_headers = [str(sheet.cell_value(0, column)) for column in range(sheet.ncols)]
    if actual_headers != expected_headers:
        raise OutputContractError("Netsis çıktısının sütun başlıkları veya sırası değişmiş.")

    data_rows = [
        row
        for row in range(1, sheet.nrows)
        if any(str(sheet.cell_value(row, column)).strip() for column in range(sheet.ncols))
    ]
    if len(data_rows) != len(records):
        raise OutputContractError(
            f"Netsis çıktı satır sayısı uyuşmuyor: beklenen {len(records)}, oluşan {len(data_rows)}."
        )

    amount_indexes = [
        index
        for index, column in enumerate(profile.columns)
        if column.source_kind == "field" and column.field == "tutar"
    ]
    if len(amount_indexes) != 1:
        raise OutputContractError("Netsis profilinde tam bir adet işlem tutarı sütunu bulunmalı.")
    amount_index = amount_indexes[0]
    try:
        output_total = money_sum(sheet.cell_value(row, amount_index) for row in data_rows)
    except ValueError as error:
        raise OutputContractError(f"Netsis tutar sütununda sayısal olmayan değer var: {error}") from error
    expected_total = money_sum(record.tutar for record in records)
    if output_total != expected_total:
        raise OutputContractError(
            f"Netsis çıktı toplamı uyuşmuyor: beklenen {expected_total}, oluşan {output_total}."
        )

    bank_indexes = [
        index
        for index, column in enumerate(profile.columns)
        if column.source_kind == "field" and column.field == "banka_hesap_kodu"
    ]
    if not bank_indexes:
        return
    bank_index = bank_indexes[0]
    missing_rows = [row + 1 for row in data_rows if not str(sheet.cell_value(row, bank_index)).strip()]
    if missing_rows:
        raise OutputContractError(f"Banka hesap kodu boş olan satırlar var: {missing_rows[:10]}")

    if not template_path or not Path(template_path).is_file() or not data_rows:
        return
    template = xlrd.open_workbook(str(template_path), formatting_info=True)
    template_sheet = template.sheet_by_index(0)
    expected_format = _number_format(template, template_sheet, 1, bank_index)
    wrong_format_rows = [
        row + 1
        for row in data_rows
        if _number_format(book, sheet, row, bank_index) != expected_format
    ]
    if wrong_format_rows:
        raise OutputContractError(
            "Banka hesap kodu hücre biçimi onaylı şablondan farklı. "
            f"Kontrol edilmesi gereken satırlar: {wrong_format_rows[:10]}"
        )


def _number_format(book, sheet, row: int, column: int) -> str:
    xf = book.xf_list[sheet.cell_xf_index(row, column)]
    return book.format_map[xf.format_key].format_str
