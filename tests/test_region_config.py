import json

from app.core.region_config import (
    RegionConfig,
    RegionConfigStore,
    active_region_config_path,
)


def _write_config(tmp_path, data):
    path = tmp_path / "bolge_kodlari.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_bolge_kodlarini_okuyor(tmp_path):
    path = _write_config(tmp_path, {
        "_aciklama": "bu bir yorum, bolge olarak sayilmamali",
        "BODRUM": {
            "kasa_kodu": 1001,
            "proje_kodu": 101,
            "ref_kodu": "R01",
            "banka_kodlari": {"GARANTI": "BANK-G-01", "YKB": "BANK-Y-01", "ZIRAAT": "BANK-Z-01"},
        },
    })
    config = RegionConfig(path)
    assert config.regions() == ("BODRUM",)
    assert config.kasa_kodu("BODRUM") == 1001
    assert config.proje_kodu("BODRUM") == 101
    assert config.banka_kodu("BODRUM", "GARANTI") == "BANK-G-01"


def test_alt_cizgili_anahtarlar_bolge_sayilmiyor(tmp_path):
    path = _write_config(tmp_path, {
        "_plasiyer_kodu": "00",
        "_genel_ref_kodu": "G01",
        "BODRUM": {"kasa_kodu": 1, "proje_kodu": 1, "ref_kodu": "G01", "banka_kodlari": {}},
    })
    config = RegionConfig(path)
    assert "_plasiyer_kodu" not in config.regions()
    assert "_genel_ref_kodu" not in config.regions()
    assert config.plasiyer_kodu() == "00"
    assert config.genel_ref_kodu() == "G01"


def test_dosya_yoksa_bos_doner(tmp_path):
    config = RegionConfig(tmp_path / "olmayan_dosya.json")
    assert config.regions() == ()
    assert config.kasa_kodu("BODRUM") is None


def test_tanimsiz_bolge_none_doner(tmp_path):
    path = _write_config(tmp_path, {"BODRUM": {"kasa_kodu": 1, "proje_kodu": 1, "ref_kodu": "G01", "banka_kodlari": {}}})
    config = RegionConfig(path)
    assert config.kasa_kodu("OLMAYAN_BOLGE") is None


def test_musteri_sube_etiketlerini_okuyor(tmp_path):
    path = _write_config(tmp_path, {
        "MUGLA": {
            "kasa_kodu": 1,
            "proje_kodu": 1,
            "ref_kodu": "G01",
            "banka_kodlari": {},
            "musteri_sube_etiketleri": ["MARMARIS"],
        },
    })
    config = RegionConfig(path)
    assert config.customer_branch_aliases("MUGLA") == ("MARMARIS",)
    assert config.customer_branch_aliases("OLMAYAN") == ("OLMAYAN",)


def test_aktif_bolgeler_siraya_gore_doner(tmp_path):
    path = _write_config(tmp_path, {
        "MUGLA": {"aktif": True, "sira": 4},
        "ANTALYA": {"aktif": True, "sira": 5},
        "NAZILLI": {"aktif": False, "sira": 3},
        "BODRUM": {"aktif": True, "sira": 1},
    })
    config = RegionConfig(path)
    assert config.regions() == ("BODRUM", "MUGLA", "ANTALYA")
    assert config.regions(include_inactive=True) == (
        "BODRUM", "NAZILLI", "MUGLA", "ANTALYA"
    )


def test_bolge_store_yeni_bolgeyi_kodsuz_degismeden_ekler(tmp_path):
    path = _write_config(tmp_path, {"_plasiyer_kodu": "00"})
    store = RegionConfigStore(path)
    saved = store.save_region("Isparta", {
        "aktif": True,
        "sira": 1,
        "kasa_kodu": 1101,
        "proje_kodu": 101,
        "ref_kodu": "R10",
        "banka_kodlari": {"garanti": "bank-g-10"},
        "musteri_sube_etiketleri": ["Isparta"],
    })
    config = store.config()
    assert saved == "ISPARTA"
    assert config.regions() == ("ISPARTA",)
    assert config.banka_kodu("ISPARTA", "GARANTI") == "BANK-G-10"
    assert config.kasa_kodu("ISPARTA") == 1101


def test_varsayilan_aktif_bolgeler_sekiz_bolgeyi_icerir():
    config = RegionConfig("config/bolge_kodlari.json")
    assert config.regions() == (
        "BODRUM", "FETHIYE", "SOKE", "MUGLA", "ANTALYA", "DENIZLI", "AYDIN", "NAZILLI"
    )


def test_manim_banka_ve_kod_sube_bolgeyi_tekil_bulur():
    config = RegionConfig("config/bolge_kodlari.json")
    assert config.find_region_by_manim_account("GARANTI", "TEST-HESAP-1007") == "AYDIN"
    assert config.find_region_by_manim_account("GARANTI", "TEST-HESAP-1008") == "NAZILLI"
    assert config.find_region_by_manim_account(
        "GARANTI", "Garanti-Aydın Ticari-1007-Vadesiz TRY"
    ) == "AYDIN"
    assert config.find_region_by_manim_account(
        "GARANTI", "Garanti-Nazilli Ticari-1008-Vadesiz TRY"
    ) == "NAZILLI"
    assert config.find_region_by_manim_account("YKB", "TEST-HESAP-2007") == "AYDIN"
    assert config.find_region_by_manim_account("YKB", "TEST-HESAP-2008") == "NAZILLI"
    assert config.find_region_by_manim_account("ZIRAAT", "TEST-HESAP-3007") == "AYDIN"
    assert config.find_region_by_manim_account("ZIRAAT", "TEST-HESAP-3008") == "NAZILLI"
    assert config.find_region_by_manim_account("GARANTI", "BILINMEYEN") is None


def test_eski_kullanici_ayarina_hesap_kodlari_eklenir_ve_nazilli_aktif_edilir(tmp_path):
    resource_config = tmp_path / "resource" / "config"
    data_root = tmp_path / "user"
    resource_config.mkdir(parents=True)
    user_config = data_root / "config" / "bolge_kodlari.json"
    user_config.parent.mkdir(parents=True)

    defaults = {
        "_config_surumu": 3,
        "NAZILLI": {
            "aktif": True,
            "sira": 8,
            "kasa_kodu": 1008,
            "manim_hesap_kodlari": {"GARANTI": "1008"},
        },
    }
    old_user_values = {
        "NAZILLI": {
            "aktif": False,
            "sira": 8,
            "kasa_kodu": 9999,
        },
    }
    (resource_config / "bolge_kodlari.json").write_text(
        json.dumps(defaults), encoding="utf-8"
    )
    user_config.write_text(json.dumps(old_user_values), encoding="utf-8")

    path = active_region_config_path(resource_config, data_root)
    config = RegionConfig(path)
    assert "NAZILLI" in config.regions()
    assert config.kasa_kodu("NAZILLI") == 9999
    assert config.manim_hesap_kodu("NAZILLI", "GARANTI") == "1008"
