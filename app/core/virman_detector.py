from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from app.core.money import money
from app.core.region_config import RegionConfig
from app.models.records import ManimRecord, VirmanRecord


@dataclass(frozen=True)
class VirmanDetection:
    record: VirmanRecord | None = None
    reason: str = ""
    candidate: bool = False


class VirmanDetector:
    """Negatif Referanslı kayıtlardan güvenli hesaplar arası virmanları ayırır."""

    def __init__(self, region_config: RegionConfig):
        self.region_config = region_config

    def detect(self, record: ManimRecord, source_region: str) -> VirmanDetection:
        if money(record.tutar) >= 0:
            return VirmanDetection()

        description = " ".join(
            value
            for value in (
                record.aciklama,
                record.karsi_hesap_adi,
                record.karsi_hesap_kodu,
            )
            if str(value or "").strip()
        )
        normalized = self._normalize(description)
        source_region = str(source_region or "").strip().upper()
        source_bank = self._bank_key(record.banka)

        explicit_virman = "VIRMAN" in normalized
        own_account_transfer = bool(
            re.search(r"\bHES(?:ABI)?[ .]*(?:EFT|HVL|HAVALE)\b", normalized)
            or "GIDEN HAVALE" in normalized
        )
        if not (explicit_virman or own_account_transfer):
            return VirmanDetection()

        source_code = self.region_config.banka_kodu(source_region, source_bank)
        project_code = self.region_config.proje_kodu(source_region)
        if not source_code or project_code is None:
            return VirmanDetection(
                reason=(
                    f"{source_region} / {source_bank} için kaynak banka veya proje kodu "
                    "tanımlı değil."
                ),
                candidate=True,
            )

        targets = self.region_config.find_manim_accounts_in_text(
            description,
            exclude=(source_region, source_bank),
        )
        if not targets:
            return VirmanDetection(
                reason=(
                    "Virman işareti bulundu ancak hedef hesap/IBAN Bölge Yönetimi’ndeki "
                    "bilinen hesap sonlarıyla eşleşmedi."
                ),
                candidate=True,
            )
        if len(targets) != 1:
            target_labels = ", ".join(f"{region}/{bank}" for region, bank in targets)
            return VirmanDetection(
                reason=f"Virman hedefi birden fazla hesapla eşleşti: {target_labels}",
                candidate=True,
            )

        target_region, target_bank = targets[0]
        target_code = self.region_config.banka_kodu(target_region, target_bank)
        if not target_code:
            return VirmanDetection(
                reason=f"{target_region} / {target_bank} için hedef banka kodu tanımlı değil.",
                candidate=True,
            )

        transaction_date = record.islem_tarihi
        date_text = transaction_date.strftime("%d.%m.%Y") if transaction_date else ""
        return VirmanDetection(
            record=VirmanRecord(
                islem_tarihi=transaction_date,
                islem_tarihi_metni=date_text,
                tutar=float(abs(money(record.tutar))),
                aciklama=record.aciklama,
                bolge=source_region,
                kaynak_banka=source_bank,
                hedef_banka=target_bank,
                kaynak_banka_hesap_kodu=str(source_code),
                hedef_banka_hesap_kodu=str(target_code),
                muh_ref_kodu=str(self.region_config.genel_ref_kodu()),
                proje_kodu=int(project_code),
                plasiyer_kodu=str(self.region_config.plasiyer_kodu()),
                kaynak="REFERANSLI_VIRMAN",
            ),
            candidate=True,
        )

    @staticmethod
    def _bank_key(value: str) -> str:
        normalized = VirmanDetector._normalize(value)
        if "GARANTI" in normalized:
            return "GARANTI"
        if "ZIRAAT" in normalized:
            return "ZIRAAT"
        if "YAPI" in normalized or "YKB" in normalized:
            return "YKB"
        return re.sub(r"[^A-Z0-9]+", "_", normalized).strip("_") or "BILINMEYEN_BANKA"

    @staticmethod
    def _normalize(value: object) -> str:
        text = unicodedata.normalize("NFKD", str(value or "").upper())
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = text.replace("İ", "I").replace("ı", "I")
        text = re.sub(r"[^A-Z0-9]+", " ", text)
        return " ".join(text.split())
