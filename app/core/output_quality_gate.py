"""MANİM çıktıları için Excel yazımından önce çalışan kalite kapısı.

Bu katman onaylı şablonu değiştirmez veya yeni bir şablon üretmez. Amacı,
Netsis'in daha sonra genel bir "Banka Kodunu Kontrol Ediniz" uyarısı vereceği
durumları, dosya üretilmeden önce açık bölge/banka/satır bilgisiyle yakalamaktır.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from app.core.manim_resolution import requires_bank_account_code
from app.core.money import money
from app.core.output_profile import OutputProfile
from app.core.region_config import RegionConfig
from app.core.text_keys import bank_key
from app.models.records import NetsisRecord, VirmanRecord


class OutputQualityError(ValueError):
    """Aktarım dosyası üretilmeden önce bulunan zorunlu veri hatası."""


@dataclass(frozen=True)
class OutputQualityReport:
    checked_havale_rows: int = 0
    checked_virman_rows: int = 0

    @property
    def checked_total(self) -> int:
        return self.checked_havale_rows + self.checked_virman_rows


def validate_netsis_rows(
    rows: Iterable[NetsisRecord],
    profile: OutputProfile,
    region_config: RegionConfig,
    *,
    output_region: str,
    output_bank: str,
) -> int:
    """Netsis havale satırlarının bölge profiliyle tutarlı olduğunu doğrular."""
    count = 0
    needs_bank_code = requires_bank_account_code(profile)
    normalized_output_bank = bank_key(output_bank)
    for row_number, row in enumerate(rows, start=1):
        count += 1
        label = _row_label(output_region, output_bank, row_number)
        if not str(row.cari_kodu or "").strip():
            raise OutputQualityError(f"{label}: cari kod boş olamaz.")
        _require_positive_amount(row.tutar, label)
        _require_date(row.islem_tarihi, label)

        row_region = str(row.bolge or "").strip().upper()
        if row_region != str(output_region or "").strip().upper():
            raise OutputQualityError(
                f"{label}: satır bölgesi '{row.bolge}' çıktı bölgesiyle uyuşmuyor."
            )
        row_bank = bank_key(row.banka)
        if output_bank != "TOPLU" and row_bank != normalized_output_bank:
            raise OutputQualityError(
                f"{label}: satır bankası '{row.banka}' çıktı bankasıyla uyuşmuyor."
            )

        if not needs_bank_code:
            continue
        expected_code = region_config.banka_kodu(row_region, row_bank)
        actual_code = str(row.banka_hesap_kodu or "").strip().upper()
        if not expected_code:
            raise OutputQualityError(
                f"{label}: {row_region} / {row_bank} için BM banka hesap kodu tanımlı değil."
            )
        if not actual_code:
            raise OutputQualityError(f"{label}: BM banka hesap kodu boş olamaz.")
        if actual_code != str(expected_code).strip().upper():
            raise OutputQualityError(
                f"{label}: BM banka hesap kodu '{actual_code}', Ayarlar'daki "
                f"'{expected_code}' koduyla uyuşmuyor."
            )
    return count


def validate_virman_rows(
    rows: Iterable[VirmanRecord],
    region_config: RegionConfig,
) -> int:
    """Tek toplu virman dosyasının yalnız aynı banka transferi taşıdığını doğrular."""
    count = 0
    expected_ref = str(region_config.genel_ref_kodu() or "").strip().upper()
    expected_plasiyer = str(region_config.plasiyer_kodu() or "").strip()
    for row_number, row in enumerate(rows, start=1):
        count += 1
        label = f"Virman satırı {row_number}"
        _require_positive_amount(row.tutar, label)
        _require_date(row.islem_tarihi, label)
        if bank_key(row.kaynak_banka) != bank_key(row.hedef_banka):
            raise OutputQualityError(
                f"{label}: farklı bankalar arası transfer hesaplar arası virman şablonuna yazılamaz."
            )
        source_code = str(row.kaynak_banka_hesap_kodu or "").strip().upper()
        target_code = str(row.hedef_banka_hesap_kodu or "").strip().upper()
        if not source_code or not target_code:
            raise OutputQualityError(f"{label}: kaynak ve hedef BM banka kodları boş olamaz.")
        expected_source = region_config.banka_kodu(row.bolge, bank_key(row.kaynak_banka))
        if source_code != str(expected_source or "").strip().upper():
            raise OutputQualityError(
                f"{label}: kaynak BM kodu Ayarlar'daki bölge/banka koduyla uyuşmuyor."
            )
        if str(row.muh_ref_kodu or "").strip().upper() != expected_ref:
            raise OutputQualityError(f"{label}: Muh.Ref.Kod onaylı genel referans koduyla uyuşmuyor.")
        if str(row.plasiyer_kodu or "").strip() != expected_plasiyer:
            raise OutputQualityError(f"{label}: Plas.Kodu '{expected_plasiyer}' olmalı.")
    return count


def _require_positive_amount(value: object, label: str) -> None:
    try:
        amount = money(value)
    except ValueError as error:
        raise OutputQualityError(f"{label}: geçersiz tutar.") from error
    if amount <= 0:
        raise OutputQualityError(f"{label}: tutar sıfırdan büyük olmalı.")


def _require_date(value: object, label: str) -> None:
    if not isinstance(value, (date, datetime)):
        raise OutputQualityError(f"{label}: işlem tarihi boş veya geçersiz.")


def _row_label(region: str, bank: str, row_number: int) -> str:
    return f"{region} / {bank} çıktı satırı {row_number}"
