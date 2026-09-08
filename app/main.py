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
from app.core.company_workspace import CompanyWorkspaceManager
from app.core.identity import AuthenticatedSession, IdentityStore
from app.core.platform_connection import PlatformConnectionStore
from app.core.platform_license_store import PlatformLicenseStore
from app.ui.login_window import LoginWindow
from app.ui.main_window import MainWindow

# Ana pencereye global referans tutulur; aksi halde login penceresi
# kapanınca Python nesnesi çöp toplanır ve ana pencere anında yok olur.
_main_window = None
_login_window = None


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

    identity_store = IdentityStore(APP_PATHS.state_dir / "platform.sqlite3")
    workspace_manager = CompanyWorkspaceManager(APP_PATHS.base_data_root)

    def show_login_window() -> None:
        global _login_window
        APP_PATHS.reset_to_installation_data()
        _login_window = LoginWindow(
            identity_store=identity_store,
            on_login_success=open_main_window,
        )
        _login_window.show()

    def open_main_window(session: AuthenticatedSession) -> None:
        global _main_window
        # Birden çok firma varsa ortak eski veriyi tahmine dayalı biçimde hiçbir
        # firmaya taşımayız. Tek-firma kurulumunda güvenli kopyalı geçiş yapılır.
        workspace = workspace_manager.prepare(
            session.company_id,
            migrate_legacy=len(identity_store.companies()) == 1,
        )
        APP_PATHS.activate_company_workspace(workspace.root)
        if workspace.migrated_legacy_data:
            logger.info("Eski yerel çalışma verisi firma alanına kopyalandı.")
        platform_url = PlatformConnectionStore(APP_PATHS.base_data_root).get().api_url
        central_license = PlatformLicenseStore(APP_PATHS.base_data_root).load(
            company_id=session.company_id,
            user_id=session.user_id,
            api_url=platform_url,
        )
        _main_window = MainWindow(
            session=session,
            identity_store=identity_store,
            on_logout=show_login_window,
            central_license=central_license,
        )
        _main_window.show()

    show_login_window()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
