from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.customer_list_profile import CustomerListProfile, CustomerListProfileStore
from app.models.records import CustomerRecord


def _default_profile() -> CustomerListProfile:
    config_dir = Path(__file__).resolve().parents[2] / "config"
    return CustomerListProfileStore(config_dir).get("f1_fom")


class CustomerParser:
    def __init__(self, file_path: str | Path, profile: CustomerListProfile | None = None):
        self.file_path = Path(file_path)
        self.profile = profile or _default_profile()

    def load(self) -> list[CustomerRecord]:
        dataframe = pd.read_excel(self.file_path, dtype=object)
        selected = self._resolve_columns(dataframe)
        if not selected["cari_kodu"] or not selected["unvan"]:
            raise ValueError(
                f"Müşteri listesinde '{self.profile.name}' profiline göre zorunlu "
                "sütunlar (cari kodu ve ünvan) bulunamadı."
            )

        records: list[CustomerRecord] = []
        for _, row in dataframe.iterrows():
            code = self._text(row[selected["cari_kodu"]])
            if not code:
                continue
            records.append(CustomerRecord(
                cari_kodu=code,
                unvan=self._text(row[selected["unvan"]]),
                vergi_no=self._text(row[selected["vergi_no"]]) if selected["vergi_no"] else "",
                sube=self._text(row[selected["sube"]]) if selected["sube"] else "",
                tabela_adi=self._text(row[selected["tabela_adi"]]) if selected["tabela_adi"] else "",
            ))
        return records

    def _resolve_columns(self, dataframe: pd.DataFrame) -> dict[str, str | None]:
        normalized = {self._key(column): str(column) for column in dataframe.columns}
        result: dict[str, str | None] = {}
        for field, aliases in self.profile.aliases.items():
            result[field] = next(
                (normalized.get(self._key(alias)) for alias in aliases if self._key(alias) in normalized),
                None,
            )
        return result

    @staticmethod
    def _key(value: object) -> str:
        return "".join(str(value).upper().replace("İ", "I").replace("Ş", "S").replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O").replace("Ç", "C").split())

    @staticmethod
    def _text(value: object) -> str:
        return "" if pd.isna(value) else str(value).strip()
