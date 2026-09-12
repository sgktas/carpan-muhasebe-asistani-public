from pathlib import Path

from app.core.erp_acceptance_target import (
    aggregate_erp_acceptance,
    erp_rejection_reason_codes,
    erp_output_candidates,
    output_choice_labels,
)


def test_manim_candidates_include_only_netsis_transfer_outputs():
    outputs = [
        "C:/out/01_BODRUM_GARANTI_12092026.xls",
        "C:/out/09_HESAPLAR_ARASI_VIRMAN_12092026.xlsx",
        "C:/out/10_REFERANSLI_12092026.xls",
        "C:/out/09_ODEME_ONAYLANDI_12092026.xls",
        "C:/out/11_KURAL_CALISTI_12092026.xls",
        "C:/out/12_GECERSIZ_MANIM_SATIRLARI_12092026.xls",
    ]

    assert erp_output_candidates("manim_transfer", "NETSIS", outputs) == (
        str(Path(outputs[0])),
        str(Path(outputs[1])),
    )


def test_fom_candidates_include_only_exact_psoft_integration_names():
    outputs = [
        "C:/out/02_SATIS_RAPORU_DUZENLENMIS.xlsx",
        "C:/out/ENT-Muhasebe_Entegrasyon(Satış_Faturaları).xls",
        "C:/out/ENT-Muhasebe_Entegrasyon(Tahsilatlar).xls",
    ]

    assert len(erp_output_candidates("report_editing", "PSOFT", outputs)) == 2


def test_output_choice_labels_disambiguate_duplicate_file_names():
    labels = output_choice_labels(["C:/first/output.xls", "C:/second/output.xls"])

    assert labels == {
        "output.xls · first": str(Path("C:/first/output.xls")),
        "output.xls · second": str(Path("C:/second/output.xls")),
    }


def test_one_accepted_file_does_not_accept_a_multi_output_operation():
    outputs = ["C:/out/a.xls", "C:/out/b.xls"]
    first = str(Path(outputs[0]))

    state = aggregate_erp_acceptance(
        "manim_transfer",
        "NETSIS",
        outputs,
        {"external_acceptance_by_file": {
            first: {"system": "NETSIS", "verdict": "ACCEPTED", "output_name": "a.xls"},
        }},
    )

    assert state.status == "PARTIAL"
    assert state.recorded_count == 1
    assert state.candidate_count == 2


def test_all_eligible_files_must_be_accepted_for_operation_acceptance():
    outputs = ["C:/out/a.xls", "C:/out/b.xls"]
    by_file = {
        str(Path(value)): {"system": "NETSIS", "verdict": "ACCEPTED", "output_name": Path(value).name}
        for value in outputs
    }

    state = aggregate_erp_acceptance(
        "manim_transfer", "NETSIS", outputs, {"external_acceptance_by_file": by_file},
    )

    assert state.status == "ACCEPTED"
    assert state.accepted_count == 2


def test_one_rejected_file_rejects_the_operation_summary():
    outputs = ["C:/out/a.xls", "C:/out/b.xls"]
    by_file = {
        str(Path(outputs[0])): {"system": "NETSIS", "verdict": "ACCEPTED"},
        str(Path(outputs[1])): {
            "system": "NETSIS", "verdict": "REJECTED",
            "reason_code": "BANK_ACCOUNT_CODE", "output_name": "b.xls",
        },
    }

    state = aggregate_erp_acceptance(
        "manim_transfer", "NETSIS", outputs, {"external_acceptance_by_file": by_file},
    )

    assert state.status == "REJECTED"
    assert state.reason_code == "BANK_ACCOUNT_CODE"
    assert state.output_name == "b.xls"


def test_legacy_operation_level_acceptance_remains_supported():
    state = aggregate_erp_acceptance(
        "report_editing",
        "PSOFT",
        ["C:/out/legacy.xls"],
        {"external_acceptance": {"system": "PSOFT", "verdict": "ACCEPTED"}},
    )

    assert state.status == "ACCEPTED"
    assert state.recorded_count == 1


def test_rejection_reason_codes_use_current_per_file_results_only():
    outputs = ["C:/out/a.xls", "C:/out/b.xls"]
    reasons = erp_rejection_reason_codes(
        "manim_transfer",
        "NETSIS",
        outputs,
        {"external_acceptance_by_file": {
            str(Path(outputs[0])): {
                "system": "NETSIS", "verdict": "REJECTED", "reason_code": "BANK_ACCOUNT_CODE",
            },
            str(Path(outputs[1])): {
                "system": "NETSIS", "verdict": "ACCEPTED", "reason_code": "",
            },
        }},
    )

    assert reasons == ("BANK_ACCOUNT_CODE",)
