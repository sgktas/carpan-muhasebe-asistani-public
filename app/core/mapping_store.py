from __future__ import annotations

import json
from pathlib import Path
import tempfile


class MappingStore:
    """Kullanıcının elle yaptığı eşleştirmeleri kalıcı olarak saklar."""

    def __init__(self, file_path: str | Path | None = None):
        self.file_path = Path(file_path or Path("data") / "customer_mappings.json")
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def get(self, key: str) -> str | list[dict] | None:
        return self.data.get(self._key(key))

    def set(self, key: str, value: str | list[dict]) -> None:
        self.set_many([(key, value)])

    def set_many(self, items: list[tuple[str, str | list[dict]]]) -> None:
        if not items:
            return
        for key, value in items:
            if isinstance(value, str):
                self.data[self._key(key)] = value.strip()
            else:
                self.data[self._key(key)] = [
                    {"musteri_kodu": str(row["musteri_kodu"]).strip(), "tutar": float(row["tutar"])}
                    for row in value
                ]
        self._save()

    def _load(self) -> dict[str, str | list[dict]]:
        if not self.file_path.exists():
            return {}
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        payload = json.dumps(self.data, ensure_ascii=False, indent=2)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.file_path.parent,
            prefix=f".{self.file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(self.file_path)

    @staticmethod
    def _key(value: str) -> str:
        return " ".join(str(value).upper().split())
