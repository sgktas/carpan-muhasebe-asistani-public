import pandas as pd
import xlrd

from app.core.active_profile_store import ActiveProfileStore
from app.core.processing_engine import ProcessingEngine


def test_toplu_netsis_sablonu_banka_kodlariyla_bolge_basina_tek_dosya_yazar(
    synthetic_project,
):
    manim_path, tahsilat_path, customer_path, project_root = synthetic_project
    rows = pd.read_excel(manim_path)
    rows.loc[0, "Banka"] = "Ziraat"
    rows.loc[0, "Tutar"] = 1200.0
    rows.loc[0, "Açıklama"] = "ZIRAAT HAVALE"
    rows.loc[1, "Banka"] = "Garanti"
    rows.loc[1, "Dekont Durumu"] = "Aktarıldı"
    rows.loc[1, "Karşı Hesap Adı"] = "ABC LTD"
    rows.loc[1, "Karşı Hesap Kodu"] = "ABC001"
    rows.loc[1, "Tutar"] = 1300.0
    rows.loc[1, "Açıklama"] = "GARANTI HAVALE"
    rows = rows.iloc[:2]
    rows.to_excel(manim_path, index=False)

    ActiveProfileStore(project_root).set_output_profile_id("netsis_toplu")
    result = ProcessingEngine([manim_path, tahsilat_path, customer_path], project_root).run()

    netsis_files = [path for path in result.created_files if "BODRUM" in path.name]
    assert len(netsis_files) == 1
    assert "GARANTI" not in netsis_files[0].name
    assert "ZIRAAT" not in netsis_files[0].name

    workbook = xlrd.open_workbook(str(netsis_files[0]))
    sheet = workbook.sheet_by_index(0)
    assert sheet.cell_value(0, 0) == "Banka Hes.Kodu(*)"
    assert sheet.cell_value(0, 18) == "Muh.Ref.Kod(*)"
    assert {sheet.cell_value(row, 0) for row in range(1, sheet.nrows)} == {
        "BANK-G-01", "BANK-Z-01"
    }
    assert {sheet.cell_value(row, 1) for row in range(1, sheet.nrows)} == {1.0}
    assert {sheet.cell_value(row, 18) for row in range(1, sheet.nrows)} == {"R01"}
