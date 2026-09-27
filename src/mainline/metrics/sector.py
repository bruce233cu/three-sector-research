from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SectorMetricInput:
    trade_date: date
    object_id: str
    taxonomy_code: str
    taxonomy_version: str
    member_ids: tuple[str, ...]
    member_bars: pd.DataFrame
    benchmark_returns: pd.Series
    all_a_amount: pd.Series | None = None
    all_a_circ_mv: pd.Series | None = None


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0 or pd.isna(denominator):
        return None
    return float(numerator / denominator)


def _compound(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    return float((1.0 + clean).prod() - 1.0)


def calculate_sector_snapshot(value: SectorMetricInput) -> dict[str, Any]:
    required = {"security_id", "trade_date", "close", "amount", "pct_chg"}
    missing = sorted(required.difference(value.member_bars.columns))
    if missing:
        raise ValueError("member_bars missing columns: " + ",".join(missing))

    bars = value.member_bars.copy()
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.date
    bars = bars[bars["security_id"].isin(value.member_ids)]
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    bars["amount"] = pd.to_numeric(bars["amount"], errors="coerce")
    bars["pct_chg"] = pd.to_numeric(bars["pct_chg"], errors="coerce") / 100.0
    if "circ_mv" in bars:
        bars["circ_mv"] = pd.to_numeric(bars["circ_mv"], errors="coerce")

    member_count = len(set(value.member_ids))
    latest = bars[bars["trade_date"] == value.trade_date].copy()
    valid_return = latest[latest["pct_chg"].notna() & latest["amount"].gt(0)]
    valid_member_count = int(valid_return["security_id"].nunique())
    sector_return_coverage = _ratio(valid_member_count, member_count) or 0.0
    sector_return = float(valid_return["pct_chg"].mean()) if sector_return_coverage >= 0.70 else None

    daily = (
        bars[bars["amount"].gt(0) & bars["pct_chg"].notna()]
        .groupby("trade_date")
        .agg(sector_return=("pct_chg", "mean"), valid=("security_id", "nunique"))
        .sort_index()
    )
    daily["coverage"] = daily["valid"] / member_count if member_count else np.nan
    daily.loc[daily["coverage"] < 0.70, "sector_return"] = np.nan
    benchmark = pd.to_numeric(value.benchmark_returns, errors="coerce").copy()
    benchmark.index = pd.to_datetime(benchmark.index).date
    benchmark = benchmark.sort_index()

    def rs(window: int) -> tuple[float | None, float]:
        joined = pd.concat([daily["sector_return"], benchmark.rename("benchmark")], axis=1).loc[: value.trade_date].tail(window)
        valid = joined.dropna()
        coverage = len(valid) / window
        if coverage < 0.90:
            return None, coverage
        return float(_compound(valid.iloc[:, 0]) - _compound(valid.iloc[:, 1])), coverage

    rs_values = {window: rs(window) for window in (5, 10, 20)}
    benchmark_return = float(benchmark.get(value.trade_date)) if value.trade_date in benchmark.index and pd.notna(benchmark.get(value.trade_date)) else None

    valid_amount = latest[latest["amount"].gt(0)]
    sector_amount = float(valid_amount["amount"].sum()) if not valid_amount.empty else None
    turnover_share = None
    turnover_intensity = None
    if value.all_a_amount is not None and value.trade_date in value.all_a_amount.index and sector_amount is not None:
        turnover_share = _ratio(sector_amount, float(value.all_a_amount.loc[value.trade_date]))
        daily_amount = bars[bars["amount"].gt(0)].groupby("trade_date")["amount"].sum()
        shares = daily_amount.div(pd.to_numeric(value.all_a_amount, errors="coerce")).replace([np.inf, -np.inf], np.nan).dropna().loc[: value.trade_date].tail(60)
        median_share = float(shares.median()) if len(shares) >= 40 else None
        if turnover_share is not None and median_share is not None and median_share > 0:
            turnover_intensity = float(turnover_share / median_share)

    up_ratio = None
    if sector_return_coverage >= 0.70 and valid_member_count:
        up_ratio = float(valid_return["pct_chg"].gt(0).sum() / valid_member_count)

    by_security = {sid: group.sort_values("trade_date") for sid, group in bars.groupby("security_id")}
    breadth: dict[str, list[bool]] = {"above_ma20": [], "above_ma60": [], "new_high_60": []}
    for sid in value.member_ids:
        group = by_security.get(sid)
        if group is None:
            continue
        closes = group[group["trade_date"] <= value.trade_date]["close"].dropna()
        for window, key in ((20, "above_ma20"), (60, "above_ma60")):
            if len(closes) >= window:
                breadth[key].append(bool(closes.iloc[-1] > closes.tail(window).mean()))
        if len(closes) >= 60:
            breadth["new_high_60"].append(bool(closes.iloc[-1] >= closes.tail(60).max()))

    breadth_coverage = {key: _ratio(len(vals), member_count) or 0.0 for key, vals in breadth.items()}
    breadth_values = {
        key: (float(sum(vals) / len(vals)) if vals and breadth_coverage[key] >= 0.70 else None)
        for key, vals in breadth.items()
    }

    top3_turnover_share = None
    if sector_amount and len(valid_amount) >= 3:
        top3_turnover_share = float(valid_amount.nlargest(3, "amount")["amount"].sum() / sector_amount)

    top3_return_contribution = None
    contribution_coverage = 0.0
    if "circ_mv" in bars:
        previous_dates = sorted(d for d in bars["trade_date"].unique() if d < value.trade_date)
        if previous_dates:
            prior = bars[bars["trade_date"] == previous_dates[-1]][["security_id", "circ_mv"]]
            contributions = valid_return[["security_id", "pct_chg"]].merge(prior, on="security_id", how="inner")
            contributions = contributions[contributions["circ_mv"].gt(0)].copy()
            contribution_coverage = _ratio(contributions["security_id"].nunique(), member_count) or 0.0
            contributions["positive_contribution"] = (contributions["circ_mv"] * contributions["pct_chg"]).clip(lower=0)
            total_positive = contributions["positive_contribution"].sum()
            if total_positive > 0 and contribution_coverage >= 0.70:
                top3_return_contribution = float(contributions.nlargest(3, "positive_contribution")["positive_contribution"].sum() / total_positive)

    turnover_cap_deviation = None
    if "circ_mv" in latest and value.all_a_circ_mv is not None and value.trade_date in value.all_a_circ_mv.index and turnover_share is not None:
        member_mv = latest["circ_mv"].dropna().sum()
        cap_share = _ratio(float(member_mv), float(value.all_a_circ_mv.loc[value.trade_date]))
        if cap_share and cap_share > 0:
            turnover_cap_deviation = float((turnover_share - cap_share) / cap_share)

    coverage = {
        "member": 1.0 if member_count else 0.0,
        "sector_return": sector_return_coverage,
        "up_ratio": sector_return_coverage,
        **breadth_coverage,
        "top3_turnover_share": _ratio(len(valid_amount), member_count) or 0.0,
        "top3_return_contribution": contribution_coverage,
        "rs_5": rs_values[5][1],
        "rs_10": rs_values[10][1],
        "rs_20": rs_values[20][1],
        "turnover_share": 1.0 if turnover_share is not None else 0.0,
        "turnover_cap_deviation": 1.0 if turnover_cap_deviation is not None else 0.0,
    }
    freeze_reasons: list[str] = []
    if sector_return_coverage < 0.70:
        freeze_reasons.append(f"sector_return_coverage={sector_return_coverage:.4f}<0.7000")
    if min(breadth_coverage.values(), default=0.0) < 0.70:
        freeze_reasons.append("breadth_coverage<0.7000")

    return {
        "as_of_date": value.trade_date.isoformat(),
        "object_id": value.object_id,
        "object_type": "industry",
        "taxonomy_code": value.taxonomy_code,
        "taxonomy_version": value.taxonomy_version,
        "member_count": member_count,
        "valid_member_count": valid_member_count,
        "sector_return": sector_return,
        "benchmark_return": benchmark_return,
        "rs_5": rs_values[5][0],
        "rs_10": rs_values[10][0],
        "rs_20": rs_values[20][0],
        "turnover_share": turnover_share,
        "turnover_intensity": turnover_intensity,
        "turnover_cap_deviation": turnover_cap_deviation,
        "up_ratio": up_ratio,
        **breadth_values,
        "top3_turnover_share": top3_turnover_share,
        "top3_return_contribution": top3_return_contribution,
        "metric_coverage_json": coverage,
        "critical_data_ok": not freeze_reasons,
        "stage_frozen": bool(freeze_reasons),
        "freeze_reason": ";".join(freeze_reasons) or None,
    }
