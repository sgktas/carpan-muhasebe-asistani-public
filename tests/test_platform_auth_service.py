from __future__ import annotations

from app.core.platform_auth_service import LocalSessionScope, PlatformAuthService
from app.core.platform_connection import PlatformAuthenticationError, PlatformConnectionConfig, PlatformLicense
from app.core.platform_session import PlatformSession


def _session(suffix: str = "1") -> PlatformSession:
    return PlatformSession(
        access_token="access-token-value" + suffix,
        refresh_token="refresh-token-value-" + ("r" * 32) + suffix,
        api_url="https://platform.carpan.example",
        display_name="Yönetici",
        role="ADMIN",
        local_company_id=1,
        local_user_id=2,
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
        self.refreshed = False
        self.activated = False
        self.config = PlatformConnectionConfig("https://platform.carpan.example")

    def login(self, **_kwargs) -> PlatformSession:
        return _session()

    def refresh(self, _refresh_token: str) -> PlatformSession:
        self.refreshed = True
        if self.refresh_error:
            raise PlatformAuthenticationError("offline", is_network_error=self.refresh_error == "network")
        return _session("2")

    def logout(self, **_kwargs) -> None:
        if self.logout_error:
            raise PlatformAuthenticationError("offline")
        self.logged_out = True

    def activate_device(self, **_kwargs) -> None:
        self.activated = True

    def license(self, _access_token: str) -> PlatformLicense:
        return PlatformLicense("PRO", "ACTIVE", None, frozenset({"manim_transfer"}), True)


def test_sign_in_saves_a_central_session():
    store = _MemoryStore()
    result = PlatformAuthService(_Client(), store, LocalSessionScope(1, 2)).sign_in(
        company_code="CARPAN", username="yonetici", password="gizli"
    )

    assert result.is_connected
    assert store.load() == result.session
    assert result.session.belongs_to_local_session(company_id=1, user_id=2)


def test_bound_session_activates_installation_and_reads_license():
    client = _Client()
    session = _session()
    license_info = PlatformAuthService(
        client, _MemoryStore(session), LocalSessionScope(1, 2)
    ).sync_device_and_license(
        session,
        installation_id="installation-identity-123456789",
        device_label="Test bilgisayarı",
    )

    assert client.activated
    assert license_info.usable


def test_restore_rotates_session_without_affecting_local_work_when_offline():
    store = _MemoryStore(_session())
    result = PlatformAuthService(_Client(refresh_error="network"), store, LocalSessionScope(1, 2)).restore()

    assert result.state == "offline"
    assert result.session is None
    assert store.load() == _session()


def test_restore_removes_expired_central_session_from_device():
    store = _MemoryStore(_session())
    result = PlatformAuthService(_Client(refresh_error="rejected"), store, LocalSessionScope(1, 2)).restore()

    assert result.state == "expired"
    assert store.load() is None


def test_sign_out_always_removes_local_copy():
    store = _MemoryStore(_session())
    result = PlatformAuthService(_Client(logout_error=True), store, LocalSessionScope(1, 2)).sign_out()

    assert result.state == "signed_out_offline"
    assert store.load() is None


def test_restore_clears_session_without_sending_secret_when_server_changed():
    stored = _session().bind_to_local_session(company_id=1, user_id=2)
    store = _MemoryStore(stored)
    client = _Client()
    client.config = PlatformConnectionConfig("https://new-platform.carpan.example")
    result = PlatformAuthService(client, store, LocalSessionScope(1, 2)).restore()

    assert result.state == "binding_changed"
    assert store.load() is None
    assert not client.refreshed


def test_restore_clears_session_without_sending_secret_for_other_local_user():
    stored = _session().bind_to_local_session(company_id=1, user_id=2)
    store = _MemoryStore(stored)
    client = _Client()
    result = PlatformAuthService(client, store, LocalSessionScope(1, 99)).restore()

    assert result.state == "binding_changed"
    assert store.load() is None
    assert not client.refreshed


def test_sign_in_rejects_session_from_different_platform_address():
    class WrongServerClient(_Client):
        def login(self, **_kwargs):
            return PlatformSession("a" * 16, "r" * 40, "https://other.carpan.example", "Yönetici", "ADMIN")
    result = PlatformAuthService(WrongServerClient(), _MemoryStore(), LocalSessionScope(1, 2)).sign_in(
        company_code="CARPAN", username="yonetici", password="gizli"
    )
    assert result.state == "rejected"
    assert not result.session


def test_sign_out_does_not_send_another_local_users_session():
    store = _MemoryStore(_session().bind_to_local_session(company_id=1, user_id=2))
    client = _Client()
    result = PlatformAuthService(client, store, LocalSessionScope(1, 99)).sign_out()

    assert result.state == "binding_changed"
    assert store.load() is None
    assert not client.logged_out
