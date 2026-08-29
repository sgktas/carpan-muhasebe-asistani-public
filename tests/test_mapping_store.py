from app.core.mapping_store import MappingStore


def test_kaydet_ve_oku_tek_kod(tmp_path):
    store = MappingStore(tmp_path / "mapping.json")
    store.set("ABC ACIKLAMA", "C001")
    assert store.get("ABC ACIKLAMA") == "C001"


def test_anahtar_normalizasyonu_bosluk_ve_buyuk_kucuk_harf(tmp_path):
    """Farklı boşluk/büyük-küçük harf ile yazılan aynı açıklama aynı kayda ulaşmalı."""
    store = MappingStore(tmp_path / "mapping.json")
    store.set("abc   Aciklama", "C001")
    assert store.get("ABC ACIKLAMA") == "C001"


def test_kalici_olarak_diskte_saklaniyor(tmp_path):
    path = tmp_path / "mapping.json"
    store1 = MappingStore(path)
    store1.set("KALICI TEST", "C777")

    store2 = MappingStore(path)  # yeni bir örnek, aynı dosyayı tekrar okur
    assert store2.get("KALICI TEST") == "C777"


def test_bolunmus_liste_formati_saklanabiliyor(tmp_path):
    store = MappingStore(tmp_path / "mapping.json")
    store.set("SUBELI", [{"musteri_kodu": "C001", "tutar": 100.5}])
    assert store.get("SUBELI") == [{"musteri_kodu": "C001", "tutar": 100.5}]


def test_olmayan_anahtar_none_doner(tmp_path):
    store = MappingStore(tmp_path / "mapping.json")
    assert store.get("HIC OLMAYAN BIR ACIKLAMA") is None
