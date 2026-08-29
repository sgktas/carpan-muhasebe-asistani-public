from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


class CustomerListCache:
    """Son başarıyla kullanılan müşteri listesini hafızada tutar.

    Müşteri listesi (F1 FOM/VisionPlus çıktısı) büyük ölçüde sabittir; sadece
    yeni açılan bayi/market müşterileri eklendikçe değişir. Kullanıcı her
    MANİM aktarımında bu dosyayı yeniden seçmek zorunda kalmasın diye, en son
    kullanılan liste burada bir kopya olarak saklanır ve yeni bir liste
    verilmediği sürece otomatik olarak kullanılır.
    """

    def __init__(self, data_root: Path):
        self._dir = data_root / "data"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self._dir / "last_musteri_listesi_meta.json"

    def _cache_path(self, suffix: str) -> Path:
        return self._dir / f"last_musteri_listesi{suffix}"

    def get(self) -> Path | None:
        meta = self._read_meta()
        if not meta:
            return None
        path = self._dir / meta["dosya_adi_hafiza"]
        return path if path.exists() else None

    def metadata(self) -> dict | None:
        return self._read_meta()

    def save(self, source: Path) -> None:
        # Önceki farklı uzantılı hafıza dosyası varsa temizle (örn. .xls -> .xlsx değişimi).
        for old in self._dir.glob("last_musteri_listesi.*"):
            old.unlink(missing_ok=True)

        cache_name = f"last_musteri_listesi{source.suffix}"
        cache_path = self._dir / cache_name
        shutil.copy2(source, cache_path)

        meta = {
            "orijinal_ad": source.name,
            "kaydedilme_tarihi": datetime.now().isoformat(timespec="seconds"),
            "dosya_adi_hafiza": cache_name,
        }
        self._meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_meta(self) -> dict | None:
        if not self._meta_path.exists():
            return None
        try:
            return json.loads(self._meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
