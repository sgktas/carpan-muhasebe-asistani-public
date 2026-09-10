from app.core.operation_history import OperationRecord
from app.integrations.health import IntegrationAcceptanceState, build_integration_health
from app.integrations.registry import build_default_integration_registry


def _record(module_id: str, acceptance: dict | None = None) -> OperationRecord:
    return OperationRecord(
        id=1, module_id=module_id, module_name="Test", actor="", status="SUCCESS",
        started_at="2026-09-10T08:00:00+00:00", completed_at=None,
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
