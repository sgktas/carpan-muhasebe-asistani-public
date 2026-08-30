import pandas as pd
from openpyxl import load_workbook

from app.core.customer_list_cache import CustomerListCache
from app.core.processing_engine import ProcessingEngine
from app.modules.customer_list.engine import CustomerListImportEngine
from app.modules.report_editing.engine import CUSTOMER_OUTPUT_COLUMNS


def test_ham_fom_musteri_listesi_ayri_modulde_duzenlenip_hafizaya_alinir(
    synthetic_project,
    tmp_path,
):
    manim_path, tahsilat_path, _customer_path, project_root = synthetic_project
    raw_customer_path = tmp_path / "input" / "ham_fom_musteri_listesi.xlsx"
    raw_customer = {column: None for column in CUSTOMER_OUTPUT_COLUMNS}
    raw_customer.update({
        "Müşteri Sayısı": 1,
        "Müşteri Kodu": "ABC001",
        "Şube": "SIMSEK-AYDIN",
        "Tabela Adi": "ABC MARKET",
        "Ünvan": "ABC LTD",
        "Vergi Numarası": "2222222222",
        "SR-Rota": "AYDIN-DD-0203",
    })
    pd.DataFrame([raw_customer]).to_excel(raw_customer_path, index=False)

    result = CustomerListImportEngine(raw_customer_path, project_root).run()

    assert result.customer_rows == 1
    assert result.cached_path.exists()
    assert result.source_name == raw_customer_path.name
    book = load_workbook(result.cached_path, data_only=True)
    try:
        assert book.active["B1"].value == "Müşteri Sayısı"
        assert book.active["D2"].value == "SIMSEK-NAZILLI"
    finally:
        book.close()
    metadata = CustomerListCache(project_root).metadata()
    assert metadata is not None
    assert metadata["orijinal_ad"] == raw_customer_path.name

    manim_result = ProcessingEngine([manim_path, tahsilat_path], project_root).run()
    assert manim_result.produced_netsis_records == 1
    assert any("hafızadaki son liste kullanıldı" in line for line in manim_result.logs)
