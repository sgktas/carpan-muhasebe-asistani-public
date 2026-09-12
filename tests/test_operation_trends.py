from datetime import datetime, timedelta, timezone

from app.core.operation_history import OperationHistory
from app.core.operation_trends import build_operation_trend_summary, filter_operation_records


def test_trends_filter_period_and_summarize_latest_erp_verdicts(tmp_path):
    history = OperationHistory(tmp_path / "history.sqlite3", company_id=1, user_id=2)
    netsis = history.start("manim_transfer", "MANİM", ["a.xlsx"])
    history.complete(netsis, ["a.xls"])
    history.record_external_acceptance(netsis, system="NETSIS", verdict="REJECTED", reason_code="BANK_ACCOUNT_CODE")
    psoft = history.start("report_editing", "FOM", ["b.xlsx"])
    history.complete(psoft, ["b.xls"], status="PARTIAL")
    history.record_external_acceptance(psoft, system="PSOFT", verdict="ACCEPTED")
    old = history.start("manim_transfer", "MANİM", ["old.xlsx"])
    history.complete(old, ["old.xls"])
    with history._connect() as conn:
        conn.execute(
            "UPDATE operations SET started_at=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(days=31)).isoformat(), old),
        )

    records = filter_operation_records(history.recent(), period_days=30, now=datetime.now(timezone.utc))
    summary = build_operation_trend_summary(records)

    assert [record.id for record in records] == [psoft, netsis]
    assert summary.operation_count == 2
    assert summary.successful_count == 1
    assert summary.partial_count == 1
    assert summary.netsis_rejected == 1
    assert summary.psoft_accepted == 1
    assert summary.netsis_accepted == 0
    assert summary.netsis_rejection_reasons == (("BANK_ACCOUNT_CODE", 1),)
    assert summary.psoft_rejection_reasons == ()


def test_all_time_filter_keeps_legacy_or_unparseable_dates(tmp_path):
    history = OperationHistory(tmp_path / "history.sqlite3", company_id=1, user_id=2)
    operation = history.start("manim_transfer", "MANİM", ["a.xlsx"])
    history.complete(operation, ["a.xls"])
    with history._connect() as conn:
        conn.execute("UPDATE operations SET started_at=? WHERE id=?", ("eski-kayit", operation))

    assert len(filter_operation_records(history.recent(), period_days=None)) == 1
    assert filter_operation_records(history.recent(), period_days=7, now=datetime.now(timezone.utc)) == []
