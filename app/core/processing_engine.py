from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from itertools import combinations
from pathlib import Path
import re
import shutil
import unicodedata
from uuid import uuid4

import pandas as pd

from app.core.active_profile_store import ActiveProfileStore
from app.core.customer_parser import CustomerParser
from app.core.customer_list_cache import CustomerListCache
from app.core.customer_list_profile import CustomerListProfileStore
from app.core.input_profile import InputProfileStore
from app.core.output_profile import OutputProfileStore
from app.core.mapping_store import MappingStore
from app.core.output_order import (
    bank_sort_key,
    chronological_key,
    region_file_prefix,
    region_sort_key,
    special_file_prefix,
)
from app.core.manim_parser import InvalidManimRow, ManimParser
from app.core.processed_files_log import ProcessedFilesLog
from app.core.region_config import RegionConfig, active_region_config_path
from app.core.tahsilat_parser import TahsilatParser
from app.models.records import CustomerRecord, ManimRecord, TahsilatRecord
from app.processors.havale_processor import HavaleProcessor
from app.writers.netsis_writer import NetsisWriter
from app.writers.odeme_onaylandi_writer import OdemeOnaylandiWriter
from app.writers.referansli_writer import ReferansliWriter
from app.writers.xls_utils import write_table_xls


@dataclass
class ProcessingResult:
    created_files: list[Path] = field(default_factory=list)
    review_file: Path | None = None
    invalid_file: Path | None = None
    output_dir: Path | None = None
    logs: list[str] = field(default_factory=list)
    total_manim_records: int = 0
    invalid_manim_records: int = 0
    produced_netsis_records: int = 0
    skipped_payment: int = 0
    skipped_reference: int = 0
    skipped_rule: int = 0
    unresolved: int = 0
    duplicate_files: list[str] = field(default_factory=list)
    odeme_onaylandi_items: list[tuple] = field(default_factory=list)
    odeme_onaylandi_path: Path | None = None


@dataclass
class UnresolvedItem:
    """Otomatik eşleşmeyen tek bir MANİM kaydı."""

    record: ManimRecord
    region: str
    reason: str
    suggested_rows: list[TahsilatRecord] = field(default_factory=list)


@dataclass
class ManualResolution:
    """Kullanıcının manuel eşleştirme ekranında bir kayıt için verdiği karar."""

    route: str
    rows: list[TahsilatRecord] | None = None
    allow_partial: bool = False


class ProcessingEngine:
    FALLBACK_REGIONS = ("BODRUM", "FETHIYE", "MUGLA", "SOKE")

    def __init__(
        self,
        files: list[Path],
        project_root: str | Path,
        data_root: str | Path | None = None,
        output_root: str | Path | None = None,
    ):
        self.files = [Path(file) for file in files]
        # project_root: paketle gelen, salt-okunur kaynaklar (config/templates)
        self.resource_root = Path(project_root)
        # data_root: kalıcı sistem verileri (eşleştirme hafızası/geçmiş).
        self.data_root = Path(data_root) if data_root is not None else self.resource_root
        # output_root: kullanıcı tarafından kolayca erişilebilen Excel çıktı alanı.
        self.output_root = (
            Path(output_root) if output_root is not None else self.data_root / "output"
        )
        # Eski çağıran kodlarla uyumluluk için alias korunur.
        self.project_root = self.resource_root

        self.region_config = RegionConfig(
            active_region_config_path(self.resource_root / "config", self.data_root)
        )
        self.REGIONS = self.region_config.regions() or self.FALLBACK_REGIONS

    def find_duplicate_manim_files(self) -> dict[Path, dict]:
        manim_files, _, _ = self._classify_files()
        processed_log = ProcessedFilesLog(self.data_root / "data" / "processed_files.json")
        duplicates: dict[Path, dict] = {}
        for manim_file in manim_files:
            file_hash = processed_log.hash_file(manim_file)
            previous = processed_log.is_processed(file_hash)
            if previous:
                duplicates[manim_file] = {"hash": file_hash, **previous}
        return duplicates

    def run(self, resolver=None, allow_duplicate_files: set[str] | None = None) -> ProcessingResult:
        result = ProcessingResult()
        manim_files, tahsilat_file, customer_file = self._classify_files()

        if not manim_files:
            raise ValueError("En az bir MANIM raporu bulunamadi.")
        if not tahsilat_file:
            raise ValueError("Tahsilat raporu bulunamadi. Dosyayi da surukleyip birakin.")

        active_profiles = ActiveProfileStore(self.data_root)
        input_profile = InputProfileStore(self.resource_root / "config").get_or_default(
            active_profiles.get_input_profile_id()
        )
        output_profile = OutputProfileStore(self.resource_root / "config").get_or_default(
            active_profiles.get_output_profile_id()
        )
        customer_list_profile = CustomerListProfileStore(self.resource_root / "config").get_or_default(
            active_profiles.get_customer_list_profile_id()
        )

        customer_cache = CustomerListCache(self.data_root)
        customer_file_is_fresh = customer_file is not None
        if customer_file is None:
            customer_file = customer_cache.get()
            if not customer_file:
                raise ValueError("Musteri listesi bulunamadi. Dosyayi da surukleyip birakin.")

        allow_duplicate_files = allow_duplicate_files or set()
        processed_log = ProcessedFilesLog(self.data_root / "data" / "processed_files.json")

        tahsilat_parser = TahsilatParser(tahsilat_file)
        tahsilat = tahsilat_parser.load()
        customers = CustomerParser(customer_file, profile=customer_list_profile).load()
        # Kullanıcının bu turda verdiği liste güncel kabul edilir. İçinde
        # MANİM'de geçen birkaç yeni kod henüz olmasa bile listeyi reddedip
        # tüm aktarımı durdurmayız; o satırlar aşağıda manuel eşleştirme
        # ekranına gider, liste ise sonraki işlemlerde kullanılmak üzere
        # hafızaya alınır.
        if customer_file_is_fresh:
            customer_cache.save(customer_file)
        customer_region_by_code, customer_region_by_name = self._customer_region_indexes(customers)
        mapping_store = MappingStore(self.data_root / "data" / "customer_mappings.json")
        region_branch_aliases = {
            region: self.region_config.customer_branch_aliases(region)
            for region in self.REGIONS
        }
        processor = HavaleProcessor(
            tahsilat,
            customers,
            mapping_store,
            region_branch_aliases=region_branch_aliases,
        )

        outputs: dict[tuple[str, str], list] = defaultdict(list)
        pending: list[UnresolvedItem] = []
        invalid_rows: list[InvalidManimRow] = []
        odeme_onaylandi_items: list[tuple[ManimRecord, str, str]] = []
        referansli_by_region: dict[str, list[ManimRecord]] = defaultdict(list)
        kural_calisti_by_region: dict[str, list[ManimRecord]] = defaultdict(list)
        islem_tarihleri: set[date] = set()
        processed_candidates: list[tuple[str, str, int]] = []
        mapping_updates: list[tuple[str, list[dict]]] = []

        result.logs.append(
            f"Girdi profili: {input_profile.name} | Çıktı profili: {output_profile.name} | "
            f"Müşteri listesi profili: {customer_list_profile.name}"
        )
        result.logs.append(f"Tahsilat raporu: {tahsilat_file.name}")
        if tahsilat_parser.selected_sheet_name != 0:
            result.logs.append(
                f"Tahsilat veri sayfası: {tahsilat_parser.selected_sheet_name} "
                "(şubeli eşleştirme için tüm kayıtlar)"
            )
        musteri_listesi_gorunen_ad = (
            customer_file.name
            if customer_file_is_fresh
            else (customer_cache.metadata() or {}).get("orijinal_ad", customer_file.name)
        )
        result.logs.append(f"Musteri listesi: {musteri_listesi_gorunen_ad}")
        if not customer_file_is_fresh:
            cache_meta = customer_cache.metadata() or {}
            result.logs.append(
                "  (bu seferde müşteri listesi verilmedi; hafızadaki son liste kullanıldı — "
                f"kaydedilme tarihi: {cache_meta.get('kaydedilme_tarihi', '-')})"
            )

        for manim_file in manim_files:
            file_hash = processed_log.hash_file(manim_file)
            previous = processed_log.is_processed(file_hash)
            if previous and file_hash not in allow_duplicate_files:
                result.duplicate_files.append(manim_file.name)
                result.logs.append(
                    f"UYARI: {manim_file.name} daha önce işlenmiş görünüyor "
                    f"({previous['tarih']}, {previous['kayit_sayisi']} kayıt) — atlandı."
                )
                continue

            file_region = self._region_from_name(manim_file.name)
            parse_result = ManimParser(manim_file, profile=input_profile).load_with_issues()
            records = parse_result.records
            invalid_rows.extend(parse_result.invalid_rows)
            result.total_manim_records += parse_result.total_rows
            result.invalid_manim_records += len(parse_result.invalid_rows)
            processed_candidates.append((file_hash, manim_file.name, parse_result.total_rows))

            result.logs.append(
                f"{manim_file.name}: {len(records)} geçerli kayıt okundu"
                + (f", {len(parse_result.invalid_rows)} bozuk satır ayrıldı." if parse_result.invalid_rows else ".")
            )
            islem_tarihleri.update(record.islem_tarihi.date() for record in records if record.islem_tarihi)

            row_region_counts: dict[str, int] = defaultdict(int)
            for record in records:
                region = self._region_for_record(
                    record,
                    file_region,
                    customer_region_by_code,
                    customer_region_by_name,
                )
                row_region_counts[region] += 1
                status = self._normalize(record.dekont_durumu)

                if "ODEME ONAYLANDI" in status:
                    if record.tutar < 0:
                        pending.append(UnresolvedItem(
                            record=record,
                            region=region,
                            reason=self._negative_payment_approval_reason(),
                        ))
                        result.logs.append(
                            "UYARI: Negatif tutarlı kayıt Ödeme Onaylandı'ya yazılmadı; "
                            "Referanslı kayıt olarak kontrol bekliyor."
                        )
                        continue
                    odeme_onaylandi_items.append((record, region, self._bank_key(record.banka)))
                    result.skipped_payment += 1
                    continue

                if "KURAL CALISTI" in status:
                    kural_calisti_by_region[region].append(record)
                    result.skipped_rule += 1
                    continue

                if "REFERANSLI" in status:
                    if record.tutar > 0 and self._has_staff_route_marker(record.aciklama):
                        pending.append(UnresolvedItem(
                            record=record,
                            region=region,
                            reason=self._ambiguous_reference_reason(),
                        ))
                        result.logs.append(
                            "UYARI: Referanslı seçilmiş ancak açıklamada ROTA/YATAN PARA "
                            "bilgisi var; Ödeme Onaylandı olma ihtimali için kullanıcı onayı bekliyor."
                        )
                        continue
                    referansli_by_region[region].append(record)
                    result.skipped_reference += 1
                    continue

                bank = self._bank_key(record.banka)
                if self._requires_bank_account_code(output_profile) and not self.region_config.banka_kodu(region, bank):
                    pending.append(UnresolvedItem(
                        record=record,
                        region=region,
                        reason=self._missing_bank_account_code_reason(region, bank),
                    ))
                    continue

                netsis_rows, reason = processor.process(record, region)
                if reason:
                    pending.append(UnresolvedItem(
                        record=record,
                        region=region,
                        reason=reason,
                        suggested_rows=list(processor.last_suggested_rows),
                    ))
                    continue

                for netsis_row in netsis_rows:
                    outputs[self._output_key(region, bank, output_profile)].append(
                        self._with_region_codes(netsis_row, region, bank)
                    )
                    result.produced_netsis_records += 1

            if row_region_counts:
                distribution = ", ".join(
                    f"{region}: {count}"
                    for region, count in sorted(
                        row_region_counts.items(),
                        key=lambda item: region_sort_key(item[0], self.REGIONS),
                    )
                )
                result.logs.append(f"  Satır bölge dağılımı: {distribution}")

        # Aynı müşteri/tahsilat adayı için iki ayrı banka hareketi oluşabilir.
        # Toplam tahsilatla kuruşu kuruşuna tutarsa otomatik aktar; fark varsa
        # kayıtlar manuel toplu eşleştirme için inceleme ekranında kalır.
        pending = self._match_combined_bank_movements(
            pending, outputs, result, output_profile, processor
        )

        if pending and resolver:
            resolutions = resolver(pending, customers, tahsilat) or {}
            still_pending: list[UnresolvedItem] = []

            for index, item in enumerate(pending):
                resolution: ManualResolution | None = resolutions.get(index)
                if not resolution or resolution.route == "ATLA":
                    still_pending.append(item)
                    continue

                if resolution.route == "ODEME_ONAYLANDI":
                    if item.record.tutar < 0:
                        still_pending.append(item)
                        result.logs.append(
                            "UYARI: Negatif tutarlı kayıt manuel olarak da Ödeme Onaylandı'ya "
                            "taşınamaz; inceleme listesinde bırakıldı."
                        )
                        continue
                    odeme_onaylandi_items.append((item.record, item.region, self._bank_key(item.record.banka)))
                    result.skipped_payment += 1
                    result.logs.append(f"Manuel olarak Ödeme Onaylandı'ya taşındı: {item.record.aciklama[:60]}...")
                    continue

                if resolution.route == "REFERANSLI":
                    referansli_by_region[item.region].append(item.record)
                    result.skipped_reference += 1
                    result.logs.append(f"Manuel olarak Referanslı'ya taşındı: {item.record.aciklama[:60]}...")
                    continue

                if resolution.route != "HAVALE" or not resolution.rows:
                    still_pending.append(item)
                    continue

                bank = self._bank_key(item.record.banka)
                if self._requires_bank_account_code(output_profile) and not self.region_config.banka_kodu(item.region, bank):
                    still_pending.append(
                        UnresolvedItem(
                            record=item.record,
                            region=item.region,
                            reason=self._missing_bank_account_code_reason(item.region, bank),
                            suggested_rows=item.suggested_rows,
                        )
                    )
                    result.logs.append(
                        f"UYARI: BM kodu olmadığı için manuel havale aktarımı bekletildi: "
                        f"{item.record.aciklama[:60]}..."
                    )
                    continue

                validated_rows, validation_error = self._validate_manual_rows(
                    resolution.rows,
                    item.record.tutar,
                    allow_partial=resolution.allow_partial,
                )
                if validation_error:
                    still_pending.append(
                        UnresolvedItem(
                            record=item.record,
                            region=item.region,
                            reason=f"Manuel eşleştirme reddedildi: {validation_error}",
                            suggested_rows=item.suggested_rows,
                        )
                    )
                    result.logs.append(
                        f"UYARI: Manuel eşleştirme kabul edilmedi ({validation_error}): "
                        f"{item.record.aciklama[:60]}..."
                    )
                    continue

                for row in validated_rows:
                    netsis_row = processor._netsis_record(
                        item.record,
                        row.musteri_kodu,
                        row.tutar,
                        "MANUEL_ESLESTIRME",
                    )
                    outputs[self._output_key(item.region, bank, output_profile)].append(
                        self._with_region_codes(netsis_row, item.region, bank)
                    )
                    result.produced_netsis_records += 1

                manual_total = round(sum(row.tutar for row in validated_rows), 2)
                remaining = round(float(item.record.tutar) - manual_total, 2)
                if resolution.allow_partial and remaining > 0.01:
                    # Eksik dağılım hafızaya alınmaz; aynı açıklama tekrar
                    # geldiğinde kullanıcı bakiye durumunu yeniden görür.
                    result.logs.append(
                        f"Manuel kısmi eşleştirme: {manual_total:,.2f} TL Netsis'e aktarıldı, "
                        f"{remaining:,.2f} TL bekleyen bakiye olarak bırakıldı: "
                        f"{item.record.aciklama[:60]}..."
                    )
                else:
                    mapping_updates.append(
                        (
                            item.record.aciklama,
                            [
                                {"musteri_kodu": row.musteri_kodu, "tutar": row.tutar}
                                for row in validated_rows
                            ],
                        )
                    )
                    result.logs.append(
                        f"Manuel eşleştirildi; çıktı başarıyla oluşunca hafızaya kaydedilecek: "
                        f"{item.record.aciklama[:60]}..."
                    )

            pending = still_pending

        result.unresolved = len(pending)
        review_rows = [self._review_row(item.region, item.record, item.reason) for item in pending]

        # Tüm MANİM dosyaları mükerrer olduğu için atlandıysa yeni çıktı veya
        # işlenmiş dosya kaydı oluşturulmaz.
        if not processed_candidates:
            return result

        baslangic_tarihi, bitis_tarihi = self._date_span(islem_tarihleri)
        tarih_etiketi = self._file_date_label(baslangic_tarihi, bitis_tarihi)
        klasor_tarih_etiketi = self._folder_date_label(baslangic_tarihi, bitis_tarihi)
        result.logs.append(
            "İşlem tarih aralığı: "
            + (
                baslangic_tarihi.strftime("%d.%m.%Y")
                if baslangic_tarihi == bitis_tarihi
                else f"{baslangic_tarihi:%d.%m.%Y} - {bitis_tarihi:%d.%m.%Y}"
            )
        )

        # Bölge/banka çıktılarında kaynak kronolojisi korunur. Python sıralaması
        # kararlı olduğu için aynı tarih-saatteki kayıtlar MANİM sırasını korur.
        for rows in outputs.values():
            rows.sort(key=self._netsis_sort_key)
        odeme_onaylandi_items.sort(
            key=lambda item: (
                region_sort_key(item[1], self.REGIONS),
                chronological_key(
                    item[0].islem_tarihi,
                    item[0].kaynak_dosya,
                    item[0].kaynak_satir,
                ),
                bank_sort_key(item[2]),
            )
        )
        for records in referansli_by_region.values():
            records.sort(key=self._manim_sort_key)
        for records in kural_calisti_by_region.values():
            records.sort(key=self._manim_sort_key)

        output_base = self.output_root
        output_base.mkdir(parents=True, exist_ok=True)
        final_output_dir = self._unique_output_dir(
            output_base / f"MANİM AKTARMA - {tarih_etiketi}"
        )
        staging_dir = output_base / f".{final_output_dir.name}.tmp-{uuid4().hex}"
        staging_dir.mkdir(parents=True, exist_ok=False)

        created_names: list[str] = []
        review_name: str | None = None
        invalid_name: str | None = None

        try:
            # NetsisWriter şablonu uygulamanın gerçek çalışma yolundan seçer:
            # paketli uygulamada ``templates/local`` içindeki doğrulanmış
            # Netsis şablonu, kaynak pakette ise varsa genel şablon kullanılır.
            # Burada ``templates/<dosya>`` yolunu doğrudan vermek local
            # şablonu atlatıp genel xlwt çıktısına düşürebiliyordu; Ephesus
            # bu çıktıyı "External table" hatasıyla reddedebiliyor.
            writer = NetsisWriter(profile=output_profile)
            try:
                ordered_outputs = sorted(
                    outputs.items(),
                    key=lambda item: (
                        region_sort_key(item[0][0], self.REGIONS),
                        bank_sort_key(item[0][1]),
                    ),
                )
                for (region, bank), rows in ordered_outputs:
                    file_name = self._netsis_file_name(
                        region, bank, tarih_etiketi, output_profile
                    )
                    writer.write(rows, staging_dir / file_name)
                    created_names.append(file_name)
                    result.logs.append(f"{file_name}: {len(rows)} Netsis satiri olusturuldu.")
            finally:
                writer.close()

            if review_rows:
                review_name = (
                    f"{special_file_prefix('INCELEME_GEREKENLER', self.REGIONS)}_"
                    f"INCELEME_GEREKENLER_{tarih_etiketi}.xls"
                )
                self._write_review(review_rows, staging_dir / review_name)
                result.logs.append(f"{review_name}: {len(review_rows)} satir kontrol bekliyor.")

            if invalid_rows:
                invalid_name = (
                    f"{special_file_prefix('GECERSIZ_MANIM_SATIRLARI', self.REGIONS)}_"
                    f"GECERSIZ_MANIM_SATIRLARI_{tarih_etiketi}.xls"
                )
                self._write_invalid_rows(invalid_rows, staging_dir / invalid_name)
                created_names.append(invalid_name)
                result.logs.append(
                    f"{invalid_name}: {len(invalid_rows)} bozuk kaynak satırı eşleştirme dışında bırakıldı."
                )

            odeme_name = (
                f"{special_file_prefix('ODEME_ONAYLANDI', self.REGIONS)}_"
                f"ODEME_ONAYLANDI_{tarih_etiketi}.xls"
            )
            odeme_path = OdemeOnaylandiWriter(self.region_config).write(
                odeme_onaylandi_items,
                staging_dir / odeme_name,
            )
            result.odeme_onaylandi_items = list(odeme_onaylandi_items)
            if odeme_path:
                created_names.append(odeme_name)
                result.logs.append(f"{odeme_name}: {len(odeme_onaylandi_items)} odeme onaylandi kaydi.")

            referansli_name = (
                f"{special_file_prefix('REFERANSLI', self.REGIONS)}_"
                f"REFERANSLI_{tarih_etiketi}.xls"
            )
            referansli_path = ReferansliWriter(self.region_config).write(
                referansli_by_region,
                staging_dir / referansli_name,
            )
            if referansli_path:
                total_referansli = sum(len(records) for records in referansli_by_region.values())
                created_names.append(referansli_name)
                result.logs.append(
                    f"{referansli_name}: {total_referansli} referansli kaydi (bolge bazinda sayfa)."
                )

            kural_calisti_name = (
                f"{special_file_prefix('KURAL_CALISTI', self.REGIONS)}_"
                f"KURAL_CALISTI_{tarih_etiketi}.xls"
            )
            kural_calisti_path = ReferansliWriter(self.region_config).write(
                kural_calisti_by_region,
                staging_dir / kural_calisti_name,
            )
            if kural_calisti_path:
                total_kural_calisti = sum(len(records) for records in kural_calisti_by_region.values())
                created_names.append(kural_calisti_name)
                result.logs.append(
                    f"{kural_calisti_name}: {total_kural_calisti} kural çalıştı kaydı (bolge bazinda sayfa)."
                )

            # Dosyalar önce geçici klasörde tamamen üretilir. Tek bir writer bile
            # hata verirse klasör silinir ve MANİM geçmişi işaretlenmez.
            staging_dir.replace(final_output_dir)

        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

        result.output_dir = final_output_dir
        if odeme_path:
            result.odeme_onaylandi_path = final_output_dir / odeme_name
        result.created_files = [final_output_dir / name for name in created_names]
        if review_name:
            result.review_file = final_output_dir / review_name
        if invalid_name:
            result.invalid_file = final_output_dir / invalid_name

        # Çıktılar görünür ve eksiksiz hale geldikten sonra kalıcı yan etkiler
        # uygulanır. İşlenmiş dosya geçmişi en son yazılır.
        mapping_store.set_many(mapping_updates)
        processed_log.mark_many(processed_candidates)
        result.logs.append(
            f"İşlem başarıyla tamamlandı; {len(processed_candidates)} MANİM dosyası işlenmiş olarak kaydedildi."
        )

        return result

    def _match_combined_bank_movements(self, pending, outputs, result, output_profile, processor):
        consumed: set[int] = set()
        for left_index, right_index in combinations(range(len(pending)), 2):
            if left_index in consumed or right_index in consumed:
                continue
            left, right = pending[left_index], pending[right_index]
            if left.region != right.region:
                continue
            left_bank = self._bank_key(left.record.banka)
            right_bank = self._bank_key(right.record.banka)
            if left_bank != right_bank:
                continue
            if not left.record.islem_tarihi or not right.record.islem_tarihi:
                continue
            if left.record.islem_tarihi.date() != right.record.islem_tarihi.date():
                continue
            # Tek tahsilat adayı, iki hareketi güvenli biçimde aynı cari koda bağlar.
            if len(left.suggested_rows) != 1 or len(right.suggested_rows) != 1:
                continue
            left_candidate, right_candidate = left.suggested_rows[0], right.suggested_rows[0]
            if str(left_candidate.musteri_kodu).strip() != str(right_candidate.musteri_kodu).strip():
                continue
            target = round(float(left_candidate.tutar), 2)
            total = round(float(left.record.tutar) + float(right.record.tutar), 2)
            if abs(total - target) > 0.01:
                continue

            for item in (left, right):
                netsis_record = processor._netsis_record(
                    item.record, str(left_candidate.musteri_kodu).strip(),
                    item.record.tutar, "BIRLESIK_BANKA_HAREKETI"
                )
                netsis_record = self._with_region_codes(netsis_record, item.region, left_bank)
                outputs[self._output_key(item.region, left_bank, output_profile)].append(netsis_record)
                result.produced_netsis_records += 1
            consumed.update({left_index, right_index})
            result.logs.append(
                f"Birleşik havale eşleşti: {left.record.tutar:,.2f} + {right.record.tutar:,.2f} TL = {target:,.2f} TL."
            )
        return [item for index, item in enumerate(pending) if index not in consumed]

    @staticmethod
    def _output_key(region: str, bank: str, output_profile) -> tuple[str, str]:
        return (region, bank if output_profile.grouping == "region_bank" else "TOPLU")

    @staticmethod
    def _requires_bank_account_code(output_profile) -> bool:
        """Seçili çıktı şablonu BM/banka hesap kodu sütununu zorunlu tutuyor mu?"""
        return any(
            column.source_kind == "field" and column.field == "banka_hesap_kodu"
            for column in output_profile.columns
        )

    @staticmethod
    def _missing_bank_account_code_reason(region: str, bank: str) -> str:
        return (
            f"{region} bölgesi {bank} için BM banka hesap kodu tanımlı değil. "
            "Ayarlar > Bölge Yönetimi bölümünden bu banka için BM kodunu ekleyin; "
            "satır boş BM koduyla Netsis aktarımına yazılmadı."
        )

    @staticmethod
    def _negative_payment_approval_reason() -> str:
        return (
            "Negatif tutarlı kayıt Ödeme Onaylandı olamaz. Bu işlem giden para "
            "olduğu için Referanslı kayıt olarak kontrol edilmelidir."
        )

    @staticmethod
    def _ambiguous_reference_reason() -> str:
        return (
            "Referanslı seçilmiş ancak açıklamada ROTA veya YATAN PARA bilgisi tespit edildi. "
            "Ödeme Onaylandı olma ihtimaline karşı onay gereklidir."
        )

    @staticmethod
    def _has_staff_route_marker(description: str) -> bool:
        """Personelin banka/ATM üzerinden yaptığı rota tahsilatlarını tanır.

        MANİM açıklamalarında hem ``ROTA104`` hem de ``ROTA 104`` biçimi
        görülebildiği için aradaki boşluk, nokta veya tire zorunlu değildir.
        """
        normalized = ProcessingEngine._normalize(description)
        return bool(re.search(r"\bROTA[\s.-]*\d{1,4}\b", normalized) or "YATAN PARA" in normalized)

    def _with_region_codes(self, record, region: str, bank: str):
        return replace(
            record,
            bolge=region,
            banka_hesap_kodu=self.region_config.banka_kodu(region, bank) or "",
        )

    def _netsis_file_name(self, region: str, bank: str, date_label: str, output_profile) -> str:
        prefix = region_file_prefix(region, self.REGIONS)
        if output_profile.grouping == "region":
            return f"{prefix}_{region}_{date_label}.xls"
        return f"{prefix}_{region}_{bank}_{date_label}.xls"

    @staticmethod
    def _validate_manual_rows(
        rows: list[TahsilatRecord],
        target_amount: float,
        allow_partial: bool = False,
    ) -> tuple[list[TahsilatRecord], str | None]:
        validated: list[TahsilatRecord] = []

        for row in rows:
            raw_code = str(row.musteri_kodu).strip()
            if not raw_code:
                return [], "Cari kod boş bırakılamaz"
            if float(row.tutar) <= 0:
                return [], f"Tutar pozitif olmalı: {row.tutar}"
            validated.append(
                TahsilatRecord(
                    # Pasif cari kodlar güncel aktif müşteri listesinde
                    # görünmeyebilir. Manuel girilen kod Netsis'e aynen
                    # gönderilir; doğrulanan tek mali kural toplam tutardır.
                    musteri_kodu=raw_code,
                    musteri_ismi=row.musteri_ismi,
                    belge_tarihi=row.belge_tarihi,
                    tutar=float(row.tutar),
                )
            )

        if not validated:
            return [], "Geçerli müşteri kodu ve tutar bulunamadı"

        total = round(sum(row.tutar for row in validated), 2)
        target = round(float(target_amount), 2)
        if total > target + 0.01:
            return [], f"Manuel toplam {total:,.2f} TL, MANİM tutarı {target_amount:,.2f} TL'yi aşamaz"
        if not allow_partial and abs(total - target) > 0.01:
            return [], f"Manuel toplam {total:,.2f} TL, MANİM tutarı {target_amount:,.2f} TL ile eşleşmiyor"

        return validated, None

    def _classify_files(self) -> tuple[list[Path], Path | None, Path | None]:
        manim_files: list[Path] = []
        tahsilat_file: Path | None = None
        customer_file: Path | None = None

        for file in self.files:
            headers = self._headers(file)
            header_keys = {self._key(header) for header in headers}
            name_key = self._key(file.stem)

            if self._is_manim_file(name_key, header_keys):
                manim_files.append(file)
                continue
            if self._is_tahsilat_file(name_key, header_keys):
                tahsilat_file = file
                continue
            if self._is_customer_file(name_key, header_keys):
                customer_file = file
                continue

        return manim_files, tahsilat_file, customer_file

    @staticmethod
    def _is_manim_file(name_key: str, header_keys: set[str]) -> bool:
        return "MANIM" in name_key or {"BANKA", "DEKONTDURUMU"}.issubset(header_keys)

    @staticmethod
    def _is_tahsilat_file(name_key: str, header_keys: set[str]) -> bool:
        if "TAHSILAT" in name_key or "TAHSILATLAR" in name_key:
            return True
        has_customer_name = bool({"MUSTERIISMI", "MUSTERIADI", "UNVAN", "CARIADI"} & header_keys)
        has_amount = bool({"TUTAR", "TAHSILATTUTARI", "TAHSILAT"} & header_keys)
        has_report_hint = bool({"BELGETARIHI", "MUSTERIKODU", "CARI KODU"} & header_keys)
        return has_customer_name and has_amount and has_report_hint

    @staticmethod
    def _is_customer_file(name_key: str, header_keys: set[str]) -> bool:
        if "MUSTERI" in name_key and ("LIST" in name_key or "LISTE" in name_key):
            return True
        has_code = bool({"MUSTERIKODU", "CARIKODU", "CARIKOD"} & header_keys)
        has_title = bool({"UNVAN", "CARIADI", "MUSTERIADI", "MUSTERIISMI"} & header_keys)
        has_customer_only_hint = bool({"VERGINO", "VERGINUMARASI", "SUBE"} & header_keys)
        return has_code and has_title and has_customer_only_hint

    @staticmethod
    def _headers(file: Path) -> list[str]:
        try:
            return [str(column).strip() for column in pd.read_excel(file, nrows=0).columns]
        except Exception as error:
            raise ValueError(f"Dosya okunamadi: {file.name}. {error}") from error

    def _region_from_name(self, name: str) -> str:
        normalized = self._normalize(name)
        for region in self.REGIONS:
            if region in normalized:
                return region
        return "BILINMEYEN_BOLGE"

    def _region_for_record(
        self,
        record: ManimRecord,
        file_region: str,
        customer_region_by_code: dict[str, str] | None = None,
        customer_region_by_name: dict[str, str] | None = None,
    ) -> str:
        """Hesap, müşteri kodu ve müşteri adı sırasıyla satır bölgesini bulur."""
        account_region = self.region_config.find_region_by_manim_account(
            self._bank_key(record.banka),
            record.sube,
        )
        if account_region:
            return account_region

        code_key = self._customer_code_key(record.karsi_hesap_kodu)
        if code_key and customer_region_by_code:
            code_region = customer_region_by_code.get(code_key)
            if code_region:
                return code_region

        name_key = self._key(record.karsi_hesap_adi)
        if name_key and customer_region_by_name:
            name_region = customer_region_by_name.get(name_key)
            if name_region:
                return name_region

        return file_region

    def _customer_region_indexes(
        self,
        customers: list[CustomerRecord],
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Yalnız tek bir bölgeye işaret eden müşteri kodu/adı eşleşmelerini indeksler."""
        regions_by_code: dict[str, set[str]] = defaultdict(set)
        regions_by_name: dict[str, set[str]] = defaultdict(set)

        for customer in customers:
            region = self.region_config.find_region_in_text(customer.sube)
            if not region:
                continue
            code_key = self._customer_code_key(customer.cari_kodu)
            if code_key:
                regions_by_code[code_key].add(region)
            for value in (customer.unvan, customer.tabela_adi):
                name_key = self._key(value)
                if name_key:
                    regions_by_name[name_key].add(region)

        code_index = {
            key: next(iter(regions))
            for key, regions in regions_by_code.items()
            if len(regions) == 1
        }
        name_index = {
            key: next(iter(regions))
            for key, regions in regions_by_name.items()
            if len(regions) == 1
        }
        return code_index, name_index

    @staticmethod
    def _bank_key(value: str) -> str:
        normalized = ProcessingEngine._normalize(value)
        if "GARANTI" in normalized:
            return "GARANTI"
        if "ZIRAAT" in normalized:
            return "ZIRAAT"
        if "YAPI" in normalized or "YKB" in normalized:
            return "YKB"
        return re.sub(r"[^A-Z0-9]+", "_", normalized).strip("_") or "BILINMEYEN_BANKA"

    @staticmethod
    def _normalize(value: str) -> str:
        value = ProcessingEngine._decode_hash_unicode(value)
        text = unicodedata.normalize("NFKD", str(value).upper())
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = text.replace("İ", "I").replace("ı", "I")
        text = re.sub(r"[^A-Z0-9]+", " ", text)
        return " ".join(text.split())

    @staticmethod
    def _key(value: str) -> str:
        value = ProcessingEngine._decode_hash_unicode(value)
        text = unicodedata.normalize("NFKD", str(value).upper())
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = text.replace("İ", "I").replace("ı", "I")
        return re.sub(r"[^A-Z0-9]+", "", text)

    @staticmethod
    def _decode_hash_unicode(value: str) -> str:
        """ZIP/aktarım sırasında ``#U00d6`` biçimine dönen Türkçe harfleri çözer."""
        return re.sub(
            r"#U([0-9A-Fa-f]{4})",
            lambda match: chr(int(match.group(1), 16)),
            str(value),
        )

    @staticmethod
    def _customer_code_key(value: str) -> str:
        return "".join(str(value).strip().upper().split())

    @staticmethod
    def _review_row(region: str, record: ManimRecord, reason: str) -> dict[str, object]:
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
    def _folder_date_label(start: date, end: date) -> str:
        if start == end:
            return start.strftime("%Y-%m-%d")
        return f"{start:%Y-%m-%d}_{end:%Y-%m-%d}"

    @staticmethod
    def _manim_sort_key(record: ManimRecord):
        value = record.islem_tarihi
        if isinstance(value, datetime):
            return value, record.kaynak_dosya, record.kaynak_satir
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day), record.kaynak_dosya, record.kaynak_satir
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
