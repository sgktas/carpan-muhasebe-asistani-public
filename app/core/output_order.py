from __future__ import annotations

from datetime import date, datetime

# Kullanıcı tarafından onaylanan operasyon sırası. Windows Dosya Gezgini
# dosyaları ada göre sıraladığı için çıktı adlarında da bu sıra numaraları
# kullanılır.
DEFAULT_REGION_ORDER: tuple[str, ...] = ("BODRUM", "FETHIYE", "SOKE", "MUGLA")
# Eski dış çağrılar için ad korunur. Üretim akışı yapılandırmadaki sırayı geçirir.
REGION_ORDER = DEFAULT_REGION_ORDER
BANK_ORDER: tuple[str, ...] = ("GARANTI", "YKB", "ZIRAAT")

_SPECIAL_OFFSETS = {
    "ODEME_ONAYLANDI": 1,
    "REFERANSLI": 2,
    "INCELEME_GEREKENLER": 3,
    "GECERSIZ_MANIM_SATIRLARI": 4,
}


def region_sort_key(
    region: str,
    region_order: tuple[str, ...] | list[str] | None = None,
) -> tuple[int, str]:
    normalized = str(region or "").strip().upper()
    order = tuple(region_order or DEFAULT_REGION_ORDER)
    try:
        return order.index(normalized), normalized
    except ValueError:
        return len(order), normalized


def bank_sort_key(bank: str) -> tuple[int, str]:
    normalized = str(bank or "").strip().upper()
    try:
        return BANK_ORDER.index(normalized), normalized
    except ValueError:
        return len(BANK_ORDER), normalized


def region_file_prefix(
    region: str,
    region_order: tuple[str, ...] | list[str] | None = None,
) -> str:
    normalized = str(region or "").strip().upper()
    order = tuple(region_order or DEFAULT_REGION_ORDER)
    try:
        return f"{order.index(normalized) + 1:02d}"
    except ValueError:
        return f"{len(order) + len(_SPECIAL_OFFSETS) + 1:02d}"


def special_file_prefix(
    name: str,
    region_order: tuple[str, ...] | list[str] | None = None,
) -> str:
    order = tuple(region_order or DEFAULT_REGION_ORDER)
    return f"{len(order) + _SPECIAL_OFFSETS[name]:02d}"


def chronological_key(value, source_file: str = "", source_row: int = 0):
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, date):
        moment = datetime(value.year, value.month, value.day)
    else:
        moment = datetime.max
    return moment, str(source_file or ""), int(source_row or 0)
