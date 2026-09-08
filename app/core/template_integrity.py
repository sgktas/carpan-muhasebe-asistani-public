from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


CHECKSUM_FILE = Path("config/local/template_checksums.json")
TEMPLATE_ROOT = Path("templates/local")


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
