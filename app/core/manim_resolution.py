from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

from app.core.money import money, money_sum
from app.core.movement_classifier import MovementRoute
from app.core.movement_router import MovementDecision, MovementRouter
from app.core.output_profile import OutputProfile
from app.core.region_config import RegionConfig
from app.core.text_keys import bank_key
from app.models.records import ManimRecord, TahsilatRecord
from app.processors.havale_processor import HavaleProcessor


@dataclass
class UnresolvedItem:
    """Otomatik eşleşmeyen tek bir MANİM kaydı."""

    record: ManimRecord
    region: str
    reason: str
    suggested_rows: list[TahsilatRecord] = field(default_factory=list)
    group_records: list[ManimRecord] = field(default_factory=list)
    group_target_amount: float | None = None


@dataclass
class ManualResolution:
    """Kullanıcının manuel eşleştirme ekranında bir kayıt için verdiği karar."""

    route: str
    rows: list[TahsilatRecord] | None = None
    allow_partial: bool = False


@dataclass
class ResolutionOutcome:
    pending: list[UnresolvedItem]
    produced_netsis_records: int = 0
    skipped_payment: int = 0
    logs: list[str] = field(default_factory=list)
    mapping_updates: list[tuple[str, list[dict]]] = field(default_factory=list)
    decision_audits: list[dict] = field(default_factory=list)


def build_decision_audit(
    record: ManimRecord,
    region: str,
    bank: str,
    *,
    decision: str,
    outcome: str,
    rule_code: str,
    reason: str = "",
) -> dict:
    """Kişisel dekont içeriğini çoğaltmadan denetlenebilir karar özeti üretir."""
    return {
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


def output_key(
    region: str,
    bank: str,
    output_profile: OutputProfile,
) -> tuple[str, str]:
    return region, bank if output_profile.grouping == "region_bank" else "TOPLU"


def requires_bank_account_code(output_profile: OutputProfile) -> bool:
    return any(
        column.source_kind == "field" and column.field == "banka_hesap_kodu"
        for column in output_profile.columns
    )


def missing_bank_account_code_reason(region: str, bank: str) -> str:
    return (
        f"{region} bölgesi {bank} için BM banka hesap kodu tanımlı değil. "
        "Ayarlar > Bölge Yönetimi bölümünden bu banka için BM kodunu ekleyin; "
        "satır boş BM koduyla Netsis aktarımına yazılmadı."
    )


def with_region_codes(record, region: str, bank: str, region_config: RegionConfig):
    return replace(
        record,
        bolge=region,
        banka_hesap_kodu=region_config.banka_kodu(region, bank) or "",
    )


def validate_manual_rows(
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
                # Pasif cari kod aktif müşteri listesinde bulunmasa da manuel
                # onayla Netsis'e aynen gönderilebilir.
                musteri_kodu=raw_code,
                musteri_ismi=row.musteri_ismi,
                belge_tarihi=row.belge_tarihi,
                tutar=float(row.tutar),
            )
        )

    if not validated:
        return [], "Geçerli müşteri kodu ve tutar bulunamadı"

    total = money_sum(row.tutar for row in validated)
    target = money(target_amount)
    if total > target:
        return [], (
            f"Manuel toplam {total:,.2f} TL, MANİM tutarı "
            f"{target_amount:,.2f} TL'yi aşamaz"
        )
    if not allow_partial and total != target:
        return [], (
            f"Manuel toplam {total:,.2f} TL, MANİM tutarı "
            f"{target_amount:,.2f} TL ile eşleşmiyor"
        )
    return validated, None


def append_virman_decision(
    decision: MovementDecision,
    region: str,
    virman_by_region: dict[str, list],
) -> str:
    virman_record = decision.virman_record
    if virman_record is None:
        raise ValueError("Aynı banka virman kararında çıktı kaydı bulunamadı.")
    virman_by_region[region].append(virman_record)
    return (
        f"Virman ayrıldı: {region}/{virman_record.kaynak_banka} -> "
        f"{virman_record.hedef_banka}, {virman_record.tutar:,.2f} TL."
    )


def reference_candidate_log(
    decision: MovementDecision,
    record: ManimRecord,
) -> str | None:
    if not decision.candidate or not decision.reason:
        return None
    return (
        "UYARI: Virman otomatik ayrılamadı; Referanslı listede bırakıldı: "
        f"{decision.reason} ({record.aciklama[:60]}...)"
    )


class CombinedBankMovementMatcher:
    """Aynı tahsilat havuzuna ait birden fazla banka hareketini birleştirir."""

    def __init__(self, region_config: RegionConfig):
        self.region_config = region_config

    def match(
        self,
        pending: list[UnresolvedItem],
        outputs: dict[tuple[str, str], list],
        output_profile: OutputProfile,
        processor: HavaleProcessor,
    ) -> ResolutionOutcome:
        candidate_groups: dict[tuple, list[tuple[int, UnresolvedItem]]] = defaultdict(list)
        for index, item in enumerate(pending):
            if not item.suggested_rows or not item.record.islem_tarihi:
                continue
            bank = bank_key(item.record.banka)
            key = (
                item.region,
                bank,
                item.record.islem_tarihi.date(),
                self._suggested_signature(item.suggested_rows),
            )
            candidate_groups[key].append((index, item))

        consumed: set[int] = set()
        manual_groups: list[UnresolvedItem] = []
        produced = 0
        logs: list[str] = []
        decision_audits: list[dict] = []
        for (region, bank, _day, _signature), indexed_items in candidate_groups.items():
            if len(indexed_items) < 2:
                continue
            items = [item for _index, item in indexed_items]
            indexes = [index for index, _item in indexed_items]
            target = money(money_sum(row.tutar for row in items[0].suggested_rows))
            total = money_sum(item.record.tutar for item in items)
            movements = " + ".join(f"{money(item.record.tutar):,.2f}" for item in items)

            if total == target:
                for candidate in items[0].suggested_rows:
                    netsis_record = processor._netsis_record(
                        items[0].record,
                        str(candidate.musteri_kodu).strip(),
                        candidate.tutar,
                        "BIRLESIK_BANKA_HAREKETI",
                    )
                    outputs[output_key(region, bank, output_profile)].append(
                        with_region_codes(
                            netsis_record,
                            region,
                            bank,
                            self.region_config,
                        )
                    )
                    produced += 1
                consumed.update(indexes)
                decision_audits.extend(
                    build_decision_audit(
                        item.record,
                        region,
                        bank,
                        decision="MATCH",
                        outcome="HAVALE",
                        rule_code="COMBINED_BANK_MOVEMENTS_EXACT",
                    )
                    for item in items
                )
                logs.append(
                    f"Birleşik havale eşleşti: {movements} TL = {target:,.2f} TL "
                    f"({len(items)} banka hareketi)."
                )
                continue

            consumed.update(indexes)
            review_reason = (
                f"{len(items)} banka hareketinin toplamı tahsilat hedefiyle eşleşmiyor."
            )
            decision_audits.extend(
                build_decision_audit(
                    item.record,
                    region,
                    bank,
                    decision="MATCH",
                    outcome="REVIEW",
                    rule_code="COMBINED_BANK_MOVEMENTS_DIFFERENCE",
                    reason=review_reason,
                )
                for item in items
            )
            manual_groups.append(
                UnresolvedItem(
                    record=items[0].record,
                    region=region,
                    reason=(
                        f"Aynı müşteri için {len(items)} havale bulundu. Tutarları düzenleyip "
                        "tahsilat hedefiyle eşitleyerek birlikte onaylayın."
                    ),
                    suggested_rows=list(items[0].suggested_rows),
                    group_records=[item.record for item in items],
                    group_target_amount=float(target),
                )
            )
            logs.append(
                f"Toplu havale kontrol bekliyor: {movements} TL; "
                f"tahsilat hedefi {target:,.2f} TL ({len(items)} banka hareketi)."
            )

        remaining = [
            item for index, item in enumerate(pending) if index not in consumed
        ] + manual_groups
        return ResolutionOutcome(
            pending=remaining,
            produced_netsis_records=produced,
            logs=logs,
            decision_audits=decision_audits,
        )

    @staticmethod
    def _suggested_signature(
        rows: list[TahsilatRecord],
    ) -> tuple[tuple[str, object], ...]:
        return tuple(
            sorted(
                (str(row.musteri_kodu).strip(), money(row.tutar))
                for row in rows
            )
        )


class ManualResolutionService:
    """Eşleştirme ekranındaki kullanıcı kararlarını mali kurallarla uygular."""

    def __init__(self, region_config: RegionConfig):
        self.region_config = region_config

    def apply(
        self,
        pending: list[UnresolvedItem],
        resolutions: dict[int, ManualResolution],
        outputs: dict[tuple[str, str], list],
        output_profile: OutputProfile,
        processor: HavaleProcessor,
        movement_router: MovementRouter,
        virman_by_region: dict[str, list],
        referansli_by_region: dict[str, list[ManimRecord]],
        odeme_onaylandi_items: list[tuple[ManimRecord, str, str]],
    ) -> ResolutionOutcome:
        still_pending: list[UnresolvedItem] = []
        produced = 0
        skipped_payment = 0
        logs: list[str] = []
        mapping_updates: list[tuple[str, list[dict]]] = []
        decision_audits: list[dict] = []

        def audit(
            item: UnresolvedItem,
            outcome: str,
            rule_code: str,
            reason: str = "",
            records: list[ManimRecord] | None = None,
        ) -> None:
            for record in records or [item.record]:
                decision_audits.append(
                    build_decision_audit(
                        record,
                        item.region,
                        bank_key(record.banka),
                        decision="MANUAL",
                        outcome=outcome,
                        rule_code=rule_code,
                        reason=reason,
                    )
                )

        for index, item in enumerate(pending):
            resolution = resolutions.get(index)
            if not resolution:
                still_pending.append(item)
                continue
            if resolution.route == "ATLA":
                still_pending.append(item)
                audit(item, "SKIPPED", "MANUAL_SKIPPED")
                continue

            if resolution.route == "ODEME_ONAYLANDI":
                if item.record.tutar < 0:
                    still_pending.append(item)
                    rejection = "Negatif tutarlı kayıt Ödeme Onaylandı'ya taşınamaz."
                    audit(
                        item,
                        "REVIEW",
                        "MANUAL_PAYMENT_NEGATIVE_REJECTED",
                        rejection,
                    )
                    logs.append(
                        "UYARI: Negatif tutarlı kayıt manuel olarak da Ödeme Onaylandı'ya "
                        "taşınamaz; inceleme listesinde bırakıldı."
                    )
                    continue
                odeme_onaylandi_items.append(
                    (item.record, item.region, bank_key(item.record.banka))
                )
                skipped_payment += 1
                audit(item, "ODEME_ONAYLANDI", "MANUAL_ROUTE")
                logs.append(
                    "Manuel olarak Ödeme Onaylandı'ya taşındı: "
                    f"{item.record.aciklama[:60]}..."
                )
                continue

            if resolution.route == "REFERANSLI":
                decision = movement_router.route_reference(item.record, item.region)
                if decision.route == MovementRoute.SAME_BANK_VIRMAN:
                    audit(item, "SAME_BANK_VIRMAN", "MANUAL_ROUTE")
                    logs.append(
                        append_virman_decision(decision, item.region, virman_by_region)
                    )
                else:
                    referansli_by_region[item.region].append(item.record)
                    audit(item, "REFERANSLI", "MANUAL_ROUTE", decision.reason)
                    candidate_log = reference_candidate_log(decision, item.record)
                    if candidate_log:
                        logs.append(candidate_log)
                    logs.append(
                        "Manuel olarak Referanslı'ya taşındı: "
                        f"{item.record.aciklama[:60]}..."
                    )
                continue

            if resolution.route != "HAVALE" or not resolution.rows:
                still_pending.append(item)
                audit(
                    item,
                    "REVIEW",
                    "MANUAL_RESOLUTION_INCOMPLETE",
                    "Manuel karar için geçerli rota ve satır bilgisi bulunamadı.",
                )
                continue

            if item.group_records:
                validated_rows, validation_error = validate_manual_rows(
                    resolution.rows,
                    item.group_target_amount or 0,
                    allow_partial=False,
                )
                if validation_error:
                    still_pending.append(item)
                    audit(
                        item,
                        "REVIEW",
                        "MANUAL_COMBINED_REJECTED",
                        validation_error,
                        records=item.group_records,
                    )
                    logs.append(
                        "UYARI: Toplu havale manuel eşleştirmesi kabul edilmedi: "
                        f"{validation_error}"
                    )
                    continue
                bank = bank_key(item.record.banka)
                for row in validated_rows:
                    netsis_row = processor._netsis_record(
                        item.group_records[0],
                        row.musteri_kodu,
                        row.tutar,
                        "TOPLU_MANUEL_ESLESTIRME",
                    )
                    outputs[output_key(item.region, bank, output_profile)].append(
                        with_region_codes(
                            netsis_row,
                            item.region,
                            bank,
                            self.region_config,
                        )
                    )
                    produced += 1
                audit(
                    item,
                    "HAVALE",
                    "MANUAL_COMBINED_MATCH",
                    records=item.group_records,
                )
                logs.append(
                    f"Toplu havale manuel onaylandı: {len(item.group_records)} hareket, "
                    f"{len(validated_rows)} cari dağılımı, {item.group_target_amount:,.2f} TL."
                )
                continue

            bank = bank_key(item.record.banka)
            if (
                requires_bank_account_code(output_profile)
                and not self.region_config.banka_kodu(item.region, bank)
            ):
                reason = missing_bank_account_code_reason(item.region, bank)
                still_pending.append(
                    UnresolvedItem(
                        record=item.record,
                        region=item.region,
                        reason=reason,
                        suggested_rows=item.suggested_rows,
                    )
                )
                audit(item, "REVIEW", "MISSING_BANK_ACCOUNT_CODE", reason)
                logs.append(
                    "UYARI: BM kodu olmadığı için manuel havale aktarımı bekletildi: "
                    f"{item.record.aciklama[:60]}..."
                )
                continue

            validated_rows, validation_error = validate_manual_rows(
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
                audit(
                    item,
                    "REVIEW",
                    "MANUAL_MATCH_REJECTED",
                    validation_error,
                )
                logs.append(
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
                outputs[output_key(item.region, bank, output_profile)].append(
                    with_region_codes(
                        netsis_row,
                        item.region,
                        bank,
                        self.region_config,
                    )
                )
                produced += 1

            manual_total = round(sum(row.tutar for row in validated_rows), 2)
            remaining = round(float(item.record.tutar) - manual_total, 2)
            if resolution.allow_partial and remaining > 0.01:
                audit(item, "HAVALE", "MANUAL_PARTIAL_MATCH")
                logs.append(
                    f"Manuel kısmi eşleştirme: {manual_total:,.2f} TL Netsis'e aktarıldı, "
                    f"{remaining:,.2f} TL bekleyen bakiye olarak bırakıldı: "
                    f"{item.record.aciklama[:60]}..."
                )
            else:
                audit(item, "HAVALE", "MANUAL_CUSTOMER_MATCH")
                mapping_updates.append(
                    (
                        item.record.aciklama,
                        [
                            {"musteri_kodu": row.musteri_kodu, "tutar": row.tutar}
                            for row in validated_rows
                        ],
                    )
                )
                logs.append(
                    "Manuel eşleştirildi; çıktı başarıyla oluşunca hafızaya kaydedilecek: "
                    f"{item.record.aciklama[:60]}..."
                )

        return ResolutionOutcome(
            pending=still_pending,
            produced_netsis_records=produced,
            skipped_payment=skipped_payment,
            logs=logs,
            mapping_updates=mapping_updates,
            decision_audits=decision_audits,
        )
