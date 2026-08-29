from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.core.input_profile import InputProfile, InputProfileStore
from app.models.records import ManimRecord


@dataclass(frozen=True)
class InvalidManimRow:
    kaynak_dosya: str
    kaynak_satir: int
    nedenler: tuple[str, ...]
    ham_veri: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ManimParseResult:
    records: list[ManimRecord]
    invalid_rows: list[InvalidManimRow]

    @property
    def total_rows(self) -> int:
        return len(self.records) + len(self.invalid_rows)


def _default_profile() -> InputProfile:
    config_dir = Path(__file__).resolve().parents[2] / "config"
    return InputProfileStore(config_dir).get("manim")


class ManimParser:
    def __init__(self, file_path: str | Path, profile: InputProfile | None = None):
        self.file_path = Path(file_path)
        self.profile = profile or _default_profile()
        # Ic alan adi -> kaynak sutun basligi (profildeki eslemenin tersi).
        self._header_for = {
            internal_field: header for header, internal_field in self.profile.columns.items()
        }

    def load(self) -> list[ManimRecord]:
        """Geriye dönük uyumluluk için yalnızca geçerli kayıtları döndürür."""
        return self.load_with_issues().records

    def load_with_issues(self) -> ManimParseResult:
        """Geçerli kayıtları ve kaynak veri hatalarını birbirinden ayırır.

        Eksik banka, işlem tarihi, geçerli tutar veya dekont durumu bulunan
        satırlar müşteri eşleştirme akışına sokulmaz. Böylece bozuk kaynak
        satırları yanlışlıkla ``0 TL`` havale gibi görünmez.
        """
        if not self.file_path.is_file():
            raise FileNotFoundError(f"MANİM dosyası bulunamadı: {self.file_path}")

        dataframe = pd.read_excel(self.file_path, dtype=object)
        dataframe.columns = [self._clean_header(column) for column in dataframe.columns]
        self._validate_columns(dataframe)

        h = self._header_for
        records: list[ManimRecord] = []
        invalid_rows: list[InvalidManimRow] = []

        for index, row in dataframe.iterrows():
            if self._is_empty_row(row):
                continue

            source_row = int(index) + 2
            bank = self._text(row[h["banka"]])
            transaction_date = self._date(row[h["islem_tarihi"]])
            amount = self._amount(row[h["tutar"]])
            receipt_status = self._text(row[h["dekont_durumu"]])

            reasons: list[str] = []
            if not bank:
                reasons.append("Banka eksik")
            if transaction_date is None:
                reasons.append("İşlem tarihi eksik veya geçersiz")
            if amount is None or amount == 0:
                reasons.append("Tutar eksik, geçersiz veya sıfır")
            if not receipt_status:
                reasons.append("Dekont durumu eksik")

            if reasons:
                invalid_rows.append(
                    InvalidManimRow(
                        kaynak_dosya=self.file_path.name,
                        kaynak_satir=source_row,
                        nedenler=tuple(reasons),
                        ham_veri=row.to_dict(),
                    )
                )
                continue

            records.append(
                ManimRecord(
                    banka=bank,
                    sube=self._text(row[h["sube"]]),
                    islem_tarihi=transaction_date,
                    aciklama=self._text(row[h["aciklama"]]),
                    tutar=amount,
                    dekont_durumu=receipt_status,
                    karsi_hesap_adi=self._text(row[h["karsi_hesap_adi"]]),
                    karsi_hesap_kodu=self._text(row[h["karsi_hesap_kodu"]]),
                    kaynak_dosya=self.file_path.name,
                    kaynak_satir=source_row,
                    ham_veri=row.to_dict(),
                )
            )

        return ManimParseResult(records=records, invalid_rows=invalid_rows)

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
    def _is_empty_row(row: pd.Series) -> bool:
        return all(pd.isna(value) or str(value).strip() == "" for value in row.values)

    @staticmethod
    def _text(value: object) -> str:
        if pd.isna(value):
            return ""
        return str(value).strip()

    @staticmethod
    def _date(value: object):
        if pd.isna(value) or str(value).strip() == "":
            return None
        converted = pd.to_datetime(value, errors="coerce", dayfirst=True)
        return None if pd.isna(converted) else converted.to_pydatetime()

    @staticmethod
    def _amount(value: object) -> float | None:
        if pd.isna(value) or str(value).strip() == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip().replace(" ", "")
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        converted = pd.to_numeric(text, errors="coerce")
        return None if pd.isna(converted) else float(converted)
