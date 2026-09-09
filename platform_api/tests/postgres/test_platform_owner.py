from dataclasses import replace
from uuid import uuid4

import psycopg

from carpan_platform.platform_owner import PlatformOwnerRepository
from carpan_platform.security import hash_password


def _repository(pg_database):
    settings = replace(pg_database.settings, owner_database_url=pg_database.owner_dsn)
    operator_id = uuid4()
    with psycopg.connect(pg_database.owner_dsn) as connection:
        connection.execute(
            "INSERT INTO carpan.users(id, username, display_name, password_hash) VALUES (%s, %s, 'Platform owner', %s)",
            (operator_id, "platform_owner_" + uuid4().hex, hash_password("Synthetic-Only-1-Platform")),
        )
        connection.execute("INSERT INTO carpan.platform_operators(user_id) VALUES (%s)", (operator_id,))
    return PlatformOwnerRepository(settings), operator_id


def test_platform_owner_provisions_company_license_and_invitation_atomically(pg_database):
    repository, operator_id = _repository(pg_database)

    provisioned = repository.provision_company(
        actor_user_id=operator_id,
        code="DEMO_OWNER",
        name="Demo owner company",
        admin_username="demo.owner.admin",
        admin_display_name="Demo owner admin",
        plan_code="PRO",
        license_status="TRIAL",
        module_ids=["manim_transfer", "report_editing"],
    )

    assert provisioned.company.code == "DEMO_OWNER"
    assert len(provisioned.invitation_token) >= 40
    with psycopg.connect(pg_database.owner_dsn) as connection:
        company = connection.execute("SELECT id FROM carpan.companies WHERE code='DEMO_OWNER'").fetchone()
        license_row = connection.execute(
            "SELECT plan_code, status, module_entitlements FROM carpan.licenses WHERE company_id=%s", (company[0],)
        ).fetchone()
        invitation = connection.execute(
            "SELECT role, created_by_user_id FROM carpan.user_invitations WHERE company_id=%s", (company[0],)
        ).fetchone()
        user = connection.execute("SELECT 1 FROM carpan.users WHERE username='demo.owner.admin'").fetchone()
    assert license_row == ("PRO", "TRIAL", ["manim_transfer", "report_editing"])
    assert invitation == ("ADMIN", operator_id)
    assert user is None


def test_platform_owner_updates_only_target_company_license(pg_database):
    repository, operator_id = _repository(pg_database)
    repository.provision_company(
        actor_user_id=operator_id,
        code="DEMO_LICENSE",
        name="Demo license company",
        admin_username="demo.license.admin",
        admin_display_name="Demo license admin",
        plan_code="TRIAL",
        license_status="TRIAL",
        module_ids=[],
    )

    repository.update_license(
        actor_user_id=operator_id,
        company_code="DEMO_LICENSE",
        plan_code="PRO",
        license_status="ACTIVE",
        module_ids=["manim_transfer"],
        enforce_central=True,
        offline_grace_hours=48,
    )

    with psycopg.connect(pg_database.owner_dsn) as connection:
        row = connection.execute(
            """
            SELECT l.plan_code, l.status, l.module_entitlements, l.enforce_central, l.offline_grace_hours
            FROM carpan.licenses l JOIN carpan.companies c ON c.id=l.company_id
            WHERE c.code='DEMO_LICENSE'
            """
        ).fetchone()
    assert row == ("PRO", "ACTIVE", ["manim_transfer"], True, 48)
