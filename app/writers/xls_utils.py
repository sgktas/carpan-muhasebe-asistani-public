from __future__ import annotations

from datetime import date, datetime
import math
import os
from pathlib import Path
import stat
from typing import Iterable, Mapping, Sequence

import xlwt


EXCEL_97_2003_MAX_ROWS = 65_536
EXCEL_97_2003_MAX_COLUMNS = 256


def xls_path(path: str | Path) -> Path:
    """Çıktı yolunu gerçek Excel 97-2003 uzantısına zorlar."""
    return Path(path).with_suffix(".xls")


def ensure_writable(path: str | Path) -> Path:
    """Dosyanın salt-okunur niteliğini platformdan bağımsız biçimde temizler."""
    path = Path(path)
    try:
        current_mode = path.stat().st_mode
        os.chmod(path, current_mode | stat.S_IWUSR | stat.S_IRUSR)
    except OSError:
        pass

    # Windows'ta chmod yanında FILE_ATTRIBUTE_READONLY bayrağını da açıkça kaldır.
    if os.name == "nt":
        try:
            import ctypes

            FILE_ATTRIBUTE_READONLY = 0x00000001
            INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
            kernel32 = ctypes.windll.kernel32
            attrs = kernel32.GetFileAttributesW(str(path))
            if attrs != INVALID_FILE_ATTRIBUTES and attrs & FILE_ATTRIBUTE_READONLY:
                kernel32.SetFileAttributesW(str(path), attrs & ~FILE_ATTRIBUTE_READONLY)
        except Exception:
            # Dosya zaten yazılabilir olabilir; çıktı üretimini bu yardımcı işlem
            # yüzünden başarısız kılmayız.
            pass
    return path


def save_xls(workbook: xlwt.Workbook, output_path: str | Path) -> Path:
    output_path = xls_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(str(output_path))
    return ensure_writable(output_path)


def safe_sheet_name(name: object, used_names: set[str] | None = None) -> str:
    raw = str(name or "Sheet1")
    for char in "[]:*?/\\":
        raw = raw.replace(char, "-")
    base = (raw.strip() or "Sheet1")[:31]
    if used_names is None or base not in used_names:
        if used_names is not None:
            used_names.add(base)
        return base

    suffix = 2
    while True:
        suffix_text = f"_{suffix}"
        candidate = f"{base[:31 - len(suffix_text)]}{suffix_text}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        suffix += 1


def normalize_xls_value(value):
    """Pandas/numpy değerlerini xlwt'nin güvenli yazabileceği tipe çevirir."""
    if value is None:
        return ""

    # pandas.NaT / numpy.nan / pd.NA gibi değerleri boş hücreye çevir.
    try:
        missing = value != value
        if isinstance(missing, bool) and missing:
            return ""
    except Exception:
        pass

    try:
        import pandas as pd

        if pd.isna(value):
            return ""
    except Exception:
        pass

    # numpy scalar'ları saf Python değerlerine dönüştür.
    item_method = getattr(value, "item", None)
    if callable(item_method) and not isinstance(value, (str, bytes, datetime, date)):
        try:
            value = item_method()
        except Exception:
            pass

    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        # BIFF8 tek hücre metin sınırı.
        return value[:32_767]
    return value


def make_styles() -> dict[str, xlwt.XFStyle]:
    header = xlwt.easyxf(
        "font: bold on; align: horiz center, vert center, wrap on; "
        "borders: left thin, right thin, top thin, bottom thin;"
    )
    text = xlwt.easyxf("align: vert center;")
    centered = xlwt.easyxf("align: horiz center, vert center;")
    date_style = xlwt.easyxf("align: horiz center, vert center;", num_format_str="DD.MM.YYYY")
    amount = xlwt.easyxf("align: horiz right, vert center;", num_format_str="#,##0.00")
    integer = xlwt.easyxf("align: horiz right, vert center;", num_format_str="0")
    return {
        "header": header,
        "text": text,
        "centered": centered,
        "date": date_style,
        "amount": amount,
        "integer": integer,
    }


def write_cell(sheet, row: int, col: int, value, styles: Mapping[str, xlwt.XFStyle], style_name: str | None = None) -> None:
    value = normalize_xls_value(value)
    style = styles.get(style_name or "text", styles["text"])
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
        style = styles["date"] if style_name is None else style
    elif isinstance(value, datetime):
        if style_name == "date":
            value = datetime(value.year, value.month, value.day)
        style = styles["date"] if style_name is None else style
    sheet.write(row, col, value, style)


def write_table_xls(
    rows: Sequence[Mapping[str, object]],
    output_path: str | Path,
    *,
    sheet_name: str = "Rapor",
    columns: Sequence[str] | None = None,
    column_widths: Mapping[str, int] | None = None,
    amount_columns: Iterable[str] = (),
    date_columns: Iterable[str] = (),
) -> Path:
    if not rows and not columns:
        raise ValueError("Excel raporu için en az bir sütun gerekli.")

    resolved_columns = list(columns or rows[0].keys())
    if len(resolved_columns) > EXCEL_97_2003_MAX_COLUMNS:
        raise ValueError("Excel 97-2003 en fazla 256 sütun destekler.")
    if len(rows) + 1 > EXCEL_97_2003_MAX_ROWS:
        raise ValueError("Excel 97-2003 en fazla 65.536 satır destekler.")

    amount_set = set(amount_columns) | {
        column for column in resolved_columns if "tutar" in column.casefold()
    }
    date_set = set(date_columns)
    widths = dict(column_widths or {})
    styles = make_styles()
    workbook = xlwt.Workbook(encoding="utf-8", style_compression=2)
    sheet = workbook.add_sheet(safe_sheet_name(sheet_name))
    sheet.panes_frozen = True
    sheet.horz_split_pos = 1

    for col_index, column in enumerate(resolved_columns):
        sheet.write(0, col_index, column, styles["header"])
        requested_width = widths.get(column)
        if requested_width is None:
            sample_lengths = [len(str(column))]
            sample_lengths.extend(len(str(normalize_xls_value(row.get(column, "")))) for row in rows[:200])
            requested_width = max(8, min(max(sample_lengths, default=8) + 2, 60))
        sheet.col(col_index).width = min(int(requested_width * 256), 65_535)

    for row_index, row in enumerate(rows, start=1):
        for col_index, column in enumerate(resolved_columns):
            style_name = "amount" if column in amount_set else "date" if column in date_set else None
            write_cell(sheet, row_index, col_index, row.get(column), styles, style_name)

    return save_xls(workbook, output_path)
