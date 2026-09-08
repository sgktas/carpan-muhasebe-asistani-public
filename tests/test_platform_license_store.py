from app.core.platform_connection import PlatformLicense
from app.core.platform_license_store import PlatformLicenseStore


def test_license_store_is_scoped_to_company_user_and_api(tmp_path):
    store = PlatformLicenseStore(tmp_path)
    license_info = PlatformLicense("PRO", "ACTIVE", None, frozenset({"manim_transfer"}), True)
    store.save(license_info, company_id=10, user_id=20, api_url="https://platform.example")

    assert store.load(company_id=10, user_id=20, api_url="https://platform.example") == license_info
    assert store.load(company_id=11, user_id=20, api_url="https://platform.example") is None
    assert store.load(company_id=10, user_id=20, api_url="https://other.example") is None


def test_license_store_clear_removes_cached_entitlements(tmp_path):
    store = PlatformLicenseStore(tmp_path)
    store.clear()
    assert store.load(company_id=1, user_id=2, api_url="https://platform.example") is None
