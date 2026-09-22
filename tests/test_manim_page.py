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


def test_mukerrer_kaynak_reddi_yeni_success_operasyonu_olusturmaz(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from PySide6.QtWidgets import QMessageBox

    from app.core.operation_history import OperationHistory
    from app.modules.manim import page as manim_page

    source = tmp_path / "SENTETIK_MANIM.xlsx"
    source.touch()
    history = OperationHistory(tmp_path / "operations.sqlite3")

    class _FakeEngine:
        def __init__(self, files, **_kwargs):
            self.files = list(files)
            self.operation_id = None

        def prepare_configuration(self):
            return SimpleNamespace(fingerprint="synthetic-config")

        def find_duplicate_manim_files(self):
            return {
                source: {
                    "hash": "synthetic-hash",
                    "tarih": "2026-09-15T10:00:00",
                    "kayit_sayisi": 1,
                }
            }

    monkeypatch.setattr(manim_page, "ProcessingEngine", _FakeEngine)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.No,
    )

    page = manim_page.ManimModulePage(history)
    page.files = [source]
    page.start_process()

    assert history.recent() == []
    assert page._operation_id is None
    assert page._processing_thread is None
    assert page.start_button.isEnabled()
    assert "Tekrar işleme iptal edildi" in page.accounting_workspace.runtime_status.text()
    page.deleteLater()


def test_raw_fom_only_selection_routes_to_source_preparation(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from app.core.operation_history import OperationHistory
    from app.modules.manim import page as manim_page

    source = tmp_path / "SENTETIK_FOM_TAHSILAT.xlsx"
    source.touch()
    history = OperationHistory(tmp_path / "operations.sqlite3")

    class _Classifier:
        def classify(self, _files):
            return SimpleNamespace(manim_files=[], tahsilat_file=None, customer_file=None)

    monkeypatch.setattr(manim_page, "ManimInputClassifier", _Classifier)
    monkeypatch.setattr(
        manim_page.ReportEditingEngine,
        "classify_file",
        staticmethod(lambda _path: "collections"),
    )

    page = manim_page.ManimModulePage(history)
    routed = []
    page.source_preparation_requested.connect(lambda files: routed.append(tuple(files)))

    assert page._route_raw_fom_sources([source]) is True
    assert routed == [(source,)]
    assert page.files == []
    page.deleteLater()
