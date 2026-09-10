from dataclasses import asdict
import json
from types import SimpleNamespace

import pytest

from app.core.active_profile_store import ActiveProfileStore
from app.core.execution_configuration import ConfigurationSnapshot
from app.core.manim_configuration import resolve_manim_configuration
from app.core.processing_engine import ProcessingEngine


def test_roundtrip_preserves_profiles_codes_and_order(synthetic_project):
    *files, root = synthetic_project
    engine = ProcessingEngine(files, root)
    snapshot = engine.prepare_configuration()
    region, input_profile, output, reference, customer = resolve_manim_configuration(
        snapshot, root / "missing.json",
    )
    assert region.snapshot() == engine.region_config.snapshot()
    assert region.regions() == engine.REGIONS
    assert output.profile_id == "netsis"
    assert reference.profile_id == "netsis_virman_toplu"
    assert input_profile.profile_id == "manim"
    assert customer.profile_id == "f1_fom"
    assert json.loads(json.dumps(asdict(output))) == snapshot.payload()["output_profile"]
    input_profile.columns.clear()
    region.entry("BODRUM")["banka_kodlari"].clear()
    fresh = resolve_manim_configuration(snapshot, root / "missing.json")
    assert fresh[0].banka_kodu("BODRUM", "GARANTI") == "BANK-G-01"
    assert fresh[1].columns


def test_run_uses_captured_settings_after_live_settings_change(synthetic_project, monkeypatch):
    *files, root = synthetic_project
    engine = ProcessingEngine(files, root)
    snapshot = engine.prepare_configuration()
    ActiveProfileStore(root).set_output_profile_id("does-not-exist")
    (root / "config" / "bolge_kodlari.json").write_text("{}", encoding="utf-8")
    (root / "config" / "input_profiles" / "manim.json").write_text("{}", encoding="utf-8")
    captured = {}

    def write(_service, plan):
        captured["plan"] = plan
        return SimpleNamespace(output_dir=None, created_files=[], review_file=None,
                               invalid_file=None, odeme_onaylandi_path=None, logs=[])

    monkeypatch.setattr("app.core.manim_output_service.ManimOutputService.write", write)
    result = engine.run()
    assert result.produced_netsis_records == 1
    assert result.skipped_payment == 1
    assert captured["plan"].output_profile.profile_id == "netsis"
    assert engine.region_config.banka_kodu("BODRUM", "GARANTI") == "BANK-G-01"
    assert engine.prepare_configuration() is snapshot


def test_new_engine_captures_changed_selection(synthetic_project):
    *files, root = synthetic_project
    first = ProcessingEngine(files, root).prepare_configuration()
    ActiveProfileStore(root).set_output_profile_id("netsis_toplu")
    second = ProcessingEngine(files, root).prepare_configuration()
    assert first.fingerprint != second.fingerprint
    assert first.payload()["output_profile"]["profile_id"] == "netsis"
    assert second.payload()["output_profile"]["profile_id"] == "netsis_toplu"


def test_incompatible_ruleset_cannot_silently_execute(synthetic_project):
    *files, root = synthetic_project
    payload = ProcessingEngine(files, root).prepare_configuration().payload()
    payload["ruleset_version"] = -1
    with pytest.raises(ValueError, match="uyumlu değil"):
        resolve_manim_configuration(ConfigurationSnapshot.create("manim_transfer", payload), root / "config.json")
