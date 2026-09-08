"""Transaction-boundary regressions; does not replace real PostgreSQL tests."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from carpan_platform import identity_repository as identity


COMPANY = UUID(int=1)
USER = UUID(int=2)


@pytest.fixture
def harness(monkeypatch):
    state = SimpleNamespace(
        row={"user_id": USER, "username": "test", "display_name": "Test",
             "password_hash": "synthetic", "user_status": "ACTIVE",
             "failed_attempts": 0, "locked_until": None,
             "role": "ADMIN", "membership_active": True},
        committed=[], pending=[], queries=[], valid=False,
    )

    class Connection:
        def execute(self, sql, params):
            state.queries.append(sql)
            if "SELECT" in sql:
                return SimpleNamespace(fetchone=lambda: state.row)
            state.pending.append((sql, params))

    @contextmanager
    def transaction(*_args):
        state.pending = []
        try:
            yield Connection()
        except Exception:
            state.pending = []
            raise
        else:
            state.committed.extend(state.pending)

    monkeypatch.setattr(identity, "tenant_transaction", transaction)
    monkeypatch.setattr(identity, "verify_password", lambda *_args: state.valid)
    repository = identity.CentralIdentityRepository(SimpleNamespace())
    monkeypatch.setattr(repository, "_resolve_company_id", lambda _: COMPANY)
    monkeypatch.setattr(repository, "_append_audit", lambda connection, **event: state.pending.append(event))
    state.repository = repository
    return state


def authenticate(state):
    return state.repository.authenticate(company_code="TEST", username="test", password="synthetic")


@pytest.mark.parametrize("case", ["unknown", "wrong_password", "locked"])
def test_rejected_login_commits_audit_before_raising(harness, case):
    if case == "unknown":
        harness.row = None
    elif case == "locked":
        harness.row["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=5)
    with pytest.raises(identity.LoginRejected):
        authenticate(harness)
    events = [entry for entry in harness.committed if isinstance(entry, dict)]
    assert len(events) == 1
    assert events[0]["outcome"] == ("BLOCKED" if case == "locked" else "FAILED")


def test_fifth_failed_attempt_commits_lock(harness):
    harness.row["failed_attempts"] = 4
    with pytest.raises(identity.LoginRejected):
        authenticate(harness)
    updates = [entry for entry in harness.committed if isinstance(entry, tuple)]
    assert len(updates) == 1
    attempts, locked_until, user_id = updates[0][1]
    assert attempts == 0
    assert locked_until > datetime.now(timezone.utc)
    assert user_id == USER


def test_authentication_serializes_user_counter_updates(harness):
    harness.valid = True
    assert authenticate(harness)["user_id"] == USER
    assert "FOR UPDATE OF u" in harness.queries[0]
    assert any(isinstance(entry, dict) and entry["outcome"] == "SUCCESS" for entry in harness.committed)


def test_unexpected_failure_rolls_back(harness, monkeypatch):
    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("synthetic storage failure")
    monkeypatch.setattr(harness.repository, "_append_audit", fail_audit)
    with pytest.raises(RuntimeError):
        authenticate(harness)
    assert not harness.committed
