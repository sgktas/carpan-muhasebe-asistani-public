from __future__ import annotations

import json
from pathlib import Path


class OutputLocationStore:
    """Kullanıcının seçtiği alternatif çıktı klasörünü hafızada tutar.

    Hiçbir seçim yapılmamışsa, varsayılan olarak ``AppPaths.output_dir``
    (Belgeler altındaki standart konum) kullanılır — bu dosya olmadan da
    program eskisi gibi çalışır.
    """

    def __init__(self, data_root: Path):
        self._path = data_root / "data" / "output_location.json"

    def get_override(self) -> Path | None:
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        value = data.get("output_dir")
        return Path(value) if value else None

    def set_override(self, path: Path) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"output_dir": str(path)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear_override(self) -> None:
        if self._path.exists():
            self._path.unlink()


def resolve_output_dir(app_paths) -> Path:
    """Kullanıcı bir klasör seçtiyse onu, seçmediyse varsayılanı döndürür."""
    override = OutputLocationStore(app_paths.data_root).get_override()
    if override and override.is_dir():
        return override
    return app_paths.output_dir
