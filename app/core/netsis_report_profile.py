from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class NetsisReportProfile:
    """Netsis'ten alınan ay sonu raporunun (Modül 03 girdisi) sütun eşlemesini tanımlar.

    Banka ekstresi profiliyle aynı şekilde, her satırda kümülatif bir 'bakiye'
    sütunu bulunması beklenir.
    """

    profile_id: str
    name: str
    description: str
    columns: dict[str, str]

    BASE_REQUIRED_FIELDS = ("tarih", "aciklama", "bakiye")

    @classmethod
    def from_json(cls, path: Path) -> "NetsisReportProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        profile = cls(
            profile_id=data["id"],
            name=data.get("name", data["id"]),
            description=data.get("description", ""),
            columns=dict(data["columns"]),
        )
        fields = set(profile.columns.values())
        missing_base = [f for f in cls.BASE_REQUIRED_FIELDS if f not in fields]
        has_tutar = "tutar" in fields
        has_borc_alacak = "borc" in fields and "alacak" in fields
        if missing_base or not (has_tutar or has_borc_alacak):
            raise ValueError(
                f"Netsis raporu profili '{profile.profile_id}' geçersiz: 'tarih', 'aciklama', "
                "'bakiye' alanları ve ayrıca ya 'tutar' ya da ('borc' ve 'alacak') alanları "
                "tanımlanmış olmalı."
            )
        return profile

    def uses_borc_alacak(self) -> bool:
        return "tutar" not in self.columns.values()


class NetsisReportProfileStore:
    def __init__(self, config_dir: Path):
        self._dir = config_dir / "netsis_report_profiles"

    def list_profiles(self) -> list[NetsisReportProfile]:
        if not self._dir.is_dir():
            return []
        return [NetsisReportProfile.from_json(p) for p in sorted(self._dir.glob("*.json"))]

    def get(self, profile_id: str) -> NetsisReportProfile:
        for profile in self.list_profiles():
            if profile.profile_id == profile_id:
                return profile
        raise FileNotFoundError(f"Netsis raporu profili bulunamadı: {profile_id}")

    def get_or_default(self, profile_id: str | None, default_id: str = "netsis") -> NetsisReportProfile:
        return self.get(profile_id or default_id)
