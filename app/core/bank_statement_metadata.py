from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class BankStatementMetadata:
    """Banka ekstresinin antet/bilgi bloğundan çıkarılan kurumsal bilgiler.

    Bankadan bankaya format değiştiği için tüm alanlar isteğe bağlıdır;
    bulunamayan bir alan ``None`` kalır, hiçbir hata fırlatılmaz.
    """

    banka_adi: str | None = None
    sirket_unvani: str | None = None
    hesap: str | None = None
    iban: str | None = None
    sube: str | None = None
    donem_baslangic: str | None = None
    donem_bitis: str | None = None
    bildirilen_bakiye: str | None = None


_LABEL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sirket_unvani": ("şirket ünvanı", "sirket unvani", "ünvan", "unvan"),
    "hesap": ("hesap",),
    "iban": ("iban",),
    "sube": ("şube", "sube"),
    "donem_baslangic": ("başlangıç", "baslangic"),
    "donem_bitis": ("bitiş", "bitis"),
    "bildirilen_bakiye": ("kullanılabilir bakiye", "bakiye"),
}


def extract_bank_statement_metadata(path: str | Path, header_row_index: int | None) -> BankStatementMetadata:
    """Gerçek başlık satırından önceki antet bloğunu tarayıp banka adı ve
    hesap bilgilerini (varsa) çıkarır. Format tanınmazsa boş bir metadata
    döner — bu, mutabakat işleminin kendisini hiçbir şekilde etkilemez.
    """
    if header_row_index is None or header_row_index == 0:
        return BankStatementMetadata()

    raw = pd.read_excel(path, header=None, dtype=object, nrows=header_row_index)

    banka_adi = None
    for _, row in raw.iterrows():
        for value in row:
            if pd.notna(value) and isinstance(value, str) and len(value.strip()) > 3:
                banka_adi = value.strip().split("\n")[0].strip()
                break
        if banka_adi:
            break

    found: dict[str, str] = {}
    for _, row in raw.iterrows():
        cells = [str(c).strip() for c in row if pd.notna(c)]
        if len(cells) < 2:
            continue
        label = cells[0].lower()
        value = cells[1]
        for field, keywords in _LABEL_KEYWORDS.items():
            if field in found:
                continue
            if any(keyword in label for keyword in keywords):
                found[field] = value

    return BankStatementMetadata(banka_adi=banka_adi, **found)


# Banka adı metninde geçebilecek anahtar kelime -> logo dosya adı (uzantısız).
# Yeni bir banka eklemek icin sadece buraya bir satir eklemeniz yeterli.
_BANK_LOGO_ALIASES: dict[str, tuple[str, ...]] = {
    "garanti": ("GARANTİ", "GARANTI"),
    "isbank": ("İŞ BANKASI", "IS BANKASI", "İŞBANK", "TÜRKİYE İŞ BANKASI"),
    "yapikredi": ("YAPI VE KREDİ", "YAPI KREDİ", "YAPIKREDI"),
    "akbank": ("AKBANK",),
    "ziraat": ("ZİRAAT", "ZIRAAT"),
    "vakifbank": ("VAKIFBANK", "VAKIF BANKASI", "VAKIFLAR BANKASI"),
    "halkbank": ("HALKBANK", "HALK BANKASI"),
    "denizbank": ("DENİZBANK", "DENIZBANK"),
    "qnb": ("QNB", "FİNANSBANK"),
    "teb": ("TEB", "TÜRK EKONOMİ BANKASI"),
    "ing": ("ING",),
    "seker": ("ŞEKERBANK", "SEKERBANK"),
    "kuveytturk": ("KUVEYT TÜRK",),
    "albaraka": ("ALBARAKA",),
    "odeabank": ("ODEA",),
    "fibabanka": ("FİBABANKA", "FIBABANKA"),
    "burgan": ("BURGAN",),
}


def find_bank_logo_path(banka_adi: str | None, assets_dir: Path) -> Path | None:
    """Banka adı metninde tanınan bir banka anahtar kelimesi varsa ve
    ``assets_dir`` altında o bankaya ait bir PNG dosyası bulunuyorsa yolunu
    döner. Ne banka tanınırsa ne de logo dosyası mevcutsa ``None`` döner —
    ekran logo olmadan da düzgün görünmelidir.
    """
    if not banka_adi:
        return None
    normalized = banka_adi.upper()
    for logo_key, keywords in _BANK_LOGO_ALIASES.items():
        if any(keyword in normalized for keyword in keywords):
            candidate = assets_dir / "bank_logos" / f"{logo_key}.png"
            if candidate.is_file():
                return candidate
    return None
