from __future__ import annotations

import pytest

from app.core.platform_session import PlatformSession, PlatformSessionStore


class _TestProtector:
    """DPAPI sözleşmesini CI'da gerçek Windows anahtarına gerek duymadan sınar."""

    PREFIX = b"test-protected:"

    def protect(self, value: bytes) -> bytes:
        return self.PREFIX + value[::-1]

    def unprotect(self, value: bytes) -> bytes:
        if not value.startswith(self.PREFIX):
            raise ValueError("not protected")
        return value[len(self.PREFIX) :][::-1]


def _session() -> PlatformSession:
    return PlatformSession(
        access_token="a" * 16,
        refresh_token="refresh-token-" + "r" * 32,
        api_url="https://platform.carpan.example",
        display_name="Çarpan Yönetici",
        role="ADMIN",
    ).bind_to_local_session(company_id=10, user_id=20)


def test_platform_session_is_saved_encrypted_and_loaded(tmp_path):
    store = PlatformSessionStore(tmp_path, protector=_TestProtector())

    store.save(_session())

    assert store.load() == _session()
    encrypted = store.path.read_bytes()
    assert b"platform.carpan.example" not in encrypted
    assert _session().refresh_token.encode("utf-8") not in encrypted


def test_invalid_or_unreadable_platform_session_is_not_used(tmp_path):
    store = PlatformSessionStore(tmp_path, protector=_TestProtector())
    store.path.write_bytes(b"unexpected")

    assert store.load() is None


def test_clear_removes_only_local_session_copy(tmp_path):
    store = PlatformSessionStore(tmp_path, protector=_TestProtector())
    store.save(_session())

    store.clear()

    assert store.load() is None


def test_unbound_or_noncanonical_session_is_not_saved(tmp_path):
    store = PlatformSessionStore(tmp_path, protector=_TestProtector())
    unbound = PlatformSession("a" * 16, "r" * 40, "https://platform.carpan.example", "Yönetici", "ADMIN")

    from app.core.platform_session import PlatformSessionError

    with pytest.raises(PlatformSessionError):
        store.save(unbound)
    assert not PlatformSession("a" * 16, "r" * 40, "https://platform.carpan.example/", "Yönetici", "ADMIN").is_valid()
