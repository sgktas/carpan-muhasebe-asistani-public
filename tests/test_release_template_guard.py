import hashlib
import json
from pathlib import Path
import runpy
import shutil

import pytest

from scripts.package_release import LOCAL_ASSETS, package_source, validate_templates


@pytest.fixture
def release_root(tmp_path):
    checksums = {}
    for name in LOCAL_ASSETS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"approved test template")
        if name.startswith("templates/local/"):
            checksums[name.removeprefix("templates/local/")] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / "config/local/template_checksums.json").write_text(json.dumps(checksums))
    (tmp_path / "config/local/output_profiles/netsis.json").write_text(json.dumps({
        "id": "netsis", "template_file": "netsis_template.xls",
    }))
    return tmp_path


def test_approved_templates_pass(release_root):
    validate_templates(release_root)


@pytest.mark.parametrize("template", [name for name in LOCAL_ASSETS if name.startswith("templates/local/")])
def test_changed_template_blocks_source_and_exe(release_root, template):
    (release_root / template).write_bytes(b"changed")
    output = release_root / "must_not_exist.zip"
    with pytest.raises(ValueError, match="sablon degismis"):
        package_source(release_root, output)
    assert not output.exists()

    project = Path(__file__).resolve().parents[1]
    (release_root / "scripts").mkdir()
    shutil.copyfile(project / "scripts/package_release.py", release_root / "scripts/package_release.py")
    with pytest.raises(ValueError, match="sablon degismis"):
        runpy.run_path(str(project / "muhasebe_asistani.spec"), init_globals={"SPECPATH": str(release_root)})


def test_missing_template_blocks_release(release_root):
    (release_root / "templates/local/netsis_template.xls").unlink()
    with pytest.raises(FileNotFoundError, match="eksik"):
        validate_templates(release_root)
