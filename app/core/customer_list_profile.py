from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class CustomerListProfile:
    """Müşteri (cari) listesi dosyasının sütun eşlemesini tanımlar.

    Her müşterinin (F1 FOM/VisionPlus, başka bir ERP, elle tutulan bir Excel
    vs.) kendi müşteri listesi dosyası kendi sütun adlarına sahip olabilir. Bu
    yüzden her iç alan için TEK bir sütun adı değil, olası isimlerin bir
    listesi (``aliases``) tutulur; dosyada bulunan ilk eşleşme kullanılır.
    Yeni bir kaynak sistem için Python koduna dokunmadan
    ``config/customer_list_profiles/`` altına yeni bir JSON profili eklemek
    yeterlidir.
    """

    profile_id: str
    name: str
    description: str
    aliases: dict[str, tuple[str, ...]]  # ic alan adi -> olasi sutun basliklari

    REQUIRED_FIELDS = ("cari_kodu", "unvan")
    OPTIONAL_FIELDS = ("vergi_no", "sube", "tabela_adi")

    @classmethod
    def from_json(cls, path: Path) -> "CustomerListProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        aliases = {field: tuple(values) for field, values in data["aliases"].items()}
        profile = cls(
            profile_id=data["id"],
            name=data.get("name", data["id"]),
            description=data.get("description", ""),
            aliases=aliases,
        )
        missing = [field for field in cls.REQUIRED_FIELDS if field not in profile.aliases]
        if missing:
            raise ValueError(
                f"Müşteri listesi profili '{profile.profile_id}' şu zorunlu alanları "
                f"eşlemiyor: {', '.join(missing)}"
            )
        return profile


class CustomerListProfileStore:
    """``config/customer_list_profiles/`` klasöründeki profil dosyalarını yönetir."""

    def __init__(self, config_dir: Path):
        self._dir = config_dir / "customer_list_profiles"

    def list_profiles(self) -> list[CustomerListProfile]:
        if not self._dir.is_dir():
            return []
        return [
            CustomerListProfile.from_json(path)
            for path in sorted(self._dir.glob("*.json"))
        ]

    def get(self, profile_id: str) -> CustomerListProfile:
        for profile in self.list_profiles():
            if profile.profile_id == profile_id:
                return profile
        raise FileNotFoundError(f"Müşteri listesi profili bulunamadı: {profile_id}")

    def get_or_default(self, profile_id: str | None, default_id: str = "f1_fom") -> CustomerListProfile:
        return self.get(profile_id or default_id)
