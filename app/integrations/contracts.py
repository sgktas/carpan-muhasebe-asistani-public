from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IntegrationCategory(StrEnum):
    ACCOUNTING = "MUHASEBE / ERP"
    BANKING = "BANKACILIK"
    REPORTING = "RAPORLAMA"


class IntegrationTransport(StrEnum):
    LOCAL_FILE = "Yerel onaylı dosya"
    SECURE_API = "Güvenli API"
    OPEN_BANKING = "Açık bankacılık"


class IntegrationMaturity(StrEnum):
    ACTIVE = "Kullanıma hazır"
    PLANNED = "Planlanıyor"


@dataclass(frozen=True)
class IntegrationManifest:
    """Bir dış sistem bağlantısının ürün ve güvenlik sözleşmesi.

    Bu tanım bağlantı sırrı, banka hareketi veya müşteri verisi taşımaz. Sadece
    hangi sistemle ne tür bir entegrasyon kurulduğunu bildirir.
    """

    integration_id: str
    name: str
    category: IntegrationCategory
    transport: IntegrationTransport
    maturity: IntegrationMaturity
    capabilities: frozenset[str]
    description: str
    data_boundary: str
    operation_module_ids: frozenset[str] = frozenset()
    acceptance_system: str | None = None

    def supports(self, capability: str) -> bool:
        return str(capability).strip() in self.capabilities
