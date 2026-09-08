from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest

from carpan_platform.database import tenant_transaction
from carpan_platform.identity_repository import CentralIdentityRepository, LoginRejected


def login(case, password=None, username=None):
    return CentralIdentityRepository(case.settings).authenticate(
        company_code=case.codes[0], username=username or case.usernames[0],
        password=password if password is not None else case.password,
    )


def audit(case):
    with tenant_transaction(case.settings, case.firms[0]) as conn:
        return conn.execute("SELECT outcome, previous_hash, event_hash FROM carpan.audit_events ORDER BY id").fetchall()


def test_runtime_role_cannot_bypass_rls(pg_case):
    with psycopg.connect(pg_case.settings.database_url) as conn:
        assert conn.execute("SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user").fetchone() == (False, False, False, False)
        assert conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'carpan' AND tableowner = current_user").fetchone()[0] == 0


@pytest.mark.parametrize("table", ["companies", "company_memberships", "licenses", "users"])
def test_missing_tenant_has_no_visible_rows(pg_case, table):
    with psycopg.connect(pg_case.settings.database_url) as conn:
        assert conn.execute(psycopg.sql.SQL("SELECT count(*) FROM carpan.{}").format(psycopg.sql.Identifier(table))).fetchone()[0] == 0


def test_users_and_licenses_are_firm_scoped(pg_case):
    with tenant_transaction(pg_case.settings, pg_case.firms[0]) as conn:
        assert [r["id"] for r in conn.execute("SELECT id FROM carpan.users").fetchall()] == [pg_case.users[0]]
        assert conn.execute("UPDATE carpan.users SET failed_attempts = 4 WHERE id = %s", (pg_case.users[1],)).rowcount == 0
        assert conn.execute("UPDATE carpan.licenses SET plan_code = 'WRONG' WHERE company_id = %s", (pg_case.firms[1],)).rowcount == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with tenant_transaction(pg_case.settings, pg_case.firms[0]) as conn:
            conn.execute("INSERT INTO carpan.licenses(company_id, plan_code) VALUES (%s, 'WRONG')", (pg_case.firms[1],))


def test_failed_login_and_unknown_user_audit_persist(pg_case):
    for kwargs in ({"password": "incorrect"}, {"username": "does-not-exist"}):
        with pytest.raises(LoginRejected):
            login(pg_case, **kwargs)
    with tenant_transaction(pg_case.settings, pg_case.firms[0]) as conn:
        assert conn.execute("SELECT failed_attempts FROM carpan.users WHERE id = %s", (pg_case.users[0],)).fetchone()["failed_attempts"] == 1
    assert [r["outcome"] for r in audit(pg_case)] == ["FAILED", "FAILED"]


def test_five_attempts_lock_even_valid_password_then_expiry_allows_login(pg_case):
    for _ in range(5):
        with pytest.raises(LoginRejected):
            login(pg_case, password="incorrect")
    with pytest.raises(LoginRejected):
        login(pg_case)
    assert [r["outcome"] for r in audit(pg_case)] == ["FAILED"] * 5 + ["BLOCKED"]
    with psycopg.connect(pg_case.database.owner_dsn) as conn:
        conn.execute("UPDATE carpan.users SET locked_until = now() - interval '1 second' WHERE id = %s", (pg_case.users[0],))
    assert login(pg_case)["user_id"] == pg_case.users[0]
    with tenant_transaction(pg_case.settings, pg_case.firms[0]) as conn:
        row = conn.execute("SELECT failed_attempts, locked_until FROM carpan.users WHERE id = %s", (pg_case.users[0],)).fetchone()
        assert row == {"failed_attempts": 0, "locked_until": None}


def test_parallel_failed_attempts_do_not_lose_counts_or_fork_audit(pg_case):
    barrier = Barrier(8)
    def attempt(_):
        barrier.wait(timeout=15)
        with pytest.raises(LoginRejected):
            login(pg_case, password="incorrect")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(attempt, range(8)))
    events = audit(pg_case)
    assert [e["outcome"] for e in events] == ["FAILED"] * 5 + ["BLOCKED"] * 3
    previous = "0" * 64
    for event in events:
        assert event["previous_hash"] == previous
        previous = event["event_hash"]


def test_wrong_company_cannot_authenticate_other_company_user(pg_case):
    with pytest.raises(LoginRejected):
        login(pg_case, username=pg_case.usernames[1])


def test_exception_rolls_back_tenant_changes(pg_case):
    with pytest.raises(RuntimeError):
        with tenant_transaction(pg_case.settings, pg_case.firms[0]) as conn:
            conn.execute("UPDATE carpan.licenses SET plan_code = 'ROLLBACK'")
            raise RuntimeError("synthetic failure")
    with tenant_transaction(pg_case.settings, pg_case.firms[0]) as conn:
        assert conn.execute("SELECT plan_code FROM carpan.licenses").fetchone()["plan_code"] == "TEST"


@pytest.mark.parametrize("table", ["company_memberships", "device_registrations", "refresh_tokens", "audit_events"])
def test_other_tenant_operational_rows_are_not_visible(pg_case, table):
    other_company, other_user = pg_case.firms[1], pg_case.users[1]
    with psycopg.connect(pg_case.database.owner_dsn) as owner:
        owner.execute("INSERT INTO carpan.device_registrations(company_id,user_id,device_fingerprint_hash) VALUES (%s,%s,%s)", (other_company, other_user, uuid4().hex * 2))
        owner.execute("INSERT INTO carpan.refresh_tokens(company_id,user_id,token_hash,expires_at) VALUES (%s,%s,%s,now()+interval '1 hour')", (other_company, other_user, uuid4().hex * 2))
        owner.execute("INSERT INTO carpan.audit_events(company_id,actor_user_id,event_type,outcome,previous_hash,event_hash) VALUES (%s,%s,'TEST','SUCCESS',%s,%s)", (other_company, other_user, "0"*64, uuid4().hex * 2))
    query = psycopg.sql.SQL("SELECT company_id FROM carpan.{} WHERE company_id = %s").format(psycopg.sql.Identifier(table))
    with tenant_transaction(pg_case.settings, pg_case.firms[0]) as conn:
        assert conn.execute(query, (other_company,)).fetchall() == []
    with tenant_transaction(pg_case.settings, other_company) as conn:
        assert len(conn.execute(query, (other_company,)).fetchall()) == 1


def test_runtime_role_cannot_modify_schema(pg_case):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with psycopg.connect(pg_case.settings.database_url) as conn:
            conn.execute("CREATE TABLE carpan.forbidden_test_table(id int)")


def test_refresh_token_can_be_consumed_only_once_in_parallel(pg_case):
    repository = CentralIdentityRepository(pg_case.settings)
    token = repository.create_refresh_session(company_id=pg_case.firms[0], user_id=pg_case.users[0])
    barrier = Barrier(2)
    def consume(_):
        barrier.wait(timeout=15)
        try:
            return repository.rotate_refresh_session(token)["user_id"]
        except LoginRejected:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, range(2)))
    assert results.count(pg_case.users[0]) == 1
    assert results.count(None) == 1
