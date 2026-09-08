import hashlib
import json

import pytest

from app.core.template_integrity import (
    TemplateIntegrityError,
    assert_approved_template,
    verify_approved_templates,
)


def _write_approved_template(root, name: str, content: bytes = b"approved-template"):
    path = root / "templates" / "local" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    checksum_path = root / "config" / "local" / "template_checksums.json"
    checksum_path.parent.mkdir(parents=True, exist_ok=True)
    checksum_path.write_text(
        json.dumps({name: hashlib.sha256(content).hexdigest()}), encoding="utf-8"
    )
    return path


def test_template_integrity_accepts_unchanged_approved_template(tmp_path):
    _write_approved_template(tmp_path, "netsis_template.xls")

    snapshot = verify_approved_templates(tmp_path)

    assert snapshot.configured
    assert snapshot.is_valid
    assert snapshot.valid_count == 1
    assert snapshot.checks[0].status == "VALID"


def test_template_integrity_reports_missing_or_changed_template(tmp_path):
    path = _write_approved_template(tmp_path, "report_editing/sales_template.xls")
    path.write_bytes(b"changed-template")

    snapshot = verify_approved_templates(tmp_path)

    assert not snapshot.is_valid
    assert snapshot.invalid_count == 1
    assert snapshot.checks[0].status == "CHANGED"


def test_template_integrity_reports_missing_manifest(tmp_path):
    snapshot = verify_approved_templates(tmp_path)

    assert not snapshot.configured
    assert not snapshot.is_valid
    assert snapshot.checks[0].status == "MISSING"


def test_runtime_guard_returns_only_unchanged_approved_path(tmp_path):
    path = _write_approved_template(tmp_path, "report_editing/collections_template.xls")

    assert assert_approved_template(tmp_path, path) == path.resolve()

    path.write_bytes(b"tampered")
    with pytest.raises(TemplateIntegrityError, match="değişmiş"):
        assert_approved_template(tmp_path, path)


def test_runtime_guard_rejects_unregistered_template(tmp_path):
    path = tmp_path / "templates" / "local" / "custom.xls"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"custom")
    checksum_path = tmp_path / "config" / "local" / "template_checksums.json"
    checksum_path.parent.mkdir(parents=True)
    checksum_path.write_text(json.dumps({}), encoding="utf-8")

    with pytest.raises(TemplateIntegrityError, match="kayıtlı değil"):
        assert_approved_template(tmp_path, path)
