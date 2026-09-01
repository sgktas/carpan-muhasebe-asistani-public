from __future__ import annotations

from datetime import datetime
from pathlib import Path

import xlwt

from app.core.output_order import bank_sort_key, chronological_key, region_sort_key
from app.core.region_config import RegionConfig
from app.models.records import ManimRecord
from app.writers.xls_utils import make_styles, save_xls, write_cell


class OdemeOnaylandiWriter:
    """Ödeme Onaylandı kayıtlarını tek Excel 97-2003 dosyasında toplar."""

    COLUMNS = [
        "KasaKodu", "Tarih", "Fisno", "GC", "Tip", "Aciklama", "Tutar",
        "Kod", "DovizTut", "Kur", "Plasiyer", "ProjeKodu", "RefKodu",
    ]
    COLUMN_WIDTHS = [10, 12, 7, 5, 5, 55, 13, 11, 10, 8, 10, 10, 9]
    CENTERED_COLUMNS = {
        "KasaKodu", "Fisno", "GC", "Tip", "Kod", "Kur",
        "Plasiyer", "ProjeKodu", "RefKodu",
    }

    def __init__(self, region_config: RegionConfig):
        self.region_config = region_config

    def write(self, items: list[tuple], output_path: Path) -> Path | None:
        if not items:
            return None

        items = sorted(
            items,
            key=lambda item: (
                region_sort_key(item[1], self.region_config.regions()),
                chronological_key(
                    item[0].islem_tarihi,
                    item[0].kaynak_dosya,
                    item[0].kaynak_satir,
                ),
                bank_sort_key(item[2]),
            ),
        )

        workbook = xlwt.Workbook(encoding="utf-8", style_compression=2)
        worksheet = workbook.add_sheet("Kasa")
        styles = make_styles()
        worksheet.panes_frozen = True
        worksheet.horz_split_pos = 1

        for col_index, (column, width) in enumerate(zip(self.COLUMNS, self.COLUMN_WIDTHS)):
            worksheet.write(0, col_index, column, styles["header"])
            worksheet.col(col_index).width = min(width * 256, 65_535)

        for row_index, item in enumerate(items, start=1):
            record, region, bank_key = item[0], item[1], item[2]
            # 4. eleman (varsa): Ödeme Onaylandı gözden geçirme ekranından
            # gelen elle düzeltilmiş Kasa Kodu / Proje Kodu değerleri.
            # Yoksa (normal MANİM Aktarma akışı) bölgeye göre hesaplanır.
            overrides = item[3] if len(item) > 3 and item[3] else {}
            kasa_kodu = overrides.get("kasa_kodu")
            if kasa_kodu is None:
                kasa_kodu = self.region_config.kasa_kodu(region)
            proje_kodu = overrides.get("proje_kodu")
            if proje_kodu is None:
                proje_kodu = self.region_config.proje_kodu(region)

            row_values = {
                "KasaKodu": kasa_kodu,
                "Tarih": self._format_tarih(record.islem_tarihi),
                "Fisno": "1",
                "GC": "C",
                "Tip": "B",
                "Aciklama": record.aciklama,
                "Tutar": float(record.tutar),
                "Kod": self.region_config.banka_kodu(region, bank_key) or "",
                "DovizTut": 0,
                "Kur": 0,
                "Plasiyer": self.region_config.plasiyer_kodu(),
                "ProjeKodu": proje_kodu,
                "RefKodu": "",
            }
            for col_index, column_name in enumerate(self.COLUMNS):
                if column_name in {"Tutar", "DovizTut"}:
                    style_name = "amount"
                elif column_name in self.CENTERED_COLUMNS:
                    style_name = "centered"
                else:
                    style_name = "text"
                write_cell(worksheet, row_index, col_index, row_values[column_name], styles, style_name)

        return save_xls(workbook, output_path)

    @staticmethod
    def _format_tarih(value) -> str:
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y")
        return str(value) if value else ""
