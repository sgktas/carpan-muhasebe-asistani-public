from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.excel_header_finder import read_excel_with_auto_header
from app.core.netsis_report_profile import NetsisReportProfile, NetsisReportProfileStore
from app.models.records import NetsisReportRecord


def _default_profile() -> NetsisReportProfile:
    config_dir = Path(__file__).resolve().parents[2] / "config"
    return NetsisReportProfileStore(config_dir).get("netsis")


class NetsisReportParser:
    def __init__(self, file_path: str | Path, profile: NetsisReportProfile | None = None):
        self.file_path = Path(file_path)
        self.profile = profile or _default_profile()
        self._header_for = {field: header for header, field in self.profile.columns.items()}

    def load(self) -> list[NetsisReportRecord]:
        if not self.file_path.is_file():
            raise FileNotFoundError(f"Netsis raporu dosyası bulunamadı: {self.file_path}")

        expected_headers = set(self.profile.columns.keys())
        dataframe = read_excel_with_auto_header(self.file_path, expected_headers)
        dataframe.columns = [self._clean_header(c) for c in dataframe.columns]
        self._validate_columns(dataframe)

        h = self._header_for
        uses_borc_alacak = self.profile.uses_borc_alacak()
        excel_header_row_index = int(dataframe.attrs.get("excel_header_row_index", 0))
        records: list[NetsisReportRecord] = []
        for index, row in dataframe.iterrows():
            tarih = self._date(row[h["tarih"]])
            bakiye = self._amount(row[h["bakiye"]])
            if tarih is None or bakiye is None:
                # Devir/toplam gibi tarihsiz özet satırları (Netsis raporlarında
                # sık görülür) gerçek bir işlem olmadığı için atlanır.
                continue

            if uses_borc_alacak:
                borc = self._amount(row[h["borc"]]) or 0.0
                alacak = self._amount(row[h["alacak"]]) or 0.0
                tutar = borc - alacak
            else:
                tutar = self._amount(row[h["tutar"]])
            if tutar is None:
                continue

            records.append(NetsisReportRecord(
                tarih=tarih,
                aciklama=self._text(row[h["aciklama"]]),
                tutar=tutar,
                bakiye=bakiye,
                kaynak_dosya=self.file_path.name,
                kaynak_satir=int(index) + excel_header_row_index + 2,
            ))
        return records

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
