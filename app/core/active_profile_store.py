from __future__ import annotations

import json
from pathlib import Path


class ActiveProfileStore:
    """Hangi girdi/çıktı profilinin şu an aktif olduğunu hafızada tutar.

    Hiçbir seçim yapılmamışsa (ilk kurulum), varsayılan olarak mevcut
    davranışla birebir aynı sonucu veren "manim" / "netsis" profilleri
    kullanılır — yani bu dosya olmadan da program eskisi gibi çalışır.
    """

    DEFAULT_INPUT_PROFILE_ID = "manim"
    DEFAULT_OUTPUT_PROFILE_ID = "netsis"
    DEFAULT_CUSTOMER_LIST_PROFILE_ID = "f1_fom"

    def __init__(self, data_root: Path):
        self._path = data_root / "data" / "active_profiles.json"

    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_input_profile_id(self) -> str:
        return self._read().get("input_profile_id") or self.DEFAULT_INPUT_PROFILE_ID

    def get_output_profile_id(self) -> str:
        return self._read().get("output_profile_id") or self.DEFAULT_OUTPUT_PROFILE_ID

    def get_customer_list_profile_id(self) -> str:
        return self._read().get("customer_list_profile_id") or self.DEFAULT_CUSTOMER_LIST_PROFILE_ID

    def set_customer_list_profile_id(self, profile_id: str) -> None:
        data = self._read()
        data["customer_list_profile_id"] = profile_id
        self._write(data)

    def set_input_profile_id(self, profile_id: str) -> None:
        data = self._read()
        data["input_profile_id"] = profile_id
        self._write(data)

    def set_output_profile_id(self, profile_id: str) -> None:
        data = self._read()
        data["output_profile_id"] = profile_id
        self._write(data)
