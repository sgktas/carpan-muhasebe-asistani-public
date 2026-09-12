import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

from scripts.package_release import LOCAL_ASSETS, package_source
from scripts.release_integrity import (
    MANIFEST_NAME,
    ReleaseIntegrityError,
    collect_release_paths,
    collect_untracked_runtime_sources,
    verify_local_imports,
)


def _write_release_root(root: Path) -> None:
    for name in LOCAL_ASSETS:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"approved release template")
    checksums = {
        name.removeprefix("templates/local/"): hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in LOCAL_ASSETS if name.startswith("templates/local/")
    }
    (root / "config/local/template_checksums.json").write_text(json.dumps(checksums), encoding="utf-8")
    (root / "config/local/output_profiles/netsis.json").write_text(
        json.dumps({"id": "netsis", "template_file": "netsis_template.xls"}), encoding="utf-8"
    )
    (root / "app").mkdir()
    (root / "app/__init__.py").write_text("", encoding="utf-8")
    (root / "app/main.py").write_text("from app import __name__\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests/test_release_template_guard.py").write_text("def test_collection_smoke():\n    assert True\n", encoding="utf-8")
    (root / "scripts").mkdir(exist_ok=True)
    # The release script itself is only needed as an allowed source file in this fixture.
    (root / "scripts/package_release.py").write_text("", encoding="utf-8")
    (root / "scripts/release_integrity.py").write_text("", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)


def test_complete_release_contains_manifest_and_runtime_sources(tmp_path):
    _write_release_root(tmp_path)
    destination = tmp_path / "release.zip"
    package_source(tmp_path, destination)
    with zipfile.ZipFile(destination) as archive:
        assert MANIFEST_NAME in archive.namelist()
        assert "app/main.py" in archive.namelist()
        manifest = json.loads(archive.read(MANIFEST_NAME))
    assert manifest["runtime_python_source_count"] == manifest["packaged_runtime_python_count"]
    assert manifest["tracked_file_count"] > 0
    assert "tracked_source_count" not in manifest


def test_missing_local_import_is_reported():
    with pytest.raises(ReleaseIntegrityError, match="app.core.publication_journal"):
        verify_local_imports(
            {"app/__init__.py", "app/core/__init__.py", "app/core/processing_engine.py"},
            lambda name: "from app.core.publication_journal import PublicationJournal" if name.endswith("processing_engine.py") else "",
        )


def test_existing_relative_local_import_is_accepted():
    paths = {
        "app/__init__.py",
        "app/core/__init__.py",
        "app/core/consumer.py",
        "app/core/publication_journal.py",
    }
    verify_local_imports(
        paths,
        lambda name: "from .publication_journal import PublicationJournal" if name.endswith("consumer.py") else "",
    )


def test_missing_relative_local_import_is_reported():
    paths = {"app/__init__.py", "app/core/__init__.py", "app/core/consumer.py"}
    with pytest.raises(ReleaseIntegrityError, match="app.core.publication_journal"):
        verify_local_imports(
            paths,
            lambda name: "from .publication_journal import PublicationJournal" if name.endswith("consumer.py") else "",
        )


def test_relative_import_at_top_level_boundary_is_resolved():
    paths = {
        "app/__init__.py",
        "app/shared.py",
        "app/core/__init__.py",
        "app/core/sub/__init__.py",
        "app/core/sub/module.py",
    }
    verify_local_imports(
        paths,
        lambda name: "from ...shared import foo" if name.endswith("module.py") else "",
    )


def test_relative_import_beyond_top_level_package_is_reported():
    paths = {"app/__init__.py", "app/module.py"}
    with pytest.raises(ReleaseIntegrityError, match="Invalid relative import: attempted beyond top-level package"):
        verify_local_imports(
            paths,
            lambda name: "from ..foo import Bar" if name.endswith("module.py") else "",
        )


def test_untracked_runtime_python_blocks_release(tmp_path):
    _write_release_root(tmp_path)
    extra = tmp_path / "app/core/publication_journal.py"
    extra.parent.mkdir(exist_ok=True)
    extra.write_text("", encoding="utf-8")
    assert "app/core/publication_journal.py" in collect_untracked_runtime_sources(tmp_path)
    with pytest.raises(ReleaseIntegrityError, match="Untracked runtime source"):
        package_source(tmp_path, tmp_path / "blocked.zip")


def test_untracked_non_runtime_note_does_not_block_release(tmp_path):
    _write_release_root(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "docs/private_notes.txt").write_text("safe", encoding="utf-8")
    (tmp_path / "tests/debug_output.json").write_text("safe", encoding="utf-8")
    (tmp_path / "assets/debug_output.txt").write_text("safe", encoding="utf-8")
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch/local_notes.txt").write_text("safe", encoding="utf-8")
    assert not collect_untracked_runtime_sources(tmp_path)
    destination = tmp_path / "allowed.zip"
    package_source(tmp_path, destination)
    with zipfile.ZipFile(destination) as archive:
        assert "docs/private_notes.txt" not in archive.namelist()
        assert "tests/debug_output.json" not in archive.namelist()
        assert "assets/debug_output.txt" not in archive.namelist()


def test_tracked_allowlisted_docs_tests_and_assets_are_packaged(tmp_path):
    _write_release_root(tmp_path)
    contents = {
        "docs/architecture.md": "tracked",
        "tests/test_tracked_example.py": "def test_tracked_example():\n    assert True\n",
        "assets/icon.txt": "tracked",
    }
    for name, content in contents.items():
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "docs", "tests", "assets"], cwd=tmp_path, check=True)
    paths = collect_release_paths(tmp_path, LOCAL_ASSETS)
    assert {"docs/architecture.md", "tests/test_tracked_example.py", "assets/icon.txt"} <= paths
    destination = tmp_path / "tracked.zip"
    package_source(tmp_path, destination)
    with zipfile.ZipFile(destination) as archive:
        assert {"docs/architecture.md", "tests/test_tracked_example.py", "assets/icon.txt"} <= set(archive.namelist())
