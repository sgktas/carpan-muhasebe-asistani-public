from pathlib import Path

import pandas as pd

from app.core.region_config import RegionConfig


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "bolge_kodlari.json"


def test_find_region_by_bank_code():
    config = RegionConfig(CONFIG_PATH)
    assert config.find_region_in_text("Banka Hesap Kodu BANK-G-01 BODRUM-BAT GARANTİ") == "BODRUM"


def test_find_region_by_alias_name():
    config = RegionConfig(CONFIG_PATH)
    assert config.find_region_in_text("Müşteri şubesi: FETHIYE") == "FETHIYE"


def test_bank_code_takes_priority_over_coincidental_alias():
    # 'ANTALYA' kelimesi metinde geciyor (banka subesi), ama BANK-G-01 kodu
    # (Bodrum'a ait) da ayni metinde varsa, kod her zaman kazanmali.
    config = RegionConfig(CONFIG_PATH)
    text = "Şube: ANTALYA TİCARİ ... Banka Hesap Kodu BANK-G-01 BODRUM-BAT"
    assert config.find_region_in_text(text) == "BODRUM"


def test_tanimayan_metin_icin_none_doner():
    config = RegionConfig(CONFIG_PATH)
    assert config.find_region_in_text("hiçbir bölgeyle ilgisi olmayan metin") is None


def test_detect_region_combines_both_files_bank_letterhead_alone_would_mislead(tmp_path):
    from app.modules.bank_reconciliation.page import _detect_region

    bank_path = tmp_path / "ekstre.xlsx"
    bank_rows_before = [
        ["T. GARANTİ BANKASI A.Ş.", None, None, None],
        ["Şube", "ANTALYA TİCARİ", None, None],
        [None, None, None, None],
    ]
    bank_header = ["Tarih", "Açıklama", "Tutar", "Bakiye"]
    bank_data = [["01.06.2026", "Devir", "1000,00", "1000,00"]]
    with pd.ExcelWriter(bank_path) as writer:
        pd.DataFrame(bank_rows_before + [bank_header] + bank_data).to_excel(writer, index=False, header=False)

    netsis_path = tmp_path / "netsis.xlsx"
    netsis_rows_before = [
        ["Banka Hesap Kodu BANK-G-01 BODRUM-BAT GARANTİ TEST HESABI", None, None, None, None],
    ]
    netsis_header = ["Tarih", "Açıklama", "Borç", "Alacak", "Bakiye"]
    netsis_data = [["01.06.2026", "Devir", 1000.0, 0.0, 1000.0]]
    with pd.ExcelWriter(netsis_path) as writer:
        pd.DataFrame(netsis_rows_before + [netsis_header] + netsis_data).to_excel(writer, index=False, header=False)

    assert _detect_region(bank_path, netsis_path) == "BODRUM"
