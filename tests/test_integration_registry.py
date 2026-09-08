import pytest

from app.integrations.contracts import (
    IntegrationCategory,
    IntegrationManifest,
    IntegrationMaturity,
    IntegrationTransport,
)
from app.integrations.registry import (
    IntegrationRegistry,
    IntegrationRegistryError,
    build_default_integration_registry,
)


def test_default_integrations_describe_current_local_data_boundaries():
    registry = build_default_integration_registry()

    netsis = registry.get("netsis_approved_export")
    assert netsis.category == IntegrationCategory.ACCOUNTING
    assert netsis.transport == IntegrationTransport.LOCAL_FILE
    assert netsis.maturity == IntegrationMaturity.ACTIVE
    assert netsis.supports("accounting.payment_export")
    assert "merkezi platforma finansal veri gönderilmez" in netsis.data_boundary
    assert [item.integration_id for item in registry.supporting("report.collection_export")] == [
        "psoft_fom_approved_export"
    ]


def test_registry_rejects_duplicate_integration_identity():
    item = IntegrationManifest(
        integration_id="test",
        name="Test",
        category=IntegrationCategory.BANKING,
        transport=IntegrationTransport.LOCAL_FILE,
        maturity=IntegrationMaturity.PLANNED,
        capabilities=frozenset(),
        description="Test bağlantısı",
        data_boundary="Yerel",
    )
    registry = IntegrationRegistry([item])

    with pytest.raises(IntegrationRegistryError):
        registry.register(item)
