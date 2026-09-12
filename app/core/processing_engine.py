from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.core.customer_parser import CustomerParser
from app.core.customer_list_cache import CustomerListCache
from app.core.execution_configuration import ConfigurationSnapshot
from app.core.manim_configuration import capture_manim_configuration, resolve_manim_configuration
from app.core.mapping_store import MappingStore
from app.core.manim_input_classifier import ManimInputClassifier
from app.core.manim_output_service import (
    ManimOutputPlan,
    ManimOutputService,
    build_review_row,
)
from app.core.manim_region_resolver import ManimRegionResolver
from app.core.manim_resolution import (
    CombinedBankMovementMatcher,
    ManualResolution,
    ManualResolutionService,
    UnresolvedItem,
    append_virman_decision,
    build_decision_audit,
    missing_bank_account_code_reason,
    output_key,
    reference_candidate_log,
    requires_bank_account_code,
    with_region_codes,
)
from app.core.movement_classifier import MovementRoute
from app.core.movement_router import MovementRouter
from app.core.output_order import region_sort_key
from app.core.manim_parser import InvalidManimRow, ManimParser
from app.core.processed_files_log import ProcessedFilesLog
from app.core.publication_journal import PublicationJournal
from app.core.region_config import RegionConfig, active_region_config_path
from app.core.review_queue import ReviewMember, ReviewQueue
from app.core.operation_simulation import OperationSimulation, SimulationSummary
from app.core.tahsilat_parser import TahsilatParser
from app.core.tahsilat_consumption_ledger import TahsilatConsumptionLedger
from app.core.text_keys import bank_key
from app.models.records import ManimRecord
from app.processors.havale_processor import HavaleProcessor


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
    virman_records: int = 0
    unresolved: int = 0
    duplicate_files: list[str] = field(default_factory=list)
    odeme_onaylandi_items: list[tuple] = field(default_factory=list)
    odeme_onaylandi_path: Path | None = None
    decision_audits: list[dict] = field(default_factory=list)
    review_queue_groups: int = 0
    simulation_summary: SimulationSummary | None = None
    consumed_tahsilat_rows: int = 0


class ProcessingEngine:
    FALLBACK_REGIONS = ("BODRUM", "FETHIYE", "MUGLA", "SOKE")

    def __init__(
        self,
        files: list[Path],
        project_root: str | Path,
        data_root: str | Path | None = None,
        output_root: str | Path | None = None,
        company_id: int | None = None,
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
        self.company_id = company_id
        self.operation_id: int | None = None

        self.region_config = RegionConfig(
            active_region_config_path(self.resource_root / "config", self.data_root)
        )
        self.REGIONS = self.region_config.regions() or self.FALLBACK_REGIONS
        self.input_classifier = ManimInputClassifier()
        self.region_resolver = ManimRegionResolver(self.region_config, self.REGIONS)
        self._configuration: ConfigurationSnapshot | None = None

    def prepare_configuration(self) -> ConfigurationSnapshot:
        """Pin settings before handing this operation to the worker thread."""
        if self._configuration is None:
            self._configuration = capture_manim_configuration(
                self.resource_root, self.data_root, self.region_config,
            )
        return self._configuration

    def find_duplicate_manim_files(self) -> dict[Path, dict]:
        manim_files = self.input_classifier.classify(self.files).manim_files
        processed_log = ProcessedFilesLog(self.data_root / "data" / "processed_files.json")
        duplicates: dict[Path, dict] = {}
        for manim_file in manim_files:
            file_hash = processed_log.hash_file(manim_file)
            previous = processed_log.is_processed(file_hash)
            if previous:
                duplicates[manim_file] = {"hash": file_hash, **previous}
        return duplicates

    @staticmethod
    def _decision_audit(
        result: ProcessingResult,
        record: ManimRecord,
        region: str,
        bank: str,
        *,
        decision: str,
        outcome: str,
        rule_code: str,
        reason: str = "",
    ) -> None:
        """Karar günlüğü için müşteri/IBAN açıklaması taşımayan özet üretir."""
        result.decision_audits.append(
            build_decision_audit(
                record,
                region,
                bank,
                decision=decision,
                outcome=outcome,
                rule_code=rule_code,
                reason=reason,
            )
        )

    def run(
        self,
        resolver=None,
        allow_duplicate_files: set[str] | None = None,
        *,
        dry_run: bool = False,
    ) -> ProcessingResult:
        result = ProcessingResult()
        inputs = self.input_classifier.classify(self.files)
        manim_files = inputs.manim_files
        tahsilat_file = inputs.tahsilat_file
        customer_file = inputs.customer_file

        if not manim_files:
            raise ValueError("En az bir MANIM raporu bulunamadi.")
        if not tahsilat_file:
            raise ValueError("Tahsilat raporu bulunamadi. Dosyayi da surukleyip birakin.")

        (self.region_config, input_profile, output_profile, reference_output_profile,
         customer_list_profile) = resolve_manim_configuration(
            self.prepare_configuration(), self.region_config.file_path,
        )
        self.REGIONS = self.region_config.regions() or self.FALLBACK_REGIONS
        self.region_resolver = ManimRegionResolver(self.region_config, self.REGIONS)

        customer_cache = CustomerListCache(self.data_root)
        customer_file_is_fresh = customer_file is not None
        if customer_file is None:
            customer_file = customer_cache.get()
            if not customer_file:
                raise ValueError("Musteri listesi bulunamadi. Dosyayi da surukleyip birakin.")

        allow_duplicate_files = allow_duplicate_files or set()
        processed_log = ProcessedFilesLog(self.data_root / "data" / "processed_files.json")
        publication_journal = None
        reusable_operation_ids: tuple[int, ...] = ()
        if not dry_run:
            publication_journal = PublicationJournal(
                self.data_root / "data" / "publication_journal.sqlite3",
                company_id=self.company_id,
            )
            publication_journal.assert_reprocessable([
                processed_log.hash_file(path) for path in manim_files
            ])
            source_hashes = {processed_log.hash_file(path) for path in manim_files}
            if source_hashes and source_hashes.issubset(allow_duplicate_files):
                reusable_operation_ids = (
                    publication_journal.committed_operation_ids_for_exact_sources(source_hashes)
                )

        tahsilat_parser = TahsilatParser(tahsilat_file)
        tahsilat_source_rows = tahsilat_parser.load()
        consumption_ledger = None
        if dry_run:
            # Simülasyon kaynak bakiyeleri değiştirmez ve boş bir defter
            # veritabanı dahi oluşturmamalıdır.
            tahsilat = list(tahsilat_source_rows)
        else:
            consumption_ledger = TahsilatConsumptionLedger(
                self.data_root / "data" / "tahsilat_consumption.sqlite3",
                company_id=self.company_id,
            )
            tahsilat = consumption_ledger.available_rows(
                tahsilat_source_rows,
                reusable_operation_ids=reusable_operation_ids,
            )
        customers = CustomerParser(customer_file, profile=customer_list_profile).load()
        # Yeni müşteri listesi bu turda okunur; ancak hafızaya alma ancak
        # gerçek aktarım başarıyla sonlandıktan sonra yapılır. Böylece
        # aktarım öncesi simülasyon hiçbir kalıcı veriyi değiştirmez.
        customer_region_by_code, customer_region_by_name = self.region_resolver.customer_indexes(customers)
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
        movement_router = MovementRouter(self.region_config)

        outputs: dict[tuple[str, str], list] = defaultdict(list)
        pending: list[UnresolvedItem] = []
        invalid_rows: list[InvalidManimRow] = []
        odeme_onaylandi_items: list[tuple[ManimRecord, str, str]] = []
        referansli_by_region: dict[str, list[ManimRecord]] = defaultdict(list)
        kural_calisti_by_region: dict[str, list[ManimRecord]] = defaultdict(list)
        virman_by_region: dict[str, list] = defaultdict(list)
        islem_tarihleri: set[date] = set()
        processed_candidates: list[tuple[str, str, int]] = []
        mapping_updates: list[tuple[str, list[dict]]] = []
        consumption_rows = []
        source_identities: dict[tuple[str, int], tuple[str, str]] = {}

        result.logs.append(
            f"Girdi profili: {input_profile.name} | Çıktı profili: {output_profile.name} | "
            f"Müşteri listesi profili: {customer_list_profile.name}"
        )
        result.logs.append(f"Referanslı çıktı profili: {reference_output_profile.name}")
        result.logs.append(f"Tahsilat raporu: {tahsilat_file.name}")
        if reusable_operation_ids:
            result.logs.append(
                "Yeniden çıktı onayı: aynı MANİM kaynaklarının önceki tahsilat "
                "dağılımları bu çalıştırmaya devredildi."
            )
        if len(tahsilat) != len(tahsilat_source_rows):
            result.logs.append(
                f"Tahsilat kullanım defteri: {len(tahsilat_source_rows) - len(tahsilat)} satırın bakiyesi kapalı olduğu için eşleştirme havuzundan çıkarıldı."
            )
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
            # Önizleme salt okunur bir yeniden hesaplamadır. Dosya daha önce
            # aktarılmış olsa bile seçili kaynak yeniden okunmalıdır; aksi
            # halde simülasyon boş karar planı gösterir. Gerçek aktarımda
            # mükerrer dosya güvenliği değişmez.
            if previous and not dry_run and file_hash not in allow_duplicate_files:
                result.duplicate_files.append(manim_file.name)
                result.logs.append(
                    f"UYARI: {manim_file.name} daha önce işlenmiş görünüyor "
                    f"({previous['tarih']}, {previous['kayit_sayisi']} kayıt) — atlandı."
                )
                continue

            file_region = self.region_resolver.from_file_name(manim_file.name)
            parse_result = ManimParser(manim_file, profile=input_profile).load_with_issues()
            records = parse_result.records
            source_identities.update({
                (record.kaynak_dosya, int(record.kaynak_satir)): (file_hash, parse_result.sheet_name)
                for record in records
            })
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
                region = self.region_resolver.for_record(
                    record,
                    file_region,
                    customer_region_by_code,
                    customer_region_by_name,
                )
                row_region_counts[region] += 1
                decision = movement_router.route(record, region)

                if decision.route == MovementRoute.REVIEW:
                    self._decision_audit(
                        result, record, region, bank_key(record.banka),
                        decision="ROUTE", outcome="REVIEW",
                        rule_code=decision.code, reason=decision.reason,
                    )
                    pending.append(UnresolvedItem(
                        record=record,
                        region=region,
                        reason=decision.reason,
                    ))
                    if decision.code == "NEGATIVE_PAYMENT_APPROVAL":
                        result.logs.append(
                            "UYARI: Negatif tutarlı kayıt Ödeme Onaylandı'ya yazılmadı; "
                            "Referanslı kayıt olarak kontrol bekliyor."
                        )
                    elif decision.code == "AMBIGUOUS_STAFF_DEPOSIT":
                        result.logs.append(
                            "UYARI: Referanslı seçilmiş ancak açıklamada ROTA/YATAN PARA "
                            "bilgisi var; Ödeme Onaylandı olma ihtimali için kullanıcı onayı bekliyor."
                        )
                    else:
                        result.logs.append(
                            f"UYARI [{decision.code}]: {decision.reason}"
                        )
                    continue

                if decision.route == MovementRoute.ODEME_ONAYLANDI:
                    self._decision_audit(
                        result, record, region, bank_key(record.banka),
                        decision="ROUTE", outcome="ODEME_ONAYLANDI",
                        rule_code=decision.code, reason=decision.reason,
                    )
                    odeme_onaylandi_items.append((record, region, bank_key(record.banka)))
                    result.skipped_payment += 1
                    continue

                if decision.route == MovementRoute.KURAL_CALISTI:
                    self._decision_audit(
                        result, record, region, bank_key(record.banka),
                        decision="ROUTE", outcome="KURAL_CALISTI",
                        rule_code=decision.code, reason=decision.reason,
                    )
                    kural_calisti_by_region[region].append(record)
                    result.skipped_rule += 1
                    continue

                if decision.route == MovementRoute.SAME_BANK_VIRMAN:
                    self._decision_audit(
                        result, record, region, bank_key(record.banka),
                        decision="ROUTE", outcome="SAME_BANK_VIRMAN",
                        rule_code=decision.code, reason=decision.reason,
                    )
                    result.logs.append(
                        append_virman_decision(decision, region, virman_by_region)
                    )
                    continue

                if decision.route == MovementRoute.REFERANSLI:
                    self._decision_audit(
                        result, record, region, bank_key(record.banka),
                        decision="ROUTE", outcome="REFERANSLI",
                        rule_code=decision.code, reason=decision.reason,
                    )
                    referansli_by_region[region].append(record)
                    candidate_log = reference_candidate_log(decision, record)
                    if candidate_log:
                        result.logs.append(candidate_log)
                    continue

                if decision.route != MovementRoute.HAVALE:
                    raise ValueError(
                        f"İşleme motorunun desteklemediği hareket rotası: {decision.route}"
                    )

                bank = bank_key(record.banka)
                if requires_bank_account_code(output_profile) and not self.region_config.banka_kodu(region, bank):
                    self._decision_audit(
                        result, record, region, bank,
                        decision="ROUTE", outcome="REVIEW",
                        rule_code="MISSING_BANK_ACCOUNT_CODE",
                        reason=missing_bank_account_code_reason(region, bank),
                    )
                    pending.append(UnresolvedItem(
                        record=record,
                        region=region,
                        reason=missing_bank_account_code_reason(region, bank),
                    ))
                    continue

                netsis_rows, reason = processor.process(record, region)
                if reason:
                    self._decision_audit(
                        result, record, region, bank,
                        decision="MATCH", outcome="REVIEW",
                        rule_code="CUSTOMER_MATCH_REVIEW", reason=reason,
                    )
                    pending.append(UnresolvedItem(
                        record=record,
                        region=region,
                        reason=reason,
                        suggested_rows=list(processor.last_suggested_rows),
                        combined_group_key=processor.last_combined_group_key,
                        combined_suggested_rows=list(
                            processor.last_combined_suggested_rows
                        ),
                    ))
                    continue

                for netsis_row in netsis_rows:
                    outputs[output_key(region, bank, output_profile)].append(
                        with_region_codes(
                            netsis_row,
                            region,
                            bank,
                            self.region_config,
                        )
                    )
                    result.produced_netsis_records += 1
                self._decision_audit(
                    result, record, region, bank,
                    decision="MATCH", outcome="HAVALE",
                    rule_code="AUTOMATIC_CUSTOMER_MATCH",
                )
                consumption_rows.extend(processor.last_consumption_rows)

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
        combined_outcome = CombinedBankMovementMatcher(self.region_config).match(
            pending, outputs, output_profile, processor,
        )
        pending = combined_outcome.pending
        result.produced_netsis_records += combined_outcome.produced_netsis_records
        result.logs.extend(combined_outcome.logs)
        result.decision_audits.extend(combined_outcome.decision_audits)
        consumption_rows.extend(combined_outcome.consumption_rows)

        if pending and resolver:
            resolutions = resolver(pending, customers, tahsilat) or {}
            manual_outcome = ManualResolutionService(self.region_config).apply(
                pending=pending,
                resolutions=resolutions,
                outputs=outputs,
                output_profile=output_profile,
                processor=processor,
                movement_router=movement_router,
                virman_by_region=virman_by_region,
                referansli_by_region=referansli_by_region,
                odeme_onaylandi_items=odeme_onaylandi_items,
            )
            pending = manual_outcome.pending
            result.produced_netsis_records += manual_outcome.produced_netsis_records
            result.skipped_payment += manual_outcome.skipped_payment
            result.logs.extend(manual_outcome.logs)
            mapping_updates.extend(manual_outcome.mapping_updates)
            result.decision_audits.extend(manual_outcome.decision_audits)
            consumption_rows.extend(manual_outcome.consumption_rows)

        result.virman_records = sum(len(records) for records in virman_by_region.values())
        result.skipped_reference = sum(len(records) for records in referansli_by_region.values())
        result.unresolved = len(pending)
        # Simülasyon özeti yalnız mevcut kararları hesaplar; çıktı, hafıza ve
        # tüketim kaydı oluşturmaz. 1D önizleme ekranı aynı servisi kullanır.
        result.simulation_summary = OperationSimulation().summarize(
            result.decision_audits,
            netsis_records=(row for rows in outputs.values() for row in rows),
        )
        review_rows: list[dict] = []
        review_groups: list[list[ReviewMember]] = []
        for item in pending:
            # Birleşik hareketlerde ekranda tek karar görünür, ancak kalıcı
            # inceleme kuyruğu ve inceleme Excel'i grubun bütün banka
            # hareketlerini korur.
            records = item.group_records or [item.record]
            review_rows.extend(
                build_review_row(item.region, record, item.reason)
                for record in records
            )
            review_groups.append([
                ReviewMember(
                    source_file=str(record.kaynak_dosya),
                    source_row=int(record.kaynak_satir),
                    amount=float(record.tutar),
                    region=item.region,
                    bank=str(record.banka),
                    reason=item.reason,
                    source_hash=source_identities.get(
                        (record.kaynak_dosya, int(record.kaynak_satir)), ("", "")
                    )[0],
                    sheet_name=source_identities.get(
                        (record.kaynak_dosya, int(record.kaynak_satir)), ("", "")
                    )[1],
                )
                for record in records
            ])

        # Tüm MANİM dosyaları mükerrer olduğu için atlandıysa yeni çıktı veya
        # işlenmiş dosya kaydı oluşturulmaz.
        if not processed_candidates or dry_run:
            if dry_run:
                result.logs.append("Simülasyon tamamlandı; çıktı ve işlenmiş dosya kaydı oluşturulmadı.")
            return result

        # Çıktı üretmeden hemen önce, simülasyon sırasında hiç yazılmayan
        # satır bazlı kullanım tutarlarını tekrar doğrula. Eşzamanlı başka bir
        # gerçek aktarım arada aynı bakiyeyi kullanmışsa dosya üretilmez.
        if consumption_ledger is None:
            raise RuntimeError("Gerçek aktarım için tahsilat kullanım defteri başlatılamadı.")
        consumption_ledger.assert_can_consume(
            consumption_rows,
            reusable_operation_ids=reusable_operation_ids,
        )

        output_artifacts = ManimOutputService(
            self.output_root,
            self.region_config,
            self.REGIONS,
        ).write(
            ManimOutputPlan(
                outputs=outputs,
                virman_by_region=virman_by_region,
                review_rows=review_rows,
                invalid_rows=invalid_rows,
                odeme_onaylandi_items=odeme_onaylandi_items,
                referansli_by_region=referansli_by_region,
                kural_calisti_by_region=kural_calisti_by_region,
                islem_tarihleri=islem_tarihleri,
                output_profile=output_profile,
                reference_output_profile=reference_output_profile,
            )
        )
        result.output_dir = output_artifacts.output_dir
        result.created_files = output_artifacts.created_files
        result.review_file = output_artifacts.review_file
        result.invalid_file = output_artifacts.invalid_file
        result.odeme_onaylandi_path = output_artifacts.odeme_onaylandi_path
        result.odeme_onaylandi_items = list(odeme_onaylandi_items)
        result.logs.extend(output_artifacts.logs)

        # Klasör artık kullanıcı tarafından görülebilir. Devamındaki yerel
        # kayıtlar kesintiye uğrarsa aynı kaynak otomatik tekrar işlenmez.
        publication_id = publication_journal.publish(
            operation_id=self.operation_id,
            source_hashes=[item[0] for item in processed_candidates],
            output_dir=output_artifacts.output_dir,
            output_files=output_artifacts.created_files,
        )

        review_queue = ReviewQueue(
            self.data_root / "data" / "operations.sqlite3",
            company_id=self.company_id,
        )
        for members in review_groups:
            group_id = review_queue.enqueue(
                members,
                operation_id=self.operation_id,
            )
            if group_id:
                result.review_queue_groups += 1
        if result.review_queue_groups:
            result.logs.append(
                f"Kalıcı inceleme kuyruğuna {result.review_queue_groups} grup kaydedildi."
            )

        # Çıktılar görünür ve eksiksiz hale geldikten sonra kalıcı yan etkiler
        # uygulanır. Tahsilat kullanım kaydı önce gelir: sonraki yerel adım
        # kesilirse yayın günlüğü zaten otomatik tekrar çalıştırmayı engeller.
        # İşlenmiş dosya geçmişi en son yazılır.
        result.consumed_tahsilat_rows = consumption_ledger.replace_for_retry(
            consumption_rows,
            operation_id=self.operation_id,
            reusable_operation_ids=reusable_operation_ids,
        )
        if customer_file_is_fresh:
            customer_cache.save(customer_file)
        mapping_store.set_many(mapping_updates)
        processed_log.mark_many(processed_candidates)
        publication_journal.commit(publication_id)
        result.logs.append(
            f"İşlem başarıyla tamamlandı; {len(processed_candidates)} MANİM dosyası işlenmiş olarak kaydedildi."
        )
        if result.consumed_tahsilat_rows:
            result.logs.append(
                f"Tahsilat kullanım defterine {result.consumed_tahsilat_rows} kaynak satır işlendi."
            )

        return result

    def _match_combined_bank_movements(self, pending, outputs, result, output_profile, processor):
        outcome = CombinedBankMovementMatcher(self.region_config).match(
            pending,
            outputs,
            output_profile,
            processor,
        )
        result.produced_netsis_records += outcome.produced_netsis_records
        result.logs.extend(outcome.logs)
        result.decision_audits.extend(outcome.decision_audits)
        return outcome.pending
