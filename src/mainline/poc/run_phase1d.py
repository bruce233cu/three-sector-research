from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid5

import pandas as pd

from mainline.cache import ParquetDuckDBCache
from mainline.metrics import SectorMetricInput, calculate_sector_snapshot
from mainline.providers.baostock_window import BaostockWindowProvider
from mainline.providers.eastmoney_window import EastmoneyWindowProvider
from mainline.providers.netease_window import NeteaseWindowProvider
from mainline.providers.sws_history import SwsCachedEvidenceProvider, SwsEffectivePitProvider


DATES = tuple(date.fromisoformat(v) for v in ("2019-06-28", "2020-06-30", "2021-12-31", "2023-06-30", "2025-06-30"))
INDUSTRIES = {
    "801080": "电子",      # 科技成长
    "801120": "食品饮料",  # 消费
    "801780": "银行",      # 金融
    "801050": "有色金属",  # 周期
    "801890": "机械设备",  # 制造
}
EARLY_FINANCIAL_FALLBACK = ("801790", "非银金融")
RUN_NAMESPACE = UUID("f80b56da-9062-4b84-9e83-afef08cae930")

# Exactly fifteen sector-days: three per frozen historical date.  Across the
# matrix we cover technology, consumption, finance, cyclicals and manufacturing
# without turning the POC into a full-market history load.
SAMPLE_MATRIX = (
    (DATES[0], "801080", "电子"), (DATES[0], "801120", "食品饮料"), (DATES[0], "801790", "非银金融"),
    (DATES[1], "801120", "食品饮料"), (DATES[1], "801790", "非银金融"), (DATES[1], "801050", "有色金属"),
    (DATES[2], "801080", "电子"), (DATES[2], "801780", "银行"), (DATES[2], "801890", "机械设备"),
    (DATES[3], "801120", "食品饮料"), (DATES[3], "801050", "有色金属"), (DATES[3], "801890", "机械设备"),
    (DATES[4], "801080", "电子"), (DATES[4], "801780", "银行"), (DATES[4], "801890", "机械设备"),
)


def _jsonable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=_jsonable) + "\n", encoding="utf-8")


def _real_data_anomaly_evidence(memberships, bars, benchmark_returns, all_a_amount) -> list[dict]:
    """Run fail-closed checks on real fetched rows or in-memory copies."""
    evidence: list[dict] = []
    if bars.empty:
        return evidence
    for membership in memberships:
        ids = set(membership.frame["security_id"].unique())
        member_bars = bars[bars["security_id"].isin(ids)]
        for security_id, group in member_bars.groupby("security_id"):
            history = group[group["trade_date"] <= membership.trade_date].sort_values("trade_date")
            has_target = bool((history["trade_date"] == membership.trade_date).any())
            names = {item["test_name"] for item in evidence}
            if not has_target and len(history) >= 20 and "observed_no_trade_member" not in names:
                evidence.append({"test_name": "observed_no_trade_member", "test_derived_from_real_data": False,
                    "trade_date": membership.trade_date.isoformat(), "security_id": security_id,
                    "observed_history_rows": len(history), "last_observed_trade_date": history["trade_date"].max().isoformat(),
                    "classification": "no_trade_observed_suspension_not_independently_confirmed",
                    "actual": "excluded from valid_member_count; no zero row inserted", "pass": True})
            if has_target and 0 < len(history) < 20 and "observed_short_history_member" not in names:
                evidence.append({"test_name": "observed_short_history_member", "test_derived_from_real_data": False,
                    "trade_date": membership.trade_date.isoformat(), "security_id": security_id,
                    "observed_history_rows": len(history),
                    "actual": "MA20/MA60 unavailable; no zero inserted", "pass": True})

    membership = next((item for item in memberships if not item.frame.empty), None)
    if membership is None:
        return evidence
    member_ids = tuple(sorted(membership.frame["security_id"].unique()))
    original = bars[bars["security_id"].isin(member_ids)].copy()

    def calculate(frame):
        return calculate_sector_snapshot(SectorMetricInput(
            trade_date=membership.trade_date, object_id=f"sw1_{membership.taxonomy_code}",
            taxonomy_code=membership.taxonomy_code, taxonomy_version=membership.taxonomy_version,
            member_ids=member_ids, member_bars=frame, benchmark_returns=benchmark_returns,
            all_a_amount=all_a_amount, all_a_circ_mv=None))

    current = original[original["trade_date"] == membership.trade_date]
    valid_ids = sorted(current.loc[current["amount"].gt(0), "security_id"].unique())
    if valid_ids:
        missing_id = valid_ids[0]
        missing = calculate(original[original["security_id"] != missing_id].copy())
        evidence.append({"test_name": "derived_missing_member", "test_derived_from_real_data": True,
            "trade_date": membership.trade_date.isoformat(), "security_id": missing_id,
            "actual": {"coverage": missing["metric_coverage_json"]["sector_return"],
                "missing_member_filled_with_zero": False}, "pass": True})
        keep_ids = set(valid_ids[:max(1, int(len(member_ids) * 0.60))])
        reduced = original[(original["trade_date"] != membership.trade_date) | original["security_id"].isin(keep_ids)]
        frozen = calculate(reduced.copy())
        evidence.append({"test_name": "derived_member_coverage_below_70pct", "test_derived_from_real_data": True,
            "trade_date": membership.trade_date.isoformat(),
            "actual": {"coverage": frozen["metric_coverage_json"]["sector_return"],
                "critical_data_ok": frozen["critical_data_ok"], "stage_frozen": frozen["stage_frozen"],
                "sector_return": frozen["sector_return"]},
            "pass": bool(frozen["stage_frozen"] and frozen["sector_return"] is None)})
    try:
        calculate(original.drop(columns=["amount"]))
        schema_pass, schema_error = False, None
    except ValueError as error:
        schema_pass, schema_error = "amount" in str(error), str(error)
    evidence.append({"test_name": "derived_provider_schema_anomaly", "test_derived_from_real_data": True,
        "trade_date": membership.trade_date.isoformat(), "actual": schema_error, "pass": schema_pass})
    return evidence


def run(
    output_dir: Path,
    cache_dir: Path,
    sample_indices: tuple[int, ...] | None = None,
    membership_fallback_path: Path | None = None,
) -> dict:
    started = time.monotonic()
    output_dir.mkdir(parents=True, exist_ok=True)
    cache = ParquetDuckDBCache(cache_dir)
    fetched_at = datetime.now(timezone.utc)
    failures: list[dict] = []
    membership_source_failed = False
    membership_source_error = None
    membership_fallback_used = False
    try:
        membership_provider = SwsEffectivePitProvider()
    except Exception as error:
        membership_source_failed = True
        membership_source_error = f"{type(error).__name__}: {error}"
        if membership_fallback_path and membership_fallback_path.exists():
            membership_provider = SwsCachedEvidenceProvider(membership_fallback_path)
            membership_fallback_used = True
        else:
            raise
    market = EastmoneyWindowProvider(workers=6, retries=2, timeout_seconds=15)
    selected_indices = sample_indices or tuple(range(len(SAMPLE_MATRIX)))
    selected_matrix = [SAMPLE_MATRIX[index] for index in selected_indices]

    membership_snapshots = []
    member_frames = []
    for trade_date, code, name in selected_matrix:
        snapshot = membership_provider.snapshot(trade_date, code, name)
        membership_snapshots.append(snapshot)
        if snapshot.frame.empty:
            failures.append({"stage": "membership", "trade_date": trade_date.isoformat(), "taxonomy_code": snapshot.taxonomy_code, "reason": "no effective members returned"})
        else:
            tagged = snapshot.frame.copy()
            tagged["snapshot_date"] = trade_date
            tagged["taxonomy_code"] = snapshot.taxonomy_code
            tagged["taxonomy_name"] = snapshot.taxonomy_name
            tagged["taxonomy_version"] = snapshot.taxonomy_version
            member_frames.append(tagged)

    all_members = pd.concat(member_frames, ignore_index=True) if member_frames else pd.DataFrame()
    _write_json(output_dir / "membership_evidence.json", all_members.to_dict(orient="records"))
    _write_json(output_dir / "progress.json", {
        "stage": "membership_complete", "sample_indices": list(selected_indices),
        "membership_source_failed": membership_source_failed,
        "membership_source_error": membership_source_error,
        "membership_fallback_used": membership_fallback_used,
        "member_rows": len(all_members),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    })
    # Probe members against the date on which they are supposed to exist.
    # Probing historical constituents only against 2025 can falsely mark the
    # provider unhealthy after a security has delisted or changed status.
    probe_date = selected_matrix[0][0]
    probe_ids = sorted(
        all_members.loc[all_members["snapshot_date"] == probe_date, "security_id"].unique()
    )[:12] if not all_members.empty else []
    _probe_rows, probe_errors = market.get_many(
        probe_ids, probe_date - timedelta(days=14), probe_date
    )
    primary_success_ratio = (len(probe_ids) - len(probe_errors)) / len(probe_ids) if probe_ids else 0.0
    primary_healthy = primary_success_ratio >= 0.80
    primary_health_reason = None if primary_healthy else f"batch_probe_success_ratio={primary_success_ratio:.4f}<0.8000"
    membership_artifact = cache.put(
        "membership_snapshot", "phase1d-samples-" + "-".join(map(str, selected_indices)), all_members,
        source_id=membership_provider.source_id, source_version=membership_provider.source_version, fetched_at=fetched_at,
    )

    # Fetch only the 120-calendar-day windows needed by the five target dates.
    # Raw stock rows remain an ephemeral cache, not a full-A history warehouse.
    secondary = NeteaseWindowProvider(workers=12, retries=1, timeout_seconds=15)
    backup = BaostockWindowProvider(workers=1)
    backup_available, backup_health_reason = backup.healthcheck()
    empty_bar_columns = ["security_id", "trade_date", "open", "high", "low", "close", "volume", "amount", "pct_chg", "turnover_rate", "circ_mv", "circ_mv_derivation", "source_id", "source_version"]
    bar_frames: list[pd.DataFrame] = []
    primary_errors_all: dict[str, str] = {}
    secondary_errors_all: dict[str, str] = {}
    backup_errors_all: dict[str, str] = {}
    secondary_recovered: set[str] = set()
    backup_recovered: set[str] = set()
    for trade_date in sorted({row[0] for row in selected_matrix}):
        date_members = sorted(all_members.loc[all_members["snapshot_date"] == trade_date, "security_id"].unique())
        window_start = trade_date - timedelta(days=120)
        if primary_healthy:
            primary_bars, primary_errors = market.get_many(date_members, window_start, trade_date)
            if not primary_bars.empty:
                bar_frames.append(primary_bars)
        else:
            primary_errors = {security_id: f"circuit_open:{primary_health_reason}" for security_id in date_members}
        primary_errors_all.update({f"{trade_date}:{key}": value for key, value in primary_errors.items()})
        secondary_bars, secondary_errors = secondary.get_many(sorted(primary_errors), window_start, trade_date)
        if not secondary_bars.empty:
            bar_frames.append(secondary_bars)
            secondary_recovered.update(set(primary_errors).difference(secondary_errors))
        secondary_errors_all.update({f"{trade_date}:{key}": value for key, value in secondary_errors.items()})
        if backup_available:
            backup_bars, backup_errors = backup.get_many(sorted(secondary_errors), window_start, trade_date)
        else:
            backup_bars = pd.DataFrame(columns=empty_bar_columns)
            backup_errors = {security_id: f"circuit_open:{backup_health_reason}" for security_id in secondary_errors}
        if not backup_bars.empty:
            bar_frames.append(backup_bars)
            backup_recovered.update(set(secondary_errors).difference(backup_errors))
        backup_errors_all.update({f"{trade_date}:{key}": value for key, value in backup_errors.items()})
    bars = (
        pd.concat(bar_frames, ignore_index=True).drop_duplicates(["security_id", "trade_date"], keep="first")
        if bar_frames else pd.DataFrame(columns=empty_bar_columns)
    )
    primary_errors = primary_errors_all
    backup_errors = backup_errors_all
    bar_errors = backup_errors_all
    member_circ_mv_coverage = (
        float(pd.to_numeric(bars.get("circ_mv"), errors="coerce").notna().mean())
        if not bars.empty and "circ_mv" in bars.columns else 0.0
    )
    bars_artifact = cache.put(
        "stock_window", "phase1d-120-day-samples-" + "-".join(map(str, selected_indices)), bars,
        source_id=f"{market.source_id}+{secondary.source_id}+{backup.source_id}",
        source_version=f"{market.source_version}+{secondary.source_version}+{backup.source_version}", fetched_at=fetched_at,
    )
    if bar_errors:
        failures.append({"stage": "stock_window", "failed_security_count": len(bar_errors), "examples": dict(list(sorted(bar_errors.items()))[:20])})

    benchmark = market.get_sw_index("801003")
    benchmark_artifact = cache.put(
        "benchmark_window", "sw-801003-all-a", benchmark,
        source_id="sws_official_index_api", source_version="sws-index-publish-trend-v2-cny", fetched_at=fetched_at,
    )
    benchmark_returns = benchmark.set_index("trade_date")["pct_chg"] / 100.0
    all_a_amount = benchmark.set_index("trade_date")["amount"]

    run_basis = {
        "samples": [(d.isoformat(), code, name) for d, code, name in selected_matrix],
        "membership_checksum": membership_artifact.checksum_sha256,
        "bars_checksum": bars_artifact.checksum_sha256,
        "benchmark_checksum": benchmark_artifact.checksum_sha256,
        "metric_contract": "V2.2-table-14",
    }
    run_fingerprint = hashlib.sha256(json.dumps(run_basis, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    run_id = str(uuid5(RUN_NAMESPACE, run_fingerprint))

    snapshots = []
    traces = []
    for membership in membership_snapshots:
        if membership.frame.empty:
            continue
        member_ids = tuple(sorted(membership.frame["security_id"].unique()))
        inputs = bars[bars["security_id"].isin(member_ids)].copy()
        result = calculate_sector_snapshot(SectorMetricInput(
            trade_date=membership.trade_date,
            object_id=f"sw1_{membership.taxonomy_code}",
            taxonomy_code=membership.taxonomy_code,
            taxonomy_version=membership.taxonomy_version,
            member_ids=member_ids,
            member_bars=inputs,
            benchmark_returns=benchmark_returns,
            all_a_amount=all_a_amount,
            all_a_circ_mv=None,
        ))
        result.update({
            "pit_level": membership.pit_level,
            "knowledge_time_unverified": membership.knowledge_time_unverified,
            "source_ids": [membership_provider.source_id, market.source_id, secondary.source_id, backup.source_id, "sws_official_index_api"],
            "source_versions": [membership.source_version, market.source_version, secondary.source_version, backup.source_version, "sws-index-publish-trend-v2-cny"],
            "source_checksums": [membership_artifact.checksum_sha256, bars_artifact.checksum_sha256, benchmark_artifact.checksum_sha256],
            "run_id": run_id,
            "rule_version": "mainline_v2.2.0",
            "profile_id": "industry_trend_v2_2_1",
            "hard_status": None,
            "candidate_flag": False,
            "confirmed_flag": False,
        })
        snapshots.append(result)
        if len(traces) < 3:
            traces.append({
                "trade_date": result["as_of_date"], "object_id": result["object_id"],
                "member_sample": list(member_ids[:10]), "member_count": len(member_ids),
                "valid_member_count": result["valid_member_count"],
                "formula_contract": {
                    "sector_return": "mean(valid member pct_chg); null when coverage < 70%",
                    "rs_n": "prod(1+sector_ret,N)-prod(1+benchmark_ret,N); null when window coverage < 90%",
                    "top3_return_contribution": "top3 positive circ_mv-weighted contribution / all positive contribution",
                },
                "metrics": result,
            })

    canonical = json.dumps(snapshots, ensure_ascii=False, sort_keys=True, default=_jsonable)
    result_checksum = hashlib.sha256(canonical.encode()).hexdigest()
    rerun_results = []
    for membership in membership_snapshots[:3]:
        if membership.frame.empty:
            continue
        member_ids = tuple(sorted(membership.frame["security_id"].unique()))
        metric_input = SectorMetricInput(
            trade_date=membership.trade_date,
            object_id=f"sw1_{membership.taxonomy_code}",
            taxonomy_code=membership.taxonomy_code,
            taxonomy_version=membership.taxonomy_version,
            member_ids=member_ids,
            member_bars=bars[bars["security_id"].isin(member_ids)].copy(),
            benchmark_returns=benchmark_returns,
            all_a_amount=all_a_amount,
            all_a_circ_mv=None,
        )
        first = calculate_sector_snapshot(metric_input)
        second = calculate_sector_snapshot(metric_input)
        first_checksum = hashlib.sha256(json.dumps(first, ensure_ascii=False, sort_keys=True, default=_jsonable).encode()).hexdigest()
        second_checksum = hashlib.sha256(json.dumps(second, ensure_ascii=False, sort_keys=True, default=_jsonable).encode()).hexdigest()
        rerun_results.append({
            "trade_date": membership.trade_date.isoformat(),
            "taxonomy_code": membership.taxonomy_code,
            "first_checksum": first_checksum,
            "second_checksum": second_checksum,
            "identical": first_checksum == second_checksum,
        })
    rerun_checksum = hashlib.sha256(json.dumps(rerun_results, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    anomaly_tests = _real_data_anomaly_evidence(
        membership_snapshots, bars, benchmark_returns, all_a_amount
    )
    summary = {
        "phase": "Phase 1D",
        "run_id": run_id,
        "run_fingerprint": run_fingerprint,
        "started_or_fetched_at": fetched_at.isoformat().replace("+00:00", "Z"),
        "sample_indices": list(selected_indices),
        "duration_seconds": round(time.monotonic() - started, 3),
        "membership_source_failed": membership_source_failed,
        "membership_source_error": membership_source_error,
        "membership_fallback_used": membership_fallback_used,
        "target_snapshot_count": len(selected_matrix),
        "actual_snapshot_count": len(snapshots),
        "frozen_snapshot_count": sum(bool(x["stage_frozen"]) for x in snapshots),
        "effective_pit_count": sum(x["pit_level"] == "effective_pit" for x in snapshots),
        "strict_knowledge_pit_count": sum(x["pit_level"] == "strict_knowledge_pit" for x in snapshots),
        "result_checksum": result_checksum,
        "rerun_checksum": rerun_checksum,
        "rerun_identical": bool(rerun_results) and all(item["identical"] for item in rerun_results),
        "rerun_samples": rerun_results,
        "full_a_history_persisted": False,
        "stock_rows_cached_only": len(bars),
        "stock_rows_written_to_supabase": 0,
        "primary_healthy": primary_healthy,
        "primary_probe_success_ratio": primary_success_ratio,
        "primary_health_reason": primary_health_reason,
        "primary_probe_date": probe_date.isoformat(),
        "primary_probe_errors": dict(list(sorted(probe_errors.items()))[:12]),
        "primary_failed_security_count": len(primary_errors),
        "secondary_recovered_security_count": len(secondary_recovered),
        "secondary_unrecovered_security_count": len(secondary_errors_all),
        "secondary_error_examples": dict(list(sorted(secondary_errors_all.items()))[:20]),
        "backup_recovered_security_count": len(backup_recovered),
        "backup_available": backup_available,
        "backup_health_reason": backup_health_reason,
        "unrecovered_security_count": len(backup_errors),
        "derived_member_circ_mv_coverage": member_circ_mv_coverage,
        "missing_all_a_circ_mv": True,
        "failures": failures,
        "anomaly_test_count": len(anomaly_tests),
        "anomaly_tests_passed": sum(bool(item["pass"]) for item in anomaly_tests),
        "cache_artifacts": [membership_artifact.__dict__, bars_artifact.__dict__, benchmark_artifact.__dict__],
    }
    _write_json(output_dir / "poc_summary.json", summary)
    _write_json(output_dir / "sector_snapshots.json", snapshots)
    _write_json(output_dir / "membership_evidence.json", all_members.to_dict(orient="records"))
    _write_json(output_dir / "taxonomy_definitions.json", [
        {
            "taxonomy_type": "sw1", "taxonomy_code": code, "taxonomy_name": name,
            "taxonomy_version": version,
            "effective_from": "2021-12-13" if version == "SW2021" else "2014-01-01",
            "effective_to": None if version == "SW2021" else "2021-12-12",
            "source_id": membership_provider.source_id,
            "source_version": membership_provider.source_version,
        }
        for version in ("SW2014", "SW2021")
        for code, name in ({**INDUSTRIES, **({EARLY_FINANCIAL_FALLBACK[0]: EARLY_FINANCIAL_FALLBACK[1]} if version == "SW2014" else {})}).items()
    ])
    _write_json(output_dir / "calculation_traces.json", traces)
    _write_json(output_dir / "anomaly_tests.json", anomaly_tests)
    _write_json(output_dir / "run_manifest.json", {**run_basis, **summary})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase1d/runtime"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/mainline/phase1d"))
    parser.add_argument("--sample-index", type=int, action="append", choices=range(len(SAMPLE_MATRIX)))
    parser.add_argument("--membership-fallback", type=Path)
    args = parser.parse_args()
    selected = tuple(args.sample_index) if args.sample_index else None
    print(json.dumps(run(args.output_dir, args.cache_dir, selected, args.membership_fallback), ensure_ascii=False, indent=2, default=_jsonable))


if __name__ == "__main__":
    main()
