from app.core.operation_history import OperationHistory
from app.core.output_evidence import build_output_evidence, verify_output_evidence


def test_output_evidence_detects_changed_and_missing_files(tmp_path):
    output = tmp_path / "aktarim.xls"
    output.write_bytes(b"ilk-cikti")
    evidence = build_output_evidence([output])

    assert evidence["state"] == "VERIFIED"
    assert verify_output_evidence(evidence)[0]["comparison"] == "VERIFIED"

    output.write_bytes(b"sonradan-degisti")
    assert verify_output_evidence(evidence)[0]["comparison"] == "CHANGED"

    output.unlink()
    assert verify_output_evidence(evidence)[0]["comparison"] == "MISSING"


def test_completed_operation_stores_local_output_evidence(tmp_path):
    output = tmp_path / "aktarim.xls"
    output.write_bytes(b"onayli-cikti")
    history = OperationHistory(tmp_path / "operations.sqlite3", company_id=1, user_id=2)
    operation_id = history.start("manim_transfer", "MANİM", ["girdi.xlsx"])

    history.complete(operation_id, [output])

    record = history.recent()[0]
    event = history.events(operation_id)[-1]
    assert record.summary["output_integrity"] == "DOĞRULANDI"
    assert event.code == "OUTPUT_EVIDENCE"
    assert event.details["algorithm"] == "SHA-256"
    assert verify_output_evidence(event.details)[0]["comparison"] == "VERIFIED"
