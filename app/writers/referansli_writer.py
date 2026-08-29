from __future__ import annotations

from pathlib import Path

import xlwt

from app.core.output_order import DEFAULT_REGION_ORDER, chronological_key
from app.core.region_config import RegionConfig
from app.models.records import ManimRecord
from app.writers.xls_utils import make_styles, save_xls, write_cell


REFERANSLI_COLUMNS: tuple[tuple[str, str], ...] = (
    ("Banka", "banka"),
    ("İşlem Tarihi", "islem_tarihi"),
    ("Açıklama", "aciklama"),
    ("Tutar", "tutar"),
    ("Dekont Durumu", "dekont_durumu"),
)


class ReferansliWriter:
    """Referanslı kayıtları aktif bölgeler için, ayarlardaki sırayla yazar."""

    def __init__(self, region_config: RegionConfig | None = None):
        self.region_config = region_config

    def write(
        self,
        items_by_region: dict[str, list[ManimRecord]],
        output_path: Path,
    ) -> Path | None:
        normalized_items = {
            str(region or "").strip().upper(): list(records or [])
            for region, records in items_by_region.items()
        }
        regions = (
            self.region_config.regions()
            if self.region_config is not None
            else DEFAULT_REGION_ORDER
        )
        if not any(normalized_items.get(region) for region in regions):
            return None

        workbook = xlwt.Workbook(encoding="utf-8", style_compression=2)
        styles = make_styles()

        for region in regions:
            records = sorted(
                normalized_items.get(region, []),
                key=lambda record: chronological_key(
                    record.islem_tarihi,
                    record.kaynak_dosya,
                    record.kaynak_satir,
                ),
            )
            worksheet = workbook.add_sheet(region)
            worksheet.panes_frozen = True
            worksheet.horz_split_pos = 1

            for column_index, (header, _attribute) in enumerate(REFERANSLI_COLUMNS):
                worksheet.write(0, column_index, header, styles["header"])

            widths = (18, 14, 65, 16, 20)
            for column_index, width in enumerate(widths):
                worksheet.col(column_index).width = min(width * 256, 65_535)

            for row_index, record in enumerate(records, start=1):
                for column_index, (_header, attribute) in enumerate(REFERANSLI_COLUMNS):
                    value = getattr(record, attribute)
                    if attribute == "islem_tarihi":
                        style_name = "date"
                    elif attribute == "tutar":
                        style_name = "amount"
                    else:
                        style_name = None
                    write_cell(
                        worksheet,
                        row_index,
                        column_index,
                        value,
                        styles,
                        style_name,
                    )

        return save_xls(workbook, output_path)
