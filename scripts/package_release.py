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


LOCAL_ASSETS = (
    "config/local/bolge_kodlari.json",
    "config/local/output_profiles/netsis.json",
    "config/local/template_checksums.json",
    "templates/local/netsis_template.xls",
    "templates/local/netsis_template.xlsx",
    "templates/local/netsis_toplu_template.xls",
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
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=root
    ).decode("utf-8").split("\0")
    paths = sorted(set(filter(None, tracked)) | set(LOCAL_ASSETS))
    for name in paths:
        if not (root / name).is_file():
            raise FileNotFoundError(f"Paket dosyasi eksik: {name}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
        for name in paths:
            archive.write(root / name, name)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip():
            raise ValueError("Arsiv butunluk kontrolu basarisiz.")
        for name in paths:
            if hashlib.sha256(archive.read(name)).digest() != hashlib.sha256((root / name).read_bytes()).digest():
                raise ValueError(f"Paket icerigi kaynakla ayni degil: {name}")
    print(f"Dogrulandi: {destination.name} ({len(paths)} dosya)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    package_source(Path(__file__).resolve().parents[1], args.destination.resolve())
