from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class BankStatementProfile:
    """Banka ekstresi (Modül 03 - Banka Mutabakatı girdisi) sütun eşlemesini tanımlar.

    MANİM formatından farklıdır: burada her satırda kümülatif (running) bir
    'bakiye' sütunu bulunması beklenir, çünkü mutabakat ay sonu bakiyesi
    üzerinden yapılır.
    """

    profile_id: str
    name: str
    description: str
    columns: dict[str, str]  # kaynak sütun adı -> ic alan adı (tarih, aciklama, tutar, bakiye)

    REQUIRED_INTERNAL_FIELDS = ("tarih", "aciklama", "tutar", "bakiye")

    @classmethod
    def from_json(cls, path: Path) -> "BankStatementProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        profile = cls(
            profile_id=data["id"],
            name=data.get("name", data["id"]),
            description=data.get("description", ""),
            columns=dict(data["columns"]),
        )
        missing = [f for f in cls.REQUIRED_INTERNAL_FIELDS if f not in profile.columns.values()]
        if missing:
            raise ValueError(
                f"Banka ekstresi profili '{profile.profile_id}' şu zorunlu alanları "
                f"eşlemiyor: {', '.join(missing)}"
            )
        return profile


class BankStatementProfileStore:
    def __init__(self, config_dir: Path):
        self._dir = config_dir / "bank_statement_profiles"

    def list_profiles(self) -> list[BankStatementProfile]:
        if not self._dir.is_dir():
            return []
        return [BankStatementProfile.from_json(p) for p in sorted(self._dir.glob("*.json"))]

    def get(self, profile_id: str) -> BankStatementProfile:
        for profile in self.list_profiles():
            if profile.profile_id == profile_id:
                return profile
        raise FileNotFoundError(f"Banka ekstresi profili bulunamadı: {profile_id}")

    def get_or_default(self, profile_id: str | None, default_id: str = "genel") -> BankStatementProfile:
        return self.get(profile_id or default_id)
