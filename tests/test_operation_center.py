from datetime import datetime, timedelta, timezone

from app.core.operation_center import build_operation_center_snapshot, operation_attention_text
from app.core.operation_history import OperationHistory


def test_operation_center_summarizes_attention_records_per_company(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3", company_id=7, user_id=3)
    success = history.start("manim_transfer", "MANİM Aktarma", ["a.xlsx"])
    history.complete(success, ["a.xls", "b.xls"])
    history.record_external_acceptance(
        success,
        system="NETSIS",
        verdict="REJECTED",
        reason_code="BANK_ACCOUNT_CODE",
    )
    partial = history.start("manim_transfer", "MANİM Aktarma", ["b.xlsx"])
    history.complete(partial, ["review.xls"], {"unresolved": 2}, status="PARTIAL")
    failed = history.start("report_editing", "FOM Rapor Düzenleme", ["c.xlsx"])
    history.fail(failed, "Şablon bulunamadı")

    snapshot = build_operation_center_snapshot(history.recent())

    assert snapshot.total_operations == 3
    assert snapshot.successful_operations == 1
    assert snapshot.attention_operations == 3
    assert snapshot.unresolved_items == 2
    assert snapshot.generated_files == 3
    assert snapshot.netsis_rejections == 1
    assert snapshot.psoft_rejections == 0
    assert [record.id for record in snapshot.attention_records] == [failed, partial, success]
    assert operation_attention_text(snapshot.attention_records[0]) == "Şablon bulunamadı"
    assert operation_attention_text(snapshot.attention_records[1]) == "2 kayıt inceleme bekliyor."
    assert operation_attention_text(snapshot.attention_records[2]) == "Netsis aktarımı reddedildi: Banka hesap kodu."


def test_operation_center_surfaces_a_simulation_mismatch(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3", company_id=7, user_id=3)
    operation = history.start("manim_transfer", "MANİM Aktarma", ["a.xlsx"])
    history.complete(
        operation,
        ["a.xls"],
        {"simulation": {"status": "MISMATCH", "preflight_netsis_total": "100.00", "actual_netsis_total": "90.00"}},
    )

    snapshot = build_operation_center_snapshot(history.recent())
    assert snapshot.simulation_verified == 0
    assert snapshot.simulation_mismatches == 1
    assert snapshot.attention_operations == 1
    assert "Simülasyon ve gerçek aktarım planı farklı" in operation_attention_text(snapshot.attention_records[0])


def test_operation_center_surfaces_point_reconciliation_difference(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3", company_id=7, user_id=3)
    operation = history.start("bank_reconciliation", "Banka Mutabakatı", ["bank.xls", "netsis.xls"])
    history.complete(
        operation,
        ["difference.xlsx"],
        {"reconciliation": {
            "status": "MISMATCH",
            "bank_only_count": 2,
            "netsis_only_count": 1,
            "opening_difference": 0,
            "movement_difference": 125,
            "difference": 125,
        }},
    )

    snapshot = build_operation_center_snapshot(history.recent())
    assert snapshot.reconciliation_attention == 1
    assert snapshot.attention_operations == 1
    assert operation_attention_text(snapshot.attention_records[0]) == (
        "Banka mutabakatı tutmuyor: fark 125.00 TL; bankada 2, Netsis'te 1 açık kayıt var."
    )


def test_operation_center_summarizes_only_the_last_seven_days(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3", company_id=7, user_id=3)
    recent = history.start("manim_transfer", "MANİM Aktarma", ["recent.xlsx"])
    history.complete(recent, ["recent.xls"])
    history.record_external_acceptance(recent, system="NETSIS", verdict="ACCEPTED")
    reconciliation = history.start("bank_reconciliation", "Banka Mutabakatı", ["bank.xls"])
    history.complete(reconciliation, ["difference.xlsx"], {"reconciliation": {"status": "OPEN_ITEMS"}})
    old = history.start("manim_transfer", "MANİM Aktarma", ["old.xlsx"])
    history.complete(old, ["old.xls"])
    with history._connect() as conn:
        conn.execute(
            "UPDATE operations SET started_at=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(days=8)).isoformat(), old),
        )

    snapshot = build_operation_center_snapshot(history.recent(), now=datetime.now(timezone.utc))

    assert snapshot.weekly_summary.operation_count == 2
    assert snapshot.weekly_summary.successful_count == 2
    assert snapshot.weekly_summary.accepted_count == 1
    assert snapshot.weekly_summary.attention_count == 1
    assert snapshot.weekly_summary.reconciliation_attention_count == 1


def test_one_file_acceptance_is_not_counted_as_full_operation_acceptance(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3", company_id=7, user_id=3)
    first = tmp_path / "a.xls"
    second = tmp_path / "b.xls"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    operation = history.start("manim_transfer", "MANİM Aktarma", ["source.xlsx"])
    history.complete(operation, [str(first), str(second)])
    history.record_external_acceptance(
        operation,
        system="NETSIS",
        verdict="ACCEPTED",
        output_file=first,
    )

    snapshot = build_operation_center_snapshot(history.recent(), now=datetime.now(timezone.utc))

    assert snapshot.weekly_summary.accepted_count == 0
    assert snapshot.netsis_rejections == 0
