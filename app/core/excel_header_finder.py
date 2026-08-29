from __future__ import annotations

from pathlib import Path

import pandas as pd


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
        row_values = {str(v).strip() for v in raw.iloc[i].values if pd.notna(v)}
        if expected_headers.issubset(row_values):
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
    dataframe.columns = [str(c).strip() for c in raw.iloc[header_row_index]]
    return dataframe
