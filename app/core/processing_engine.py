from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.core.active_profile_store import ActiveProfileStore
from app.core.customer_parser import CustomerParser
from app.core.customer_list_cache import CustomerListCache
from app.core.customer_list_profile import CustomerListProfileStore
from app.core.input_profile import InputProfileStore
from app.core.output_profile import OutputProfileStore
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
from app.core.region_config import RegionConfig, active_region_config_path
from app.core.tahsilat_parser import TahsilatParser
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
        self.input_classifier = ManimInputClassifier()
        self.region_resolver = ManimRegionResolver(self.region_config, self.REGIONS)

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
            {
                "decision": decision,
                "outcome": outcome,
                "region": region,
                "bank": bank,
                "amount": round(float(record.tutar), 2),
                "source_file": Path(record.kaynak_dosya).name,
                "source_row": int(record.kaynak_satir),
                "rule_code": rule_code,
                "reason": reason,
            }
        )

    def run(self, resolver=None, allow_duplicate_files: set[str] | None = None) -> ProcessingResult:
        result = ProcessingResult()
        inputs = self.input_classifier.classify(self.files)
        manim_files = inputs.manim_files
        tahsilat_file = inputs.tahsilat_file
        customer_file = inputs.customer_file

        if not manim_files:
            raise ValueError("En az bir MANIM raporu bulunamadi.")
        if not tahsilat_file:
            raise ValueError("Tahsilat raporu bulunamadi. Dosyayi da surukleyip birakin.")

        active_profiles = ActiveProfileStore(self.data_root)
        user_config_dir = self.data_root / "config"
        input_profile = InputProfileStore(
            self.resource_root / "config", user_config_dir
        ).get_or_default(
            active_profiles.get_input_profile_id()
        )
        output_profile_store = OutputProfileStore(
            self.resource_root / "config", user_config_dir
        )
        output_profile = output_profile_store.get_or_default(
            active_profiles.get_output_profile_id()
        )
        reference_output_profile = output_profile_store.get_or_default(
            active_profiles.get_reference_output_profile_id(),
            default_id="netsis_virman_toplu",
        )
        customer_list_profile = CustomerListProfileStore(
            self.resource_root / "config", user_config_dir
        ).get_or_default(
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

        result.logs.append(
            f"Girdi profili: {input_profile.name} | Çıktı profili: {output_profile.name} | "
            f"Müşteri listesi profili: {customer_list_profile.name}"
        )
        result.logs.append(f"Referanslı çıktı profili: {reference_output_profile.name}")
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

            file_region = self.region_resolver.from_file_name(manim_file.name)
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

        result.virman_records = sum(len(records) for records in virman_by_region.values())
        result.skipped_reference = sum(len(records) for records in referansli_by_region.values())
        result.unresolved = len(pending)
        review_rows = [
            build_review_row(item.region, item.record, item.reason)
            for item in pending
        ]

        # Tüm MANİM dosyaları mükerrer olduğu için atlandıysa yeni çıktı veya
        # işlenmiş dosya kaydı oluşturulmaz.
        if not processed_candidates:
            return result

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

        # Çıktılar görünür ve eksiksiz hale geldikten sonra kalıcı yan etkiler
        # uygulanır. İşlenmiş dosya geçmişi en son yazılır.
        mapping_store.set_many(mapping_updates)
        processed_log.mark_many(processed_candidates)
        result.logs.append(
            f"İşlem başarıyla tamamlandı; {len(processed_candidates)} MANİM dosyası işlenmiş olarak kaydedildi."
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
        return outcome.pending
