from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.core.output_contract import FOM_INTEGRATION_BASENAMES


_NON_ERP_MANIM_MARKERS = (
    "ODEME_ONAYLANDI",
    "REFERANSLI",
    "KURAL_CALISTI",
    "INCELEME_GEREKENLER",
    "GECERSIZ_MANIM_SATIRLARI",
)


@dataclass(frozen=True)
class ErpAcceptanceState:
    """One operation's ERP result, aggregated across its eligible files."""

    system: str
    status: str
    candidate_count: int
    recorded_count: int
    accepted_count: int
    rejected_count: int
    reason_code: str = ""
    output_name: str = ""


def aggregate_erp_acceptance(
    module_id: str,
    system: str,
    output_files: Iterable[str | Path],
    summary: object,
) -> ErpAcceptanceState:
    """Aggregate file verdicts without treating one accepted file as the whole run.

    Records created before file-level evidence existed keep their operation-level
    meaning through ``external_acceptance``.
    """
    normalized_system = str(system).strip().upper()
    candidates = erp_output_candidates(module_id, normalized_system, output_files)
    candidate_keys = {str(Path(value)) for value in candidates}
    payload = summary if isinstance(summary, dict) else {}
    by_file = payload.get("external_acceptance_by_file", {})
    if isinstance(by_file, dict) and by_file:
        legacy = payload.get("external_acceptance", {})
        latest_bound = (
            legacy
            if isinstance(legacy, dict)
            and str(legacy.get("system", "")).strip().upper() == normalized_system
            and str(Path(str(legacy.get("output_path", "")))) in candidate_keys
            else None
        )
        matching: list[dict] = []
        for path, value in by_file.items():
            if str(Path(str(path))) not in candidate_keys or not isinstance(value, dict):
                continue
            if str(value.get("system", "")).strip().upper() != normalized_system:
                continue
            matching.append(value)
        accepted = sum(str(value.get("verdict", "")).strip().upper() == "ACCEPTED" for value in matching)
        rejected_values = [
            value for value in matching
            if str(value.get("verdict", "")).strip().upper() == "REJECTED"
        ]
        rejected = len(rejected_values)
        recorded = accepted + rejected
        if rejected:
            status = "REJECTED"
            latest = (
                latest_bound
                if latest_bound and str(latest_bound.get("verdict", "")).strip().upper() == "REJECTED"
                else rejected_values[-1]
            )
        elif candidates and recorded == len(candidates) and accepted == len(candidates):
            status = "ACCEPTED"
            latest = matching[-1] if matching else {}
        elif recorded:
            status = "PARTIAL"
            latest = latest_bound or matching[-1]
        else:
            status = "NO_RESULT"
            latest = {}
        return ErpAcceptanceState(
            system=normalized_system,
            status=status,
            candidate_count=len(candidates),
            recorded_count=recorded,
            accepted_count=accepted,
            rejected_count=rejected,
            reason_code=str(latest.get("reason_code", "")).strip().upper(),
            output_name=str(latest.get("output_name", "")).strip(),
        )

    legacy = payload.get("external_acceptance", {})
    if isinstance(legacy, dict) and str(legacy.get("system", "")).strip().upper() == normalized_system:
        verdict = str(legacy.get("verdict", "")).strip().upper()
        if verdict in {"ACCEPTED", "REJECTED"}:
            return ErpAcceptanceState(
                system=normalized_system,
                status=verdict,
                candidate_count=len(candidates),
                recorded_count=len(candidates) or 1,
                accepted_count=(len(candidates) or 1) if verdict == "ACCEPTED" else 0,
                rejected_count=1 if verdict == "REJECTED" else 0,
                reason_code=str(legacy.get("reason_code", "")).strip().upper(),
                output_name=str(legacy.get("output_name", "")).strip(),
            )
    return ErpAcceptanceState(normalized_system, "NO_RESULT", len(candidates), 0, 0, 0)


def erp_rejection_reason_codes(
    module_id: str,
    system: str,
    output_files: Iterable[str | Path],
    summary: object,
) -> tuple[str, ...]:
    """Return current safe rejection categories, once for each rejected file."""
    normalized_system = str(system).strip().upper()
    candidate_keys = {
        str(Path(value))
        for value in erp_output_candidates(module_id, normalized_system, output_files)
    }
    payload = summary if isinstance(summary, dict) else {}
    by_file = payload.get("external_acceptance_by_file", {})
    if isinstance(by_file, dict) and by_file:
        return tuple(
            str(value.get("reason_code", "")).strip().upper()
            for path, value in by_file.items()
            if str(Path(str(path))) in candidate_keys
            and isinstance(value, dict)
            and str(value.get("system", "")).strip().upper() == normalized_system
            and str(value.get("verdict", "")).strip().upper() == "REJECTED"
            and str(value.get("reason_code", "")).strip()
        )
    legacy = payload.get("external_acceptance", {})
    if (
        isinstance(legacy, dict)
        and str(legacy.get("system", "")).strip().upper() == normalized_system
        and str(legacy.get("verdict", "")).strip().upper() == "REJECTED"
        and str(legacy.get("reason_code", "")).strip()
    ):
        return (str(legacy.get("reason_code", "")).strip().upper(),)
    return ()


def erp_output_candidates(
    module_id: str,
    system: str,
    output_files: Iterable[str | Path],
) -> tuple[str, ...]:
    """Return only files that the user can actually submit to that ERP."""
    normalized_system = str(system).strip().upper()
    candidates: list[str] = []
    for value in output_files:
        path = Path(value)
        if path.suffix.casefold() not in {".xls", ".xlsx"}:
            continue
        if normalized_system == "PSOFT":
            if path.stem not in FOM_INTEGRATION_BASENAMES:
                continue
        elif normalized_system == "NETSIS":
            upper_name = path.stem.upper()
            if str(module_id) != "manim_transfer":
                continue
            if any(marker in upper_name for marker in _NON_ERP_MANIM_MARKERS):
                continue
        else:
            continue
        candidates.append(str(path))
    return tuple(candidates)


def output_choice_labels(paths: Iterable[str | Path]) -> dict[str, str]:
    """Build readable, collision-safe labels for an ERP output picker."""
    normalized = [str(Path(value)) for value in paths]
    name_counts: dict[str, int] = {}
    for value in normalized:
        name = Path(value).name
        name_counts[name] = name_counts.get(name, 0) + 1
    return {
        (
            Path(value).name
            if name_counts[Path(value).name] == 1
            else f"{Path(value).name} · {Path(value).parent.name}"
        ): value
        for value in normalized
    }
