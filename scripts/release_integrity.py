"""Release kaynak paketleri için küçük, bağımsız bütünlük kontrolleri.

Bu modül muhasebe akışını çalıştırmaz. Yalnızca kaynak paketin uygulamayı
import edebilecek eksiksiz ve güvenli bir envantere sahip olduğunu doğrular.
"""
from __future__ import annotations

import ast
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


RUNTIME_SOURCE_DIRS = (
    "app",
    "scripts",
    "platform_api/carpan_platform",
    "platform_api/scripts",
)
SOURCE_DIRS = RUNTIME_SOURCE_DIRS + ("tests", "docs", "assets", "config/output_profiles")
ROOT_FILES = (
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "README.md",
    "SECURITY.md",
    "derle.bat",
    "muhasebe_asistani.spec",
    "pytest.ini",
    "requirements.txt",
    "platform_api/README.md",
    "platform_api/requirements.txt",
)
MANIFEST_NAME = "release_source_manifest.json"


class ReleaseIntegrityError(RuntimeError):
    """Kaynak paketin dağıtıma güvenle uygun olmadığını bildirir."""


def git_files(root: Path) -> set[str]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=root, stderr=subprocess.DEVNULL
        ).decode("utf-8")
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseIntegrityError("Release için Git çalışma ağacı gerekli.") from error
    return {name.replace("\\", "/") for name in output.split("\0") if name}


def _normal(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_runtime_python(name: str) -> bool:
    return name.endswith(".py") and any(
        name == folder or name.startswith(f"{folder}/") for folder in RUNTIME_SOURCE_DIRS
    )


def collect_runtime_sources(root: Path) -> set[str]:
    """Uygulamanın çalışırken çağırabileceği yerel Python kaynaklarını toplar."""
    paths: set[str] = set()
    for folder in RUNTIME_SOURCE_DIRS:
        base = root / folder
        if not base.is_dir():
            continue
        paths.update(_normal(path, root) for path in base.rglob("*.py") if path.is_file())
    return paths


def collect_release_paths(
    root: Path, local_assets: tuple[str, ...], tracked: set[str] | None = None
) -> set[str]:
    """Yalnız takip edilen izinli dosyalardan güvenli paylaşılabilir paket oluşturur."""
    tracked = git_files(root) if tracked is None else tracked
    paths: set[str] = set()
    for folder in SOURCE_DIRS:
        base = root / folder
        if base.is_dir():
            paths.update(
                name
                for path in base.rglob("*")
                if path.is_file() and (name := _normal(path, root)) in tracked
            )
    paths.update(name for name in ROOT_FILES if name in tracked and (root / name).is_file())
    paths.update(local_assets)
    return paths


def collect_untracked_runtime_sources(root: Path, tracked: set[str] | None = None) -> set[str]:
    tracked = git_files(root) if tracked is None else tracked
    return collect_runtime_sources(root) - tracked


def ensure_no_untracked_runtime_sources(root: Path, tracked: set[str] | None = None) -> None:
    missing = sorted(collect_untracked_runtime_sources(root, tracked))
    if missing:
        formatted = "\n".join(f"- {name}" for name in missing)
        raise ReleaseIntegrityError(
            "RELEASE BLOCKED\n\nUntracked runtime source files detected:\n"
            f"{formatted}\n\nFix: Add/commit these files before releasing, or move non-runtime code outside the runtime source tree."
        )


def _module_name(path: str) -> str | None:
    if not path.endswith(".py"):
        return None
    source = path[:-3]
    # platform_api/carpan_platform is installed/imported as ``carpan_platform``;
    # it is not a child package of the repository's ``platform_api`` folder.
    if source.startswith("platform_api/carpan_platform/"):
        source = source.removeprefix("platform_api/")
    normalized = source.replace("/", ".")
    return normalized[:-9] if normalized.endswith(".__init__") else normalized


def _local_modules(paths: set[str]) -> set[str]:
    modules = {name for path in paths if (name := _module_name(path))}
    for module in tuple(modules):
        parts = module.split(".")
        modules.update(".".join(parts[:index]) for index in range(1, len(parts)))
    return modules


def _relative_import_modules(path: str, node: ast.ImportFrom) -> tuple[set[str], str | None]:
    """Bir relative importu çözer veya paket sınırı ihlalini bildirir."""
    module = _module_name(path)
    if module is None:
        return set(), None
    current_package = module if path.endswith("/__init__.py") else module.rpartition(".")[0]
    parts = [part for part in current_package.split(".") if part]
    parent_count = node.level - 1
    if parent_count >= len(parts):
        return set(), "Invalid relative import: attempted beyond top-level package"
    base = ".".join(parts[:len(parts) - parent_count])
    if node.module:
        return {f"{base}.{node.module}" if base else node.module}, None
    return {f"{base}.{alias.name}" if base else alias.name for alias in node.names}, None


def verify_local_imports(paths: set[str], read_text) -> None:
    """AST ile absolute ve relative yerel importların pakette olduğunu denetler."""
    modules = _local_modules(paths)
    errors: list[str] = []
    for path in sorted(name for name in paths if name.endswith(".py")):
        try:
            tree = ast.parse(read_text(path), filename=path)
        except SyntaxError as error:
            errors.append(f"Syntax error in {path}: {error.msg}")
            continue
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    imported.add(node.module)
                elif node.level > 0:
                    relative_modules, relative_error = _relative_import_modules(path, node)
                    imported.update(relative_modules)
                    if relative_error:
                        errors.append(f"{relative_error}\nImported by: {path}")
        for module in sorted(imported):
            if module.startswith(("app.", "carpan_platform.")) and module not in modules:
                errors.append(f"Missing local module: {module}\nImported by: {path}")
    if errors:
        raise ReleaseIntegrityError("RELEASE SOURCE INTEGRITY FAILED\n\n" + "\n\n".join(errors))


def build_source_manifest(root: Path, tracked: set[str], packaged_paths: set[str]) -> dict:
    def git_value(*args: str) -> str | None:
        try:
            return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    status = git_value("status", "--porcelain") or ""
    runtime_paths = collect_runtime_sources(root)
    return {
        "build_timestamp_utc": datetime.now(UTC).isoformat(),
        "commit": git_value("rev-parse", "HEAD"),
        "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status),
        "tracked_file_count": len(tracked),
        "runtime_python_source_count": len(runtime_paths),
        "packaged_source_count": len(packaged_paths),
        "packaged_runtime_python_count": len(runtime_paths & packaged_paths),
    }


def verify_package_sources(expected_paths: set[str], archive: zipfile.ZipFile) -> None:
    packaged = set(archive.namelist()) - {MANIFEST_NAME}
    missing = sorted(expected_paths - packaged)
    if missing:
        raise ReleaseIntegrityError("Package source integrity failed. Missing files:\n" + "\n".join(f"- {name}" for name in missing))
    verify_local_imports(packaged, lambda name: archive.read(name).decode("utf-8"))


def run_import_smoke_test(extracted_root: Path) -> None:
    code = "import importlib, sys; sys.path.insert(0, '.'); import app; importlib.import_module('app.main')"
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=extracted_root, text=True,
        capture_output=True, timeout=30, env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise ReleaseIntegrityError(f"Python import smoke test failed.\n{detail}")


def run_collection_smoke_test(extracted_root: Path) -> None:
    """Yalnız release guard testinin keşfedilebildiği minimal pytest smoke testidir."""
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/test_release_template_guard.py"],
        cwd=extracted_root, text=True, capture_output=True, timeout=45,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise ReleaseIntegrityError(f"Minimal test collection smoke test failed.\n{detail}")


def verify_release_archive(destination: Path, expected_paths: set[str]) -> None:
    # Windows'ta kullanıcı TEMP klasörü kurumsal ilke/antivirüs tarafından
    # kilitlenebiliyor. Paketin bulunduğu yazılabilir klasör kontrollü bir
    # doğrulama alanıdır ve işlem bitince otomatik temizlenir.
    with tempfile.TemporaryDirectory(prefix=".carpan-release-", dir=destination.parent) as temporary:
        extracted = Path(temporary)
        with zipfile.ZipFile(destination) as archive:
            if archive.testzip():
                raise ReleaseIntegrityError("Release archive integrity check failed.")
            verify_package_sources(expected_paths, archive)
            archive.extractall(extracted)
        run_import_smoke_test(extracted)
        run_collection_smoke_test(extracted)


def manifest_bytes(manifest: dict) -> bytes:
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
