from __future__ import annotations

from datetime import datetime
from pathlib import Path
import zipfile


class BackupError(RuntimeError):
    pass


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
                archive.write(source, Path("CarpanMuhasebeAsistani") / relative)
                included += 1
            archive.writestr(
                "CarpanMuhasebeAsistani/YEDEK_BILGISI.txt",
                "Çarpan Muhasebe Asistanı yerel veri yedeği\n"
                f"Oluşturulma: {datetime.now().isoformat(timespec='seconds')}\n"
                f"Dosya sayısı: {included}\n",
            )
    except (OSError, zipfile.BadZipFile) as error:
        destination.unlink(missing_ok=True)
        raise BackupError(f"Yedek oluşturulamadı: {error}") from error

    if not zipfile.is_zipfile(destination):
        destination.unlink(missing_ok=True)
        raise BackupError("Oluşturulan yedek doğrulanamadı.")
    return destination
