from datetime import datetime, timedelta, timezone

from app.core.platform_connection import PlatformLicense
from app.core.platform_license_policy import central_license_access


def _license(**changes) -> PlatformLicense:
    values = {
        "plan_code": "PRO",
        "status": "ACTIVE",
        "expires_at": None,
        "enabled_modules": frozenset({"manim_transfer"}),
        "usable": True,
        "enforcement_required": False,
        "offline_grace_hours": 168,
        "fetched_at": None,
    }
    values.update(changes)
    return PlatformLicense(**values)


def test_unenforced_central_license_does_not_interrupt_current_local_work():
    assert central_license_access(_license()) is None


def test_invalid_license_is_always_rejected_when_server_explicitly_reports_it():
    assert central_license_access(_license(usable=False)) is False


def test_enforced_license_allows_only_within_offline_grace_period():
    now = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    current = _license(
        enforcement_required=True,
        offline_grace_hours=24,
        fetched_at=(now - timedelta(hours=23)).isoformat(),
    )
    expired = _license(
        enforcement_required=True,
        offline_grace_hours=24,
        fetched_at=(now - timedelta(hours=25)).isoformat(),
    )

    assert central_license_access(current, now=now) is True
    assert central_license_access(expired, now=now) is False


def test_enforced_license_without_a_trusted_check_time_is_not_allowed():
    assert central_license_access(_license(enforcement_required=True, fetched_at=None)) is False
