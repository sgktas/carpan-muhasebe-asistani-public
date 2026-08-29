from pathlib import Path

from app.core.app_paths import _user_data_root, _user_output_root


def test_data_root_environment_override(tmp_path, monkeypatch):
    target = tmp_path / "ozel_veri_klasoru"
    monkeypatch.setenv("MUHASEBE_ASISTANI_DATA_DIR", str(target))

    assert _user_data_root() == target.resolve()


def test_output_root_environment_override(tmp_path, monkeypatch):
    target = tmp_path / "gorunur_ciktilar"
    monkeypatch.setenv("MUHASEBE_ASISTANI_OUTPUT_DIR", str(target))

    assert _user_output_root() == target.resolve()


def test_non_windows_output_is_under_documents(monkeypatch):
    monkeypatch.delenv("MUHASEBE_ASISTANI_OUTPUT_DIR", raising=False)
    monkeypatch.setattr("app.core.app_paths.sys.platform", "linux")

    output = _user_output_root()

    assert output == Path.home() / "Documents" / "Çarpan Muhasebe Asistanı" / "Çıktılar"
