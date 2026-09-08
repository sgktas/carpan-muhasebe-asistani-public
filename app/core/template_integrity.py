from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


CHECKSUM_FILE = Path("config/local/template_checksums.json")
TEMPLATE_ROOT = Path("templates/local")


class TemplateIntegrityError(RuntimeError):
    """Onaylı şablon değişmiş veya güvenilir kaynaktan gelmiyorsa yükselir."""


def runtime_template_enforcement_enabled() -> bool:
    """Üretim Windows çalıştırmasında yerel şablon denetimini etkinleştirir.

    Public kaynak testleri gerçek şirket şablonlarını taşımaz ve bunu açıkça
    ``MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG=1`` ile belirtir. Bu bayrak
    yalnız test/public kaynak davranışını seçer; gerçek Windows kurulumunda
    şablon doğrulaması atlanamaz.
    """
    import os

    return os.name == "nt" and os.environ.get("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG") != "1"


@dataclass(frozen=True)
class TemplateIntegrityCheck:
    template_name: str
    status: str
    message: str


@dataclass(frozen=True)
class TemplateIntegritySnapshot:
    checks: tuple[TemplateIntegrityCheck, ...]
    configured: bool

    @property
    def valid_count(self) -> int:
        return sum(check.status == "VALID" for check in self.checks)

    @property
    def invalid_count(self) -> int:
        return sum(check.status != "VALID" for check in self.checks)

    @property
    def is_valid(self) -> bool:
        return self.configured and bool(self.checks) and self.invalid_count == 0


def verify_approved_templates(resource_root: str | Path) -> TemplateIntegritySnapshot:
    """Onaylı yerel şablonların yalnız okunur bütünlük kontrolünü yapar.

    Bu kontrol hiçbir dosyayı değiştirmez. Kontrol değeri veya şablon eksikse
    kullanıcıya görünür bir uyarı üretir; şablonu yeniden oluşturmayı denemez.
    """
    root = Path(resource_root)
    checksum_path = root / CHECKSUM_FILE
    if not checksum_path.is_file():
        return TemplateIntegritySnapshot(
            checks=(
                TemplateIntegrityCheck(
                    "Kontrol listesi",
                    "MISSING",
                    "Onaylı şablon kontrol listesi bu kurulumda bulunamadı.",
                ),
            ),
            configured=False,
        )
    try:
        raw_checksums = json.loads(checksum_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return TemplateIntegritySnapshot(
            checks=(
                TemplateIntegrityCheck(
                    "Kontrol listesi",
                    "INVALID",
                    "Onaylı şablon kontrol listesi okunamadı.",
                ),
            ),
            configured=False,
        )
    if not isinstance(raw_checksums, dict) or not raw_checksums:
        return TemplateIntegritySnapshot(
            checks=(
                TemplateIntegrityCheck(
                    "Kontrol listesi",
                    "INVALID",
                    "Onaylı şablon kontrol listesi geçersiz.",
                ),
            ),
            configured=False,
        )

    checks: list[TemplateIntegrityCheck] = []
    for name, expected_hash in sorted(raw_checksums.items()):
        template_name = str(name).replace("\\", "/")
        template_path = root / TEMPLATE_ROOT / template_name
        if not template_path.is_file():
            checks.append(
                TemplateIntegrityCheck(template_name, "MISSING", "Şablon dosyası bulunamadı.")
            )
            continue
        actual_hash = hashlib.sha256(template_path.read_bytes()).hexdigest()
        if actual_hash != str(expected_hash):
            checks.append(
                TemplateIntegrityCheck(
                    template_name,
                    "CHANGED",
                    "Şablon onaylı özgün dosyayla uyuşmuyor.",
                )
            )
            continue
        checks.append(TemplateIntegrityCheck(template_name, "VALID", "Doğrulandı."))
    return TemplateIntegritySnapshot(checks=tuple(checks), configured=True)


def assert_approved_template(resource_root: str | Path, template_path: str | Path) -> Path:
    """Tek bir çıktı şablonunun manifestteki özgün dosya olduğunu doğrular.

    ``verify_approved_templates`` kullanıcı arayüzünde toplu durum gösterir;
    bu fonksiyon ise yazma işleminden hemen önce çağrılan çalışma zamanı
    kilididir. Böylece şablon bozulduğunda genel Excel üretimine düşülmez.
    """
    root = Path(resource_root).resolve()
    path = Path(template_path).resolve()
    local_root = (root / TEMPLATE_ROOT).resolve()
    try:
        manifest_name = path.relative_to(local_root).as_posix()
    except ValueError as error:
        raise TemplateIntegrityError(
            f"Şablon onaylı yerel şablon klasörünün dışında: {path}"
        ) from error

    checksum_path = root / CHECKSUM_FILE
    if not checksum_path.is_file():
        raise TemplateIntegrityError("Onaylı şablon kontrol listesi bulunamadı.")
    try:
        raw_checksums = json.loads(checksum_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise TemplateIntegrityError("Onaylı şablon kontrol listesi okunamadı.") from error
    expected_hash = raw_checksums.get(manifest_name) if isinstance(raw_checksums, dict) else None
    if not expected_hash:
        raise TemplateIntegrityError(
            f"Şablon kontrol listesinde kayıtlı değil: {manifest_name}"
        )
    if not path.is_file():
        raise TemplateIntegrityError(f"Onaylı şablon dosyası bulunamadı: {manifest_name}")
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash != str(expected_hash):
        raise TemplateIntegrityError(
            f"Onaylı şablon değişmiş: {manifest_name}. Genel Excel çıktısı üretilmedi."
        )
    return path
