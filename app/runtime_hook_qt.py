"""Paketli Windows uygulamasında Qt DLL'lerinin kesin yükleme yolunu kurar."""

from __future__ import annotations

import os
from pathlib import Path
import sys


if getattr(sys, "frozen", False):
    qt_dir = Path(sys._MEIPASS) / "PySide6"
    if qt_dir.is_dir():
        # Bazı Windows kurulumlarında sistemdeki farklı bir Qt6 DLL'i önce
        # bulunduğunda QtGui yüklenemez. Paketle gelen aynı sürüm DLL'leri
        # uygulama başlamadan önce açıkça önceliklendirilir.
        os.environ["PATH"] = str(qt_dir) + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(qt_dir))
        os.environ.setdefault("QT_PLUGIN_PATH", str(qt_dir / "plugins"))
