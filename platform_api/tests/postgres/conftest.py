"""Opt-in real PostgreSQL tests. Only disposable loopback servers are allowed."""
from dataclasses import replace
import os
import secrets
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from carpan_platform.config import Settings
from carpan_platform.security import hash_password
from scripts.migrate import apply_migrations


class SyntheticCase(SimpleNamespace):
    def __repr__(self):
        return "<isolated PostgreSQL test context; credentials omitted>"


@pytest.fixture(scope="session")
def pg_database():
    dsn = os.getenv("CARPAN_TEST_PG_ADMIN_DSN")
    if not dsn:
        if os.getenv("CARPAN_TEST_REQUIRE_POSTGRES") == "1":
            pytest.fail("Required PostgreSQL test connection is missing.")
        pytest.skip("Use the isolated PostgreSQL test runner to enable these tests.")
    info = conninfo_to_dict(dsn)
    if info.get("host") != "127.0.0.1" or info.get("dbname") != "postgres":
        pytest.fail("Tests require an explicitly selected disposable loopback server / postgres database.")
    if info.get("hostaddr", "127.0.0.1") != "127.0.0.1" or info.get("service"):
        pytest.fail("Remote addresses and service indirection are not allowed in database tests.")
    identifier = "carpan_test_" + uuid4().hex
    role = identifier + "_app"
    password = secrets.token_urlsafe(32)
    database_dsn = make_conninfo(dsn, dbname=identifier, connect_timeout=5)
    role_created = database_created = False
    with psycopg.connect(dsn, autocommit=True) as admin:
        try:
            admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS").format(sql.Identifier(role), sql.Literal(password)))
            role_created = True
            admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(identifier)))
            database_created = True
            apply_migrations(database_dsn)
            # A second run must preserve already-applied migrations.
            apply_migrations(database_dsn)
            with psycopg.connect(database_dsn) as owner:
                owner.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(identifier), sql.Identifier(role)))
                owner.execute(sql.SQL("GRANT USAGE ON SCHEMA carpan TO {}").format(sql.Identifier(role)))
                for table in ("companies", "users", "company_memberships", "licenses", "device_registrations", "refresh_tokens", "audit_events"):
                    owner.execute(sql.SQL("GRANT SELECT ON carpan.{} TO {}").format(sql.Identifier(table), sql.Identifier(role)))
                owner.execute(sql.SQL("GRANT UPDATE(failed_attempts, locked_until, last_login_at) ON carpan.users TO {}").format(sql.Identifier(role)))
                owner.execute(sql.SQL("GRANT INSERT, UPDATE ON carpan.licenses, carpan.refresh_tokens TO {}").format(sql.Identifier(role)))
                owner.execute(sql.SQL("GRANT INSERT ON carpan.audit_events TO {}").format(sql.Identifier(role)))
                owner.execute(sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA carpan TO {}").format(sql.Identifier(role)))
                owner.execute(sql.SQL("GRANT EXECUTE ON FUNCTION carpan.resolve_company_code(text), carpan.consume_refresh_token(character) TO {}").format(sql.Identifier(role)))
            settings = Settings("test", make_conninfo(database_dsn, user=role, password=password,
                               options="-c statement_timeout=15000 -c lock_timeout=10000"), None, "carpan-test", ())
            yield SyntheticCase(owner_dsn=database_dsn, settings=settings, role=role)
        finally:
            # These names are generated here, never taken from a user database.
            if database_created:
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(identifier)))
            if role_created:
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


@pytest.fixture
def pg_case(pg_database):
    firms = [uuid4(), uuid4()]
    users = [uuid4(), uuid4()]
    codes = ["TEST_" + uuid4().hex, "TEST_" + uuid4().hex]
    usernames = ["user_" + uuid4().hex, "user_" + uuid4().hex]
    password = "Synthetic-Only-" + secrets.token_urlsafe(20)
    with psycopg.connect(pg_database.owner_dsn) as conn:
        for company, user, code, username in zip(firms, users, codes, usernames):
            conn.execute("INSERT INTO carpan.companies(id, code, name) VALUES (%s, %s, 'Synthetic test company')", (company, code))
            conn.execute("INSERT INTO carpan.users(id, username, display_name, password_hash) VALUES (%s, %s, 'Synthetic test user', %s)", (user, username, hash_password(password)))
            conn.execute("INSERT INTO carpan.company_memberships(company_id, user_id, role) VALUES (%s, %s, 'ADMIN')", (company, user))
            conn.execute("INSERT INTO carpan.licenses(company_id, plan_code) VALUES (%s, 'TEST')", (company,))
    return SyntheticCase(database=pg_database, settings=replace(pg_database.settings), firms=firms, users=users, codes=codes, usernames=usernames, password=password)
