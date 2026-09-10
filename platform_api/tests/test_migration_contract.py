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
    assert "carpan.resolve_company_code" in migration


def test_refresh_rotation_migration_consumes_each_token_once():
    migration = (Path(__file__).resolve().parents[1] / "migrations" / "0002_refresh_session_rotation.sql").read_text(encoding="utf-8")
    assert "carpan.consume_refresh_token" in migration
    assert "SECURITY DEFINER" in migration
    assert "FOR UPDATE OF t" in migration
    assert "SET revoked_at = now()" in migration


def test_users_migration_scopes_global_identities_by_company_membership():
    migration = (Path(__file__).resolve().parents[1] / "migrations" / "0003_users_tenant_scope.sql").read_text(encoding="utf-8")
    assert "ALTER TABLE carpan.users ENABLE ROW LEVEL SECURITY" in migration
    assert "m.user_id = users.id" in migration
    assert "WITH CHECK" in migration


def test_atomic_refresh_rotation_migration_replaces_token_in_one_transaction():
    migration = (Path(__file__).resolve().parents[1] / "migrations" / "0004_atomic_refresh_rotation.sql").read_text(encoding="utf-8")
    assert "carpan.rotate_refresh_token" in migration
    assert "INSERT INTO carpan.refresh_tokens" in migration
    assert "UPDATE carpan.refresh_tokens" in migration
    assert "SECURITY DEFINER" in migration


def test_platform_operator_migration_is_separate_from_company_scope():
    migration = (Path(__file__).resolve().parents[1] / "migrations" / "0008_platform_operators.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS carpan.platform_operators" in migration
    assert "CREATE TABLE IF NOT EXISTS carpan.platform_audit_events" in migration
    assert "ALTER TABLE carpan.platform_operators ENABLE ROW LEVEL SECURITY" in migration


def test_platform_audit_context_migration_stays_data_minimum():
    migration = (Path(__file__).resolve().parents[1] / "migrations" / "0009_platform_audit_context.sql").read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS event_data JSONB" in migration
    assert "müşteri, banka, IBAN, Excel veya finansal" in migration


def test_nginx_examples_keep_rate_limits_outside_application_memory():
    deploy_root = Path(__file__).resolve().parents[1] / "deploy" / "nginx"
    zone_config = (deploy_root / "carpan-platform-rate-limit.conf.example").read_text(encoding="utf-8")
    server_config = (deploy_root / "carpan-platform.conf.example").read_text(encoding="utf-8")

    assert "limit_req_zone $binary_remote_addr zone=carpan_auth:10m rate=10r/m;" in zone_config
    assert "location ~ ^/v1/(auth/login|platform/auth/login)$" in server_config
    assert "limit_req zone=carpan_auth burst=5 nodelay;" in server_config
    assert "limit_req_status 429;" in server_config
    assert "location ^~ /v1/" not in server_config


def test_platform_audit_chain_is_added_in_a_new_immutable_migration():
    migration = (Path(__file__).resolve().parents[1] / "migrations" / "0010_platform_audit_chain.sql").read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS previous_hash CHAR(64)" in migration
    assert "ADD COLUMN IF NOT EXISTS event_hash CHAR(64)" in migration
    assert "pg_advisory_xact_lock" not in migration
    assert "idx_platform_audit_events_hash" in migration
