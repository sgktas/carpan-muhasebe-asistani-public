from __future__ import annotations

from collections.abc import Iterable

from app.integrations.contracts import (
    IntegrationCategory,
    IntegrationManifest,
    IntegrationMaturity,
    IntegrationTransport,
)


class IntegrationRegistryError(ValueError):
    pass


class IntegrationRegistry:
    """Entegrasyonların tek kayıt noktası.

    Yeni banka, ERP veya açık bankacılık sağlayıcısı yalnız bu kayıt defteri ve
    kendi adaptörü üzerinden eklenir. Böylece iş kuralları modül içine dağılmaz.
    """

    def __init__(self, integrations: Iterable[IntegrationManifest] = ()): 
        self._items: dict[str, IntegrationManifest] = {}
        for integration in integrations:
            self.register(integration)

    def register(self, integration: IntegrationManifest) -> None:
        integration_id = str(integration.integration_id).strip()
        if not integration_id:
            raise IntegrationRegistryError("Entegrasyon kimliği boş olamaz.")
        if integration_id in self._items:
            raise IntegrationRegistryError(f"Entegrasyon zaten kayıtlı: {integration_id}")
        self._items[integration_id] = integration

    def all(self) -> tuple[IntegrationManifest, ...]:
        return tuple(sorted(self._items.values(), key=lambda item: (item.category, item.name)))

    def get(self, integration_id: str) -> IntegrationManifest:
        try:
            return self._items[str(integration_id).strip()]
        except KeyError as error:
            raise IntegrationRegistryError("Entegrasyon bulunamadı.") from error

    def supporting(self, capability: str) -> tuple[IntegrationManifest, ...]:
        return tuple(item for item in self.all() if item.supports(capability))


def build_default_integration_registry() -> IntegrationRegistry:
    """Bugün çalışan dosya tabanlı adaptörleri merkezi listede toplar.

    Bu kayıtlar onaylı şablonlara işaret eder fakat şablonu değiştirmez veya
    kopyalamaz. Canlı banka/API adaptörleri ileride ayrı güvenli uygulamalar
    olarak eklenecektir.
    """
    return IntegrationRegistry(
        (
            IntegrationManifest(
                integration_id="netsis_approved_export",
                name="Netsis Aktarım",
                category=IntegrationCategory.ACCOUNTING,
                transport=IntegrationTransport.LOCAL_FILE,
                maturity=IntegrationMaturity.ACTIVE,
                capabilities=frozenset({"accounting.payment_export", "accounting.transfer_export"}),
                description="MANİM hareketlerini onaylı Netsis şablonlarıyla aktarım dosyasına hazırlar.",
                data_boundary="Excel çıktısı bilgisayarda oluşturulur; merkezi platforma finansal veri gönderilmez.",
                operation_module_ids=frozenset({"manim_transfer"}),
                acceptance_system="NETSIS",
            ),
            IntegrationManifest(
                integration_id="psoft_fom_approved_export",
                name="Psoft / FOM Aktarım",
                category=IntegrationCategory.REPORTING,
                transport=IntegrationTransport.LOCAL_FILE,
                maturity=IntegrationMaturity.ACTIVE,
                capabilities=frozenset({"report.sales_export", "report.collection_export"}),
                description="Satış ve tahsilat raporlarını onaylı FOM entegrasyon şablonlarıyla hazırlar.",
                data_boundary="Excel çıktısı bilgisayarda oluşturulur; merkezi platforma finansal veri gönderilmez.",
                operation_module_ids=frozenset({"report_editing"}),
                acceptance_system="PSOFT",
            ),
            IntegrationManifest(
                integration_id="bank_statement_file_import",
                name="Banka Ekstresi Dosya İçe Aktarımı",
                category=IntegrationCategory.BANKING,
                transport=IntegrationTransport.LOCAL_FILE,
                maturity=IntegrationMaturity.ACTIVE,
                capabilities=frozenset({"bank.statement_import", "bank.reconciliation_input"}),
                description="Banka hareket raporlarını yerel olarak tanır ve mutabakat/aktarım akışına alır.",
                data_boundary="Banka dosyası yalnız kullanıcının bilgisayarında işlenir.",
            ),
        )
    )
