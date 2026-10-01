"""V2.2.1 explicit ALL_A_EQUAL_WEIGHT availability clarification.

Inputs are normalized decimal daily returns with independently certified
historical universe and return semantics. This module never certifies providers.
"""
from dataclasses import dataclass, replace
from datetime import date
import math
import pandas as pd

from .availability import calculate_v221_snapshot

BENCHMARK_ID = "ALL_A_EQUAL_WEIGHT"
BENCHMARK_MIN_COVERAGE = 0.95


@dataclass(frozen=True)
class BenchmarkDay:
    trade_date: date
    benchmark_return: float | None
    benchmark_coverage: float | None
    universe_count: int
    valid_count: int
    all_a_amount: float | None
    amount_coverage: float | None
    reason: str | None
    source_snapshot_ids: tuple[str, ...]


def calculate_benchmark_day(trade_date, universe, observations, *,
                            universe_verified, returns_verified,
                            source_snapshot_ids=()):
    """Universe: id/share_type/list_date/delist_date; bars: id/return/amount.

    ST shares remain included. Delisting day is inclusive. Missing observations,
    suspension and zero trading amount remain missing; they are never zero returns.
    An unknown denominator has NULL coverage, not a claimed zero percent.
    """
    trade_date = pd.Timestamp(trade_date).date()
    if not universe_verified or universe.empty:
        return BenchmarkDay(trade_date, None, None, 0, 0, None, None,
                            "historical_all_a_universe_unverified", tuple(source_snapshot_ids))
    u = universe.copy()
    if u.security_id.duplicated().any():
        raise ValueError("duplicate historical universe security")
    listed = pd.to_datetime(u.list_date, errors="coerce")
    delisted = pd.to_datetime(u.delist_date, errors="coerce")
    if listed.isna().any():
        raise ValueError("unknown listing date")
    ids = set(u.loc[(u.share_type == "A") & (listed <= pd.Timestamp(trade_date))
                    & (delisted.isna() | (delisted >= pd.Timestamp(trade_date))), "security_id"])
    if not ids:
        return BenchmarkDay(trade_date, None, None, 0, 0, None, None,
                            "empty_historical_all_a_universe", tuple(source_snapshot_ids))
    bars = observations.copy()
    if bars.security_id.duplicated().any():
        raise ValueError("duplicate security/day observation")
    bars = bars[bars.security_id.isin(ids)]
    amount = pd.to_numeric(bars.amount, errors="coerce")
    returns = pd.to_numeric(bars.daily_return, errors="coerce")
    amount_valid = amount.map(lambda x: pd.notna(x) and math.isfinite(x) and x > 0)
    valid = amount_valid & returns.map(lambda x: pd.notna(x) and math.isfinite(x) and x >= -1)
    coverage = int(valid.sum()) / len(ids)
    amount_coverage = int(amount_valid.sum()) / len(ids)
    available = returns_verified and coverage >= BENCHMARK_MIN_COVERAGE
    reason = None if available else ("daily_return_semantics_unverified" if not returns_verified
                                     else "benchmark_coverage_below_95_percent")
    # Original amount definition: sum valid observed A-share amounts. Its
    # provider/dataset quality gate remains independent of benchmark's 95%.
    total_amount = float(amount[amount_valid].sum()) if amount_valid.any() else None
    return BenchmarkDay(trade_date, float(returns[valid].mean()) if available else None,
                        coverage, len(ids), int(valid.sum()), total_amount,
                        amount_coverage, reason, tuple(source_snapshot_ids))


def calculate_v221_with_benchmark(value, days):
    """Only verified ALL_A outputs enter V2.2.1; legacy 801003 cannot enter."""
    if len(value.member_ids) != len(set(value.member_ids)):
        raise ValueError("duplicate membership: reject before metric propagation")
    calendar = sorted(pd.Timestamp(d).date() for d in value.market_trading_dates
                      if pd.Timestamp(d).date() <= value.trade_date)
    if len(calendar) != len(set(calendar)) or not calendar or calendar[-1] != value.trade_date:
        raise ValueError("invalid target market calendar")
    if len({d.trade_date for d in days}) != len(days):
        raise ValueError("duplicate benchmark day")
    by_date = {d.trade_date: d for d in days}
    benchmark = pd.Series({d: by_date[d].benchmark_return if d in by_date else None
                           for d in calendar}, dtype=float)
    amounts = pd.Series({d: by_date[d].all_a_amount if d in by_date else None
                         for d in calendar}, dtype=float)
    bars = value.member_bars.copy()
    bars["trade_date"] = pd.to_datetime(bars.trade_date).dt.date
    # A fixed market-calendar window prevents missing dates stretching RS/median.
    bars = bars[bars.trade_date.isin(calendar[-60:])]
    result = calculate_v221_snapshot(replace(value, member_bars=bars,
                                             benchmark_returns=benchmark.reindex(calendar[-60:]),
                                             all_a_amount=amounts.reindex(calendar[-60:])))
    current = by_date.get(value.trade_date)
    available = current is not None and current.benchmark_return is not None
    result["metric_coverage_json"]["benchmark"] = current.benchmark_coverage if current else None
    result["decision_reason"]["benchmark"] = {
        "identity": BENCHMARK_ID, "availability_threshold": .95,
        "rs_window_threshold": .90, "sector_internal_threshold": .70,
        "universe_count": current.universe_count if current else None,
        "valid_count": current.valid_count if current else None,
        "reason": current.reason if current else "benchmark_input_missing",
        "source_snapshot_ids": list(current.source_snapshot_ids) if current else [],
    }
    reasons = [r for r in (result["freeze_reason"] or "").split(";") if r]
    if not available:
        reasons.append(current.reason if current else "benchmark_input_missing")
    if result["turnover_share"] is None:
        reasons.append("historical_all_a_amount_unavailable")
    result.update(stage_frozen=bool(reasons), critical_data_ok=not reasons,
                  freeze_reason=";".join(reasons) or None)
    return result
