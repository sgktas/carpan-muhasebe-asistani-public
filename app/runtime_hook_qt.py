"""Paketli Windows uygulamasında Qt DLL'lerinin kesin yükleme yolunu kurar."""

from __future__ import annotations

import os
from pathlib import Path
import sys


if getattr(sys, "frozen", False):
    bundle_root = Path(sys._MEIPASS)
    qt_dir = bundle_root / "PySide6"
    if qt_dir.is_dir():
        # Bazı Windows kurulumlarında sistemdeki farklı bir Qt6 DLL'i önce
        # bulunduğunda QtGui yüklenemez. Paketle gelen aynı sürüm DLL'leri
        # uygulama başlamadan önce açıkça önceliklendirilir.
        dll_paths = [str(qt_dir), str(bundle_root)]
        os.environ["PATH"] = os.pathsep.join(dll_paths + [os.environ.get("PATH", "")])
        _dll_directory_handles = []
        if hasattr(os, "add_dll_directory"):
            # add_dll_directory dönüş nesnesi yaşadığı sürece etkindir. Önceki
            # sürümde tutulmadığı için nesne hemen kapanabiliyor ve QtGui'nin
            # bağımlı DLL'leri bazı bilgisayarlarda bulunamıyordu.
            for dll_path in dll_paths:
                _dll_directory_handles.append(os.add_dll_directory(dll_path))
        os.environ.setdefault("QT_PLUGIN_PATH", str(qt_dir / "plugins"))
