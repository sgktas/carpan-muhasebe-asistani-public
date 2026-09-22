from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from app.ui.accounting_workspace import AccountingWorkspace
from app.ui.accounting_view import AccountingView, SourceView
from tests.test_accounting_view import record

APP = QApplication.instance() or QApplication([])

def test_empty_workspace_and_selected_row_inspector(tmp_path):
    history = SimpleNamespace(company_id=1, recent=lambda limit: [])
    widget = AccountingWorkspace(history, SimpleNamespace(resource_root=tmp_path,data_root=tmp_path))
    assert '0 kaynak' in widget.facts.text()
    assert widget.records.rowCount() == 0
    assert 'bulunamadı' in widget.previous.text()
    r=record(issue='Synthetic validation issue')
    widget.view=AccountingView((SourceView(r.source,'MANİM Excel',(r,)),))
    widget.render()
    assert widget.sources.rowCount() == 1
    widget.records.selectRow(0)
    assert 'Synthetic validation issue' in widget.inspector.toPlainText()
    assert r.source in widget.inspector.toPlainText()
    widget.search.setText('absent synthetic filter')
    assert widget.records.rowCount() == 0
    widget.close()


def test_existing_engine_result_updates_workspace_without_new_write_semantics(synthetic_project, monkeypatch):
    from app.core.app_paths import AppPaths
    from app.core.operation_history import OperationHistory
    from app.core.processing_engine import ProcessingEngine
    from app.modules.manim import page as page_module
    from app.ui.accounting_view import load_sources
    sources = list(synthetic_project[:3])
    root = synthetic_project[3]
    paths = AppPaths(root, root, root/'output')
    paths.ensure_writable_dirs()
    monkeypatch.setattr(page_module, 'APP_PATHS', paths)
    history = OperationHistory(paths.state_dir/'operations.sqlite3', company_id=1)
    page = page_module.ManimModulePage(history)
    page.files = sources
    page.accounting_workspace.view = load_sources(sources, root, root)
    page._operation_id = history.start('manim_transfer','Synthetic operation',sources)
    engine = ProcessingEngine(sources,root,company_id=1)
    engine.operation_id = page._operation_id
    result = engine.run()
    page._process_succeeded(result)
    assert result.created_files
    assert page.accounting_workspace.summary is result.simulation_summary
    page.accounting_workspace.set_filter_mode("all")
    assert page.accounting_workspace.records.rowCount() == result.total_manim_records
    assert history.recent(1)[0].status == 'SUCCESS'
    page.close()


def test_workspace_matches_approved_operational_structure_without_fake_metrics(tmp_path):
    history = SimpleNamespace(company_id=1, recent=lambda limit: [])
    widget = AccountingWorkspace(
        history,
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path),
    )

    assert widget.page_title.text() == "Muhasebe Otomasyon Merkezi"
    assert widget.source_stat.value.text() == "0 kaynak dosya"
    assert widget.region_stat.value.text() == "0 bölge"
    assert widget.record_stat.value.text() == "0 kayıt"
    assert len(widget.steps) == 6
    assert widget.records.columnCount() == 8
    assert widget.inspector.objectName() == "recordInspector"
    assert "İncelemek için" in widget.inspector.toPlainText()
    assert not widget.preview_button.isEnabled()
    assert not widget.output_button.isEnabled()
    widget.close()


def test_workspace_decision_summary_uses_real_audits_only(tmp_path):
    history = SimpleNamespace(company_id=1, recent=lambda limit: [])
    widget = AccountingWorkspace(
        history,
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path),
    )
    ready = record(row=2)
    review = record(row=3)
    invalid = record(row=4, issue="Synthetic invalid source")
    widget.view = AccountingView(
        (SourceView("synthetic_manim.xlsx", "MANİM Excel", (ready, review, invalid)),)
    )
    widget.audits = (
        dict(
            source_file="synthetic_manim.xlsx",
            source_row=2,
            region=ready.region,
            bank=ready.bank,
            amount=str(ready.amount),
            outcome="HAVALE",
            rule_code="SYNTHETIC_READY",
        ),
        dict(
            source_file="synthetic_manim.xlsx",
            source_row=3,
            region=review.region,
            bank=review.bank,
            amount=str(review.amount),
            outcome="REVIEW",
            rule_code="SYNTHETIC_REVIEW",
            reason="Synthetic review",
        ),
    )
    widget.render()

    assert widget.legend_auto.text.text().startswith("1 ")
    assert widget.legend_review.text.text().startswith("1 ")
    assert widget.legend_error.text.text().startswith("1 ")
    assert "3 kayıt" in widget.decision_total.text()
    widget.close()


def test_workspace_action_buttons_forward_signals_without_qt_clicked_argument(tmp_path):
    history = SimpleNamespace(company_id=1, recent=lambda limit: [])
    widget = AccountingWorkspace(
        history,
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path),
    )
    r = record()
    widget.view = AccountingView(
        (SourceView("synthetic_manim.xlsx", "MANİM Excel", (r,)),)
    )
    widget.render()
    calls = {"preview": 0, "output": 0, "add": 0, "tools": 0, "clear": 0}
    widget.preview_requested.connect(lambda: calls.__setitem__("preview", calls["preview"] + 1))
    widget.output_requested.connect(lambda: calls.__setitem__("output", calls["output"] + 1))
    widget.add_sources_requested.connect(lambda: calls.__setitem__("add", calls["add"] + 1))
    widget.source_tools_requested.connect(lambda: calls.__setitem__("tools", calls["tools"] + 1))
    widget.clear_sources_requested.connect(lambda: calls.__setitem__("clear", calls["clear"] + 1))

    widget.preview_button.click()
    assert not widget.output_button.isEnabled()
    widget.set_result(SimpleNamespace(simulation_summary=None, decision_audits=(), unresolved=0), preview=True)
    widget.output_button.click()
    widget.add_source_button.click()
    widget.source_tools_button.click()
    widget.clear_source_button.click()

    assert calls == {"preview": 1, "output": 1, "add": 1, "tools": 1, "clear": 1}
    widget.close()


def test_observability_failure_does_not_leave_completed_workspace_busy(tmp_path):
    history = SimpleNamespace(company_id=1, recent=lambda limit: [])
    widget = AccountingWorkspace(
        history,
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path),
    )
    r = record()
    widget.view = AccountingView(
        (SourceView("synthetic_manim.xlsx", "MANİM Excel", (r,)),)
    )
    widget.operation_reader = SimpleNamespace(
        get_operation_view=lambda _operation_id: (_ for _ in ()).throw(RuntimeError("synthetic read failure"))
    )
    widget.set_busy(True, "Yerel çalışma · Muhasebe kararı hazırlanıyor…")
    result = SimpleNamespace(
        simulation_summary=None,
        decision_audits=(),
        created_files=[tmp_path / "synthetic-output.xls"],
    )

    widget.set_result(result, preview=False, operation_id=42)

    assert not widget.is_busy
    assert widget.output_button.text() == "Yeniden çıktı oluştur"
    assert widget.header_state.text() == "Tamamlandı"
    widget.close()


def test_record_inspector_can_collapse_and_reopen_without_losing_workspace(tmp_path):
    history = SimpleNamespace(company_id=1, recent=lambda limit: [])
    widget = AccountingWorkspace(
        history,
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path),
    )

    assert widget.inspector_frame.maximumWidth() == 320
    assert widget.inspector_open_button.isHidden()

    widget.set_inspector_visible(False, animated=False)
    assert widget.inspector_frame.isHidden()
    assert not widget.detail_toggle.isHidden()
    assert not widget.detail_toggle.isChecked()

    widget.set_inspector_visible(True, animated=False)
    assert not widget.inspector_frame.isHidden()
    assert widget.inspector_frame.maximumWidth() == 320
    assert widget.inspector_open_button.isHidden()
    widget.close()


def test_completed_output_marks_workflow_complete_even_with_special_routed_records(tmp_path):
    from app.core.operation_simulation import OperationSimulation

    history = SimpleNamespace(company_id=1, recent=lambda limit: [])
    widget = AccountingWorkspace(
        history,
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path),
    )
    payment = record(row=20)
    reference = record(row=21)
    widget.view = AccountingView(
        (SourceView('synthetic_manim.xlsx', 'MANİM Excel', (payment, reference)),)
    )
    audits = (
        dict(source_file='synthetic_manim.xlsx', source_row=20, region=payment.region,
             bank=payment.bank, amount=str(payment.amount), outcome='ODEME_ONAYLANDI',
             rule_code='SYNTHETIC_PAYMENT'),
        dict(source_file='synthetic_manim.xlsx', source_row=21, region=reference.region,
             bank=reference.bank, amount=str(reference.amount), outcome='REFERANSLI',
             rule_code='SYNTHETIC_REFERENCE'),
    )
    summary = OperationSimulation().summarize(audits)
    widget.operation_reader = None
    result = SimpleNamespace(
        simulation_summary=summary,
        decision_audits=audits,
        created_files=[tmp_path / 'synthetic-output.xls'],
        unresolved=0,
    )

    widget.set_result(result, preview=False, operation_id=99)

    assert widget.header_state.text() == 'Tamamlandı'
    assert widget.output_button.text() == 'Yeniden çıktı oluştur'
    assert all(step.property('stepState') == 'complete' for step in widget.steps)
    assert widget.attention_tab.text().endswith('0')
    assert widget.ready_tab.text().endswith('2')
    assert widget.legend_auto.text.text().startswith('2 ')
    assert widget.legend_manual.text.text().startswith('0 ')
    widget.close()


def test_completed_output_exposes_published_output_access(tmp_path):
    history = SimpleNamespace(company_id=1, recent=lambda limit: [])
    widget = AccountingWorkspace(
        history,
        SimpleNamespace(resource_root=tmp_path, data_root=tmp_path),
    )
    source = record()
    widget.view = AccountingView(
        (SourceView("synthetic_manim.xlsx", "MANİM Excel", (source,)),)
    )
    output_dir = tmp_path / "synthetic-published-output"
    output_dir.mkdir()
    output_file = output_dir / "synthetic.xls"
    output_file.write_bytes(b"synthetic")
    result = SimpleNamespace(
        simulation_summary=None,
        decision_audits=(),
        created_files=[output_file],
        output_dir=output_dir,
        unresolved=0,
    )

    widget.set_result(result, preview=False, operation_id=7)

    assert not widget.output_access.isHidden()
    assert widget.output_access_label.text() == "1 çıktı hazır"
    assert widget.open_output_button.isEnabled()
    assert not widget.inspector_output_button.isHidden()
    assert widget.open_output_button.toolTip() == str(output_dir)
    widget.close()
