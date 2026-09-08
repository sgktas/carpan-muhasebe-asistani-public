from __future__ import annotations

from app.core.platform_auth_service import PlatformAuthService
from app.core.platform_connection import PlatformAuthenticationError
from app.core.platform_session import PlatformSession


def _session(suffix: str = "1") -> PlatformSession:
    return PlatformSession(
        access_token="access-token-value" + suffix,
        refresh_token="refresh-token-value-" + ("r" * 32) + suffix,
        api_url="https://platform.carpan.example",
        display_name="Yönetici",
        role="ADMIN",
    )


class _MemoryStore:
    def __init__(self, session: PlatformSession | None = None):
        self.session = session

    def save(self, session: PlatformSession) -> None:
        self.session = session

    def load(self) -> PlatformSession | None:
        return self.session

    def clear(self) -> None:
        self.session = None


class _Client:
    def __init__(self, *, refresh_error: str = "", logout_error: bool = False):
        self.refresh_error = refresh_error
        self.logout_error = logout_error
        self.logged_out = False

    def login(self, **_kwargs) -> PlatformSession:
        return _session()

    def refresh(self, _refresh_token: str) -> PlatformSession:
        if self.refresh_error:
            raise PlatformAuthenticationError("offline", is_network_error=self.refresh_error == "network")
        return _session("2")

    def logout(self, **_kwargs) -> None:
        if self.logout_error:
            raise PlatformAuthenticationError("offline")
        self.logged_out = True


def test_sign_in_saves_a_central_session():
    store = _MemoryStore()
    result = PlatformAuthService(_Client(), store).sign_in(
        company_code="CARPAN", username="yonetici", password="gizli"
    )

    assert result.is_connected
    assert store.load() == result.session


def test_restore_rotates_session_without_affecting_local_work_when_offline():
    store = _MemoryStore(_session())
    result = PlatformAuthService(_Client(refresh_error="network"), store).restore()

    assert result.state == "offline"
    assert result.session is None
    assert store.load() == _session()


def test_restore_removes_expired_central_session_from_device():
    store = _MemoryStore(_session())
    result = PlatformAuthService(_Client(refresh_error="rejected"), store).restore()

    assert result.state == "expired"
    assert store.load() is None


def test_sign_out_always_removes_local_copy():
    store = _MemoryStore(_session())
    result = PlatformAuthService(_Client(logout_error=True), store).sign_out()

    assert result.state == "signed_out_offline"
    assert store.load() is None
