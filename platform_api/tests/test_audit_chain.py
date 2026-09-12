from datetime import datetime, timezone
import hashlib

from carpan_platform.audit_chain import (
    GENESIS_HASH,
    verify_company_audit_chains,
    verify_platform_audit_chain,
)


def _row(*, event_id, previous_hash, company_id="company-a", event_type="LOGIN", outcome="SUCCESS", event_data=None):
    return {
        "id": event_id,
        "company_id": company_id,
        "actor_user_id": "user-a",
        "event_type": event_type,
        "outcome": outcome,
        "event_data": event_data or {"role": "ADMIN"},
        "previous_hash": previous_hash,
        "event_hash": "",
        "created_at": datetime(2026, 9, 12, 9, 0, event_id, tzinfo=timezone.utc),
    }


def _signed(rows, *, company_scoped):
    # Importing the internal canonical calculator avoids duplicating production
    # hash formatting in this test fixture while still exercising verification.
    from carpan_platform.audit_chain import _event_hash

    previous = GENESIS_HASH
    for row in rows:
        row["previous_hash"] = previous
        row["event_hash"] = _event_hash(row, previous_hash=previous, include_company_id=company_scoped)
        previous = row["event_hash"]
    return rows


def test_company_audit_chains_are_verified_per_company():
    company_a = _signed([_row(event_id=1, previous_hash=""), _row(event_id=2, previous_hash="")], company_scoped=True)
    company_b = _signed([_row(event_id=3, previous_hash="", company_id="company-b")], company_scoped=True)

    results = verify_company_audit_chains([*company_a, *company_b])

    assert [(result.chain_name, result.valid, result.event_count) for result in results] == [
        ("firma:company-a", True, 2), ("firma:company-b", True, 1)
    ]


def test_audit_verification_detects_changed_event_data():
    rows = _signed([_row(event_id=1, previous_hash=""), _row(event_id=2, previous_hash="")], company_scoped=True)
    rows[1]["event_data"] = {"role": "AUDITOR"}

    result = verify_company_audit_chains(rows)[0]

    assert result.valid is False
    assert result.invalid_event_id == 2


def test_platform_audit_verification_detects_a_removed_or_relinked_event():
    rows = _signed([_row(event_id=1, previous_hash=""), _row(event_id=2, previous_hash="")], company_scoped=False)
    rows[1]["previous_hash"] = hashlib.sha256(b"wrong").hexdigest()

    result = verify_platform_audit_chain(rows)

    assert result.valid is False
    assert result.invalid_event_id == 2
