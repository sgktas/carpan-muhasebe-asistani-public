from __future__ import annotations

from collections import defaultdict

from app.core.region_config import RegionConfig
from app.core.text_keys import bank_key, compact_key, customer_code_key, normalized_words
from app.models.records import CustomerRecord, ManimRecord


class ManimRegionResolver:
    """MANİM satırının bölgesini kesin kanıt önceliğiyle belirler."""

    def __init__(self, region_config: RegionConfig, regions: tuple[str, ...]):
        self.region_config = region_config
        self.regions = regions

    def from_file_name(self, name: str) -> str:
        normalized = normalized_words(name)
        for region in self.regions:
            if region in normalized:
                return region
        return "BILINMEYEN_BOLGE"

    def for_record(
        self,
        record: ManimRecord,
        file_region: str,
        customer_region_by_code: dict[str, str] | None = None,
        customer_region_by_name: dict[str, str] | None = None,
    ) -> str:
        account_region = self.region_config.find_region_by_manim_account(
            bank_key(record.banka),
            record.sube,
        )
        if account_region:
            return account_region

        code = customer_code_key(record.karsi_hesap_kodu)
        if code and customer_region_by_code:
            code_region = customer_region_by_code.get(code)
            if code_region:
                return code_region

        name = compact_key(record.karsi_hesap_adi)
        if name and customer_region_by_name:
            name_region = customer_region_by_name.get(name)
            if name_region:
                return name_region

        return file_region

    def customer_indexes(
        self,
        customers: list[CustomerRecord],
    ) -> tuple[dict[str, str], dict[str, str]]:
        regions_by_code: dict[str, set[str]] = defaultdict(set)
        regions_by_name: dict[str, set[str]] = defaultdict(set)

        for customer in customers:
            region = self.region_config.find_region_in_text(customer.sube)
            if not region:
                continue
            code = customer_code_key(customer.cari_kodu)
            if code:
                regions_by_code[code].add(region)
            for value in (customer.unvan, customer.tabela_adi):
                name = compact_key(value)
                if name:
                    regions_by_name[name].add(region)

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
