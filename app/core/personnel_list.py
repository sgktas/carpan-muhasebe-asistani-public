from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import pandas as pd

from app.core.region_config import RegionConfig

_TURKISH_UPPER_MAP = {"Ş": "S", "Ğ": "G", "Ü": "U", "Ö": "O", "Ç": "C"}


def _normalize(text: str) -> str:
    text = (text or "").upper()
    for tr_char, ascii_char in _TURKISH_UPPER_MAP.items():
        text = text.replace(tr_char, ascii_char)
    text = text.replace("İ", "I")
    return text


@dataclass(frozen=True)
class PersonnelEntry:
    ad: str  # normalize edilmiş ad soyad
    ad_gorunen: str  # orijinal (ekranda gösterilecek) ad soyad
    bolge: str
    kelimeler: tuple[str, ...]  # ad soyadın normalize edilmiş kelimeleri


class PersonnelList:
    """Şube + personel adı listesini okur; her personelin hangi bölgede
    çalıştığını (mevcut bölge takma adları üzerinden) çözer.
    """

    def __init__(self, entries: list[PersonnelEntry]):
        self.entries = entries

    @classmethod
    def from_excel(cls, path: str | Path, region_config: RegionConfig) -> "PersonnelList":
        dataframe = pd.read_excel(path, dtype=object)
        columns = {str(c).strip().upper(): c for c in dataframe.columns}
        sube_col = columns.get("ŞUBE") or columns.get("SUBE")
        personel_col = columns.get("PERSONEL")
        if not sube_col or not personel_col:
            raise ValueError(
                "Personel listesinde 'ŞUBE' ve 'PERSONEL' sütunları bulunamadı. "
                f"Bulunan sütunlar: {', '.join(map(str, dataframe.columns))}"
            )

        entries: list[PersonnelEntry] = []
        for _, row in dataframe.iterrows():
            sube_text = str(row[sube_col]).strip() if pd.notna(row[sube_col]) else ""
            ad_text = str(row[personel_col]).strip() if pd.notna(row[personel_col]) else ""
            if not sube_text or not ad_text:
                continue
            bolge = region_config.find_region_in_text(sube_text)
            if not bolge:
                continue
            normalized_ad = _normalize(ad_text)
            words = tuple(w for w in normalized_ad.split() if len(w) >= 3)
            if not words:
                continue
            entries.append(PersonnelEntry(ad=normalized_ad, ad_gorunen=ad_text, bolge=bolge, kelimeler=words))

        return cls(entries)

    def find_matches(self, aciklama: str) -> list[PersonnelEntry]:
        """Açıklama metninde geçen personel(ler)i bulur.

        Bir personelin TÜM isim kelimelerinin (kısaltılmamış olanların)
        açıklamada geçmesi aranır — böylece 'ALİ' gibi tek başına çok genel
        bir ad, yanlışlıkla eşleşmeyi tetiklemez.
        """
        normalized_aciklama = _normalize(aciklama)
        # Kelime sınırlarına duyarlı arama için açıklamayı da kelimelere ayır.
        aciklama_words = set(re.findall(r"[A-Z]+", normalized_aciklama))

        matches = []
        for entry in self.entries:
            if all(word in aciklama_words for word in entry.kelimeler):
                matches.append(entry)
        return matches
