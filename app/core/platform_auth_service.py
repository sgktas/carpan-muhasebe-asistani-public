from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.platform_connection import PlatformAuthenticationError
from app.core.platform_session import PlatformSession, PlatformSessionError, canonical_platform_url


class AuthenticationClient(Protocol):
    config: object

    def login(self, *, company_code: str, username: str, password: str) -> PlatformSession: ...

    def refresh(self, refresh_token: str) -> PlatformSession: ...

    def logout(self, *, access_token: str, refresh_token: str) -> None: ...


class SessionStore(Protocol):
    def save(self, session: PlatformSession) -> None: ...

    def load(self) -> PlatformSession | None: ...

    def clear(self) -> None: ...


@dataclass(frozen=True)
class CentralSessionResult:
    state: str
    session: PlatformSession | None
    message: str

    @property
    def is_connected(self) -> bool:
        return self.state == "connected"


@dataclass(frozen=True)
class LocalSessionScope:
    """The local user allowed to use one encrypted central session."""

    company_id: int
    user_id: int

    def __post_init__(self) -> None:
        if int(self.company_id) <= 0 or int(self.user_id) <= 0:
            raise ValueError("Merkezi oturum için geçerli bir yerel firma ve kullanıcı gerekir.")


class PlatformAuthService:
    """Merkezi oturumun ağ ve yerel saklama akışını tek noktada yönetir.

    Yerel muhasebe çalışma alanı bu servise bağlı değildir: merkezi bağlantı
    yokken uygulama normal şekilde yerelde çalışmaya devam eder. Bu servis
    sadece lisans, kullanıcı ve cihaz tarafı için kullanılacaktır.
    """

    def __init__(self, client: AuthenticationClient, session_store: SessionStore, local_scope: LocalSessionScope):
        self._client = client
        self._session_store = session_store
        self._local_scope = local_scope

    def _configured_url(self) -> str:
        try:
            return canonical_platform_url(getattr(self._client.config, "api_url", ""))
        except (AttributeError, PlatformSessionError):
            raise PlatformSessionError("Merkezi platform adresi doğrulanamadı.") from None

    def _bind(self, session: PlatformSession) -> PlatformSession:
        configured_url = self._configured_url()
        if canonical_platform_url(session.api_url) != configured_url:
            raise PlatformSessionError("Merkezi oturum farklı bir platform adresinden geldi.")
        return session.bind_to_local_session(
            company_id=self._local_scope.company_id,
            user_id=self._local_scope.user_id,
        )

    def _is_current_binding(self, session: PlatformSession) -> bool:
        try:
            return (
                session.belongs_to_local_session(
                    company_id=self._local_scope.company_id,
                    user_id=self._local_scope.user_id,
                )
                and canonical_platform_url(session.api_url) == self._configured_url()
            )
        except PlatformSessionError:
            return False

    def sign_in(self, *, company_code: str, username: str, password: str) -> CentralSessionResult:
        try:
            session = self._client.login(
                company_code=company_code,
                username=username,
                password=password,
            )
            session = self._bind(session)
            self._session_store.save(session)
        except (PlatformAuthenticationError, PlatformSessionError) as error:
            return CentralSessionResult("rejected", None, str(error))
        return CentralSessionResult("connected", session, "Merkezi oturum açıldı.")

    def restore(self) -> CentralSessionResult:
        previous = self._session_store.load()
        if previous is None:
            return CentralSessionResult("not_signed_in", None, "Merkezi oturum bulunamadı.")
        if not self._is_current_binding(previous):
            self._session_store.clear()
            return CentralSessionResult(
                "binding_changed",
                None,
                "Merkezi oturum bu yerel firma, kullanıcı veya platform adresiyle eşleşmiyor. Yeniden giriş yapın.",
            )
        try:
            refreshed = self._bind(self._client.refresh(previous.refresh_token))
            self._session_store.save(refreshed)
        except (PlatformAuthenticationError, PlatformSessionError) as error:
            if not error.is_network_error:
                self._session_store.clear()
                return CentralSessionResult(
                    "expired",
                    None,
                    "Merkezi oturumun süresi doldu. Yeniden giriş yapın.",
                )
            # Ağ kesintisinde yerel iş akışı durmamalı. Yerel anahtar korunur,
            # ancak merkezi erişim için geçerli sayılmaz.
            return CentralSessionResult(
                "offline",
                None,
                "Merkezi platforma ulaşılamıyor. Yerel çalışma devam ediyor.",
            )
        return CentralSessionResult("connected", refreshed, "Merkezi oturum yenilendi.")

    def sign_out(self) -> CentralSessionResult:
        session = self._session_store.load()
        if session is None:
            return CentralSessionResult("not_signed_in", None, "Merkezi oturum zaten kapalı.")
        if not self._is_current_binding(session):
            self._session_store.clear()
            return CentralSessionResult(
                "binding_changed",
                None,
                "Merkezi oturum bu yerel firma, kullanıcı veya platform adresiyle eşleşmiyor. Bu cihazdaki eski kayıt silindi.",
            )
        remote_completed = True
        try:
            self._client.logout(access_token=session.access_token, refresh_token=session.refresh_token)
        except PlatformAuthenticationError:
            remote_completed = False
        finally:
            # Kullanıcının bu cihazdan çıkış isteği her durumda yerel kopyayı siler.
            self._session_store.clear()
        if remote_completed:
            return CentralSessionResult("signed_out", None, "Merkezi oturum kapatıldı.")
        return CentralSessionResult(
            "signed_out_offline",
            None,
            "Bu cihazdaki oturum silindi. Merkezi iptal bağlantı kurulamadığı için süre sonunda tamamlanacak.",
        )
