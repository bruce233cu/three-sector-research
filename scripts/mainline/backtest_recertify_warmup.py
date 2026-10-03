"""Create a NEW immutable warmup data version from current provider responses.

This is deliberately not a recovery of the original certified bytes. It reuses
the frozen effective-PIT universe and membership evidence, reacquires only the
2024-04-30 predecessor plus the 84 warmup sessions, and records both raw and
normalized checksums. It never writes Production or changes a rule/profile.
"""
import argparse
import gzip
import hashlib
import json
import math
import os
import sys
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mainline.backtest.runner import read, write
from mainline.engine.replay import digest
from mainline.metrics.historical_universe import historical_benchmark_universe_resolver
from mainline.providers.phase1f_free import normalize, version

ACCEPTED = {"success", "valid_no_trade", "valid_not_listed"}
PROVIDER = "Sina"
ENDPOINT = "https://finance.sina.com.cn/realstock/company/{symbol}/hisdata_klc2/klc_kl.js"
WINDOW_START = "2024-04-30"
WARMUP_START = "2024-05-06"
WARMUP_END = "2024-08-30"
WARMUP_SESSIONS = 84


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def classify_failure(exc):
    response = getattr(exc, "response", None)
    http = getattr(response, "status_code", None)
    text = str(exc)
    transient = http == 429 or (http is not None and http >= 500) or type(exc).__name__ in {
        "Timeout", "ConnectTimeout", "ReadTimeout", "ConnectionError"
    }
    if "unit" in text:
        category = "INVALID_UNIT"
    elif "schema" in text or "OHLC" in text or "duplicate" in text:
        category = "INVALID_SCHEMA"
    elif transient:
        category = "TRANSIENT_PROVIDER"
    elif "empty" in text:
        category = "UNPROVEN_EMPTY"
    else:
        category = "PROVIDER_OR_VALIDATION_ERROR"
    return {"category": category, "transient": transient, "http_status": http,
            "error_type": type(exc).__name__, "error": text}


def fetch_decode(sid, start, end):
    import requests
    import py_mini_racer
    from akshare.stock.cons import hk_js_decode, zh_sina_a_stock_hist_url

    if version("akshare") != "1.18.97":
        raise RuntimeError("DEPENDENCY: akshare==1.18.97 required")
    if "finance.sina.com.cn/realstock/company/" not in zh_sina_a_stock_hist_url:
        raise RuntimeError("unexpected upstream URL in pinned AKShare")
    symbol = sid.split(".")[1].lower() + sid.split(".")[0]
    url = zh_sina_a_stock_hist_url.format(symbol)
    fetched_at = utc_now()
    response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 mainline-warmup-recertification"})
    response.raise_for_status()
    js = py_mini_racer.MiniRacer()
    try:
        js.eval(hk_js_decode)
        raw = js.call("d", response.text.split("=", 1)[1].split(";", 1)[0].strip().strip('"'))
    finally:
        if hasattr(js, "close"):
            js.close()
    frame, audit = normalize(raw, sid, start, end)
    audit.update({"provider": PROVIDER, "provider_library": "akshare", "provider_library_version": version("akshare"),
                  "source_endpoint": ENDPOINT, "requested_url": url, "request_parameters": {"symbol": symbol},
                  "fetched_at": fetched_at, "response_checksum": sha_bytes(response.content),
                  "response_bytes": len(response.content), "http_status": response.status_code})
    return frame, audit, response.content


def recertify_one(sid, old, cache, start, end, active_dates, max_attempts=3):
    parquet = cache / (sid + ".parquet")
    audit_path = cache / (sid + ".json")
    raw_path = cache / (sid + ".response.bin")
    attempts = []
    for attempt in range(1, max_attempts + 1):
        try:
            cached = parquet.exists() and audit_path.exists() and raw_path.exists()
            if cached:
                frame = pd.read_parquet(parquet)
                audit = json.loads(audit_path.read_text())
                raw = raw_path.read_bytes()
                if audit.get("response_checksum") != sha_bytes(raw):
                    raise ValueError("cached raw response checksum mismatch")
                if audit.get("normalized_checksum") != digest(frame.astype(object).where(pd.notna(frame), None).to_dict("records")):
                    raise ValueError("cached normalized checksum mismatch")
            else:
                frame, audit, raw = fetch_decode(sid, start, end)
            if not frame.empty and not audit.get("unit_check_ok"):
                raise ValueError("amount unit not certified")
            status = "success"
            if frame.empty:
                if not active_dates:
                    status = "valid_not_listed"
                elif set(active_dates) <= set(audit.get("no_trade_dates", [])):
                    status = "valid_no_trade"
                else:
                    raise ValueError("empty response without certified no-trade proof")
            frame = frame.drop(columns=["circ_mv"], errors="ignore")
            frame["trade_date"] = frame["trade_date"].astype(str)
            normalized_checksum = digest(frame.astype(object).where(pd.notna(frame), None).to_dict("records"))
            audit.update({"security_id": sid, "status": status, "normalized_checksum": normalized_checksum,
                          "window_start": str(start), "window_end": str(end), "cache_reused": cached,
                          "request_count": 0 if cached else attempt, "retry_count": 0 if cached else attempt - 1,
                          "old_certified_response_checksum": old.get("raw_payload_checksum"),
                          "matches_old_certified_response": audit["response_checksum"] == old.get("raw_payload_checksum"),
                          "certification_relation": "NEW_DATA_VERSION_NOT_OLD_RECOVERY",
                          "attempts": attempts})
            if not cached:
                temp = parquet.with_suffix(".tmp.parquet")
                frame.to_parquet(temp, index=False)
                temp.replace(parquet)
                temp = audit_path.with_suffix(".tmp.json")
                temp.write_text(json.dumps(audit, ensure_ascii=False, separators=(",", ":")))
                temp.replace(audit_path)
                temp = raw_path.with_suffix(".tmp.bin")
                temp.write_bytes(raw)
                temp.replace(raw_path)
            return frame, audit
        except Exception as exc:
            failure = classify_failure(exc)
            attempts.append({"attempt": attempt, **failure})
            if not failure["transient"] or attempt == max_attempts:
                return None, {"security_id": sid, "status": "failed", "provider": PROVIDER,
                              "window_start": str(start), "window_end": str(end), "attempts": attempts, **failure,
                              "old_certified_response_checksum": old.get("raw_payload_checksum"),
                              "certification_relation": "NEW_DATA_VERSION_NOT_OLD_RECOVERY"}
            time.sleep(min(2 ** attempt, 8))


def main(g3_zip, production_zip, universe_zip, output, cache):
    started = utc_now()
    output.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(g3_zip) as archive:
        original = json.loads(archive.read("real_fetch_manifest.json"))
        provenance = json.loads(archive.read("real_input_provenance.json"))
        old_benchmark = json.loads(archive.read("real_benchmark.json"))
    with zipfile.ZipFile(production_zip) as archive:
        memberships = json.loads(archive.read("real_memberships.json"))
    with zipfile.ZipFile(universe_zip) as archive:
        intervals = json.loads(archive.read("temporary_universe_intervals.json"))

    dates = [row["trade_date"] for row in old_benchmark if row["trade_date"] < "2024-09-02"]
    if len(dates) != WARMUP_SESSIONS or dates[0] != WARMUP_START or dates[-1] != WARMUP_END:
        raise ValueError("frozen 84-session contract changed")
    calendar = read(ROOT / "reports/milestone-a-fast-close/calendar_input.json")
    predecessor = calendar[calendar.index(dates[0]) - 1]
    if predecessor != WINDOW_START:
        raise ValueError("warmup predecessor changed")
    universe_source = provenance["universe_source"]
    certificate = universe_source["metadata"]["certificate"]
    universe = {day: historical_benchmark_universe_resolver(day, intervals, certificate=certificate) for day in dates}
    if any(not value.verified for value in universe.values()):
        raise ValueError("effective-PIT universe not verified")
    old = {row["security_id"]: row for row in original}
    required = {member["security_id"] for value in universe.values() for member in value.members}
    absent_from_frozen_contract = sorted(required - set(old))
    if absent_from_frozen_contract:
        raise ValueError("effective-PIT universe contains securities absent from frozen acquisition contract: "
                         + ",".join(absent_from_frozen_contract))
    requested = sorted(required)
    active = {sid: [] for sid in requested}
    for day, value in universe.items():
        for member in value.members:
            if member["security_id"] in active:
                active[member["security_id"]].append(day)

    frames, audits = [], []
    start_date, end_date = date.fromisoformat(predecessor), date.fromisoformat(dates[-1])
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(recertify_one, sid, old[sid], cache, start_date, end_date, active[sid]) for sid in requested]
        for index, future in enumerate(as_completed(futures), 1):
            frame, audit = future.result()
            audits.append(audit)
            if frame is not None:
                frames.append(frame)
            if index % 250 == 0:
                print("WARMUP_RECERTIFICATION", index, len(requested), "failures", sum(x["status"] == "failed" for x in audits), flush=True)
    audits.sort(key=lambda item: item["security_id"])
    failures = [item for item in audits if item["status"] not in ACCEPTED]
    write(output / "provider_fetch_audit.json.gz", audits)
    write(output / "provider_failures.json", failures)
    if failures:
        write(output / "recertification_status.json", {"status": "FAIL", "created_at": started,
              "requested": len(requested), "accepted": len(requested) - len(failures), "failures": len(failures),
              "certification_relation": "NEW_DATA_VERSION_NOT_OLD_RECOVERY", "production_writes": 0})
        raise ValueError("new data version acquisition incomplete")

    bars = pd.concat(frames, ignore_index=True)
    bars["trade_date"] = bars["trade_date"].astype(str)
    if bars.duplicated(["security_id", "trade_date"]).any():
        raise ValueError("duplicate normalized security-date")
    close = bars.pivot(index="trade_date", columns="security_id", values="close").reindex([predecessor] + dates)
    amount = bars.pivot(index="trade_date", columns="security_id", values="amount").reindex([predecessor] + dates)
    returns = (close.div(close.shift(1)) - 1).where((close > 0) & (close.shift(1) > 0) & (amount > 0))
    ma20 = close.rolling(20, min_periods=20).mean()
    ma60 = close.rolling(60, min_periods=60).mean()
    high60 = close.rolling(60, min_periods=60).max()
    price_contract = [{"security_id": item["security_id"], "response_checksum": item.get("response_checksum"),
                       "normalized_checksum": item.get("normalized_checksum"), "status": item["status"]} for item in audits]
    price_version_checksum = digest(price_contract)
    namespace = uuid.UUID("8a86b07b-a346-5e0e-a123-5d483350b937")
    price_snapshot_id = str(uuid.uuid5(namespace, "warmup-price-v2:" + price_version_checksum))
    benchmark = []
    for day in dates:
        ids = [member["security_id"] for member in universe[day].members]
        previous = calendar[calendar.index(day) - 1]
        eligible = [member["security_id"] for member in universe[day].members if member["listing_date"] <= previous]
        valid_returns = returns.loc[day].reindex(eligible).dropna()
        coverage = len(valid_returns) / len(ids)
        benchmark.append({"trade_date": day, "benchmark_return": float(valid_returns.mean()) if coverage >= .95 else None,
                          "benchmark_coverage": coverage, "universe_count": len(ids), "valid_return_count": len(valid_returns)})
    benchmark_checksum = digest(benchmark)
    benchmark_snapshot_id = str(uuid.uuid5(namespace, "warmup-benchmark-v2:" + benchmark_checksum))
    source_ids = {"price": price_snapshot_id, "benchmark": benchmark_snapshot_id,
                  "membership": provenance["source_ids"]["membership"],
                  "universe": universe_source["source_snapshot_id"]}

    live = read(ROOT / "reports/milestone-d-baseline-v1/data/certified_board_inputs.json.gz")
    identity = {row["object_id"]: {key: row[key] for key in ["object_id", "object_type", "taxonomy_code", "taxonomy_version", "industry_name"]} for row in live}
    history, panel, membership_checks = {}, [], []
    for day in dates:
        ids = [member["security_id"] for member in universe[day].members]
        valid_returns = returns.loc[day].reindex(ids).dropna()
        benchmark_row = next(row for row in benchmark if row["trade_date"] == day)
        all_amount = amount.loc[day].reindex(ids).where(lambda values: values > 0).dropna()
        total_amount = float(all_amount.sum()) if len(all_amount) else None
        all_up = float(valid_returns.gt(0).mean()) if len(valid_returns) / len(ids) >= .70 else None
        available_ma20 = ma20.loc[day].reindex(ids).dropna()
        all_above_ma20 = float(close.loc[day].reindex(available_ma20.index).gt(available_ma20).mean()) if len(available_ma20) / len(ids) >= .70 else None
        membership = memberships[day]
        if membership["taxonomy_version"] != "SW2021" or not membership["complete"]:
            raise ValueError("warmup membership invalid")
        if set(membership["members"]) != set(identity):
            raise ValueError("warmup membership taxonomy incomplete")
        for object_id in sorted(identity):
            member_ids = membership["members"][object_id]
            if not set(member_ids) <= set(ids):
                raise ValueError("future/outside-universe membership")
            membership_checksum = digest({"trade_date": day, "taxonomy_version": "SW2021", "object_id": object_id,
                                          "members": sorted(member_ids)})
            if membership_checksum != membership["checksums"][object_id]:
                raise ValueError("membership checksum changed")
            sector_returns = returns.loc[day].reindex(member_ids).dropna()
            sector_amount = amount.loc[day].reindex(member_ids).where(lambda values: values > 0).dropna()
            return_coverage = len(sector_returns) / len(member_ids)
            amount_coverage = len(sector_amount) / len(member_ids)
            share = float(sector_amount.sum()) / total_amount if total_amount and amount_coverage >= .70 else None
            row = {**identity[object_id], "as_of_date": day, "member_count": len(member_ids),
                   "valid_member_count": len(sector_returns),
                   "sector_return": float(sector_returns.mean()) if return_coverage >= .70 else None,
                   "benchmark_return": benchmark_row["benchmark_return"], "turnover_share": share,
                   "up_ratio": float(sector_returns.gt(0).mean()) if return_coverage >= .70 else None,
                   "all_a_up_ratio": all_up, "all_a_above_ma20": all_above_ma20,
                   "top3_turnover_share": float(sector_amount.nlargest(3).sum() / sector_amount.sum()) if len(sector_amount) >= 3 else None,
                   "source_snapshot_ids": [source_ids[key] for key in ["membership", "price", "benchmark", "universe"]],
                   "membership_checksum": membership_checksum, "evidence_kind": "real_historical_board",
                   "metric_coverage_json": {"sector_return": return_coverage, "amount": amount_coverage,
                                            "benchmark": benchmark_row["benchmark_coverage"]}}
            for field, indicator in [("above_ma20", ma20), ("above_ma60", ma60), ("new_high_60", high60)]:
                available = indicator.loc[day].reindex(member_ids).dropna()
                current = close.loc[day].reindex(available.index)
                coverage = len(available) / len(member_ids)
                row["metric_coverage_json"][field] = coverage
                row[field] = float((current.ge(available) if field == "new_high_60" else current.gt(available)).mean()) if coverage >= .70 else None
            object_history = history.setdefault(object_id, [])
            object_history.append(row)
            for window in [5, 10, 20]:
                pairs = [(item["sector_return"], item["benchmark_return"]) for item in object_history[-window:]
                         if item["sector_return"] is not None and item["benchmark_return"] is not None]
                row["rs_" + str(window)] = math.prod(1 + left for left, right in pairs) - math.prod(1 + right for left, right in pairs) if len(pairs) / window >= .9 else None
                row["metric_coverage_json"]["rs_" + str(window)] = len(pairs) / window
            shares = [item["turnover_share"] for item in object_history[-60:] if item["turnover_share"] is not None]
            reference = median(shares) if len(shares) >= 40 else None
            row["turnover_intensity"] = share / reference if share is not None and reference is not None and reference > 0 else None
            row["critical_data_ok"] = all(row[field] is not None for field in ["sector_return", "benchmark_return", "rs_20",
                                              "turnover_share", "up_ratio", "above_ma20", "above_ma60", "new_high_60"])
            row["stage_frozen"] = not row["critical_data_ok"]
            row["freeze_reason"] = None if row["critical_data_ok"] else "required_metric_coverage_unavailable"
            panel.append(row)
        membership_checks.append({"trade_date": day, "complete": True, "industry_count": len(membership["members"]),
                                  "effective_pit": True, "future_membership_detected": False})
    if len(panel) != WARMUP_SESSIONS * 31:
        raise ValueError("warmup panel row count incomplete")

    current_benchmark = {row["trade_date"]: row["benchmark_return"] for row in benchmark}
    old_benchmark_map = {row["trade_date"]: row["benchmark_return"] for row in old_benchmark if row["trade_date"] in current_benchmark}
    changed_benchmark_dates = [day for day in dates if current_benchmark[day] != old_benchmark_map.get(day)]
    membership_payload = {day: memberships[day] for day in dates}
    panel_checksum = digest(panel)
    membership_checksum = digest(membership_payload)
    version_core = {"provider": PROVIDER, "price_version_checksum": price_version_checksum,
                    "benchmark_checksum": benchmark_checksum, "panel_checksum": panel_checksum,
                    "membership_checksum": membership_checksum, "trade_dates": [dates[0], dates[-1]],
                    "sessions": len(dates), "taxonomy_version": "SW2021"}
    version_id = "warmup_data_version_v2_" + digest(version_core)[:16]
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    fetch_run_id = "github-actions:" + str(run_id)
    source_snapshots = [
        {"source_snapshot_id": price_snapshot_id, "dataset_code": "warmup_security_daily",
         "source_version": version_id + ":price", "provider": PROVIDER, "fetched_at": started,
         "response_checksum": price_version_checksum, "row_count": len(bars),
         "raw_location": "workflow artifact mainline-warmup-recertification-cache-" + str(run_id),
         "pit_level": "effective_pit", "knowledge_time_verified": False},
        {"source_snapshot_id": benchmark_snapshot_id, "dataset_code": "warmup_equal_weight_benchmark",
         "source_version": version_id + ":benchmark", "provider": "derived_from_recertified_security_daily",
         "fetched_at": started, "response_checksum": benchmark_checksum, "row_count": len(benchmark),
         "raw_location": "reports/milestone-d-warmup/recertification-" + str(run_id) + "/warmup_benchmark.json",
         "pit_level": "effective_pit", "knowledge_time_verified": False},
    ]
    provider_fetch_runs = [{"fetch_run_id": fetch_run_id, "provider": PROVIDER, "source_endpoint": ENDPOINT,
        "started_at": started, "finished_at": utc_now(), "requested": len(requested), "accepted": len(audits),
        "failed": 0, "response_checksums_recorded": len(audits), "normalized_checksums_recorded": len(audits),
        "certification_relation": "NEW_DATA_VERSION_NOT_OLD_RECOVERY", "production_writes": 0}]
    manifest = {"version_id": version_id, "created_at": started, "certification_relation": "NEW_VERSION_NOT_ORIGINAL_RECOVERY",
                "provider": PROVIDER, "provider_library": "akshare", "provider_library_version": version("akshare"),
                "source_endpoint": ENDPOINT, "request_parameters": {"symbols": "effective-PIT benchmark universe",
                    "window_start": predecessor, "window_end": dates[-1], "adjust": "unadjusted", "fields": "OHLCV,amount"},
                "trade_date_range": {"predecessor": predecessor, "warmup_start": dates[0], "warmup_end": dates[-1], "sessions": len(dates)},
                "taxonomy_version": "SW2021", "membership_version": provenance["membership_source_version"],
                "security_universe": {"definition": "frozen effective-PIT benchmark universe", "requested": len(requested)},
                "source_snapshot_ids": source_ids, "provider_fetch_run_ids": [fetch_run_id],
                "fetched_at_range": [min(item["fetched_at"] for item in audits), max(item["fetched_at"] for item in audits)],
                "checksums": {"price_contract": price_version_checksum, "benchmark": benchmark_checksum,
                    "panel": panel_checksum, "membership": membership_checksum, "audit": digest(audits)},
                "response_checksums_recorded": len(audits), "normalized_checksums_recorded": len(audits),
                "knowledge_time_verified": False, "knowledge_time_unverified": True, "pit_level": "effective_pit",
                "missing_fields": ["circ_mv", "strict_knowledge_time"],
                "coverage": {"provider_requests": len(requested), "accepted": len(audits), "ratio": 1.0,
                    "panel_days": len(dates), "panel_industries": 31, "panel_rows": len(panel)},
                "old_version_comparison": {"old_certified_checksums_available": sum(bool(item.get("old_certified_response_checksum")) for item in audits),
                    "old_certified_checksums_unavailable": sum(not bool(item.get("old_certified_response_checksum")) for item in audits),
                    "old_certified_response_matches": sum(item["matches_old_certified_response"] for item in audits),
                    "old_certified_response_mismatches": sum(bool(item.get("old_certified_response_checksum")) and
                        not item["matches_old_certified_response"] for item in audits),
                    "benchmark_dates_changed": changed_benchmark_dates},
                "raw_response_storage": "workflow artifact mainline-warmup-recertification-cache-" + str(run_id),
                "normalized_security_storage": "workflow artifact mainline-warmup-recertification-cache-" + str(run_id),
                "no_future_membership_backfill": True, "null_filled_with_zero": False, "production_writes": 0,
                "formal_rule_changed": False, "formal_profile_changed": False, "version_core": version_core}
    write(output / "warmup_board_inputs.json.gz", panel)
    write(output / "warmup_memberships.json.gz", membership_payload)
    write(output / "warmup_benchmark.json", benchmark)
    write(output / "membership_verification.json", membership_checks)
    write(output / "source_snapshots.json", source_snapshots)
    write(output / "provider_fetch_runs.json", provider_fetch_runs)
    write(output / "warmup_data_version_manifest.json", manifest)
    write(output / "recertification_status.json", {"status": "PASS", "version_id": version_id,
          "requested": len(requested), "accepted": len(audits), "failures": 0, "panel_rows": len(panel),
          "panel_checksum": panel_checksum, "production_writes": 0})
    print(json.dumps({"status": "PASS", "version_id": version_id, "requests": len(requested),
                      "panel_rows": len(panel)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--g3-zip", type=Path, required=True)
    parser.add_argument("--production-zip", type=Path, required=True)
    parser.add_argument("--universe-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    try:
        main(args.g3_zip, args.production_zip, args.universe_zip, args.output, args.cache)
    except Exception as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        error_path = args.output / "recertification_error.json"
        if not error_path.exists():
            write(error_path, {"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc),
                               "created_at": utc_now(), "production_writes": 0})
        raise
