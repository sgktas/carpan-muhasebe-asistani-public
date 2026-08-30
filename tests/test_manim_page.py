from pathlib import Path

from app.modules.manim.page import ManimModulePage


class _FakeCustomerListCache:
    cached_path: Path | None = None

    def __init__(self, _data_root):
        pass

    def get(self):
        return self.cached_path


def test_girdi_aciklamasi_sabit_manim_sayisi_soylemez(monkeypatch):
    monkeypatch.setattr(
        "app.modules.manim.page.CustomerListCache",
        _FakeCustomerListCache,
    )

    _FakeCustomerListCache.cached_path = None
    first_use = ManimModulePage._input_files_description()
    assert "Müşteri Listesi modülünden" in first_use
    assert "4 MANİM" not in first_use

    _FakeCustomerListCache.cached_path = Path("hafizadaki_musteri_listesi.xlsx")
    cached = ManimModulePage._input_files_description()
    assert "son müşteri listesi hafızadan kullanılır" in cached
    assert "4 MANİM" not in cached
