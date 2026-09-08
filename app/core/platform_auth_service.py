from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.platform_connection import PlatformAuthenticationError
from app.core.platform_session import PlatformSession


class AuthenticationClient(Protocol):
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


class PlatformAuthService:
    """Merkezi oturumun ağ ve yerel saklama akışını tek noktada yönetir.

    Yerel muhasebe çalışma alanı bu servise bağlı değildir: merkezi bağlantı
    yokken uygulama normal şekilde yerelde çalışmaya devam eder. Bu servis
    sadece lisans, kullanıcı ve cihaz tarafı için kullanılacaktır.
    """

    def __init__(self, client: AuthenticationClient, session_store: SessionStore):
        self._client = client
        self._session_store = session_store

    def sign_in(self, *, company_code: str, username: str, password: str) -> CentralSessionResult:
        try:
            session = self._client.login(
                company_code=company_code,
                username=username,
                password=password,
            )
            self._session_store.save(session)
        except PlatformAuthenticationError as error:
            return CentralSessionResult("rejected", None, str(error))
        return CentralSessionResult("connected", session, "Merkezi oturum açıldı.")

    def restore(self) -> CentralSessionResult:
        previous = self._session_store.load()
        if previous is None:
            return CentralSessionResult("not_signed_in", None, "Merkezi oturum bulunamadı.")
        try:
            refreshed = self._client.refresh(previous.refresh_token)
            self._session_store.save(refreshed)
        except PlatformAuthenticationError as error:
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
