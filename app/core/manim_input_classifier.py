from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.text_keys import compact_key


@dataclass(frozen=True)
class ManimInputBundle:
    manim_files: list[Path]
    tahsilat_file: Path | None
    customer_file: Path | None


class ManimInputClassifier:
    """Seçilen Excel dosyalarını ad ve başlık kanıtlarıyla türlerine ayırır."""

    def classify(self, files: list[Path]) -> ManimInputBundle:
        manim_files: list[Path] = []
        tahsilat_file: Path | None = None
        customer_file: Path | None = None

        for file in files:
            headers = self._headers(file)
            header_keys = {compact_key(header) for header in headers}
            name_key = compact_key(file.stem)

            if self._is_manim_file(name_key, header_keys):
                manim_files.append(file)
                continue
            if self._is_tahsilat_file(name_key, header_keys):
                tahsilat_file = file
                continue
            if self._is_customer_file(name_key, header_keys):
                customer_file = file

        return ManimInputBundle(manim_files, tahsilat_file, customer_file)

    @staticmethod
    def _is_manim_file(name_key: str, header_keys: set[str]) -> bool:
        return "MANIM" in name_key or {"BANKA", "DEKONTDURUMU"}.issubset(header_keys)

    @staticmethod
    def _is_tahsilat_file(name_key: str, header_keys: set[str]) -> bool:
        if "TAHSILAT" in name_key or "TAHSILATLAR" in name_key:
            return True
        has_customer_name = bool(
            {"MUSTERIISMI", "MUSTERIADI", "UNVAN", "CARIADI"} & header_keys
        )
        has_amount = bool({"TUTAR", "TAHSILATTUTARI", "TAHSILAT"} & header_keys)
        has_report_hint = bool(
            {"BELGETARIHI", "MUSTERIKODU", "CARI KODU"} & header_keys
        )
        return has_customer_name and has_amount and has_report_hint

    @staticmethod
    def _is_customer_file(name_key: str, header_keys: set[str]) -> bool:
        if "MUSTERI" in name_key and ("LIST" in name_key or "LISTE" in name_key):
            return True
        has_code = bool({"MUSTERIKODU", "CARIKODU", "CARIKOD"} & header_keys)
        has_title = bool(
            {"UNVAN", "CARIADI", "MUSTERIADI", "MUSTERIISMI"} & header_keys
        )
        has_customer_only_hint = bool(
            {"VERGINO", "VERGINUMARASI", "SUBE"} & header_keys
        )
        return has_code and has_title and has_customer_only_hint

    @staticmethod
    def _headers(file: Path) -> list[str]:
        try:
            return [
                str(column).strip()
                for column in pd.read_excel(file, nrows=0).columns
            ]
        except Exception as error:
            raise ValueError(f"Dosya okunamadi: {file.name}. {error}") from error
