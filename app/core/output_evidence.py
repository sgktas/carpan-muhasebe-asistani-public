from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


EVIDENCE_ALGORITHM = "SHA-256"
_CHUNK_SIZE = 1024 * 1024


def build_output_evidence(paths: Iterable[str | Path]) -> dict:
    """Yerel çıktıların içerik parmak izini oluşturur.

    Bu kayıt yalnız dosya yolu, boyutu ve özet değerini içerir; Excel/banka
    verisi ya da müşteri içeriği merkezi bir servise gönderilmez.
    """
    files = [_fingerprint(Path(path)) for path in paths]
    state = (
        "VERIFIED"
        if files and all(item["state"] == "VERIFIED" for item in files)
        else "ATTENTION"
    )
    return {
        "algorithm": EVIDENCE_ALGORITHM,
        "state": state,
        "files": files,
    }


def verify_output_evidence(evidence: dict) -> list[dict]:
    """Kayıtlı parmak izlerini mevcut yerel dosyalarla karşılaştırır."""
    if str(evidence.get("algorithm", "")) != EVIDENCE_ALGORITHM:
        return []
    verified: list[dict] = []
    for item in evidence.get("files", []):
        if not isinstance(item, dict):
            continue
        path = Path(str(item.get("path", "")))
        current = _fingerprint(path)
        expected_state = str(item.get("state", ""))
        if expected_state != "VERIFIED":
            comparison = "BASELINE_UNAVAILABLE"
        elif current["state"] != "VERIFIED":
            comparison = current["state"]
        elif (
            current["size"] == item.get("size")
            and current["sha256"] == item.get("sha256")
        ):
            comparison = "VERIFIED"
        else:
            comparison = "CHANGED"
        verified.append({**item, "comparison": comparison})
    return verified


def _fingerprint(path: Path) -> dict:
    item = {
        "path": str(path),
        "name": path.name or str(path),
        "state": "VERIFIED",
        "size": None,
        "sha256": "",
    }
    try:
        if path.is_symlink():
            item["state"] = "UNSAFE_PATH"
            return item
        if not path.is_file():
            item["state"] = "MISSING"
            return item
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
                digest.update(chunk)
        item["size"] = path.stat().st_size
        item["sha256"] = digest.hexdigest()
    except OSError:
        item["state"] = "UNREADABLE"
    return item
