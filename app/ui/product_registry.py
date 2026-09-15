"""Presentation-only product navigation registry for the new Çarpan shell."""
from __future__ import annotations

from dataclasses import dataclass


ACTIVE = "ACTIVE"
LOCKED = "LOCKED"
UNCONFIGURED = "UNCONFIGURED"
COMING_SOON = "COMING_SOON"


@dataclass(frozen=True)
class ProductModule:
    module_id: str
    display_name: str
    group: str
    order: int
    icon_name: str
    default_state: str
    description: str
    legacy_target: str | None = None
    capability: str | None = None


PRODUCT_MODULES = (
    ProductModule("dashboard", "Ana Kontrol", "ANA KONTROL", 10, "history", ACTIVE,
                  "Çalışma alanındaki modüllere ve yerel operasyonlara erişin."),
    ProductModule("accounting_automation", "Muhasebe Otomasyonu", "MUHASEBE", 20, "transfer", ACTIVE,
                  "Kaynakları sınıflandırın, kuralları uygulayın ve belirsiz kayıtları inceleyin."),
    ProductModule("tax_automation", "Vergi Otomasyonu", "VERGİ", 30, "report", COMING_SOON,
                  "Aylık vergi çalışma alanı ürün planına göre açılacaktır."),
    ProductModule("banking", "Bankalar", "FİNANS MODÜLLERİ", 40, "folder", UNCONFIGURED,
                  "Banka bağlantısı yapılandırılmadı. Dosya tabanlı kaynaklar Muhasebe Otomasyonu içinden kullanılabilir."),
    ProductModule("einvoice", "E-Fatura", "FİNANS MODÜLLERİ", 50, "report", LOCKED,
                  "E-Fatura bağlantısı için ek modül gerekir."),
    ProductModule("reconciliation", "Mutabakat", "FİNANS MODÜLLERİ", 60, "folder", ACTIVE,
                  "Banka ve cari mutabakat araçlarını açın."),
    ProductModule("integrations", "Entegrasyonlar", "PLATFORM", 70, "settings", ACTIVE,
                  "Yerel çıktı adaptörlerinin ve gelecekteki bağlantıların durumunu inceleyin.", "integrations", "settings.manage"),
    ProductModule("operations", "Operasyon Merkezi", "PLATFORM", 80, "history", ACTIVE,
                  "İşlem durumu, inceleme ve kurtarma görünümünü takip edin.", "operations_center", "history.read"),
    ProductModule("reports", "Raporlar", "PLATFORM", 90, "report", ACTIVE,
                  "Rapor standardizasyonu ve çıktı hazırlama araçlarını açın."),
    ProductModule("settings", "Ayarlar", "YÖNETİM", 100, "settings", ACTIVE,
                  "Çalışma alanı, profil ve onaylı şablon ayarlarını yönetin.", "settings", "settings.manage"),
)


def grouped_product_modules() -> tuple[tuple[str, tuple[ProductModule, ...]], ...]:
    groups: dict[str, list[ProductModule]] = {}
    for module in PRODUCT_MODULES:
        groups.setdefault(module.group, []).append(module)
    return tuple(
        (group, tuple(sorted(items, key=lambda item: item.order)))
        for group, items in groups.items()
    )
