from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path


@dataclass(frozen=True)
class OutputColumn:
    """Çıktı şablonundaki tek bir sütunun tanımı.

    ``source_kind == "field"``  -> ``field`` adındaki iç kayıt alanı yazılır
                                    (örn. ``cari_kodu``, ``tutar``, ``aciklama``,
                                    ``islem_tarihi``).
    ``source_kind == "const"``  -> her satırda aynı ``value`` yazılır (örn.
                                    Netsis'teki sabit bir TCMB kodu gibi).
    ``style`` yalnız görünüm/biçimlendirme için kullanılır: "date", "amount",
    "integer", "centered" veya "text".
    ``force_text``: Excel'in uzun rakam dizisini (örn. cari kodu) otomatik
    sayıya/bilimsel gösterime çevirmesini engellemek için True olmalı.
    """

    header: str
    width: int
    style: str
    source_kind: str
    field: str | None = None
    value: object = None
    force_text: bool = False


@dataclass(frozen=True)
class OutputProfile:
    profile_id: str
    name: str
    description: str
    template_file: str
    columns: tuple[OutputColumn, ...]
    category: str = "havale"
    grouping: str = "region_bank"
    protected: bool = False
    output_extension: str = ".xls"

    def headers(self) -> list[str]:
        return [column.header for column in self.columns]

    def widths(self) -> list[int]:
        return [column.width for column in self.columns]

    def column_index(self, style: str | None = None, force_text: bool | None = None) -> list[int]:
        """Verilen kritere uyan sütunların (0 tabanlı) indekslerini döndürür."""
        indexes = []
        for i, column in enumerate(self.columns):
            if style is not None and column.style != style:
                continue
            if force_text is not None and column.force_text != force_text:
                continue
            indexes.append(i)
        return indexes

    @classmethod
    def from_json(cls, path: Path) -> "OutputProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        columns = tuple(
            OutputColumn(
                header=col["header"],
                width=col.get("width", 12),
                style=("amount" if "tutar" in col["header"].casefold()
                       else col.get("style", "text")),
                source_kind=col["source"],
                field=col.get("field"),
                value=col.get("value"),
                force_text=col.get("force_text", False),
            )
            for col in data["columns"]
        )
        return cls(
            profile_id=data["id"],
            name=data.get("name", data["id"]),
            description=data.get("description", ""),
            template_file=data["template_file"],
            columns=columns,
            category=data.get("category", "havale"),
            grouping=data.get("grouping", "region_bank"),
            protected=bool(data.get("protected", False)),
            output_extension=(
                "." + str(data.get("output_extension", "xls")).strip().lstrip(".").lower()
            ),
        )


class OutputProfileStore:
    """``config/output_profiles/`` klasöründeki profil dosyalarını yönetir."""

    def __init__(self, config_dir: Path, user_config_dir: Path | None = None):
        self._config_dir = config_dir
        self._dir = config_dir / "output_profiles"
        self._local_dir = config_dir / "local" / "output_profiles"
        self._user_dir = Path(user_config_dir) / "output_profiles" if user_config_dir else None

    def list_profiles(self) -> list[OutputProfile]:
        profiles: dict[str, OutputProfile] = {}
        directories = [self._dir]
        if os.environ.get("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG") != "1":
            directories.append(self._local_dir)
            if self._user_dir is not None:
                directories.append(self._user_dir)
        for directory in directories:
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                profile = OutputProfile.from_json(path)
                existing = profiles.get(profile.profile_id)
                if existing is not None and existing.protected and not profile.protected:
                    # Yerel şirket ayarları aynı profil kimliğiyle alan/sabit
                    # değerleri güncelleyebilir; ancak onaylı profil kilidi
                    # hiçbir katmanda kaldırılamaz.
                    profile = replace(profile, protected=True)
                profiles[profile.profile_id] = profile
        return [profiles[key] for key in sorted(profiles)]

    def get(self, profile_id: str) -> OutputProfile:
        for profile in self.list_profiles():
            if profile.profile_id == profile_id:
                return profile
        raise FileNotFoundError(f"Çıktı profili bulunamadı: {profile_id}")

    def get_or_default(self, profile_id: str | None, default_id: str = "netsis") -> OutputProfile:
        return self.get(profile_id or default_id)
