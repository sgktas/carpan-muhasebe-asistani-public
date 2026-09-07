from datetime import datetime, timedelta, timezone

import pytest

from carpan_platform.licensing import (
    LicenseSnapshot,
    installation_hash,
    normalize_module_entitlements,
)


def test_module_entitlements_are_normalized_without_duplicates():
    assert normalize_module_entitlements(["manim_transfer", " report_editing ", "manim_transfer", 1]) == (
        "manim_transfer",
        "report_editing",
    )


def test_only_active_or_trial_unexpired_license_is_usable():
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    active = LicenseSnapshot("PRO", "ACTIVE", now + timedelta(days=1), ())
    expired = LicenseSnapshot("PRO", "ACTIVE", now - timedelta(seconds=1), ())
    suspended = LicenseSnapshot("PRO", "SUSPENDED", None, ())

    assert active.is_usable(now)
    assert not expired.is_usable(now)
    assert not suspended.is_usable(now)


def test_installation_identity_is_hashed_and_not_saved_raw():
    installation_id = "5f304c9ed2914ad6b0f1469255a3a01e"

    assert installation_hash(installation_id) != installation_id
    assert len(installation_hash(installation_id)) == 64
    with pytest.raises(ValueError):
        installation_hash("short")
