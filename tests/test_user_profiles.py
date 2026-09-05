import json

from app.core.input_profile import InputProfileStore
from app.core.output_profile import OutputProfileStore


def test_user_output_profile_overrides_packaged_profile(tmp_path, monkeypatch):
    monkeypatch.delenv("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG", raising=False)
    resource_config = tmp_path / "resource" / "config"
    user_config = tmp_path / "user" / "config"
    (resource_config / "output_profiles").mkdir(parents=True)
    (user_config / "output_profiles").mkdir(parents=True)
    base = {
        "id": "custom",
        "name": "Paket Profili",
        "description": "",
        "template_file": "base.xls",
        "columns": [],
    }
    custom = {**base, "name": "Kullanıcı Profili", "template_file": "C:/user/custom.xls"}
    (resource_config / "output_profiles" / "custom.json").write_text(json.dumps(base), encoding="utf-8")
    (user_config / "output_profiles" / "custom.json").write_text(json.dumps(custom), encoding="utf-8")

    profile = OutputProfileStore(resource_config, user_config).get("custom")

    assert profile.name == "Kullanıcı Profili"
    assert profile.template_file == "C:/user/custom.xls"


def test_user_output_profile_cannot_remove_approved_profile_lock(tmp_path, monkeypatch):
    monkeypatch.delenv("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG", raising=False)
    resource_config = tmp_path / "resource" / "config"
    user_config = tmp_path / "user" / "config"
    (resource_config / "output_profiles").mkdir(parents=True)
    (user_config / "output_profiles").mkdir(parents=True)
    base = {
        "id": "netsis",
        "name": "Onaylı",
        "description": "",
        "template_file": "base.xls",
        "protected": True,
        "columns": [],
    }
    custom = {**base, "name": "Yerel", "protected": False}
    (resource_config / "output_profiles" / "netsis.json").write_text(
        json.dumps(base), encoding="utf-8"
    )
    (user_config / "output_profiles" / "netsis.json").write_text(
        json.dumps(custom), encoding="utf-8"
    )

    profile = OutputProfileStore(resource_config, user_config).get("netsis")

    assert profile.name == "Yerel"
    assert profile.protected is True


def test_user_input_profile_is_loaded_from_writable_data_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG", raising=False)
    resource_config = tmp_path / "resource" / "config"
    user_config = tmp_path / "user" / "config"
    (resource_config / "input_profiles").mkdir(parents=True)
    (user_config / "input_profiles").mkdir(parents=True)
    columns = {
        "Banka": "banka",
        "Şube": "sube",
        "Tarih": "islem_tarihi",
        "Açıklama": "aciklama",
        "Tutar": "tutar",
        "Durum": "dekont_durumu",
        "Karşı Ad": "karsi_hesap_adi",
        "Karşı Kod": "karsi_hesap_kodu",
    }
    payload = {"id": "user_input", "name": "Kullanıcı", "description": "", "columns": columns}
    (user_config / "input_profiles" / "user_input.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    assert InputProfileStore(resource_config, user_config).get("user_input").name == "Kullanıcı"
