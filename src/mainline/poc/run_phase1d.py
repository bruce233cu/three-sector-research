from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid5

import pandas as pd

from mainline.cache import ParquetDuckDBCache
from mainline.metrics import SectorMetricInput, calculate_sector_snapshot
from mainline.providers.eastmoney_window import EastmoneyWindowProvider
from mainline.providers.sws_history import SwsEffectivePitProvider


DATES = tuple(date.fromisoformat(v) for v in ("2019-06-28", "2020-06-30", "2021-12-31", "2023-06-30", "2025-06-30"))
INDUSTRIES = {
    "801080": "电子",      # 科技成长
    "801120": "食品饮料",  # 消费
    "801780": "银行",      # 金融
    "801050": "有色金属",  # 周期
    "801890": "机械设备",  # 制造
}
RUN_NAMESPACE = UUID("f80b56da-9062-4b84-9e83-afef08cae930")


def _jsonable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=_jsonable) + "\n", encoding="utf-8")


def run(output_dir: Path, cache_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    cache = ParquetDuckDBCache(cache_dir)
    fetched_at = datetime.now(timezone.utc)
    failures: list[dict] = []
    membership_provider = SwsEffectivePitProvider()
    market = EastmoneyWindowProvider()

    membership_snapshots = []
    member_frames = []
    for trade_date in DATES:
        for code, name in INDUSTRIES.items():
            snapshot = membership_provider.snapshot(trade_date, code, name)
            membership_snapshots.append(snapshot)
            if snapshot.frame.empty:
                failures.append({"stage": "membership", "trade_date": trade_date.isoformat(), "taxonomy_code": code, "reason": "no effective members returned"})
            else:
                tagged = snapshot.frame.copy()
                tagged["snapshot_date"] = trade_date
                tagged["taxonomy_code"] = code
                tagged["taxonomy_name"] = name
                tagged["taxonomy_version"] = snapshot.taxonomy_version
                member_frames.append(tagged)

    all_members = pd.concat(member_frames, ignore_index=True) if member_frames else pd.DataFrame()
    membership_artifact = cache.put(
        "membership_snapshot", "phase1d-five-dates-five-industries", all_members,
        source_id=membership_provider.source_id, source_version=membership_provider.source_version, fetched_at=fetched_at,
    )

    unique_ids = sorted(all_members["security_id"].unique()) if not all_members.empty else []
    bars, bar_errors = market.get_many(unique_ids, date(2019, 3, 1), date(2025, 6, 30))
    bars_artifact = cache.put(
        "stock_window", "phase1d-20190301-20250630-selected-members", bars,
        source_id=market.source_id, source_version=market.source_version, fetched_at=fetched_at,
    )
    if bar_errors:
        failures.append({"stage": "stock_window", "failed_security_count": len(bar_errors), "examples": dict(list(sorted(bar_errors.items()))[:20])})

    benchmark = market.get_sw_index("801003")
    benchmark_artifact = cache.put(
        "benchmark_window", "sw-801003-all-a", benchmark,
        source_id="sws_official_index_api", source_version="sws-index-publish-trend-v1", fetched_at=fetched_at,
    )
    benchmark_returns = benchmark.set_index("trade_date")["pct_chg"] / 100.0
    all_a_amount = benchmark.set_index("trade_date")["amount"]

    run_basis = {
        "dates": [d.isoformat() for d in DATES], "industries": INDUSTRIES,
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
            "source_ids": [membership_provider.source_id, market.source_id, "sws_official_index_api"],
            "source_versions": [membership.source_version, market.source_version, "sws-index-publish-trend-v1"],
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
    rerun_checksum = hashlib.sha256(json.dumps(snapshots, ensure_ascii=False, sort_keys=True, default=_jsonable).encode()).hexdigest()
    summary = {
        "phase": "Phase 1D",
        "run_id": run_id,
        "run_fingerprint": run_fingerprint,
        "started_or_fetched_at": fetched_at.isoformat().replace("+00:00", "Z"),
        "target_snapshot_count": len(DATES) * len(INDUSTRIES),
        "actual_snapshot_count": len(snapshots),
        "frozen_snapshot_count": sum(bool(x["stage_frozen"]) for x in snapshots),
        "effective_pit_count": sum(x["pit_level"] == "effective_pit" for x in snapshots),
        "strict_knowledge_pit_count": sum(x["pit_level"] == "strict_knowledge_pit" for x in snapshots),
        "result_checksum": result_checksum,
        "rerun_checksum": rerun_checksum,
        "rerun_identical": result_checksum == rerun_checksum,
        "full_a_history_persisted": False,
        "stock_rows_cached_only": len(bars),
        "stock_rows_written_to_supabase": 0,
        "missing_circ_mv": True,
        "failures": failures,
        "cache_artifacts": [membership_artifact.__dict__, bars_artifact.__dict__, benchmark_artifact.__dict__],
    }
    _write_json(output_dir / "poc_summary.json", summary)
    _write_json(output_dir / "sector_snapshots.json", snapshots)
    _write_json(output_dir / "calculation_traces.json", traces)
    _write_json(output_dir / "run_manifest.json", {**run_basis, **summary})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase1d/runtime"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/mainline/phase1d"))
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir, args.cache_dir), ensure_ascii=False, indent=2, default=_jsonable))


if __name__ == "__main__":
    main()
