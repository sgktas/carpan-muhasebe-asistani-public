from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
import xlrd

from app.core.money import money_sum
from app.core.erp_acceptance_matrix import (
    FOM_ACCEPTANCE_MATRIX,
    NETSIS_ACCEPTANCE_MATRIX,
)
from app.core.output_profile import OutputProfile
from app.models.records import NetsisRecord


class OutputContractError(ValueError):
    """Oluşan Excel dosyası seçili muhasebe profiliyle uyuşmadığında."""


# Psoft, FOM'un kendi dışa aktarma adlarını nesne adı olarak bekliyor. Bu iki
# ad kullanıcı tarafından gerçek aktarımda doğrulandı; serbest ad kabul etme.
FOM_SALES_OUTPUT_BASENAME = "ENT-Muhasebe_Entegrasyon(Satış_Faturaları)"
FOM_COLLECTION_OUTPUT_BASENAME = "ENT-Muhasebe_Entegrasyon(Tahsilatlar)"
FOM_INTEGRATION_BASENAMES = frozenset(
    {FOM_SALES_OUTPUT_BASENAME, FOM_COLLECTION_OUTPUT_BASENAME}
)


def validate_fom_integration_output(
    output_path: str | Path,
    *,
    expected_basename: str,
    expected_sheet_name: str,
    expected_headers: list[str],
    expected_data_rows: int,
    template_path: str | Path | None = None,
) -> None:
    """Psoft'a verilecek FOM .xls çıktısının aktarım sözleşmesini denetler."""
    output_path = Path(output_path)
    if output_path.suffix.casefold() != ".xls":
        raise OutputContractError("FOM entegrasyon çıktısı Excel 97-2003 (.xls) olmalı.")
    if output_path.stem != expected_basename:
        raise OutputContractError(
            f"FOM entegrasyon dosya adı değişmiş: {output_path.name}"
        )
    if expected_basename not in FOM_INTEGRATION_BASENAMES:
        raise OutputContractError(
            "Psoft entegrasyon dosya adı onaylı satış veya tahsilat adı olmalı."
        )
    if not expected_sheet_name or len(expected_sheet_name) > 31:
        raise OutputContractError(
            "FOM entegrasyon şablonunun çalışma sayfası adı geçersiz."
        )
    try:
        if output_path.read_bytes()[:8] != bytes.fromhex("D0CF11E0A1B11AE1"):
            raise OutputContractError(
                "FOM entegrasyon çıktısının uzantısı .xls ancak dosya biçimi Excel 97-2003 değil."
            )
        output = _WorkbookView.open(output_path)
    except OutputContractError:
        raise
    except Exception as error:
        raise OutputContractError(
            f"FOM entegrasyon Excel'i doğrulanamadı: {error}"
        ) from error

    if output.sheet_names != [expected_sheet_name]:
        raise OutputContractError(
            f"FOM entegrasyon sayfa adı değişmiş: {output.sheet_names}"
        )
    if output.ncols != len(expected_headers):
        raise OutputContractError(
            "FOM entegrasyon çıktısının sütun sayısı şablonla uyuşmuyor."
        )

    baseline_headers = [str(value or "") for value in expected_headers]
    template = None
    if template_path and Path(template_path).is_file():
        try:
            template = _WorkbookView.open(Path(template_path))
        except Exception as error:
            raise OutputContractError(
                f"FOM entegrasyon şablonu doğrulanamadı: {error}"
            ) from error
        if template.ncols != output.ncols:
            raise OutputContractError(
                "FOM entegrasyon çıktısının sütun sayısı orijinal şablonla uyuşmuyor."
            )
        if template.sheet_names != [expected_sheet_name]:
            raise OutputContractError(
                "FOM entegrasyon şablonunun çalışma sayfası adı beklenen özgün adla uyuşmuyor."
            )
        baseline_headers = [
            str(template.value(0, column) or "")
            for column in range(template.ncols)
        ]

    actual_headers = [
        str(output.value(0, column) or "")
        for column in range(output.ncols)
    ]
    if actual_headers != baseline_headers:
        raise OutputContractError(
            "FOM entegrasyon çıktısının başlıkları veya sütun sırası şablondan farklı."
        )

    data_rows = [
        row
        for row in range(1, output.nrows)
        if any(str(output.value(row, column) or "").strip() for column in range(output.ncols))
    ]
    if len(data_rows) != expected_data_rows:
        raise OutputContractError(
            "FOM entegrasyon satır sayısı uyuşmuyor: "
            f"beklenen {expected_data_rows}, oluşan {len(data_rows)}."
        )

    acceptance_rule = FOM_ACCEPTANCE_MATRIX.get(expected_basename)
    if acceptance_rule:
        text_headers = acceptance_rule.text_headers
        header_indexes = {
            header: index for index, header in enumerate(actual_headers)
            if header in text_headers
        }
        invalid_cells = [
            f"{header} satır {row + 1}"
            for header, column in header_indexes.items()
            for row in data_rows
            if str(output.value(row, column) or "").strip()
            and not output.is_text(row, column)
        ]
        if invalid_cells:
            raise OutputContractError(
                "FOM entegrasyonundaki kimlik alanları metin olarak korunmadı: "
                + ", ".join(invalid_cells[:10])
            )

        if (
            template is not None
            and template.nrows > 1
            and data_rows
            and acceptance_rule.template_format_scope == "all"
        ):
            wrong_cells = [
                f"{actual_headers[column] or f'Sütun {column + 1}'} satır {row + 1}"
                for row in data_rows
                for column in range(output.ncols)
                if output.number_format(row, column) != template.number_format(1, column)
            ]
            if wrong_cells:
                raise OutputContractError(
                    "FOM entegrasyon hücre biçimleri onaylı şablondan farklı: "
                    + ", ".join(wrong_cells[:10])
                )


def validate_netsis_output(
    output_path: str | Path,
    profile: OutputProfile,
    records: list[NetsisRecord],
    template_path: str | Path | None = None,
) -> None:
    """Netsis'e verilmeden önce başlık, satır, tutar ve kritik biçimi denetler."""
    output_path = Path(output_path)
    try:
        output = _WorkbookView.open(output_path)
    except Exception as error:
        raise OutputContractError(f"Çıktı Excel dosyası doğrulanamadı: {error}") from error

    expected_sheets = ["Sheet1"]
    template = None
    if template_path and Path(template_path).is_file():
        template = _WorkbookView.open(Path(template_path))
        expected_sheets = template.sheet_names
    if output.sheet_names != expected_sheets:
        raise OutputContractError(
            f"Netsis çıktı sayfaları onaylı şablonla uyuşmuyor: {output.sheet_names}"
        )
    expected_headers = profile.headers()
    actual_headers = [str(output.value(0, column) or "") for column in range(output.ncols)]
    if actual_headers != expected_headers:
        raise OutputContractError("Netsis çıktısının sütun başlıkları veya sırası değişmiş.")

    data_rows = [
        row
        for row in range(1, output.nrows)
        if any(str(output.value(row, column) or "").strip() for column in range(output.ncols))
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
        output_total = money_sum(output.value(row, amount_index) for row in data_rows)
    except ValueError as error:
        raise OutputContractError(f"Netsis tutar sütununda sayısal olmayan değer var: {error}") from error
    expected_total = money_sum(record.tutar for record in records)
    if output_total != expected_total:
        raise OutputContractError(
            f"Netsis çıktı toplamı uyuşmuyor: beklenen {expected_total}, oluşan {output_total}."
        )

    acceptance_rule = NETSIS_ACCEPTANCE_MATRIX.get(profile.profile_id)
    if acceptance_rule:
        if acceptance_rule.require_profile_constants:
            wrong_constants = [
                f"{column.header} satır {row + 1}"
                for column_index, column in enumerate(profile.columns)
                if column.source_kind == "const"
                for row in data_rows
                if not _same_constant(output.value(row, column_index), column.value)
            ]
            if wrong_constants:
                raise OutputContractError(
                    "Netsis sabit alanları profil sözleşmesinden farklı: "
                    + ", ".join(wrong_constants[:10])
                )

        text_headers = acceptance_rule.text_headers
        text_indexes = [
            index for index, column in enumerate(profile.columns)
            if column.header in text_headers or column.force_text
        ]
        invalid_text_cells = [
            f"{profile.columns[column].header} satır {row + 1}"
            for column in text_indexes
            for row in data_rows
            if output.value(row, column) not in (None, "")
            and not output.is_text(row, column)
        ]
        if invalid_text_cells:
            raise OutputContractError(
                "Netsis metin alanları sayıya dönüştü: "
                + ", ".join(invalid_text_cells[:10])
            )

        if acceptance_rule.require_date_cells:
            invalid_date_cells = [
                f"{profile.columns[column].header} satır {row + 1}"
                for column in profile.column_index(style="date")
                for row in data_rows
                if output.value(row, column) not in (None, "")
                and not output.is_date(row, column)
            ]
            if invalid_date_cells:
                raise OutputContractError(
                    "Netsis tarih alanları gerçek Excel tarihi değil: "
                    + ", ".join(invalid_date_cells[:10])
                )

        invalid_amount_formats = [
            f"{profile.columns[column].header} satır {row + 1}"
            for column in profile.column_index(style="amount")
            for row in data_rows
            if output.value(row, column) not in (None, "")
            and output.number_format(row, column) != "#,##0.00"
        ]
        if invalid_amount_formats:
            raise OutputContractError(
                "Netsis tutar alanları binlik ayraçlı ve iki ondalıklı değil: "
                + ", ".join(invalid_amount_formats[:10])
            )

    bank_indexes = [
        index
        for index, column in enumerate(profile.columns)
        if column.source_kind == "field"
        and str(column.field or "").endswith("banka_hesap_kodu")
    ]
    if bank_indexes:
        missing_rows = [
            row + 1
            for row in data_rows
            if any(not str(output.value(row, index) or "").strip() for index in bank_indexes)
        ]
        if missing_rows:
            raise OutputContractError(f"Banka hesap kodu boş olan satırlar var: {missing_rows[:10]}")

    if template is None or not data_rows:
        return
    if acceptance_rule:
        format_headers = acceptance_rule.template_format_headers
        format_indexes = (
            range(output.ncols)
            if "*" in format_headers
            else [
                index for index, column in enumerate(profile.columns)
                if column.header in format_headers
            ]
        )
        wrong_cells = [
            f"{profile.columns[column].header} satır {row + 1}"
            for row in data_rows
            for column in format_indexes
            if output.number_format(row, column) != template.number_format(1, column)
        ]
        if wrong_cells:
            label = (
                "Hesaplar arası virman hücre biçimleri"
                if profile.profile_id == "netsis_virman_toplu"
                else "Netsis hücre biçimi"
            )
            raise OutputContractError(
                f"{label} onaylı şablondan farklı: "
                + ", ".join(wrong_cells[:10])
            )


def _same_constant(actual: object, expected: object) -> bool:
    if expected in (None, ""):
        return actual in (None, "")
    return actual == expected


class _WorkbookView:
    def __init__(self, book, sheet, *, xlsx: bool):
        self.book = book
        self.sheet = sheet
        self.xlsx = xlsx
        self.sheet_names = list(book.sheetnames if xlsx else book.sheet_names())
        self.nrows = int(sheet.max_row if xlsx else sheet.nrows)
        self.ncols = int(sheet.max_column if xlsx else sheet.ncols)

    @classmethod
    def open(cls, path: Path) -> "_WorkbookView":
        if path.suffix.casefold() == ".xlsx":
            book = load_workbook(path, data_only=True, read_only=False)
            return cls(book, book.worksheets[0], xlsx=True)
        book = xlrd.open_workbook(str(path), formatting_info=True)
        return cls(book, book.sheet_by_index(0), xlsx=False)

    def value(self, row: int, column: int):
        if self.xlsx:
            return self.sheet.cell(row=row + 1, column=column + 1).value
        return self.sheet.cell_value(row, column)

    def number_format(self, row: int, column: int) -> str:
        if self.xlsx:
            return str(self.sheet.cell(row=row + 1, column=column + 1).number_format)
        xf = self.book.xf_list[self.sheet.cell_xf_index(row, column)]
        return self.book.format_map[xf.format_key].format_str

    def is_text(self, row: int, column: int) -> bool:
        if self.xlsx:
            return self.sheet.cell(row=row + 1, column=column + 1).data_type in {"s", "inlineStr"}
        return self.sheet.cell_type(row, column) == xlrd.XL_CELL_TEXT

    def is_date(self, row: int, column: int) -> bool:
        if self.xlsx:
            return isinstance(
                self.sheet.cell(row=row + 1, column=column + 1).value,
                (date, datetime),
            )
        return self.sheet.cell_type(row, column) == xlrd.XL_CELL_DATE
