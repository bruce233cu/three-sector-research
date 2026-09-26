from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import pandas as pd


QUALITY_THRESHOLDS: dict[str, tuple[float, float]] = {
    "daily_bars": (0.98, 0.95),
    "membership_history": (0.95, 0.90),
    "sector_return_coverage": (0.80, 0.70),
    "breadth_coverage": (0.80, 0.70),
}


@dataclass(frozen=True)
class DataQualityReport:
    dataset_code: str
    as_of_date: date
    expected_count: int
    actual_count: int
    duplicate_count: int
    missing_count: int
    completeness_ratio: float
    stale_days: int
    schema_valid: bool
    source_conflict_flag: bool
    pit_violation_count: int
    warnings: tuple[str, ...]


def evaluate_daily_quality(
    frame: pd.DataFrame,
    *,
    dataset_code: str,
    as_of_date: date,
    expected_count: int,
    key_columns: tuple[str, ...],
    required_columns: tuple[str, ...],
    fetched_at: datetime,
    source_conflict_flag: bool = False,
    available_at_column: str | None = None,
    calculation_cutoff: datetime | None = None,
) -> DataQualityReport:
    missing_columns = [c for c in required_columns if c not in frame.columns]
    schema_valid = not missing_columns
    duplicate_count = int(frame.duplicated(list(key_columns)).sum()) if all(c in frame.columns for c in key_columns) else 0
    actual_count = len(frame)
    missing_count = max(expected_count - actual_count, 0)
    completeness = 1.0 if expected_count == 0 else min(actual_count / expected_count, 1.0)
    fetched_date = fetched_at.astimezone(timezone.utc).date()
    stale_days = max((as_of_date - fetched_date).days, 0)
    pit_violations = 0
    warnings: list[str] = []
    if missing_columns:
        warnings.append("missing_columns:" + ",".join(missing_columns))
    if duplicate_count:
        warnings.append(f"duplicates:{duplicate_count}")
    warning_threshold = QUALITY_THRESHOLDS.get(dataset_code, (0.98, 0.95))[0]
    if completeness < warning_threshold:
        warnings.append(f"completeness:{completeness:.4f}<{warning_threshold:.4f}")
    if available_at_column and calculation_cutoff and available_at_column in frame.columns:
        values = pd.to_datetime(frame[available_at_column], utc=True, errors="coerce")
        pit_violations = int((values > calculation_cutoff).fillna(False).sum())
        if pit_violations:
            warnings.append(f"future_availability:{pit_violations}")
    if source_conflict_flag:
        warnings.append("source_conflict")
    return DataQualityReport(
        dataset_code=dataset_code,
        as_of_date=as_of_date,
        expected_count=expected_count,
        actual_count=actual_count,
        duplicate_count=duplicate_count,
        missing_count=missing_count,
        completeness_ratio=completeness,
        stale_days=stale_days,
        schema_valid=schema_valid,
        source_conflict_flag=source_conflict_flag,
        pit_violation_count=pit_violations,
        warnings=tuple(warnings),
    )


def market_data_anomalies(frame: pd.DataFrame) -> tuple[str, ...]:
    """Detect invalid market rows without replacing missing values with zero."""
    warnings: list[str] = []
    numeric = {name: pd.to_numeric(frame[name], errors="coerce") for name in ("open", "high", "low", "close", "amount", "volume") if name in frame}
    if {"open", "high", "low", "close"}.issubset(numeric):
        invalid_ohlc = (
            (numeric["high"] < numeric["low"])
            | (numeric["high"] < numeric["open"])
            | (numeric["high"] < numeric["close"])
            | (numeric["low"] > numeric["open"])
            | (numeric["low"] > numeric["close"])
            | (numeric["close"] < 0)
        )
        if invalid_ohlc.any():
            warnings.append(f"invalid_ohlc:{int(invalid_ohlc.sum())}")
    for name in ("amount", "volume"):
        if name in numeric:
            invalid = numeric[name] < 0
            if invalid.any():
                warnings.append(f"negative_{name}:{int(invalid.sum())}")
    return tuple(warnings)
