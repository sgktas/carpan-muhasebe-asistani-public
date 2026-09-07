from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil


@dataclass(frozen=True)
class CompanyWorkspace:
    company_id: int
    root: Path
    migrated_legacy_data: bool


class CompanyWorkspaceManager:
    """Firma verilerini aynı bilgisayarda fiziksel olarak ayırır.

    Eski tek-firma kurulumundaki dosyalar ilk geçişte *kopyalanır*. Böylece
    geri dönüş için özgün dosyalar yerinde kalır; işlem sırasında veri silinmez.
    Kimlik veritabanı (`platform.sqlite3`) ortak başlangıç alanında kalır.
    """

    MARKER_NAME = "workspace_migration.json"
    IDENTITY_FILES = {"platform.sqlite3", "platform.sqlite3-wal", "platform.sqlite3-shm"}

    def __init__(self, installation_data_root: str | Path):
        self.installation_data_root = Path(installation_data_root)

    def workspace_path(self, company_id: int) -> Path:
        return self.installation_data_root / "companies" / f"company-{int(company_id):08d}"

    def prepare(self, company_id: int, *, migrate_legacy: bool) -> CompanyWorkspace:
        root = self.workspace_path(company_id)
        root.mkdir(parents=True, exist_ok=True)
        marker = root / self.MARKER_NAME
        migrated = False
        if migrate_legacy and not marker.exists():
            self._copy_legacy_state(root)
            marker.write_text(
                json.dumps(
                    {"version": 1, "company_id": int(company_id), "mode": "copied-not-moved"},
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
            migrated = True
        for folder in (root / "data", root / "config", root / "templates", root / "logs"):
            folder.mkdir(parents=True, exist_ok=True)
        return CompanyWorkspace(int(company_id), root, migrated)

    def _copy_legacy_state(self, workspace_root: Path) -> None:
        for folder_name in ("config", "templates", "logs"):
            source = self.installation_data_root / folder_name
            if source.is_dir():
                shutil.copytree(source, workspace_root / folder_name, dirs_exist_ok=True)

        source_data = self.installation_data_root / "data"
        if not source_data.is_dir():
            return
        target_data = workspace_root / "data"
        target_data.mkdir(parents=True, exist_ok=True)
        for source in source_data.rglob("*"):
            relative = source.relative_to(source_data)
            if any(part in self.IDENTITY_FILES for part in relative.parts):
                continue
            target = target_data / relative
            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
