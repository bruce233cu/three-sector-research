from __future__ import annotations

from dataclasses import dataclass

from .checks import DataQualityReport, QUALITY_THRESHOLDS


@dataclass(frozen=True)
class FreezeDecision:
    critical_data_ok: bool
    stage_frozen: bool
    freeze_reason: tuple[str, ...]


def decide_freeze(reports: list[DataQualityReport], *, minimum_core_completeness: float | None = None) -> FreezeDecision:
    reasons: list[str] = []
    for report in reports:
        if not report.schema_valid:
            reasons.append(f"{report.dataset_code}:schema_invalid")
        dataset_threshold = QUALITY_THRESHOLDS.get(report.dataset_code, (0.98, 0.95))[1]
        freeze_threshold = minimum_core_completeness if minimum_core_completeness is not None else dataset_threshold
        if report.completeness_ratio < freeze_threshold:
            reasons.append(f"{report.dataset_code}:completeness={report.completeness_ratio:.4f}<{freeze_threshold:.4f}")
        if report.source_conflict_flag:
            reasons.append(f"{report.dataset_code}:source_conflict")
        if report.pit_violation_count:
            reasons.append(f"{report.dataset_code}:pit_violation={report.pit_violation_count}")
    return FreezeDecision(not reasons, bool(reasons), tuple(reasons))
