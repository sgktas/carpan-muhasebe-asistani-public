from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


APP_VENDOR = "Carpan"
APP_NAME = "MuhasebeAsistani"
VISIBLE_OUTPUT_FOLDER = "Çarpan Muhasebe Asistanı"
VISIBLE_OUTPUT_SUBFOLDER = "Çıktılar"


@dataclass(frozen=True)
class AppPaths:
    """Uygulama kaynaklarını, sistem verilerini ve kullanıcı çıktılarını ayırır.

    PyInstaller ``--onefile`` çalışırken paket kaynakları geçici ``_MEIPASS``
    klasörüne açılır. Bu klasöre yazılan dosyalar uygulama kapanınca silinir.
    Bu nedenle:

    - şablon/config/logo gibi kaynaklar ``resource_root`` altında yalnız okunur,
    - eşleştirme hafızası ve işlenmiş dosya geçmişi ``data_root`` altında kalır,
    - kullanıcının açacağı Excel çıktıları görünür ``output_root`` altında tutulur.
    """

    resource_root: Path
    data_root: Path
    output_root: Path

    @property
    def assets_dir(self) -> Path:
        return self.resource_root / "assets"

    @property
    def config_dir(self) -> Path:
        return self.resource_root / "config"

    @property
    def templates_dir(self) -> Path:
        return self.resource_root / "templates"

    @property
    def state_dir(self) -> Path:
        return self.data_root / "data"

    @property
    def output_dir(self) -> Path:
        return self.output_root

    def ensure_writable_dirs(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def discover(cls) -> "AppPaths":
        paths = cls(
            resource_root=_resource_root(),
            data_root=_user_data_root(),
            output_root=_user_output_root(),
        )
        paths.ensure_writable_dirs()
        return paths


def _resource_root() -> Path:
    # PyInstaller onefile/onedir paketlerinde sys._MEIPASS paket kaynaklarının
    # açıldığı geçici dizindir. Kaynak koddan çalışırken proje kökü kullanılır.
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root).resolve()
    return Path(__file__).resolve().parents[2]


def _user_data_root() -> Path:
    """Platforma uygun, kalıcı ve kullanıcı tarafından yazılabilir sistem yolu."""
    override = os.environ.get("MUHASEBE_ASISTANI_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    return base / APP_VENDOR / APP_NAME


def _user_output_root() -> Path:
    """Kullanıcının kolayca görebileceği kalıcı çıktı klasörünü döndürür.

    Windows Gezgini ``Documents`` klasörünü Türkçe sistemlerde ``Belgeler``
    olarak gösterir. Klasör, gizli AppData alanının dışında tutulur.
    """
    override = os.environ.get("MUHASEBE_ASISTANI_OUTPUT_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform.startswith("win"):
        documents = _windows_documents_dir()
    else:
        documents = Path.home() / "Documents"

    return documents / VISIBLE_OUTPUT_FOLDER / VISIBLE_OUTPUT_SUBFOLDER


def _windows_documents_dir() -> Path:
    """Windows'ta mümkünse gerçek Known Folder 'Documents' yolunu kullanır."""
    try:
        import ctypes
        from ctypes import wintypes
        import uuid

        # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        folder_id = uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7")

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        guid = GUID(
            folder_id.fields[0],
            folder_id.fields[1],
            folder_id.fields[2],
            (ctypes.c_ubyte * 8)(*folder_id.bytes[8:]),
        )
        path_ptr = ctypes.c_wchar_p()
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(path_ptr)
        )
        if result == 0 and path_ptr.value:
            try:
                return Path(path_ptr.value)
            finally:
                ctypes.windll.ole32.CoTaskMemFree(path_ptr)
    except Exception:
        pass

    return Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"


APP_PATHS = AppPaths.discover()
