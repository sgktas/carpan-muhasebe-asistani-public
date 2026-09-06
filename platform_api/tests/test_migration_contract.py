from pathlib import Path


def test_initial_migration_has_tenant_and_audit_contracts():
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "0001_platform_core.sql"
    ).read_text(encoding="utf-8")

    for table in (
        "carpan.companies",
        "carpan.users",
        "carpan.company_memberships",
        "carpan.licenses",
        "carpan.device_registrations",
        "carpan.refresh_tokens",
        "carpan.audit_events",
    ):
        assert table in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "app.company_id" in migration
