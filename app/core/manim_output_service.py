from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
import shutil
from uuid import uuid4

from app.core.manim_parser import InvalidManimRow
from app.core.output_order import (
    bank_sort_key,
    chronological_key,
    region_file_prefix,
    region_sort_key,
    special_file_prefix,
)
from app.core.output_profile import OutputProfile
from app.core.region_config import RegionConfig
from app.models.records import ManimRecord
from app.writers.netsis_writer import NetsisWriter
from app.writers.odeme_onaylandi_writer import OdemeOnaylandiWriter
from app.writers.referansli_writer import ReferansliWriter
from app.writers.xls_utils import write_table_xls


def build_review_row(
    region: str,
    record: ManimRecord,
    reason: str,
) -> dict[str, object]:
    return {
        "Bolge": region,
        "Kaynak Dosya": record.kaynak_dosya,
        "Kaynak Satir": record.kaynak_satir,
        "Banka": record.banka,
        "Tarih": record.islem_tarihi,
        "Tutar": record.tutar,
        "Dekont Durumu": record.dekont_durumu,
        "Aciklama": record.aciklama,
        "Karsi Hesap Adi": record.karsi_hesap_adi,
        "Karsi Hesap Kodu": record.karsi_hesap_kodu,
        "Neden": reason,
    }


@dataclass
class ManimOutputPlan:
    outputs: dict[tuple[str, str], list]
    virman_by_region: dict[str, list]
    review_rows: list[dict[str, object]]
    invalid_rows: list[InvalidManimRow]
    odeme_onaylandi_items: list[tuple[ManimRecord, str, str]]
    referansli_by_region: dict[str, list[ManimRecord]]
    kural_calisti_by_region: dict[str, list[ManimRecord]]
    islem_tarihleri: set[date]
    output_profile: OutputProfile
    reference_output_profile: OutputProfile


@dataclass
class ManimOutputArtifacts:
    output_dir: Path
    created_files: list[Path] = field(default_factory=list)
    review_file: Path | None = None
    invalid_file: Path | None = None
    odeme_onaylandi_path: Path | None = None
    logs: list[str] = field(default_factory=list)


class ManimOutputService:
    """Hazırlanmış MANİM kayıtlarını onaylı şablonlarla atomik olarak yazar."""

    def __init__(
        self,
        output_root: Path,
        region_config: RegionConfig,
        regions: tuple[str, ...],
    ):
        self.output_root = Path(output_root)
        self.region_config = region_config
        self.regions = regions

    def write(self, plan: ManimOutputPlan) -> ManimOutputArtifacts:
        start_date, end_date = self._date_span(plan.islem_tarihleri)
        date_label = self._file_date_label(start_date, end_date)
        logs = [
            "İşlem tarih aralığı: "
            + (
                start_date.strftime("%d.%m.%Y")
                if start_date == end_date
                else f"{start_date:%d.%m.%Y} - {end_date:%d.%m.%Y}"
            )
        ]

        self._sort_plan(plan)
        self.output_root.mkdir(parents=True, exist_ok=True)
        final_output_dir = self._unique_output_dir(
            self.output_root / f"MANİM AKTARMA - {date_label}"
        )
        staging_dir = self.output_root / f".{final_output_dir.name}.tmp-{uuid4().hex}"
        staging_dir.mkdir(parents=True, exist_ok=False)

        created_names: list[str] = []
        review_name: str | None = None
        invalid_name: str | None = None
        payment_name: str | None = None
        payment_created = False

        try:
            writer = NetsisWriter(profile=plan.output_profile)
            try:
                ordered_outputs = sorted(
                    plan.outputs.items(),
                    key=lambda item: (
                        region_sort_key(item[0][0], self.regions),
                        bank_sort_key(item[0][1]),
                    ),
                )
                for (region, bank), rows in ordered_outputs:
                    file_name = self._netsis_file_name(
                        region, bank, date_label, plan.output_profile
                    )
                    writer.write(rows, staging_dir / file_name)
                    created_names.append(file_name)
                    logs.append(f"{file_name}: {len(rows)} Netsis satiri olusturuldu.")
            finally:
                writer.close()

            virman_rows = self._ordered_virman_records(plan)
            if virman_rows:
                virman_writer = NetsisWriter(profile=plan.reference_output_profile)
                try:
                    # Virman aktarımı bölge dosyası değildir: tüm kaynak
                    # bölgelerdeki aynı-banka şube transferleri, kullanıcı
                    # tarafından onaylanan tek toplu şablona yazılır.
                    virman_name = (
                        f"{special_file_prefix('HESAPLAR_ARASI_VIRMAN', self.regions)}_"
                        f"HESAPLAR_ARASI_VIRMAN_{date_label}"
                        f"{plan.reference_output_profile.output_extension}"
                    )
                    virman_writer.write(virman_rows, staging_dir / virman_name)
                    created_names.append(virman_name)
                    logs.append(
                        f"{virman_name}: {len(virman_rows)} giden virman satırı oluşturuldu."
                    )
                finally:
                    virman_writer.close()

            if plan.review_rows:
                review_name = (
                    f"{special_file_prefix('INCELEME_GEREKENLER', self.regions)}_"
                    f"INCELEME_GEREKENLER_{date_label}.xls"
                )
                self._write_review(plan.review_rows, staging_dir / review_name)
                logs.append(
                    f"{review_name}: {len(plan.review_rows)} satir kontrol bekliyor."
                )

            if plan.invalid_rows:
                invalid_name = (
                    f"{special_file_prefix('GECERSIZ_MANIM_SATIRLARI', self.regions)}_"
                    f"GECERSIZ_MANIM_SATIRLARI_{date_label}.xls"
                )
                self._write_invalid_rows(plan.invalid_rows, staging_dir / invalid_name)
                created_names.append(invalid_name)
                logs.append(
                    f"{invalid_name}: {len(plan.invalid_rows)} bozuk kaynak satırı "
                    "eşleştirme dışında bırakıldı."
                )

            payment_name = (
                f"{special_file_prefix('ODEME_ONAYLANDI', self.regions)}_"
                f"ODEME_ONAYLANDI_{date_label}.xls"
            )
            payment_path = OdemeOnaylandiWriter(self.region_config).write(
                plan.odeme_onaylandi_items,
                staging_dir / payment_name,
            )
            if payment_path:
                payment_created = True
                created_names.append(payment_name)
                logs.append(
                    f"{payment_name}: {len(plan.odeme_onaylandi_items)} odeme onaylandi kaydi."
                )

            reference_name = (
                f"{special_file_prefix('REFERANSLI', self.regions)}_"
                f"REFERANSLI_{date_label}.xls"
            )
            reference_path = ReferansliWriter(self.region_config).write(
                plan.referansli_by_region,
                staging_dir / reference_name,
            )
            if reference_path:
                reference_count = sum(
                    len(records) for records in plan.referansli_by_region.values()
                )
                created_names.append(reference_name)
                logs.append(
                    f"{reference_name}: {reference_count} referansli kaydi "
                    "(bolge bazinda sayfa)."
                )

            rule_name = (
                f"{special_file_prefix('KURAL_CALISTI', self.regions)}_"
                f"KURAL_CALISTI_{date_label}.xls"
            )
            rule_path = ReferansliWriter(self.region_config).write(
                plan.kural_calisti_by_region,
                staging_dir / rule_name,
            )
            if rule_path:
                rule_count = sum(
                    len(records) for records in plan.kural_calisti_by_region.values()
                )
                created_names.append(rule_name)
                logs.append(
                    f"{rule_name}: {rule_count} kural çalıştı kaydı "
                    "(bolge bazinda sayfa)."
                )

            # Her çıktı tamamlanmadan nihai klasör görünmez. Herhangi bir
            # writer hata verirse geçici klasör kaldırılır.
            staging_dir.replace(final_output_dir)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

        return ManimOutputArtifacts(
            output_dir=final_output_dir,
            created_files=[final_output_dir / name for name in created_names],
            review_file=(final_output_dir / review_name) if review_name else None,
            invalid_file=(final_output_dir / invalid_name) if invalid_name else None,
            odeme_onaylandi_path=(
                final_output_dir / payment_name
                if payment_created and payment_name
                else None
            ),
            logs=logs,
        )

    def _sort_plan(self, plan: ManimOutputPlan) -> None:
        for rows in plan.outputs.values():
            rows.sort(key=self._netsis_sort_key)
        plan.odeme_onaylandi_items.sort(
            key=lambda item: (
                region_sort_key(item[1], self.regions),
                chronological_key(
                    item[0].islem_tarihi,
                    item[0].kaynak_dosya,
                    item[0].kaynak_satir,
                ),
                bank_sort_key(item[2]),
            )
        )
        for records in plan.referansli_by_region.values():
            records.sort(key=self._manim_sort_key)
        for records in plan.kural_calisti_by_region.values():
            records.sort(key=self._manim_sort_key)
        for records in plan.virman_by_region.values():
            records.sort(
                key=lambda record: (
                    record.islem_tarihi or datetime.max,
                    record.kaynak_banka,
                    record.hedef_banka,
                )
            )

    def _ordered_virman_records(self, plan: ManimOutputPlan) -> list:
        """Bölge ayrımı olmadan tek aktarım dosyası için kronolojik sıralama."""
        rows = [
            record
            for records in plan.virman_by_region.values()
            for record in records
        ]
        return sorted(
            rows,
            key=lambda record: (
                record.islem_tarihi or datetime.max,
                region_sort_key(record.bolge, self.regions),
                record.kaynak_banka,
                record.hedef_banka,
            ),
        )

    def _netsis_file_name(
        self,
        region: str,
        bank: str,
        date_label: str,
        output_profile: OutputProfile,
    ) -> str:
        prefix = region_file_prefix(region, self.regions)
        if output_profile.grouping == "region":
            return f"{prefix}_{region}_{date_label}.xls"
        return f"{prefix}_{region}_{bank}_{date_label}.xls"

    @staticmethod
    def _write_review(rows: list[dict[str, object]], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return write_table_xls(
            rows,
            output_path,
            sheet_name="İnceleme",
            amount_columns=("Tutar",),
            date_columns=("Tarih",),
        )

    @staticmethod
    def _write_invalid_rows(rows: list[InvalidManimRow], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report_rows: list[dict[str, object]] = []
        for item in rows:
            row = {
                "Kaynak Dosya": item.kaynak_dosya,
                "Kaynak Satır": item.kaynak_satir,
                "Neden": "; ".join(item.nedenler),
            }
            row.update({str(key): value for key, value in item.ham_veri.items()})
            report_rows.append(row)
        return write_table_xls(report_rows, output_path, sheet_name="Geçersiz MANİM")

    @staticmethod
    def _date_span(values: set[date]) -> tuple[date, date]:
        if not values:
            today = datetime.now().date()
            return today, today
        return min(values), max(values)

    @staticmethod
    def _file_date_label(start: date, end: date) -> str:
        if start == end:
            return start.strftime("%d%m%Y")
        if start.year == end.year and start.month == end.month:
            return f"{start:%d}-{end:%d.%m.%Y}"
        if start.year == end.year:
            return f"{start:%d.%m}-{end:%d.%m.%Y}"
        return f"{start:%d.%m.%Y}-{end:%d.%m.%Y}"

    @staticmethod
    def _manim_sort_key(record: ManimRecord):
        value = record.islem_tarihi
        if isinstance(value, datetime):
            return value, record.kaynak_dosya, record.kaynak_satir
        if isinstance(value, date):
            return (
                datetime(value.year, value.month, value.day),
                record.kaynak_dosya,
                record.kaynak_satir,
            )
        return datetime.max, record.kaynak_dosya, record.kaynak_satir

    @staticmethod
    def _netsis_sort_key(record):
        value = record.islem_tarihi
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day)
        return datetime.max

    @staticmethod
    def _unique_output_dir(preferred: Path) -> Path:
        if not preferred.exists():
            return preferred
        suffix = 2
        while True:
            candidate = preferred.with_name(f"{preferred.name}_{suffix}")
            if not candidate.exists():
                return candidate
            suffix += 1
