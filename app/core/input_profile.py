from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class InputProfile:
    """Bir banka hareket raporu (MANİM benzeri) girdisinin sütun eşlemesini tanımlar.

    ``columns``: kaynak Excel dosyasındaki sütun başlığı -> ManimRecord alan adı.
    Yeni bir bankacılık/raporlama sistemi eklemek için Python koduna dokunmadan
    ``config/input_profiles/`` altına bu şemada yeni bir JSON dosyası eklemek
    yeterlidir.
    """

    profile_id: str
    name: str
    description: str
    columns: dict[str, str]  # kaynak sütun adı -> ic alan adı

    REQUIRED_INTERNAL_FIELDS = (
        "banka", "sube", "islem_tarihi", "aciklama", "tutar",
        "dekont_durumu", "karsi_hesap_adi", "karsi_hesap_kodu",
    )

    def header_for(self, internal_field: str) -> str:
        for header, field in self.columns.items():
            if field == internal_field:
                return header
        raise KeyError(f"Profilde '{internal_field}' alanı için sütun tanımlanmamış: {self.profile_id}")

    @classmethod
    def from_json(cls, path: Path) -> "InputProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        profile = cls(
            profile_id=data["id"],
            name=data.get("name", data["id"]),
            description=data.get("description", ""),
            columns=dict(data["columns"]),
        )
        missing = [field for field in cls.REQUIRED_INTERNAL_FIELDS if field not in profile.columns.values()]
        if missing:
            raise ValueError(
                f"Girdi profili '{profile.profile_id}' şu zorunlu alanları eşlemiyor: {', '.join(missing)}"
            )
        return profile


class InputProfileStore:
    """``config/input_profiles/`` klasöründeki profil dosyalarını yönetir."""

    def __init__(self, config_dir: Path, user_config_dir: Path | None = None):
        self._dir = config_dir / "input_profiles"
        self._user_dir = Path(user_config_dir) / "input_profiles" if user_config_dir else None

    def list_profiles(self) -> list[InputProfile]:
        profiles: dict[str, InputProfile] = {}
        for directory in (self._dir, self._user_dir):
            if directory is None or not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                profile = InputProfile.from_json(path)
                profiles[profile.profile_id] = profile
        return [profiles[key] for key in sorted(profiles)]

    def get(self, profile_id: str) -> InputProfile:
        for profile in self.list_profiles():
            if profile.profile_id == profile_id:
                return profile
        raise FileNotFoundError(f"Girdi profili bulunamadı: {profile_id}")

    def get_or_default(self, profile_id: str | None, default_id: str = "manim") -> InputProfile:
        return self.get(profile_id or default_id)
