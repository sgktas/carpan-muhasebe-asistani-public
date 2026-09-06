import sqlite3

import pytest

from app.core import identity
from app.core.identity import (
    AuthenticatedSession,
    AuthenticationError,
    IdentityError,
    IdentityStore,
)


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    monkeypatch.setattr(identity, "PASSWORD_ITERATIONS", 1_000)


def _create_admin(store: IdentityStore) -> AuthenticatedSession:
    return store.create_initial_admin(
        company_name="Çarpan Test",
        username="admin",
        display_name="Test Yönetici",
        password="Guvenli1234",
    )


def test_initial_setup_creates_real_admin_and_hashed_password(tmp_path):
    database = tmp_path / "platform.sqlite3"
    store = IdentityStore(database)
    assert store.needs_initial_setup()

    session = _create_admin(store)

    assert not store.needs_initial_setup()
    assert session.role == "ADMIN"
    assert session.can("users.manage")
    assert session.allows_module("manim_transfer")
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT password_hash, password_salt FROM users WHERE id = ?",
            (session.user_id,),
        ).fetchone()
    assert bytes(row[0]) != b"Guvenli1234"
    assert len(bytes(row[1])) == 32
    assert store.audit_chain_is_valid()


def test_authentication_and_failed_login_audit(tmp_path):
    store = IdentityStore(tmp_path / "platform.sqlite3")
    admin = _create_admin(store)

    with pytest.raises(AuthenticationError, match="Kullanıcı adı"):
        store.authenticate("admin", "yanlis", admin.company_id)

    logged_in = store.authenticate("ADMIN", "Guvenli1234", admin.company_id)
    assert logged_in.user_id == admin.user_id
    assert logged_in.company_name == "Çarpan Test"
    assert store.audit_chain_is_valid()


def test_account_is_temporarily_locked_after_repeated_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "MAX_FAILED_ATTEMPTS", 2)
    store = IdentityStore(tmp_path / "platform.sqlite3")
    admin = _create_admin(store)

    for _ in range(2):
        with pytest.raises(AuthenticationError, match="Kullanıcı adı"):
            store.authenticate("admin", "yanlis", admin.company_id)

    with pytest.raises(AuthenticationError, match="geçici olarak kilitli"):
        store.authenticate("admin", "Guvenli1234", admin.company_id)


def test_admin_can_create_and_manage_role_scoped_user(tmp_path):
    store = IdentityStore(tmp_path / "platform.sqlite3")
    admin = _create_admin(store)
    user_id = store.create_user(
        admin,
        username="operator",
        display_name="Muhasebe Uzmanı",
        password="Operator1234",
        role="OPERATOR",
    )

    operator = store.authenticate("operator", "Operator1234", admin.company_id)
    assert operator.allows_module("bank_reconciliation")
    assert not operator.can("users.manage")
    with pytest.raises(IdentityError, match="yönetici"):
        store.create_user(
            operator,
            username="yetkisiz",
            display_name="Yetkisiz Kullanıcı",
            password="Yetkisiz1234",
            role="AUDITOR",
        )

    store.update_member(admin, user_id, role="AUDITOR", active=True)
    auditor = store.authenticate("operator", "Operator1234", admin.company_id)
    assert auditor.can("audit.read")
    assert not auditor.allows_module("manim_transfer")
    assert store.audit_events(auditor)[0].action == "LOGIN"

    with pytest.raises(IdentityError, match="denetim yetkisi"):
        store.audit_events(operator)


def test_admin_cannot_remove_own_admin_access(tmp_path):
    store = IdentityStore(tmp_path / "platform.sqlite3")
    admin = _create_admin(store)

    with pytest.raises(IdentityError, match="Kendi yönetici"):
        store.update_member(admin, admin.user_id, role="OPERATOR", active=True)


def test_audit_chain_detects_database_tampering(tmp_path):
    database = tmp_path / "platform.sqlite3"
    store = IdentityStore(database)
    _create_admin(store)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE security_audit_events SET outcome = 'CHANGED' WHERE id = 1"
        )

    assert not store.audit_chain_is_valid()
