import sys
from pathlib import Path

# Proje kök klasörünü PYTHONPATH'e ekle.
# Bu sayede dosya "python app/main.py" ile doğrudan çalıştırılsa bile
# "from app...." importları çalışır (aksi halde "ModuleNotFoundError: No module named 'app'" hatası alınırdı).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.core.app_logging import configure_logging, install_exception_logging
from app.core.app_paths import APP_PATHS
from app.ui.login_window import LoginWindow
from app.ui.main_window import MainWindow

# Ana pencereye global referans tutulur; aksi halde login penceresi
# kapanınca Python nesnesi çöp toplanır ve ana pencere anında yok olur.
_main_window = None


def _set_windows_app_id() -> None:
    """Windows görev çubuğu ve pencere ikonunun aynı uygulamaya bağlanmasını sağlar."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Carpan.MuhasebeAsistani"
        )
    except Exception:
        pass


def _load_app_icon() -> QIcon:
    icon_path = APP_PATHS.assets_dir / "carpan.ico"
    return QIcon(str(icon_path)) if icon_path.is_file() else QIcon()


def main():
    logger = configure_logging(APP_PATHS.data_root)
    install_exception_logging(logger)
    logger.info("Uygulama başlatılıyor")
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app_icon = _load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    def open_main_window(username: str) -> None:
        global _main_window
        _main_window = MainWindow(username=username)
        _main_window.show()

    login = LoginWindow(on_login_success=open_main_window)
    login.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
