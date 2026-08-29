from pathlib import Path

import pandas as pd

from app.core.bank_statement_metadata import extract_bank_statement_metadata, find_bank_logo_path
from app.core.bank_statement_parser import BankStatementParser


def _make_antetli_ekstre(path):
    rows_before = [
        ["T. GARANTİ BANKASI A.Ş.\nGenel Müdürlük: ...", None, None, None],
        ["Şirket Ünvanı", "TEST FİRMA A.Ş.", None, None],
        ["IBAN", "TR00 0000 0000 0000 0000 00", None, None],
        ["Şube", "TEST ŞUBE", None, None],
        ["Başlangıç", "01.07.2026", None, None],
        ["Bitiş", "31.07.2026", None, None],
        ["Bakiye", "1.000,00 TL", None, None],
    ]
    header = ["Tarih", "Açıklama", "Tutar", "Bakiye"]
    data_rows = [["01.07.2026", "Devir", "1.000,00", "1.000,00"]]
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows_before + [header] + data_rows).to_excel(writer, index=False, header=False)


def test_metadata_cikarimi_dogru_calisir(tmp_path):
    path = tmp_path / "ekstre.xlsx"
    _make_antetli_ekstre(path)

    meta = BankStatementParser(path).load_metadata()
    assert meta.banka_adi == "T. GARANTİ BANKASI A.Ş."
    assert meta.sirket_unvani == "TEST FİRMA A.Ş."
    assert meta.iban == "TR00 0000 0000 0000 0000 00"
    assert meta.sube == "TEST ŞUBE"
    assert meta.donem_baslangic == "01.07.2026"
    assert meta.donem_bitis == "31.07.2026"


def test_metadata_yoksa_bos_doner(tmp_path):
    path = tmp_path / "duz_ekstre.xlsx"
    pd.DataFrame([
        {"Tarih": "01.07.2026", "Açıklama": "Devir", "Tutar": 1000.0, "Bakiye": 1000.0},
    ]).to_excel(path, index=False)

    meta = BankStatementParser(path).load_metadata()
    assert meta.banka_adi is None


def test_logo_bulunamazsa_none_doner(tmp_path):
    assert find_bank_logo_path("T. GARANTİ BANKASI A.Ş.", tmp_path) is None


def test_logo_dosyasi_varsa_bulunur(tmp_path):
    (tmp_path / "bank_logos").mkdir()
    logo_path = tmp_path / "bank_logos" / "garanti.png"
    logo_path.write_bytes(b"fake-png-bytes")
    found = find_bank_logo_path("T. GARANTİ BANKASI A.Ş.", tmp_path)
    assert found == logo_path


def test_tanimayan_banka_adi_icin_none_doner(tmp_path):
    (tmp_path / "bank_logos").mkdir()
    (tmp_path / "bank_logos" / "garanti.png").write_bytes(b"fake")
    assert find_bank_logo_path("BİLİNMEYEN BANKA A.Ş.", tmp_path) is None
