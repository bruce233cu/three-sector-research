from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MetricValue:
    value: float | None
    valid: bool
    coverage: float
    reason_if_invalid: str | None = None

    def dict(self) -> dict:
        return asdict(self)


def _invalid(reason: str, coverage: float = 0.0) -> MetricValue:
    return MetricValue(None, False, float(coverage), reason)


def compound_return(values: Iterable[float], *, expected: int, minimum_coverage: float = .9) -> MetricValue:
    series = pd.Series(list(values), dtype="float64").dropna()
    coverage = min(len(series) / expected, 1.0) if expected else 0.0
    if coverage < minimum_coverage:
        return _invalid("valid_window_below_90pct", coverage)
    return MetricValue(float(np.prod(1 + series / 100.0) - 1), True, coverage)


def relative_strength(sector: Iterable[float], benchmark: Iterable[float], *, window: int) -> MetricValue:
    left, right = pd.Series(list(sector), dtype="float64"), pd.Series(list(benchmark), dtype="float64")
    paired = pd.concat([left, right], axis=1).dropna().tail(window)
    coverage = min(len(paired) / window, 1.0)
    if coverage < .9:
        return _invalid("paired_return_window_below_90pct", coverage)
    value = np.prod(1 + paired.iloc[:, 0] / 100.0) - np.prod(1 + paired.iloc[:, 1] / 100.0)
    return MetricValue(float(value), True, coverage)


def win_rate(sector: Iterable[float], benchmark: Iterable[float], *, window: int) -> MetricValue:
    paired = pd.concat([pd.Series(list(sector), dtype="float64"), pd.Series(list(benchmark), dtype="float64")], axis=1).tail(window).dropna()
    minimum = 4 if window == 5 else 8
    coverage = min(len(paired) / window, 1.0)
    if len(paired) < minimum:
        return _invalid(f"valid_comparison_days_below_{minimum}", coverage)
    return MetricValue(float((paired.iloc[:, 0] > paired.iloc[:, 1]).mean()), True, coverage)


def turnover_metrics(sector_amount: Iterable[float], market_amount: Iterable[float]) -> dict[str, MetricValue]:
    paired = pd.concat([pd.Series(list(sector_amount), dtype="float64"), pd.Series(list(market_amount), dtype="float64")], axis=1)
    shares = (paired.iloc[:, 0] / paired.iloc[:, 1].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    current = shares.iloc[-1] if len(shares) else np.nan
    share = _invalid("current_turnover_share_missing") if pd.isna(current) else MetricValue(float(current), True, 1.0)
    prior20 = shares.iloc[:-1].tail(20).dropna()
    mean20 = _invalid("turnover_history_below_20", len(prior20) / 20) if len(prior20) < 20 else MetricValue(float(prior20.mean()), True, 1.0)
    prior60 = shares.iloc[:-1].tail(60).dropna()
    if len(prior60) < 40 or not share.valid:
        intensity = _invalid("turnover_history_below_40", len(prior60) / 60)
    else:
        median = float(prior60.median())
        intensity = _invalid("turnover_median_zero", 1.0) if median == 0 else MetricValue(float(share.value / median), True, len(prior60) / 60)
    return {"turnover_share": share, "turnover_share_20d_mean": mean20, "turnover_intensity": intensity}


def breadth(value: float | None, *, valid_members: int, members: int, reason: str = "member_coverage_below_70pct") -> MetricValue:
    coverage = valid_members / members if members else 0.0
    if value is None or coverage < .7:
        return _invalid(reason, coverage)
    return MetricValue(float(value), True, coverage)


def strongest_percentiles(values: dict[str, MetricValue]) -> dict[str, MetricValue]:
    valid = {key: metric.value for key, metric in values.items() if metric.valid and metric.value is not None}
    if len(valid) < 10:
        return {key: _invalid("cross_section_objects_below_10", len(valid) / 10) for key in values}
    series = pd.Series(valid, dtype="float64")
    pct = series.rank(method="average", ascending=False, pct=True)
    return {key: MetricValue(float(pct[key]), True, 1.0) if key in pct else _invalid("metric_missing") for key in values}
