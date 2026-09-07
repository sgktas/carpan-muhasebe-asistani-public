from app.core.operation_center import build_operation_center_snapshot, operation_attention_text
from app.core.operation_history import OperationHistory


def test_operation_center_summarizes_attention_records_per_company(tmp_path):
    history = OperationHistory(tmp_path / "operations.sqlite3", company_id=7, user_id=3)
    success = history.start("manim_transfer", "MANİM Aktarma", ["a.xlsx"])
    history.complete(success, ["a.xls", "b.xls"])
    partial = history.start("manim_transfer", "MANİM Aktarma", ["b.xlsx"])
    history.complete(partial, ["review.xls"], {"unresolved": 2}, status="PARTIAL")
    failed = history.start("report_editing", "FOM Rapor Düzenleme", ["c.xlsx"])
    history.fail(failed, "Şablon bulunamadı")

    snapshot = build_operation_center_snapshot(history.recent())

    assert snapshot.total_operations == 3
    assert snapshot.successful_operations == 1
    assert snapshot.attention_operations == 2
    assert snapshot.unresolved_items == 2
    assert snapshot.generated_files == 3
    assert [record.id for record in snapshot.attention_records] == [failed, partial]
    assert operation_attention_text(snapshot.attention_records[0]) == "Şablon bulunamadı"
    assert operation_attention_text(snapshot.attention_records[1]) == "2 kayıt inceleme bekliyor."
