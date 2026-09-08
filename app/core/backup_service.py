from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile


class BackupError(RuntimeError):
    pass


MANIFEST_PATH = "CarpanMuhasebeAsistani/YEDEK_MANIFEST.json"


def _safe_archive_name(name: str) -> str:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise BackupError(f"Yedekte güvensiz dosya yolu bulundu: {name}")
    return path.as_posix()


def create_local_backup(data_root: Path, destination: Path) -> Path:
    """Yerel ayar ve eşleştirme hafızasını tek bir ZIP dosyasında yedekler.

    Günlük dosyaları yedeğe alınmaz. Hedef dosya veri klasörünün içinde olsa
    bile yedeğin kendisi tekrar ZIP'e eklenmez.
    """
    data_root = Path(data_root).resolve()
    destination = Path(destination).resolve()
    if not data_root.is_dir():
        raise BackupError(f"Uygulama veri klasörü bulunamadı: {data_root}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    included = 0
    manifest_files: list[dict[str, object]] = []
    created_at = datetime.now().isoformat(timespec="seconds")
    try:
        with zipfile.ZipFile(
            destination,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for source in sorted(data_root.rglob("*")):
                if not source.is_file() or source.resolve() == destination:
                    continue
                relative = source.relative_to(data_root)
                if relative.parts and relative.parts[0].casefold() == "logs":
                    continue
                archive_name = _safe_archive_name(
                    (Path("CarpanMuhasebeAsistani") / relative).as_posix()
                )
                data = source.read_bytes()
                archive.writestr(archive_name, data)
                manifest_files.append({
                    "path": archive_name,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                })
                included += 1
            archive.writestr(
                "CarpanMuhasebeAsistani/YEDEK_BILGISI.txt",
                "Çarpan Muhasebe Asistanı yerel veri yedeği\n"
                f"Oluşturulma: {created_at}\n"
                f"Dosya sayısı: {included}\n",
            )
            archive.writestr(
                MANIFEST_PATH,
                json.dumps(
                    {"version": 1, "created_at": created_at, "files": manifest_files},
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
            )
    except (OSError, zipfile.BadZipFile) as error:
        destination.unlink(missing_ok=True)
        raise BackupError(f"Yedek oluşturulamadı: {error}") from error

    if not zipfile.is_zipfile(destination):
        destination.unlink(missing_ok=True)
        raise BackupError("Oluşturulan yedek doğrulanamadı.")
    validate_local_backup(destination)
    return destination


def validate_local_backup(backup_path: str | Path) -> dict[str, object]:
    """Yedek manifestini ve her dosyanın SHA-256 bütünlüğünü doğrular."""
    path = Path(backup_path).resolve()
    if not path.is_file() or not zipfile.is_zipfile(path):
        raise BackupError("Geçerli bir ZIP yedeği seçilmedi.")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = [_safe_archive_name(name) for name in archive.namelist()]
            if len(names) != len(set(names)):
                raise BackupError("Yedekte yinelenen dosya adı bulundu.")
            if MANIFEST_PATH not in names:
                raise BackupError("Yedek bütünlük manifesti bulunamadı.")
            manifest = json.loads(archive.read(MANIFEST_PATH).decode("utf-8"))
            files = manifest.get("files")
            if manifest.get("version") != 1 or not isinstance(files, list):
                raise BackupError("Yedek manifesti geçersiz.")
            expected_paths: set[str] = set()
            for item in files:
                if not isinstance(item, dict):
                    raise BackupError("Yedek manifestinde geçersiz dosya kaydı var.")
                name = _safe_archive_name(str(item.get("path", "")))
                if name in expected_paths or name not in names:
                    raise BackupError(f"Yedek manifesti dosyayla uyuşmuyor: {name}")
                expected_paths.add(name)
                data = archive.read(name)
                if int(item.get("size", -1)) != len(data):
                    raise BackupError(f"Yedek dosya boyutu uyuşmuyor: {name}")
                if str(item.get("sha256", "")) != hashlib.sha256(data).hexdigest():
                    raise BackupError(f"Yedek dosyası bozulmuş: {name}")
            return manifest
    except BackupError:
        raise
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError) as error:
        raise BackupError(f"Yedek doğrulanamadı: {error}") from error
