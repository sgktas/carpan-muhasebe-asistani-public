import hashlib
import json

from app.core.template_integrity import verify_approved_templates


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
