from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


_TURKISH_HEADER_TRANSLATION = str.maketrans(
    {"Ç": "C", "Ğ": "G", "İ": "I", "Ö": "O", "Ş": "S", "Ü": "U"}
)

# Banka ve Netsis dışa aktarımlarında aynı alan farklı görünen başlıklarla
# gelebiliyor. Profildeki anlamı koruyup yalnız yaygın başlık karşılıklarını
# eşdeğer sayıyoruz; sütun sırasına bağlı tahmin yapılmıyor.
_HEADER_EQUIVALENCE_GROUPS = (
    {"TARIH", "ISLEM TARIHI", "ISLEM TARIH SAAT", "ISLEM TARIHI SAATI", "HAREKET TARIHI"},
    {"ACIKLAMA", "ISLEM ACIKLAMASI", "ISLEM ACIKLAMA", "HAREKET ACIKLAMASI"},
    {"TUTAR", "ISLEM TUTARI", "HAREKET TUTARI"},
    {"BAKIYE", "HESAP BAKIYESI", "GUNCEL BAKIYE"},
    {"BORC", "BORC TUTARI"},
    {"ALACAK", "ALACAK TUTARI"},
)


def normalize_excel_header(value: object) -> str:
    text = " ".join(str(value).replace("\n", " ").split()).upper()
    text = text.translate(_TURKISH_HEADER_TRANSLATION)
    return " ".join(re.findall(r"[A-Z0-9]+", text))


def headers_are_equivalent(actual: object, expected: object) -> bool:
    actual_key = normalize_excel_header(actual)
    expected_key = normalize_excel_header(expected)
    if actual_key == expected_key:
        return True
    return any(
        actual_key in group and expected_key in group
        for group in _HEADER_EQUIVALENCE_GROUPS
    )


def _canonical_header(actual: object, expected_headers: set[str]) -> str:
    # Önce birebir normalize edilmiş eşleşmeyi seç; ardından anlam eşdeğerine
    # düş. Böylece birden fazla profil alanı olduğunda en kesin başlık kazanır.
    for expected in expected_headers:
        if normalize_excel_header(actual) == normalize_excel_header(expected):
            return expected
    for expected in expected_headers:
        if headers_are_equivalent(actual, expected):
            return expected
    return " ".join(str(actual).replace("\n", " ").split())


def read_excel_raw(path: str | Path) -> pd.DataFrame:
    return pd.read_excel(path, header=None, dtype=object)


def extract_letterhead_text(path, header_row_index: int | None) -> str:
    """Gerçek başlık satırından önceki antet/bilgi bloğundaki tüm hücreleri
    tek bir metin olarak birleştirir (bölge/banka kodu gibi bilgileri aramak
    için kullanılır). Antet yoksa boş metin döner.
    """
    if header_row_index is None or header_row_index == 0:
        return ""
    raw = pd.read_excel(path, header=None, dtype=object, nrows=header_row_index)
    pieces = []
    for _, row in raw.iterrows():
        for value in row:
            if pd.notna(value):
                pieces.append(str(value))
    return " ".join(pieces)


def find_header_row(raw: pd.DataFrame, expected_headers: set[str], max_scan_rows: int = 40) -> int | None:
    for i in range(min(max_scan_rows, len(raw))):
        row_values = [v for v in raw.iloc[i].values if pd.notna(v)]
        if all(
            any(headers_are_equivalent(actual, expected) for actual in row_values)
            for expected in expected_headers
        ):
            return i
    return None


def read_excel_with_auto_header(path, expected_headers: set[str], max_scan_rows: int = 40) -> pd.DataFrame:
    """Gerçek banka/Netsis Excel dışa aktarımlarında, asıl veri tablosundan önce
    genelde bir antet/bilgi bloğu (banka logosu, şirket ünvanı, hesap bilgileri
    vb.) bulunur — bu yüzden gerçek sütun başlıkları her zaman 1. satırda
    olmayabilir. Bu fonksiyon, beklenen sütun adlarının tamamının aynı satırda
    bulunduğu ilk satırı bulup gerçek başlık satırı olarak kullanır; üstündeki
    her şeyi (antet/bilgi bloğunu) atar.
    """
    raw = read_excel_raw(path)
    header_row_index = find_header_row(raw, expected_headers, max_scan_rows)

    if header_row_index is None:
        # Beklenen başlıklar bulunamadıysa, ilk satırı başlık kabul edip
        # normal davranışa geri dön — çağıran taraf zaten eksik sütun
        # hatasını üretecek, bu da kullanıcıya daha anlaşılır bir mesaj verir.
        raw.columns = [str(c) for c in raw.iloc[0]]
        return raw.iloc[1:].reset_index(drop=True)

    dataframe = raw.iloc[header_row_index + 1:].reset_index(drop=True)
    dataframe.columns = [
        _canonical_header(column, expected_headers)
        for column in raw.iloc[header_row_index]
    ]
    return dataframe
