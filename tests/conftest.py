import os
import shutil
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG", "1")


@pytest.fixture
def synthetic_project(tmp_path):
    """Gerçek proje kökünün templates/ ve config/ klasörlerini kullanan,
    ama girdi/çıktı dosyaları için ayrı (geçici) bir klasör kuran test ortamı.

    Dönüş: (manim_path, tahsilat_path, customer_path, project_root)
    """
    project_root = tmp_path
    (project_root / "templates").mkdir()
    (project_root / "config").mkdir()
    shutil.copy(PROJECT_ROOT / "config" / "bolge_kodlari.json", project_root / "config" / "bolge_kodlari.json")
    shutil.copytree(PROJECT_ROOT / "config" / "input_profiles", project_root / "config" / "input_profiles")
    shutil.copytree(PROJECT_ROOT / "config" / "output_profiles", project_root / "config" / "output_profiles")
    shutil.copytree(PROJECT_ROOT / "config" / "customer_list_profiles", project_root / "config" / "customer_list_profiles")

    input_dir = tmp_path / "input"
    input_dir.mkdir()

    manim_path = input_dir / "TEST_BODRUM_Manim.xlsx"
    pd.DataFrame([
        {
            "Banka": "Garanti", "Kod - Şube": "123", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "NORMAL ODEME", "Tutar": 1000.0,
            "Dekont Durumu": "Aktarıldı", "Karşı Hesap Adı": "ABC LTD", "Karşı Hesap Kodu": "ABC001",
        },
        {
            "Banka": "Garanti", "Kod - Şube": "123", "İşlem Tarihi": pd.Timestamp("2026-07-15"),
            "Açıklama": "ROTA 104 ODEME ONAY TEST", "Tutar": 2500.0,
            "Dekont Durumu": "Ödeme Onaylandı", "Karşı Hesap Adı": "", "Karşı Hesap Kodu": "",
        },
        {
            "Banka": "Garanti", "Kod - Şube": "123", "İşlem Tarihi": pd.Timestamp("2026-07-16"),
            "Açıklama": "REFERANSLI TEST", "Tutar": 777.0,
            "Dekont Durumu": "Referanslı", "Karşı Hesap Adı": "", "Karşı Hesap Kodu": "",
        },
    ]).to_excel(manim_path, index=False)

    tahsilat_path = input_dir / "TEST_tahsilat_raporu.xlsx"
    pd.DataFrame([
        {"Müşteri Kodu": "XYZ999", "Müşteri İsmi": "XYZ FIRMASI", "Belge Tarihi": pd.Timestamp("2026-07-15"), "Tutar": 999999},
    ]).to_excel(tahsilat_path, index=False)

    customer_path = input_dir / "musteri_listesi.xlsx"
    pd.DataFrame([
        {"Müşteri Kodu": "ABC001", "Ünvan": "ABC LTD", "Vergi No": "2222222222", "Şube": "BODRUM"},
        {"Müşteri Kodu": "XYZ999", "Ünvan": "XYZ FIRMASI", "Vergi No": "1111111111", "Şube": "BODRUM"},
    ]).to_excel(customer_path, index=False)

    return manim_path, tahsilat_path, customer_path, project_root
