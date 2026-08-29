import pandas as pd

from app.core.customer_parser import CustomerParser


def test_vergi_numarasi_sutun_adi_okunur(tmp_path):
    file_path = tmp_path / "musteriler.xlsx"
    pd.DataFrame([
        {
            "Müşteri Kodu": "C001",
            "Ünvan": "TEST GIDA LTD STI",
            "Tabela Adi": "TEST MAGAZA FETHIYE",
            "Vergi Numarası": "0111111111",
            "Şube": "SIMSEK-KUSADASI",
        }
    ]).to_excel(file_path, index=False)

    records = CustomerParser(file_path).load()

    assert len(records) == 1
    assert records[0].vergi_no == "0111111111"
    assert records[0].tabela_adi == "TEST MAGAZA FETHIYE"
