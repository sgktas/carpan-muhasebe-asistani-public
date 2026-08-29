import pandas as pd

from app.core.bank_statement_parser import BankStatementParser
from app.core.netsis_report_parser import NetsisReportParser
from app.core.reconciliation_engine import ReconciliationEngine
from app.writers.reconciliation_writer import ReconciliationReportWriter


def _make_bank_excel(path):
    pd.DataFrame([
        {"Tarih": "01.07.2026", "Açıklama": "Devir", "Tutar": "10.000,00", "Bakiye": "10.000,00"},
        {"Tarih": "05.07.2026", "Açıklama": "Havale Gelen", "Tutar": "2.500,00", "Bakiye": "12.500,00"},
        {"Tarih": "12.07.2026", "Açıklama": "EFT Giden", "Tutar": "-1.200,00", "Bakiye": "11.300,00"},
        {"Tarih": "20.07.2026", "Açıklama": "Komisyon", "Tutar": "-15,00", "Bakiye": "11.285,00"},
    ]).to_excel(path, index=False)


def _make_netsis_excel(path, eksik_satir=False):
    rows = [
        {"Tarih": "01.07.2026", "Açıklama": "Devir", "Borç": 10000.0, "Alacak": 0.0, "Bakiye": 10000.0},
        {"Tarih": "05.07.2026", "Açıklama": "Havale Gelen", "Borç": 2500.0, "Alacak": 0.0, "Bakiye": 12500.0},
        {"Tarih": "12.07.2026", "Açıklama": "EFT Giden", "Borç": 0.0, "Alacak": 1200.0, "Bakiye": 11300.0},
    ]
    if not eksik_satir:
        rows.append({"Tarih": "20.07.2026", "Açıklama": "Komisyon", "Borç": 0.0, "Alacak": 15.0, "Bakiye": 11285.0})
    pd.DataFrame(rows).to_excel(path, index=False)


def test_bank_statement_parser_okur(tmp_path):
    path = tmp_path / "ekstre.xlsx"
    _make_bank_excel(path)
    records = BankStatementParser(path).load()
    assert len(records) == 4
    assert records[0].tutar == 10000.0
    assert records[-1].bakiye == 11285.0


def test_netsis_report_parser_okur(tmp_path):
    path = tmp_path / "netsis_rapor.xlsx"
    _make_netsis_excel(path)
    records = NetsisReportParser(path).load()
    assert len(records) == 4
    assert records[-1].bakiye == 11285.0


def test_bank_statement_parser_antetli_dosyada_basligi_bulur(tmp_path):
    # Gercek banka ekstrelerinde veri tablosundan once sirket/hesap bilgisi
    # bloku olur; gercek baslik satiri 1. satir degildir.
    path = tmp_path / "antetli_ekstre.xlsx"
    rows_before = [
        ["T. GARANTİ BANKASI A.Ş.", None, None, None],
        ["Şirket Ünvanı", "TEST A.Ş.", None, None],
        ["Bakiye", "11.285,00 TL", None, None],
        [None, None, None, None],
    ]
    header = ["Tarih", "Açıklama", "Tutar", "Bakiye"]
    data_rows = [
        ["01.07.2026", "Devir", "10.000,00", "10.000,00"],
        ["05.07.2026", "Havale", "1.285,00", "11.285,00"],
    ]
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows_before + [header] + data_rows).to_excel(writer, index=False, header=False)

    records = BankStatementParser(path).load()
    assert len(records) == 2
    assert records[0].aciklama == "Devir"
    assert records[-1].bakiye == 11285.0


def test_netsis_report_parser_borc_alacak_ve_devir_satirini_dogru_isler(tmp_path):
    # Gercek Netsis raporlarinda tutar tek sutun degil Borc/Alacak seklindedir,
    # ayrica tarihsiz bir 'Devreden' satiri ve sonda tarihsiz toplam satirlari olur.
    path = tmp_path / "netsis_gercekci.xlsx"
    rows = [
        [None, None, "Devreden", 5000.0, 0.0, 5000.0],
        ["01.07.2026", "Tahsilat", "Cari Havale", 1000.0, 0.0, 6000.0],
        ["02.07.2026", "Odeme", "Virman", 0.0, 500.0, 5500.0],
        [None, None, "Genel Toplam", 1000.0, 500.0, 5500.0],
    ]
    header = ["Tarih", "Fiş No", "Açıklama", "Borç", "Alacak", "Bakiye"]
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([header] + rows).to_excel(writer, index=False, header=False)

    records = NetsisReportParser(path).load()
    # Devreden ve Genel Toplam (tarihsiz) satirlari atlanmali, sadece 2 gercek islem kalmali.
    assert len(records) == 2
    assert records[0].tutar == 1000.0  # Borc - Alacak = 1000 - 0
    assert records[1].tutar == -500.0  # Borc - Alacak = 0 - 500
    assert records[-1].bakiye == 5500.0


def test_ucdan_uca_mutabik_senaryo(tmp_path):
    bank_path = tmp_path / "ekstre.xlsx"
    netsis_path = tmp_path / "netsis_rapor.xlsx"
    _make_bank_excel(bank_path)
    _make_netsis_excel(netsis_path, eksik_satir=False)

    bank_records = BankStatementParser(bank_path).load()
    netsis_records = NetsisReportParser(netsis_path).load()
    result = ReconciliationEngine().reconcile(bank_records, netsis_records)

    assert result.mutabik is True
    assert result.fark == 0

    output_path = tmp_path / "mutabakat_raporu.xlsx"
    written = ReconciliationReportWriter().write(result, output_path)
    assert written.is_file()


def test_ucdan_uca_eksik_kayit_tespit_edilir(tmp_path):
    bank_path = tmp_path / "ekstre.xlsx"
    netsis_path = tmp_path / "netsis_rapor.xlsx"
    _make_bank_excel(bank_path)
    _make_netsis_excel(netsis_path, eksik_satir=True)  # Netsis'e komisyon hiç işlenmemiş

    bank_records = BankStatementParser(bank_path).load()
    netsis_records = NetsisReportParser(netsis_path).load()
    result = ReconciliationEngine().reconcile(bank_records, netsis_records)

    assert result.mutabik is False
    assert result.fark == 11285.0 - 11300.0
    assert len(result.sadece_bankada) == 1
    assert result.sadece_bankada[0].aciklama == "Komisyon"
    assert len(result.sadece_netposte) == 0

    output_path = tmp_path / "mutabakat_raporu.xlsx"
    ReconciliationReportWriter().write(result, output_path)
    assert output_path.is_file()
