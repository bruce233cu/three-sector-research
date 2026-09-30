from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.mainline.cache.parquet_duckdb import ParquetDuckDBCache
from src.mainline.metrics.candidate import MetricValue, relative_strength, strongest_percentiles, turnover_metrics, win_rate
from src.mainline.providers.sws_index import SW2021_LEVEL1, SwsIndexProvider
from src.mainline.rules.candidate import evaluate_s1


def invalid(reason: str) -> MetricValue:
    return MetricValue(None, False, 0.0, reason)


def _jsonable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, MetricValue):
        return value.dict()
    raise TypeError(type(value).__name__)


def run(config_path: Path, output_dir: Path, cache_dir: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    cache = ParquetDuckDBCache(cache_dir)
    provider = SwsIndexProvider()
    run_id = str(uuid.uuid4())
    fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    all_rows: list[dict] = []
    snapshots: list[dict] = []

    windows = config["windows"]
    global_start = min(date.fromisoformat(item["start"]) for item in windows) - timedelta(days=110)
    global_end = max(date.fromisoformat(item["end"]) for item in windows)
    benchmark = provider.fetch("801003", "申万A股指数", global_start, global_end)
    benchmark_frame = benchmark.frame.set_index("trade_date")
    benchmark_artifact = cache.put("phase2a_index", f"801003:{global_start}:{global_end}", benchmark.frame, source_id=benchmark.source_id, source_version=benchmark.source_version)
    snapshots.append(benchmark_artifact.__dict__)
    sectors = {}
    for code, name in SW2021_LEVEL1.items():
        series = provider.fetch(code, name, global_start, global_end)
        sectors[code] = series
        artifact = cache.put("phase2a_index", f"{code}:{global_start}:{global_end}", series.frame, source_id=series.source_id, source_version=series.source_version)
        snapshots.append(artifact.__dict__)

    for window in windows:
        start, end = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
        trade_dates = [d for d in benchmark_frame.index if start <= d <= end]
        for trade_date in trade_dates:
            day_metrics: dict[str, dict[str, MetricValue]] = {}
            for code, series in sectors.items():
                sf = series.frame.set_index("trade_date").loc[:trade_date]
                bf = benchmark_frame.loc[:trade_date]
                aligned = sf[["pct_chg"]].join(bf[["pct_chg"]], how="inner", lsuffix="_sector", rsuffix="_benchmark")
                turnover = turnover_metrics(sf.get("amount", pd.Series(dtype=float)), bf.get("amount", pd.Series(dtype=float)))
                mean20 = turnover["turnover_share_20d_mean"]
                share = turnover["turnover_share"]
                vs20 = invalid("turnover_share_or_mean_invalid") if not (share.valid and mean20.valid) else MetricValue(float(share.value - mean20.value), True, min(share.coverage, mean20.coverage))
                day_metrics[code] = {
                    "rs_5": relative_strength(aligned.pct_chg_sector, aligned.pct_chg_benchmark, window=5),
                    "rs_10": relative_strength(aligned.pct_chg_sector, aligned.pct_chg_benchmark, window=10),
                    "win_5": win_rate(aligned.pct_chg_sector, aligned.pct_chg_benchmark, window=5),
                    "turnover_share_vs_20d": vs20,
                    "turnover_intensity": turnover["turnover_intensity"],
                    "up_ratio_vs_all_a": invalid("constituent_breadth_input_unavailable"),
                    "above_ma20_vs_all_a": invalid("constituent_breadth_input_unavailable"),
                }
            percentiles = strongest_percentiles({code: metrics["rs_5"] for code, metrics in day_metrics.items()})
            for code, metrics in day_metrics.items():
                metrics["rs_5_cross_section_percentile"] = percentiles[code]
                decision = evaluate_s1(metrics, rule_version=config["rule_version"], parameter_profile=config["parameter_profile"])
                all_rows.append({
                    "run_id": run_id, "window_id": window["id"], "window_kind": window["kind"],
                    "trade_date": trade_date, "object_id": f"SW1:{code}", "taxonomy_code": code,
                    "industry_name": SW2021_LEVEL1[code], "taxonomy_version": "SW2021",
                    "metrics": {key: value.dict() for key, value in metrics.items()}, **decision,
                })

    canonical = json.dumps(all_rows, ensure_ascii=False, sort_keys=True, default=_jsonable)
    checksum = hashlib.sha256(canonical.encode()).hexdigest()
    summary = []
    frame = pd.DataFrame(all_rows)
    for window_id, group in frame.groupby("window_id"):
        s1 = group[group.final_decision == "S1"]
        dates = group.trade_date.nunique()
        transitions = 0
        for _, sector in group.sort_values("trade_date").groupby("taxonomy_code"):
            transitions += int(((sector.final_decision.shift() == "S1") & (sector.final_decision == "S0")).sum())
        summary.append({
            "window_id": window_id, "trading_days": int(dates), "s1_occurrences": int(len(s1)),
            "s1_industries": int(s1.taxonomy_code.nunique()), "candidate_to_s0": transitions,
            "data_insufficient": int((group.final_decision == "DATA_INSUFFICIENT").sum()),
            "candidate_switch_frequency": float(s1.groupby("trade_date").taxonomy_code.nunique().mean()) if len(s1) else 0.0,
        })
    payload = {"run_id": run_id, "fetched_at": fetched_at, "rule_version": config["rule_version"], "parameter_profile": config["parameter_profile"], "result_checksum": checksum, "summary": summary, "results": all_rows, "source_snapshots": snapshots}
    (output_dir / "phase2a_results.json").write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=_jsonable) + "\n", encoding="utf-8")
    (output_dir / "phase2a_summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/phase2a_casebook_v1.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/phase2a/runtime"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/mainline/phase2a"))
    args = parser.parse_args()
    result = run(args.config, args.output, args.cache)
    print(json.dumps({"run_id": result["run_id"], "checksum": result["result_checksum"], "summary": result["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
