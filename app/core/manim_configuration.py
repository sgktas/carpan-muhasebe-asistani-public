"""Capture and resolve the settings actually used by one MANİM run.

Snapshots stay in the local company workspace, not the central API. They
contain configuration only, never source workbooks or customer mappings.
"""
from dataclasses import asdict
from pathlib import Path

from app.core.active_profile_store import ActiveProfileStore
from app.core.customer_list_profile import CustomerListProfile, CustomerListProfileStore
from app.core.execution_configuration import ConfigurationSnapshot
from app.core.input_profile import InputProfile, InputProfileStore
from app.core.output_profile import OutputColumn, OutputProfile, OutputProfileStore
from app.core.region_config import RegionConfig


# Increment when routing/matching semantics change. Settings revisions are
# content-addressed separately; this is not a template approval/version.
MANIM_RULESET_VERSION = 1


def capture_manim_configuration(
    resource_root: Path, data_root: Path, region_config: RegionConfig,
) -> ConfigurationSnapshot:
    selections = ActiveProfileStore(data_root).selection_snapshot()
    config_dir, user_dir = resource_root / "config", data_root / "config"
    output_store = OutputProfileStore(config_dir, user_dir)
    return ConfigurationSnapshot.create("manim_transfer", {
        "schema_version": 1,
        "ruleset_version": MANIM_RULESET_VERSION,
        "regions": region_config.snapshot(),
        "input_profile": asdict(InputProfileStore(config_dir, user_dir).get_or_default(
            selections["input_profile_id"])),
        "output_profile": asdict(output_store.get_or_default(selections["output_profile_id"])),
        "reference_output_profile": asdict(output_store.get_or_default(
            selections["reference_output_profile_id"], default_id="netsis_virman_toplu")),
        "customer_list_profile": asdict(CustomerListProfileStore(config_dir, user_dir).get_or_default(
            selections["customer_list_profile_id"])),
    })


def resolve_manim_configuration(
    snapshot: ConfigurationSnapshot, region_path: Path,
) -> tuple[RegionConfig, InputProfile, OutputProfile, OutputProfile, CustomerListProfile]:
    payload = snapshot.payload()
    if (snapshot.module_id != "manim_transfer" or payload.get("schema_version") != 1
            or payload.get("ruleset_version") != MANIM_RULESET_VERSION):
        raise ValueError("MANİM işlem ayarı bu uygulama sürümüyle uyumlu değil.")

    def output_profile(values: dict) -> OutputProfile:
        values = dict(values)
        values["columns"] = tuple(OutputColumn(**column) for column in values["columns"])
        return OutputProfile(**values)

    customer = dict(payload["customer_list_profile"])
    customer["aliases"] = {key: tuple(value) for key, value in customer["aliases"].items()}
    return (
        RegionConfig(region_path, snapshot=payload["regions"]),
        InputProfile(**payload["input_profile"]),
        output_profile(payload["output_profile"]),
        output_profile(payload["reference_output_profile"]),
        CustomerListProfile(**customer),
    )
