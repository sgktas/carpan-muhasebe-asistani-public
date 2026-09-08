from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class PlatformConnectionError(ValueError):
    """Merkezi platform bağlantı ayarı geçerli olmadığında."""


class PlatformAuthenticationError(RuntimeError):
    """Merkezi platform giriş veya oturum yenileme isteği kabul edilmediğinde."""


@dataclass(frozen=True)
class PlatformConnectionConfig:
    api_url: str = ""


@dataclass(frozen=True)
class PlatformConnectionStatus:
    state: str
    message: str
    service: str | None = None

    @property
    def is_connected(self) -> bool:
        return self.state == "connected"


class PlatformConnectionStore:
    """Merkezi API adresini yalnız yerel uygulama ayarlarında saklar.

    Finansal veri, müşteri listesi, parola veya erişim belirteci bu dosyaya
    yazılmaz. Merkezi girişte oturum belirteçleri ``PlatformSessionStore``
    tarafından işletim sistemi korumalı ayrı bir depoda tutulur.
    """

    FILE_NAME = "platform_connection.json"

    def __init__(self, data_root: str | Path):
        self.path = Path(data_root) / self.FILE_NAME

    def get(self) -> PlatformConnectionConfig:
        if not self.path.is_file():
            return PlatformConnectionConfig()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return PlatformConnectionConfig(api_url=self._normalize_url(payload.get("api_url", "")))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return PlatformConnectionConfig()

    def save(self, api_url: str) -> PlatformConnectionConfig:
        config = PlatformConnectionConfig(api_url=self._normalize_url(api_url))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
        return config

    @staticmethod
    def _normalize_url(value: object) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        parsed = urlparse(raw)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise PlatformConnectionError("Merkezi platform adresi tam bir web adresi olmalı.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise PlatformConnectionError("Merkezi platform adresinde kullanıcı bilgisi veya ek parametre olmamalı.")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise PlatformConnectionError("Merkezi platform bağlantısı HTTPS kullanmalı.")
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}{path}"


class PlatformApiClient:
    """Masaüstünün merkezi API'ye HTTPS üzerinden yaptığı sınırlı çağrılar.

    Bu sınıf PostgreSQL'e bağlanmaz ve başlangıç aşamasında yalnız sağlık
    denetimi yapar. Böylece VPS hazır olmadan masaüstünün yerel çalışması
    etkilenmez.
    """

    def __init__(
        self,
        config: PlatformConnectionConfig,
        *,
        opener: Callable[..., object] | None = None,
    ):
        self.config = config
        self._opener = opener or urlopen

    def health(self, timeout_seconds: float = 4.0) -> PlatformConnectionStatus:
        if not self.config.api_url:
            return PlatformConnectionStatus(
                state="not_configured",
                message="Merkezi platform henüz yapılandırılmadı. Yerel çalışma devam ediyor.",
            )
        request = Request(
            f"{self.config.api_url}/health",
            headers={"Accept": "application/json", "User-Agent": "Carpan-Muhasebe-Asistani"},
            method="GET",
        )
        try:
            with self._opener(request, timeout=timeout_seconds) as response:
                if getattr(response, "status", 200) != 200:
                    return PlatformConnectionStatus("unavailable", "Merkezi platform yanıt vermedi.")
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError):
            return PlatformConnectionStatus(
                "unavailable",
                "Merkezi platforma şu an ulaşılamıyor. Yerel çalışma devam ediyor.",
            )
        if not isinstance(payload, dict) or (
            payload.get("service") != "carpan-platform-api" or payload.get("status") != "ok"
        ):
            return PlatformConnectionStatus(
                "unavailable",
                "Merkezi platform hazır değil. Yerel çalışma devam ediyor.",
            )
        return PlatformConnectionStatus(
            "connected",
            "Merkezi platform bağlantısı hazır.",
            service=str(payload["service"]),
        )

    def login(
        self,
        *,
        company_code: str,
        username: str,
        password: str,
        timeout_seconds: float = 8.0,
    ):
        """Merkezi giriş yapar; parola yalnız bu HTTPS isteğinde kullanılır."""
        payload = self._post_json(
            "/v1/auth/login",
            {
                "company_code": str(company_code).strip(),
                "username": str(username).strip(),
                "password": str(password),
            },
            timeout_seconds=timeout_seconds,
        )
        return self._session_from_response(payload)

    def refresh(self, refresh_token: str, *, timeout_seconds: float = 8.0):
        """Tek kullanımlık yenileme anahtarını döndürerek yeni oturum alır."""
        payload = self._post_json(
            "/v1/auth/refresh",
            {"refresh_token": str(refresh_token)},
            timeout_seconds=timeout_seconds,
        )
        return self._session_from_response(payload)

    def logout(self, *, access_token: str, refresh_token: str, timeout_seconds: float = 8.0) -> None:
        """Sunucudaki oturumu iptal eder; başarısızsa yerel oturum silinmemelidir."""
        self._post_json(
            "/v1/auth/logout",
            {"refresh_token": str(refresh_token)},
            access_token=str(access_token),
            timeout_seconds=timeout_seconds,
            expect_json=False,
        )

    def _post_json(
        self,
        path: str,
        payload: dict[str, str],
        *,
        timeout_seconds: float,
        access_token: str | None = None,
        expect_json: bool = True,
    ) -> dict:
        if not self.config.api_url:
            raise PlatformAuthenticationError("Merkezi platform adresi yapılandırılmadı.")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Carpan-Muhasebe-Asistani",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        request = Request(
            f"{self.config.api_url}{path}",
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with self._opener(request, timeout=timeout_seconds) as response:
                status_code = getattr(response, "status", 200)
                raw = response.read()
        except HTTPError as error:
            if error.code in {401, 403}:
                raise PlatformAuthenticationError("Merkezi oturum doğrulanamadı.") from None
            raise PlatformAuthenticationError("Merkezi platforma şu an ulaşılamıyor.") from None
        except (URLError, OSError, TimeoutError):
            raise PlatformAuthenticationError("Merkezi platforma şu an ulaşılamıyor.") from None
        if status_code not in {200, 201, 204}:
            raise PlatformAuthenticationError("Merkezi platform isteği tamamlanamadı.")
        if not expect_json:
            return {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PlatformAuthenticationError("Merkezi platform geçerli bir yanıt vermedi.") from None
        if not isinstance(parsed, dict):
            raise PlatformAuthenticationError("Merkezi platform geçerli bir yanıt vermedi.")
        return parsed

    def _session_from_response(self, payload: dict):
        # Döngüsel içe aktarmayı önlemek için yalnız bu ağ sınırında yüklenir.
        from app.core.platform_session import PlatformSession

        try:
            session = PlatformSession(
                access_token=str(payload["access_token"]),
                refresh_token=str(payload["refresh_token"]),
                api_url=self.config.api_url,
                display_name=str(payload["display_name"]),
                role=str(payload["role"]),
            )
        except (KeyError, TypeError, ValueError):
            raise PlatformAuthenticationError("Merkezi platform oturum bilgisi eksik gönderdi.") from None
        if not session.is_valid():
            raise PlatformAuthenticationError("Merkezi platform oturum bilgisi geçersiz.")
        return session
