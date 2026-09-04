from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.bank_statement_metadata import BankStatementMetadata, extract_bank_statement_metadata
from app.core.bank_statement_profile import BankStatementProfile, BankStatementProfileStore
from app.core.excel_header_finder import find_header_row, read_excel_raw, read_excel_with_auto_header
from app.models.records import BankStatementRecord


def _default_profile() -> BankStatementProfile:
    config_dir = Path(__file__).resolve().parents[2] / "config"
    return BankStatementProfileStore(config_dir).get("genel")


class BankStatementParser:
    def __init__(self, file_path: str | Path, profile: BankStatementProfile | None = None):
        self.file_path = Path(file_path)
        self.profile = profile or _default_profile()
        self._header_for = {field: header for header, field in self.profile.columns.items()}

    def load(self) -> list[BankStatementRecord]:
        if not self.file_path.is_file():
            raise FileNotFoundError(f"Banka ekstresi dosyası bulunamadı: {self.file_path}")

        expected_headers = set(self.profile.columns.keys())
        dataframe = read_excel_with_auto_header(self.file_path, expected_headers)
        dataframe.columns = [self._clean_header(c) for c in dataframe.columns]
        self._validate_columns(dataframe)

        h = self._header_for
        excel_header_row_index = int(dataframe.attrs.get("excel_header_row_index", 0))
        records: list[BankStatementRecord] = []
        for index, row in dataframe.iterrows():
            tarih = self._date(row[h["tarih"]])
            tutar = self._amount(row[h["tutar"]])
            if tarih is None or tutar is None:
                continue
            records.append(BankStatementRecord(
                tarih=tarih,
                aciklama=self._text(row[h["aciklama"]]),
                tutar=tutar,
                bakiye=self._amount(row[h["bakiye"]]),
                kaynak_dosya=self.file_path.name,
                kaynak_satir=int(index) + excel_header_row_index + 2,
            ))
        return records

    def load_metadata(self) -> BankStatementMetadata:
        """Ekstrenin antet bloğundan banka adı, şirket ünvanı, IBAN vb.
        bilgileri çıkarır. Format tanınmazsa boş bir metadata döner; bu,
        ana mutabakat işlemini hiçbir şekilde etkilemez.
        """
        raw = read_excel_raw(self.file_path)
        header_row_index = find_header_row(raw, set(self.profile.columns.keys()))
        return extract_bank_statement_metadata(self.file_path, header_row_index)

    @staticmethod
    def _clean_header(value: object) -> str:
        return " ".join(str(value).replace("\n", " ").split())

    def _validate_columns(self, dataframe: pd.DataFrame) -> None:
        missing = [name for name in self.profile.columns if name not in dataframe.columns]
        if missing:
            columns = ", ".join(map(str, dataframe.columns))
            raise ValueError(
                f"'{self.profile.name}' profiline göre dosyada beklenen sütunlar bulunamadı: "
                f"{', '.join(missing)}. Bulunan sütunlar: {columns}"
            )

    @staticmethod
    def _text(value: object) -> str:
        return "" if pd.isna(value) else str(value).strip()

    @staticmethod
    def _date(value: object):
        if pd.isna(value):
            return None
        try:
            parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
        except (ValueError, TypeError):
            return None
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()

    @staticmethod
    def _amount(value: object):
        if pd.isna(value):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(".", "").replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None
