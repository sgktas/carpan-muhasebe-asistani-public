from pathlib import Path

from app.core.operation_history import OperationRecord
from app.integrations.health import IntegrationAcceptanceState, build_integration_health
from app.integrations.registry import build_default_integration_registry


def _record(
    module_id: str,
    acceptance: dict | None = None,
    *,
    operation_id: int = 1,
    started_at: str = "2026-09-10T08:00:00+00:00",
) -> OperationRecord:
    return OperationRecord(
        id=operation_id, module_id=module_id, module_name="Test", actor="", status="SUCCESS",
        started_at=started_at, completed_at=None,
        input_files=[], output_files=["output.xls"],
        summary={"external_acceptance": acceptance} if acceptance else {},
        error_message=None,
    )


def test_health_uses_latest_history_order_for_each_external_integration():
    registry = build_default_integration_registry()
    health = build_integration_health(
        registry.all(),
        [
            _record("manim_transfer", {"system": "NETSIS", "verdict": "REJECTED"}),
            _record("report_editing", {"system": "PSOFT", "verdict": "ACCEPTED"}),
        ],
    )

    assert health["netsis_approved_export"].state == IntegrationAcceptanceState.REJECTED
    assert health["netsis_approved_export"].text == "Son aktarım reddedildi"
    assert health["psoft_fom_approved_export"].state == IntegrationAcceptanceState.ACCEPTED
    assert health["bank_statement_file_import"].state == IntegrationAcceptanceState.NOT_APPLICABLE


def test_health_never_mistakes_another_system_result_for_the_integration():
    registry = build_default_integration_registry()
    health = build_integration_health(
        registry.all(),
        [_record("manim_transfer", {"system": "PSOFT", "verdict": "ACCEPTED"})],
    )

    assert health["netsis_approved_export"].state == IntegrationAcceptanceState.NO_RESULT


def test_health_uses_real_operation_recency_not_the_input_list_order():
    registry = build_default_integration_registry()
    health = build_integration_health(
        registry.all(),
        [
            _record(
                "manim_transfer", {"system": "NETSIS", "verdict": "ACCEPTED"},
                operation_id=2, started_at="2026-09-11T08:00:00+00:00",
            ),
            _record(
                "manim_transfer", {"system": "NETSIS", "verdict": "REJECTED"},
                operation_id=1, started_at="2026-09-10T08:00:00+00:00",
            ),
        ],
    )

    result = health["netsis_approved_export"]

    assert result.state == IntegrationAcceptanceState.ACCEPTED
    assert result.operation_id == 2
    assert result.recorded_at == "2026-09-11T08:00:00+00:00"


def test_health_reports_partial_file_level_result_as_incomplete():
    registry = build_default_integration_registry()
    first = "C:/out/a.xls"
    record = _record("manim_transfer")
    record.output_files[:] = [first, "C:/out/b.xls"]
    record.summary["external_acceptance_by_file"] = {
        str(Path(first)): {"system": "NETSIS", "verdict": "ACCEPTED"},
    }

    result = build_integration_health(registry.all(), [record])["netsis_approved_export"]

    assert result.state == IntegrationAcceptanceState.NO_RESULT
    assert result.text == "Sonucun 1/2 dosyası kaydedildi"
