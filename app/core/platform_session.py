from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
from typing import Protocol
from urllib.parse import urlparse


class PlatformSessionError(RuntimeError):
    """Merkezi oturum bu cihazda güvenli biçimde saklanamadığında."""


def canonical_platform_url(value: object) -> str:
    """Return the single canonical API address allowed for a stored session."""
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if not raw or parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise PlatformSessionError("Merkezi platform adresi tam bir web adresi olmalı.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise PlatformSessionError("Merkezi platform adresinde kullanıcı bilgisi veya ek parametre olmamalı.")
    host = parsed.hostname.casefold()
    if parsed.scheme == "http" and host not in {"127.0.0.1", "localhost", "::1"}:
        raise PlatformSessionError("Merkezi platform bağlantısı HTTPS kullanmalı.")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc.casefold()}{path}"


@dataclass(frozen=True)
class PlatformSession:
    """Merkezi API'den alınan, yalnız cihaz sahibine ait oturum verisi.

    Bu nesne işlem, müşteri veya banka verisi taşımaz. ``refresh_token`` uzun
    süreli olduğu için uygulama dizinine ya da JSON ayar dosyasına yazılmaz.
    """

    access_token: str
    refresh_token: str
    api_url: str
    display_name: str
    role: str
    local_company_id: int = 0
    local_user_id: int = 0

    def is_valid(self) -> bool:
        return all(
            (
                len(self.access_token.strip()) >= 16,
                len(self.refresh_token.strip()) >= 40,
                canonical_platform_url(self.api_url) == self.api_url,
                bool(self.display_name.strip()),
                bool(self.role.strip()),
            )
        )

    @property
    def has_local_scope(self) -> bool:
        return self.local_company_id > 0 and self.local_user_id > 0

    def bind_to_local_session(self, *, company_id: int, user_id: int) -> "PlatformSession":
        if not self.is_valid() or int(company_id) <= 0 or int(user_id) <= 0:
            raise PlatformSessionError("Merkezi oturum yerel firma ve kullanıcıyla bağlanamadı.")
        return replace(self, local_company_id=int(company_id), local_user_id=int(user_id))

    def belongs_to_local_session(self, *, company_id: int, user_id: int) -> bool:
        return self.has_local_scope and self.local_company_id == int(company_id) and self.local_user_id == int(user_id)


class DataProtector(Protocol):
    def protect(self, value: bytes) -> bytes: ...

    def unprotect(self, value: bytes) -> bytes: ...


class WindowsDataProtector:
    """Windows DPAPI ile veriyi yalnız mevcut Windows kullanıcısına bağlar."""

    CRYPTPROTECT_UI_FORBIDDEN = 0x1

    class _DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    def __init__(self) -> None:
        if not sys.platform.startswith("win"):
            raise PlatformSessionError("Güvenli merkezi oturum saklama bu işletim sisteminde kullanılamıyor.")

    @classmethod
    def _blob(cls, value: bytes) -> tuple["WindowsDataProtector._DataBlob", object]:
        buffer = ctypes.create_string_buffer(value)
        return cls._DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer

    @staticmethod
    def _read_blob(blob: "WindowsDataProtector._DataBlob") -> bytes:
        if not blob.cbData:
            return b""
        return ctypes.string_at(blob.pbData, blob.cbData)

    @staticmethod
    def _release_blob(blob: "WindowsDataProtector._DataBlob") -> None:
        if blob.pbData:
            ctypes.windll.kernel32.LocalFree(blob.pbData)

    def protect(self, value: bytes) -> bytes:
        input_blob, _buffer = self._blob(value)
        output_blob = self._DataBlob()
        protected = ctypes.windll.crypt32.CryptProtectData
        protected.argtypes = [
            ctypes.POINTER(self._DataBlob),
            wintypes.LPCWSTR,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(self._DataBlob),
        ]
        protected.restype = wintypes.BOOL
        if not protected(
            ctypes.byref(input_blob),
            "Çarpan Muhasebe Asistanı merkezi oturumu",
            None,
            None,
            None,
            self.CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output_blob),
        ):
            raise PlatformSessionError("Windows oturum verisini güvenli biçimde koruyamadı.")
        try:
            return self._read_blob(output_blob)
        finally:
            self._release_blob(output_blob)

    def unprotect(self, value: bytes) -> bytes:
        input_blob, _buffer = self._blob(value)
        output_blob = self._DataBlob()
        unprotected = ctypes.windll.crypt32.CryptUnprotectData
        unprotected.argtypes = [
            ctypes.POINTER(self._DataBlob),
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(self._DataBlob),
        ]
        unprotected.restype = wintypes.BOOL
        description = wintypes.LPWSTR()
        if not unprotected(
            ctypes.byref(input_blob),
            ctypes.byref(description),
            None,
            None,
            None,
            self.CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output_blob),
        ):
            raise PlatformSessionError("Merkezi oturum bu Windows kullanıcısına ait değil veya bozulmuş.")
        try:
            return self._read_blob(output_blob)
        finally:
            if description:
                ctypes.windll.kernel32.LocalFree(description)
            self._release_blob(output_blob)


class UnavailableDataProtector:
    """Windows DPAPI olmayan ortamda oturum verisi yazılmasını engeller.

    Bu yalnız Linux tabanlı otomatik kalite kontrolü gibi desteklenmeyen
    ortamlarda ayarlar ekranının güvenle açılabilmesi içindir. Veriyi şifresiz
    saklamaz; kaydetme/okuma girişimi açık hata verir.
    """

    def protect(self, value: bytes) -> bytes:
        raise PlatformSessionError(
            "Merkezi oturum bu işletim sisteminde güvenli biçimde saklanamaz."
        )

    def unprotect(self, value: bytes) -> bytes:
        raise PlatformSessionError(
            "Merkezi oturum bu işletim sisteminde güvenli biçimde açılamaz."
        )


class PlatformSessionStore:
    """Merkezi oturumu DPAPI ile şifrelenmiş tek bir yerel dosyada tutar."""

    FILE_NAME = "platform_session.bin"

    def __init__(self, data_root: str | Path, *, protector: DataProtector | None = None):
        self.path = Path(data_root) / self.FILE_NAME
        self._protector = protector or (
            WindowsDataProtector()
            if sys.platform.startswith("win")
            else UnavailableDataProtector()
        )

    def save(self, session: PlatformSession) -> None:
        if not session.is_valid() or not session.has_local_scope:
            raise PlatformSessionError("Merkezi oturum verisi eksik veya geçersiz.")
        payload = json.dumps(asdict(session), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        encrypted = self._protector.protect(payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        try:
            temporary.write_bytes(encrypted)
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)

    def load(self) -> PlatformSession | None:
        if not self.path.is_file():
            return None
        try:
            payload = json.loads(self._protector.unprotect(self.path.read_bytes()).decode("utf-8"))
            session = PlatformSession(
                access_token=str(payload["access_token"]),
                refresh_token=str(payload["refresh_token"]),
                api_url=str(payload["api_url"]),
                display_name=str(payload["display_name"]),
                role=str(payload["role"]),
                local_company_id=int(payload.get("local_company_id", 0)),
                local_user_id=int(payload.get("local_user_id", 0)),
            )
        except (OSError, UnicodeDecodeError, KeyError, TypeError, ValueError, json.JSONDecodeError, PlatformSessionError):
            return None
        return session if session.is_valid() else None

    def clear(self) -> None:
        """Yerel kopyayı kaldırır; sunucudaki oturum ayrıca logout ile iptal edilir."""
        self.path.unlink(missing_ok=True)
