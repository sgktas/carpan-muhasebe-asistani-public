from datetime import datetime
from pathlib import Path

import xlrd
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.personnel_list_cache import PersonnelListCache
from app.core.region_config import RegionConfig
from app.models.records import ManimRecord
from app.ui.odeme_onaylandi_review_dialog import OdemeOnaylandiReviewDialog

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "bolge_kodlari.json"

_app = QApplication.instance() or QApplication([])


def test_bolge_duzeltme_dogru_kasa_ve_proje_kodu_uretir(tmp_path, monkeypatch):
    # Bloke eden mesaj kutularini test icin devre disi birak.
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))

    region_config = RegionConfig(CONFIG_PATH)
    personnel_cache = PersonnelListCache(tmp_path)
    record = ManimRecord(
        banka="Garanti", sube="SOKE", islem_tarihi=datetime(2026, 8, 1, 10, 0),
        aciklama="CEP ŞUBE-HVL- -TEST MUSTERI", tutar=50000.0, dekont_durumu="Aktarıldı",
        karsi_hesap_adi="", karsi_hesap_kodu="", kaynak_dosya="test.xlsx", kaynak_satir=1,
    )
    # Bankacı hatası: kayıt yanlışlıkla BODRUM bölgesi olarak işlenmiş.
    items = [(record, "BODRUM", "garanti")]
    output_path = tmp_path / "odeme_onaylandi.xls"

    dialog = OdemeOnaylandiReviewDialog(items, output_path, region_config, personnel_cache)
    assert dialog._region_combos[0].currentText() == "BODRUM"

    dialog._region_combos[0].setCurrentText("SOKE")
    dialog._save()

    workbook = xlrd.open_workbook(str(output_path))
    sheet = workbook.sheet_by_index(0)
    row = dict(zip(sheet.row_values(0), sheet.row_values(1)))

    assert row["KasaKodu"] == region_config.kasa_kodu("SOKE")
    assert row["ProjeKodu"] == region_config.proje_kodu("SOKE")


def test_bolge_degismezse_dosya_yeniden_yazilmaz(tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))

    region_config = RegionConfig(CONFIG_PATH)
    personnel_cache = PersonnelListCache(tmp_path)
    record = ManimRecord(
        banka="Garanti", sube="SOKE", islem_tarihi=datetime(2026, 8, 1, 10, 0),
        aciklama="Test", tutar=1000.0, dekont_durumu="Aktarıldı",
        karsi_hesap_adi="", karsi_hesap_kodu="", kaynak_dosya="test.xlsx", kaynak_satir=1,
    )
    items = [(record, "SOKE", "garanti")]
    output_path = tmp_path / "odeme_onaylandi.xls"

    dialog = OdemeOnaylandiReviewDialog(items, output_path, region_config, personnel_cache)
    dialog._save()  # bolge degistirilmedi

    assert not output_path.exists()


def test_personel_onerisi_uyumsuzlugu_dogru_bulur(tmp_path, monkeypatch):
    import pandas as pd

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))

    region_config = RegionConfig(CONFIG_PATH)
    personnel_cache = PersonnelListCache(tmp_path)

    personnel_path = tmp_path / "personel.xlsx"
    pd.DataFrame([
        {"ŞUBE": "SIMSEK-ANTALYA", "PERSONEL": "AHMET CAGDAS"},
        {"ŞUBE": "SIMSEK-BODRUM", "PERSONEL": "MEHMET YILMAZ"},
    ]).to_excel(personnel_path, index=False)
    personnel_cache.save(personnel_path)

    # Aciklamada ANTALYA personeli AHMET CAGDAS geciyor, ama kayit SOKE olarak islenmis.
    record = ManimRecord(
        banka="Garanti", sube="SOKE", islem_tarihi=datetime(2026, 8, 1, 10, 0),
        aciklama="CEP ŞUBE-HVL- -AHMET CAGDAS", tutar=1000.0, dekont_durumu="Aktarıldı",
        karsi_hesap_adi="", karsi_hesap_kodu="", kaynak_dosya="test.xlsx", kaynak_satir=1,
    )
    items = [(record, "SOKE", "garanti")]
    output_path = tmp_path / "odeme_onaylandi.xls"

    dialog = OdemeOnaylandiReviewDialog(items, output_path, region_config, personnel_cache)
    assert dialog.personnel_list is not None
    oneri_item = dialog.table.item(0, 7)
    assert "ANTALYA" in oneri_item.text()
    assert "AHMET CAGDAS" in oneri_item.text()


def test_kasa_ve_proje_kodu_dogrudan_elle_degistirilebilir(tmp_path, monkeypatch):
    """Asıl istenen özellik: bölgeye dokunmadan, Kasa Kodu/Proje Kodu'nu
    doğrudan elle değiştirip yazdırabilmek."""
    from PySide6.QtWidgets import QTableWidgetItem

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))

    region_config = RegionConfig(CONFIG_PATH)
    personnel_cache = PersonnelListCache(tmp_path)
    record = ManimRecord(
        banka="Garanti", sube="SOKE", islem_tarihi=datetime(2026, 8, 1, 10, 0),
        aciklama="Test", tutar=1000.0, dekont_durumu="Aktarıldı",
        karsi_hesap_adi="", karsi_hesap_kodu="", kaynak_dosya="test.xlsx", kaynak_satir=1,
    )
    items = [(record, "SOKE", "garanti")]
    output_path = tmp_path / "odeme_onaylandi.xls"

    dialog = OdemeOnaylandiReviewDialog(items, output_path, region_config, personnel_cache)
    # Bolge SOKE olarak kalsin, ama Kasa Kodu/Proje Kodu'nu dogrudan ozel bir
    # degere elle degistir (bolgenin kendi degerlerinden farkli).
    dialog.table.setItem(0, 5, QTableWidgetItem("99999"))
    dialog.table.setItem(0, 6, QTableWidgetItem("888"))
    dialog._save()

    workbook = xlrd.open_workbook(str(output_path))
    sheet = workbook.sheet_by_index(0)
    row = dict(zip(sheet.row_values(0), sheet.row_values(1)))

    assert row["KasaKodu"] == 99999
    assert row["ProjeKodu"] == 888
