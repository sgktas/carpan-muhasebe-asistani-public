from pathlib import Path

import pandas as pd

from app.models.records import TahsilatRecord


class TahsilatParser:
    COLUMN_ALIASES = {
        "musteri_kodu": ("Müşteri Kodu", "MusteriKodu", "Cari Kod", "CariKodu"),
        "musteri_ismi": ("Müşteri İsmi", "MusteriIsmi", "Ünvan", "Unvan", "Cari Adı", "CariAdi"),
        "belge_tarihi": ("Belge Tarihi", "BelgeTarihi", "Tarih"),
        "tutar": ("Tutar", "Tahsilat Tutarı", "TahsilatTutari"),
    }

    # FOM Rapor Düzenleme modülünün ürettiği dosyada ilk sayfa filtreli Netsis
    # raporudur; şubeli eşleştirme için gerekli bütün tahsilatlar bu sayfadadır.
    FULL_COLLECTION_SHEET_KEYS = {"SUBELILER", "SUBELI"}

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.selected_sheet_name: str | int = 0

    def load(self) -> list[TahsilatRecord]:
        dataframe = self._read_dataframe()
        columns = self._resolve_columns(dataframe)
        missing = [field for field in ("musteri_kodu", "musteri_ismi", "tutar") if not columns[field]]
        if missing:
            raise ValueError("Tahsilat raporunda zorunlu sütunlar bulunamadı: " + ", ".join(missing))

        records: list[TahsilatRecord] = []
        for _, row in dataframe.iterrows():
            customer_code = self._text(row[columns["musteri_kodu"]])
            if not customer_code:
                continue
            records.append(TahsilatRecord(
                musteri_kodu=customer_code,
                musteri_ismi=self._text(row[columns["musteri_ismi"]]),
                belge_tarihi=self._date(row[columns["belge_tarihi"]]) if columns["belge_tarihi"] else None,
                tutar=self._amount(row[columns["tutar"]]),
            ))
        return records

    def _read_dataframe(self) -> pd.DataFrame:
        """Doğru tahsilat veri sayfasını seçer.

        Tek sayfalı ham tahsilat raporlarında ilk sayfa okunur. FOM Rapor Düzenleme
        modülünün çıktısında ``ŞUBELİLER`` sayfası varsa yalnız o sayfa okunur;
        çünkü ilk sayfa filtreli bir alt kümedir ve iki sayfayı birleştirmek aynı
        kayıtları mükerrer hale getirir.
        """
        workbook = pd.ExcelFile(self.file_path)
        preferred_sheet = next(
            (
                sheet
                for sheet in workbook.sheet_names
                if self._key(sheet) in self.FULL_COLLECTION_SHEET_KEYS
            ),
            None,
        )
        self.selected_sheet_name = preferred_sheet if preferred_sheet is not None else 0
        return pd.read_excel(
            workbook,
            sheet_name=self.selected_sheet_name,
            dtype=object,
        )

    def _resolve_columns(self, dataframe: pd.DataFrame) -> dict[str, str | None]:
        normalized = {self._key(column): str(column) for column in dataframe.columns}
        return {field: next((normalized.get(self._key(alias)) for alias in aliases if self._key(alias) in normalized), None) for field, aliases in self.COLUMN_ALIASES.items()}

    @staticmethod
    def _key(value: object) -> str:
        return "".join(str(value).upper().replace("İ", "I").replace("Ş", "S").replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O").replace("Ç", "C").split())

    @staticmethod
    def _text(value: object) -> str:
        return "" if pd.isna(value) else str(value).strip()

    @staticmethod
    def _date(value: object):
        converted = pd.to_datetime(value, errors="coerce", dayfirst=True)
        return None if pd.isna(converted) else converted.to_pydatetime()

    @staticmethod
    def _amount(value: object) -> float:
        if pd.isna(value) or str(value).strip() == "":
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(" ", "")
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        return float(pd.to_numeric(text, errors="coerce") or 0.0)
