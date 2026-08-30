from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from app.core.customer_list_cache import CustomerListCache
from app.core.customer_parser import CustomerParser
from app.modules.report_editing.engine import prepare_fom_customer_list


MODULE_ID = "customer_list_import"
MODULE_NAME = "Müşteri Listesi"


@dataclass
class CustomerListImportResult:
    cached_path: Path
    customer_rows: int
    source_name: str
    logs: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "customer_rows": self.customer_rows,
            "source_name": self.source_name,
            "cached_file": self.cached_path.name,
        }


class CustomerListImportEngine:
    """Ham FOM müşteri listesini standartlaştırıp MANİM hafızasına kaydeder."""

    def __init__(self, source_path: str | Path, data_root: str | Path):
        self.source_path = Path(source_path)
        self.data_root = Path(data_root)

    def run(self) -> CustomerListImportResult:
        if self.source_path.suffix.lower() not in {".xlsx", ".xls"}:
            raise ValueError("Müşteri listesi Excel (.xlsx veya .xls) formatında olmalıdır.")
        if not self.source_path.is_file():
            raise FileNotFoundError(f"Müşteri listesi bulunamadı: {self.source_path.name}")

        cache = CustomerListCache(self.data_root)
        prepared_path = cache._dir / f".musteri_listesi_hazir_{uuid4().hex}.xlsx"
        try:
            customer_rows = prepare_fom_customer_list(self.source_path, prepared_path)
            parsed_rows = CustomerParser(prepared_path).load()
            if not parsed_rows:
                raise ValueError("Müşteri listesinde kullanılabilir müşteri kaydı bulunamadı.")
            cache.save(prepared_path, original_name=self.source_path.name)
            cached_path = cache.get()
            if not cached_path:
                raise RuntimeError("Düzenlenmiş müşteri listesi hafızaya kaydedilemedi.")
        finally:
            prepared_path.unlink(missing_ok=True)

        return CustomerListImportResult(
            cached_path=cached_path,
            customer_rows=customer_rows,
            source_name=self.source_path.name,
            logs=[
                f"Ham FOM müşteri listesi düzenlendi: {customer_rows} kayıt.",
                "Aydın'daki AYDIN-DD-02 rotaları Nazilli şubesine ayrıldı.",
                "Düzenlenmiş liste MANİM Aktarma için hafızaya kaydedildi.",
            ],
        )
