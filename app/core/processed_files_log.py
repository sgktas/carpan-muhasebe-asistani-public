from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
import tempfile


class ProcessedFilesLog:
    """Hangi MANİM dosyalarının daha önce başarıyla işlendiğini takip eder.

    Kayıt, yalnızca tüm çıktı dosyaları başarıyla üretildikten sonra toplu ve
    atomik olarak yazılır. Böylece yarım kalan bir işlem, dosyayı yanlışlıkla
    "işlendi" durumuna getirmez.
    """

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
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
    def hash_file(path: str | Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def is_processed(self, file_hash: str) -> dict | None:
        return self.data.get(file_hash)

    def mark_processed(self, file_hash: str, file_name: str, record_count: int) -> None:
        self.mark_many([(file_hash, file_name, record_count)])

    def mark_many(self, items: list[tuple[str, str, int]]) -> None:
        """Bir işlemde tamamlanan tüm MANİM dosyalarını tek yazımla kaydeder."""
        if not items:
            return
        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for file_hash, file_name, record_count in items:
            self.data[file_hash] = {
                "dosya_adi": file_name,
                "tarih": completed_at,
                "kayit_sayisi": int(record_count),
            }
        self._save()
