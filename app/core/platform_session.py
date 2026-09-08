from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
from typing import Protocol


class PlatformSessionError(RuntimeError):
    """Merkezi oturum bu cihazda güvenli biçimde saklanamadığında."""


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

    def is_valid(self) -> bool:
        return all(
            (
                len(self.access_token.strip()) >= 16,
                len(self.refresh_token.strip()) >= 40,
                self.api_url.startswith("https://") or self.api_url.startswith("http://localhost"),
                bool(self.display_name.strip()),
                bool(self.role.strip()),
            )
        )


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


class PlatformSessionStore:
    """Merkezi oturumu DPAPI ile şifrelenmiş tek bir yerel dosyada tutar."""

    FILE_NAME = "platform_session.bin"

    def __init__(self, data_root: str | Path, *, protector: DataProtector | None = None):
        self.path = Path(data_root) / self.FILE_NAME
        self._protector = protector or WindowsDataProtector()

    def save(self, session: PlatformSession) -> None:
        if not session.is_valid():
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
            )
        except (OSError, UnicodeDecodeError, KeyError, TypeError, ValueError, json.JSONDecodeError, PlatformSessionError):
            return None
        return session if session.is_valid() else None

    def clear(self) -> None:
        """Yerel kopyayı kaldırır; sunucudaki oturum ayrıca logout ile iptal edilir."""
        self.path.unlink(missing_ok=True)
