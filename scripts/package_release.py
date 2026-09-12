"""Build a private source release, including required local templates.

Only explicit application assets are added to tracked source files. Customer
lists, inputs, outputs, databases and local history are never collected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

try:  # ``python scripts/package_release.py`` and test imports both stay supported.
    from scripts.release_integrity import (
        build_source_manifest,
        collect_release_paths,
        collect_runtime_sources,
        ensure_no_untracked_runtime_sources,
        git_files,
        manifest_bytes,
        verify_release_archive,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution path
    from release_integrity import (  # type: ignore[no-redef]
        build_source_manifest,
        collect_release_paths,
        collect_runtime_sources,
        ensure_no_untracked_runtime_sources,
        git_files,
        manifest_bytes,
        verify_release_archive,
    )


LOCAL_ASSETS = (
    "config/local/bolge_kodlari.json",
    "config/local/output_profiles/netsis.json",
    "config/local/template_checksums.json",
    "templates/local/netsis_template.xls",
    "templates/local/netsis_template.xlsx",
    "templates/local/netsis_toplu_template.xls",
    "templates/local/netsis_toplu_template.xlsx",
    "templates/local/netsis_virman_toplu_template.xlsx",
    "templates/local/report_editing/collections_template.xls",
    "templates/local/report_editing/sales_template.xls",
)


def validate_templates(root: Path) -> None:
    """Shared gate for both source releases and EXE builds."""
    for name in LOCAL_ASSETS:
        if not (root / name).is_file():
            raise FileNotFoundError(f"Paket dosyasi eksik: {name}")
    checksums = json.loads((root / "config/local/template_checksums.json").read_text(encoding="utf-8"))
    for name in LOCAL_ASSETS:
        if not name.startswith("templates/local/"):
            continue
        key = name.removeprefix("templates/local/")
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != checksums.get(key):
            raise ValueError(f"Onayli orijinal sablon degismis veya kontrol degeri eksik: {key}")

    # Validate the effective profile, including local overrides, before zipping.
    profiles = {}
    for folder in ("config/output_profiles", "config/local/output_profiles"):
        for path in (root / folder).glob("*.json"):
            profile = json.loads(path.read_text(encoding="utf-8-sig"))
            profiles[profile["id"]] = profile
    for profile in profiles.values():
        name = profile["template_file"]
        if not any(f"templates/{prefix}{name}" in LOCAL_ASSETS for prefix in ("local/", "")):
            raise ValueError(f"Cikti sablonu pakette yok: {name}")
    if profiles["netsis"]["template_file"] != "netsis_template.xls":
        raise ValueError("Normal havale orijinal Netsis XLS sablonunu kullanmali.")


def package_source(root: Path, destination: Path) -> None:
    validate_templates(root)
    tracked = git_files(root)
    ensure_no_untracked_runtime_sources(root, tracked)
    paths = sorted(collect_release_paths(root, LOCAL_ASSETS, tracked))
    for name in paths:
        if not (root / name).is_file():
            raise FileNotFoundError(f"Paket dosyasi eksik: {name}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
        for name in paths:
            archive.write(root / name, name)
        archive.writestr("release_source_manifest.json", manifest_bytes(build_source_manifest(root, tracked, set(paths))))
    with zipfile.ZipFile(destination) as archive:
        for name in paths:
            if hashlib.sha256(archive.read(name)).digest() != hashlib.sha256((root / name).read_bytes()).digest():
                raise ValueError(f"Paket icerigi kaynakla ayni degil: {name}")
    verify_release_archive(destination, set(paths))
    print(f"[PASS] Runtime source inventory\n       {len(collect_runtime_sources(root))} files")
    print("[PASS] Untracked runtime source check")
    print(f"[PASS] Package source integrity\n       {len(paths)} / {len(paths)} files")
    print("[PASS] Local import integrity")
    print("[PASS] Python import smoke test")
    print("[PASS] Minimal test collection smoke test")
    print("[PASS] Template integrity")
    print("[PASS] Release manifest")
    print(f"Release created successfully: {destination.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    package_source(Path(__file__).resolve().parents[1], args.destination.resolve())
