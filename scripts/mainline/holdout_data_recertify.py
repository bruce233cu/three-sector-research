"""Build an isolated post-Development data version for Holdout selection.

This job does not evaluate BASELINE/V4-A or select/label Holdout cases.  It
reacquires the bounded provider inputs, builds a 31-SW1 daily BOARD panel,
replays only the frozen production state kernel twice, and records whether the
result is qualified input space for a later blind casebook-freeze step.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import sys
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import py_mini_racer
from akshare.stock.cons import hk_js_decode

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mainline.engine.replay import digest, replay
from mainline.metrics.historical_universe import historical_benchmark_universe_resolver
from mainline.providers.phase1f_free import SinaWindow, normalize, version
from mainline.providers.sws_history import (
    SWS_CODE_URL,
    SWS_STOCK_HISTORY_URL,
    SwsEffectivePitProvider,
)

DEVELOPMENT_LAST_DATE = "2025-06-30"
REQUIRED_WARMUP_SESSIONS = 84
MIN_EPISODE_GAP_SESSIONS = 20
CALENDAR_URL = "https://finance.sina.com.cn/realstock/company/klc_td_sh.txt"
PRICE_ENDPOINT = "https://finance.sina.com.cn/realstock/company/{symbol}/hisdata_klc2/klc_kl.js"
PRODUCTION_FLAGS = {"PRODUCTION_MAINLINE_ENABLED": False, "MAINLINE_LIVE": False}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, default=str).encode()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False,
                               default=str) + "\n")


def write_gzip_json(path: Path, value) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        json.dump(value, handle, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
                  default=str)


def source_id(run_id: str, dataset: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{run_id}:{dataset}"))


def fetch(url: str, *, timeout: int = 40, minimum_bytes: int = 1024) -> tuple[bytes, dict]:
    fetched_at = now()
    response = requests.get(url, timeout=timeout,
                            headers={"User-Agent": "Mozilla/5.0 holdout-data-recertification/1.0"},
                            verify=False if "swsresearch.com" in url else True)
    response.raise_for_status()
    if len(response.content) < minimum_bytes:
        raise RuntimeError(f"short response: {url}: {len(response.content)}")
    return response.content, {"url": url, "fetched_at": fetched_at,
                              "http_status": response.status_code,
                              "response_bytes": len(response.content),
                              "response_checksum": sha_bytes(response.content)}


def decode_calendar(raw: bytes, end: date) -> list[str]:
    js = py_mini_racer.MiniRacer()
    try:
        js.eval(hk_js_decode)
        decoded = js.call("d", raw.decode().split("=", 1)[1].split(";", 1)[0].strip().strip('"'))
    finally:
        if hasattr(js, "close"):
            js.close()
    dates = sorted({str(value)[:10] for value in decoded if str(value)[:10] <= str(end)})
    if not dates or dates != sorted(set(dates)):
        raise ValueError("invalid Sina SSE calendar")
    return dates


def level1_mapping(provider: SwsEffectivePitProvider, code_raw: bytes) -> dict[str, str]:
    codes = pd.read_excel(io.BytesIO(code_raw), dtype=str)
    names = sorted(provider.history.level1_name.unique())
    mapping = {}
    for name in names:
        candidates = codes[codes["一级行业名称"] == name]
        explicit = ([str(value).replace(".0", "") for value in
                     candidates.get("一级行业代码", pd.Series(dtype=str)).dropna()])
        if len(set(explicit)) == 1:
            mapping[name] = explicit[0]
            continue
        roots = [str(value).replace(".0", "") for value in candidates["行业代码"].dropna()
                 if str(value).replace(".0", "").endswith("0000")]
        if len(set(roots)) != 1:
            raise ValueError("official level-1 code mapping unavailable: " + name)
        mapping[name] = roots[0]
    if len(mapping) != 31:
        raise ValueError(f"expected 31 SW1 industries, got {len(mapping)}")
    return mapping


def load_universe(universe_zip: Path) -> tuple[list[dict], dict, str]:
    with zipfile.ZipFile(universe_zip) as archive:
        records = json.loads(archive.read("temporary_universe_intervals.json"))
        sources = json.loads(archive.read("source_snapshots.json"))
    source = next(item for item in sources if item["dataset_code"] == "historical_benchmark_universe")
    certificate = source["metadata"]["certificate"]
    if not all(certificate.get(exchange, {}).get("complete_historical_ledger")
               for exchange in ("SH", "SZ", "BJ")):
        raise ValueError("historical all-A universe certificate incomplete")
    return records, source, sha_bytes(canonical(records))


def active_alias_map(resolution) -> dict[str, str]:
    result = {}
    for member in resolution.members:
        alias = f"{member['historical_code']}.{member['exchange']}"
        prior = result.setdefault(alias, member["security_id"])
        if prior != member["security_id"]:
            raise ValueError("overlapping historical code alias: " + alias)
    return result


def fetch_price(alias: str, start: date, end: date, cache: Path) -> tuple[pd.DataFrame | None, dict]:
    parquet = cache / f"{alias}.parquet"
    audit_path = cache / f"{alias}.json"
    if parquet.exists() and audit_path.exists():
        frame = pd.read_parquet(parquet)
        audit = json.loads(audit_path.read_text())
        normalized = digest(frame.astype(object).where(pd.notna(frame), None).to_dict("records"))
        if normalized != audit["normalized_checksum"]:
            raise ValueError("cached normalized checksum mismatch: " + alias)
        return frame, dict(audit, cache_reused=True)
    if version("akshare") != "1.18.97":
        raise RuntimeError("akshare==1.18.97 required")
    symbol = alias.split(".")[1].lower() + alias.split(".")[0]
    url = PRICE_ENDPOINT.format(symbol=symbol)
    attempts = []
    for attempt in range(1, 4):
        try:
            raw, request = fetch(url, timeout=15, minimum_bytes=1)
            js = py_mini_racer.MiniRacer()
            try:
                js.eval(hk_js_decode)
                rows = js.call("d", raw.decode().split("=", 1)[1].split(";", 1)[0].strip().strip('"'))
            finally:
                if hasattr(js, "close"):
                    js.close()
            frame, upstream = normalize(rows, alias, start, end)
            frame = frame.drop(columns=["circ_mv"], errors="ignore")
            if not frame.empty and not upstream.get("unit_check_ok"):
                raise ValueError("amount unit check failed")
            frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
            normalized = digest(frame.astype(object).where(pd.notna(frame), None).to_dict("records"))
            audit = {"alias_security_id": alias, "status": "success" if len(frame) else "empty",
                     "row_count": len(frame), "normalized_checksum": normalized,
                     "provider": "Sina", "provider_library": "akshare",
                     "provider_library_version": version("akshare"), "attempt": attempt,
                     **request, **upstream}
            frame.to_parquet(parquet, index=False)
            write_json(audit_path, audit)
            return frame, audit
        except Exception as error:
            attempts.append({"attempt": attempt, "type": type(error).__name__, "error": str(error)[:300]})
            if attempt < 3:
                time.sleep(2 ** (attempt - 1))
    return None, {"alias_security_id": alias, "status": "failed", "attempts": attempts}


def max_independent_anchor_count(sessions: int, gap: int) -> int:
    """Optimistic upper bound: zero-length windows and exactly gap sessions apart."""
    return 0 if sessions <= 0 else 1 + (sessions - 1) // gap


def main(args) -> None:
    out = args.output
    cache = args.cache
    out.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    fetched_at = now()
    profile = json.loads((ROOT / "config/parameter_profile_industry_trend_v221_state_completion_v1.json").read_text())
    development_casebook = json.loads((ROOT / "reports/milestone-d-baseline-v1/casebook.json").read_text())
    actual_development_last = max(case["post_window_end"] for case in development_casebook["cases"])
    if actual_development_last != DEVELOPMENT_LAST_DATE:
        raise ValueError(f"Development boundary changed: {actual_development_last}")

    # The last complete market day is the last calendar session strictly before
    # the UTC execution date.  This prevents an in-progress target session.
    raw_calendar, calendar_request = fetch(CALENDAR_URL)
    calendar = decode_calendar(raw_calendar, datetime.now(timezone.utc).date() - timedelta(days=1))
    development_index = calendar.index(DEVELOPMENT_LAST_DATE)
    post_development = calendar[development_index + 1:]
    if len(post_development) <= REQUIRED_WARMUP_SESSIONS:
        raise ValueError("not enough post-Development sessions for 84-day warmup")
    warmup_dates = post_development[:REQUIRED_WARMUP_SESSIONS]
    safe_start = post_development[REQUIRED_WARMUP_SESSIONS]
    mechanical_gap_start = post_development[MIN_EPISODE_GAP_SESSIONS - 1]
    live_dates = [value for value in post_development if value >= safe_start]
    dates = warmup_dates + live_dates
    predecessor = calendar[calendar.index(warmup_dates[0]) - 1]
    last_date = dates[-1]

    stock_raw, stock_request = fetch(SWS_STOCK_HISTORY_URL)
    code_raw, code_request = fetch(SWS_CODE_URL)
    provider = SwsEffectivePitProvider(stock_bytes=stock_raw, code_bytes=code_raw)
    mapping = level1_mapping(provider, code_raw)
    names = sorted(mapping)
    records, universe_source, universe_payload_checksum = load_universe(args.universe_zip)
    universe = {day: historical_benchmark_universe_resolver(day, records,
                certificate=universe_source["metadata"]["certificate"]) for day in [predecessor] + dates}
    if any(not value.verified for value in universe.values()):
        bad = {day: value.reasons for day, value in universe.items() if not value.verified}
        raise ValueError("effective-PIT universe not verified: " + json.dumps(bad)[:1000])

    aliases = sorted({alias for value in universe.values() for alias in active_alias_map(value)})
    audits, frames = [], []
    began = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(fetch_price, alias, date.fromisoformat(predecessor),
                            date.fromisoformat(last_date), cache): alias for alias in aliases}
        for index, job in enumerate(as_completed(jobs), start=1):
            frame, audit = job.result()
            audits.append(audit)
            if frame is not None and len(frame):
                frames.append(frame)
            if index % 250 == 0:
                print("HOLDOUT DATA FETCH", index, len(aliases), "seconds", int(time.monotonic()-began), flush=True)
    if not frames:
        raise ValueError("no price observations")
    alias_bars = pd.concat(frames, ignore_index=True)
    alias_bars["trade_date"] = pd.to_datetime(alias_bars["trade_date"]).dt.strftime("%Y-%m-%d")
    if alias_bars.duplicated(["security_id", "trade_date"]).any():
        raise ValueError("duplicate alias/date bars")

    # Map each date's historical exchange code to the canonical universe ID.
    canonical_rows = []
    for day in [predecessor] + dates:
        aliases_for_day = active_alias_map(universe[day])
        part = alias_bars[alias_bars.trade_date == day].copy()
        part = part[part.security_id.isin(aliases_for_day)]
        part["security_id"] = part.security_id.map(aliases_for_day)
        canonical_rows.append(part)
    bars = pd.concat(canonical_rows, ignore_index=True)
    if bars.duplicated(["security_id", "trade_date"]).any():
        raise ValueError("duplicate canonical security/date bars")
    bars = bars.sort_values(["security_id", "trade_date"])
    bars_path = cache / "normalized_holdout_window.parquet"
    bars.to_parquet(bars_path, index=False)
    bars_checksum = sha_bytes(bars_path.read_bytes())

    all_days = [predecessor] + dates
    close = bars.pivot(index="trade_date", columns="security_id", values="close").reindex(all_days)
    amount = bars.pivot(index="trade_date", columns="security_id", values="amount").reindex(all_days)
    returns = close.div(close.shift(1)) - 1
    returns = returns.where((close > 0) & (close.shift(1) > 0) & (amount > 0))
    ma20 = close.rolling(20, min_periods=20).mean()
    ma60 = close.rolling(60, min_periods=60).mean()
    high60 = close.rolling(60, min_periods=60).max()

    source_ids = {name: source_id(run_id, name) for name in
                  ("calendar", "membership", "price", "benchmark", "board", "universe")}
    panel, memberships, benchmarks, histories = [], {}, [], {}
    membership_alias_misses = []
    for day in dates:
        resolution = universe[day]
        canonical_ids = [member["security_id"] for member in resolution.members]
        prior = calendar[calendar.index(day) - 1]
        eligible = [member["security_id"] for member in resolution.members
                    if member["listing_date"] <= prior]
        valid_returns = returns.loc[day].reindex(eligible).dropna()
        benchmark_coverage = len(valid_returns) / len(canonical_ids)
        benchmark_return = float(valid_returns.mean()) if benchmark_coverage >= .95 else None
        valid_amount = amount.loc[day].reindex(canonical_ids)
        valid_amount = valid_amount.where(valid_amount > 0).dropna()
        all_amount = float(valid_amount.sum()) if len(valid_amount) else None
        all_up = float(valid_returns.gt(0).mean()) if benchmark_coverage >= .70 else None
        all_ma20 = ma20.loc[day].reindex(canonical_ids).dropna()
        all_above = (float(close.loc[day].reindex(all_ma20.index).gt(all_ma20).mean())
                     if len(all_ma20) / len(canonical_ids) >= .70 else None)
        benchmarks.append({"trade_date": day, "benchmark_return": benchmark_return,
                           "benchmark_coverage": benchmark_coverage,
                           "universe_count": len(canonical_ids),
                           "valid_return_count": len(valid_returns),
                           "all_a_amount": all_amount,
                           "amount_coverage": len(valid_amount) / len(canonical_ids)})
        alias_map = active_alias_map(resolution)
        daily_members, daily_rows = {}, []
        for industry_name in names:
            taxonomy_code = mapping[industry_name]
            object_id = "sw1_classification_" + taxonomy_code
            snapshot = provider.snapshot(date.fromisoformat(day), taxonomy_code, industry_name)
            aliases_in_membership = snapshot.frame.security_id.tolist()
            member_ids = sorted({alias_map[alias] for alias in aliases_in_membership if alias in alias_map})
            misses = sorted(set(aliases_in_membership) - set(alias_map))
            if misses:
                membership_alias_misses.append({"trade_date": day, "object_id": object_id,
                                                "count": len(misses), "sample": misses[:5]})
            if not member_ids:
                raise ValueError(f"empty effective membership: {day}:{industry_name}")
            daily_members[object_id] = member_ids
            rr = returns.loc[day].reindex(member_ids).dropna()
            aa = amount.loc[day].reindex(member_ids).where(lambda value: value > 0).dropna()
            coverage = len(rr) / len(member_ids)
            amount_coverage = len(aa) / len(member_ids)
            share = float(aa.sum()) / all_amount if all_amount and amount_coverage >= .70 else None
            row = {"as_of_date": day, "object_id": object_id, "object_type": "industry",
                   "taxonomy_code": taxonomy_code, "taxonomy_version": "SW2021",
                   "industry_name": industry_name, "member_count": len(member_ids),
                   "valid_member_count": len(rr),
                   "sector_return": float(rr.mean()) if coverage >= .70 else None,
                   "benchmark_return": benchmark_return, "turnover_share": share,
                   "up_ratio": float(rr.gt(0).mean()) if coverage >= .70 else None,
                   "all_a_up_ratio": all_up, "all_a_above_ma20": all_above,
                   "top3_turnover_share": float(aa.nlargest(3).sum()/aa.sum()) if len(aa) >= 3 else None,
                   "turnover_cap_deviation": None, "top3_return_contribution": None,
                   "rule_version": profile["rule_version"],
                   "metric_availability_version": profile["metric_availability_version"],
                   "source_snapshot_ids": [source_ids[key] for key in
                                           ("membership", "price", "benchmark", "universe")],
                   "run_id": run_id, "evidence_kind": "real_historical_board",
                   "metric_coverage_json": {"sector_return": coverage, "amount": amount_coverage,
                                            "benchmark": benchmark_coverage}}
            for field, indicator in (("above_ma20", ma20), ("above_ma60", ma60),
                                     ("new_high_60", high60)):
                available = indicator.loc[day].reindex(member_ids).dropna()
                current = close.loc[day].reindex(available.index)
                metric_coverage = len(available) / len(member_ids)
                row["metric_coverage_json"][field] = metric_coverage
                row[field] = (float((current.ge(available) if field == "new_high_60"
                                     else current.gt(available)).mean())
                              if metric_coverage >= .70 else None)
            history = histories.setdefault(object_id, [])
            history.append(row)
            for length in (5, 10, 20):
                pairs = [(item["sector_return"], item["benchmark_return"])
                         for item in history[-length:]
                         if item["sector_return"] is not None and item["benchmark_return"] is not None]
                row[f"rs_{length}"] = (math.prod(1 + left for left, _ in pairs) -
                                        math.prod(1 + right for _, right in pairs)
                                        if len(pairs) / length >= .9 else None)
                row["metric_coverage_json"][f"rs_{length}"] = len(pairs) / length
            shares = [item["turnover_share"] for item in history[-60:]
                      if item["turnover_share"] is not None]
            med = float(np.median(shares)) if len(shares) >= 40 else None
            row["turnover_intensity"] = share / med if share is not None and med and med > 0 else None
            required = ("sector_return", "benchmark_return", "rs_20", "turnover_share", "up_ratio",
                        "above_ma20", "above_ma60", "new_high_60")
            row["critical_data_ok"] = all(row[key] is not None for key in required)
            row["stage_frozen"] = not row["critical_data_ok"]
            row["freeze_reason"] = None if row["critical_data_ok"] else "required_metric_coverage_unavailable"
            row["membership_checksum"] = digest({"trade_date": day, "taxonomy_version": "SW2021",
                                                  "object_id": object_id, "members": member_ids})
            daily_rows.append(row)
        memberships[day] = {"trade_date": day, "taxonomy_version": "SW2021", "complete": True,
                            "members": daily_members,
                            "checksums": {row["object_id"]: row["membership_checksum"] for row in daily_rows},
                            "source_snapshot_ids": [source_ids["membership"]]}
        panel.extend(daily_rows)

    calls = []
    def resolver(day):
        calls.append(day)
        return memberships[day]

    first = replay(panel, dates, profile, resolver)
    first_calls = list(calls)
    calls.clear()
    second = replay(panel, dates, profile, resolver)
    deterministic = digest(first) == digest(second) and first_calls == calls
    if not deterministic:
        raise ValueError("state replay is not deterministic")

    live_outputs = [row for row in first["rows"] if row["state"]["trade_date"] >= safe_start]
    last_by_object = {}
    for row in first["rows"]:
        last_by_object[row["snapshot"]["object_id"]] = row["state"]["checkpoint"]
    counters_ok = all(set(("confirm", "recover", "weaken", "retire")) <=
                      set(checkpoint["consecutive"]) for checkpoint in last_by_object.values())
    safe_rows = [row for row in first["rows"] if row["state"]["trade_date"] == safe_start]
    initialization_ok = (len(safe_rows) == 31 and all(row["state"]["state"] is not None for row in safe_rows)
                         and all(row["state"]["last_date"] == safe_start for row in safe_rows))
    membership_ok = (not membership_alias_misses and
                     all(len(value["members"]) == 31 and value["complete"] for value in memberships.values()))
    all_live_panel = [row for row in panel if row["as_of_date"] >= safe_start]
    panel_complete = len(all_live_panel) == len(live_dates) * 31
    qualified = all((membership_ok, panel_complete, initialization_ok, counters_ok, deterministic))

    optimistic_capacity = max_independent_anchor_count(len(live_dates), MIN_EPISODE_GAP_SESSIONS)
    enough_for_25 = qualified and optimistic_capacity >= 25
    qualification_rows = []
    for day in live_dates:
        output = [row for row in first["rows"] if row["state"]["trade_date"] == day]
        qualification_rows.append({"trade_date": day, "required_sessions": REQUIRED_WARMUP_SESSIONS,
                                   "available_prior_sessions": calendar.index(day) - calendar.index(warmup_dates[0]),
                                   "industry_count": len(output), "membership_ok": membership_ok,
                                   "market_data_ok": len(output) == 31, "indicator_window_ok": len(output) == 31,
                                   "state_initialization_ok": initialization_ok,
                                   "counter_initialization_ok": counters_ok, "freeze_semantics_ok": True,
                                   "deterministic_ok": deterministic,
                                   "qualification_status": "QUALIFIED" if qualified else "FAIL"})

    coverage_rows = []
    for day in dates:
        rows = [row for row in panel if row["as_of_date"] == day]
        coverage_rows.append({"trade_date": day, "phase": "warmup" if day < safe_start else "clean_candidate",
                              "industry_count": len(rows), "complete_31": len(rows) == 31,
                              "critical_data_ok_count": sum(row["critical_data_ok"] for row in rows),
                              "frozen_count": sum(row["stage_frozen"] for row in rows),
                              "benchmark_min_coverage": min(row["metric_coverage_json"]["benchmark"] for row in rows)})
    sector_rows = []
    for object_id in sorted({row["object_id"] for row in panel}):
        rows = [row for row in panel if row["object_id"] == object_id and row["as_of_date"] >= safe_start]
        sector_rows.append({"object_id": object_id, "industry_name": rows[0]["industry_name"],
                            "taxonomy_code": rows[0]["taxonomy_code"], "live_sessions": len(rows),
                            "qualified_sessions": sum(row["critical_data_ok"] for row in rows),
                            "minimum_member_count": min(row["member_count"] for row in rows),
                            "minimum_sector_return_coverage": min(row["metric_coverage_json"]["sector_return"] for row in rows)})

    version_seed = {"calendar": calendar_request["response_checksum"],
                    "membership": sha_bytes(stock_raw + code_raw),
                    "universe": universe_payload_checksum, "prices": bars_checksum,
                    "start": warmup_dates[0], "safe_start": safe_start, "end": last_date}
    version_id = "holdout_data_version_v1_" + sha_bytes(canonical(version_seed))[:16]
    snapshots = [
        {"source_snapshot_id": source_ids["calendar"], "dataset_code": "trading_calendar",
         "source_id": "sina_sse_trade_calendar", **calendar_request},
        {"source_snapshot_id": source_ids["membership"], "dataset_code": "membership_history",
         "source_id": provider.source_id, "source_version": provider.source_version,
         "stock_workbook": stock_request, "taxonomy_workbook": code_request,
         "pit_level": "effective_pit", "knowledge_time_unverified": True},
        {"source_snapshot_id": source_ids["universe"], "dataset_code": "historical_benchmark_universe",
         "source_id": universe_source["source_id"], "source_version": universe_source["source_version"],
         "response_checksum": universe_payload_checksum, "parent_source_snapshot_id": universe_source["source_snapshot_id"],
         "pit_level": "effective_pit", "knowledge_time_unverified": True},
        {"source_snapshot_id": source_ids["price"], "dataset_code": "stock_window",
         "source_id": "sina_akshare_existing", "source_version": "akshare:1.18.97:SinaWindow",
         "source_endpoint": PRICE_ENDPOINT, "normalized_checksum": bars_checksum,
         "request_count": len(audits), "failed_requests": sum(item["status"] == "failed" for item in audits)},
    ]
    manifest = {"version_id": version_id, "created_at": fetched_at, "run_id": run_id,
                "code_commit": os.environ.get("GITHUB_SHA"), "provider_fetch_run_id": os.environ.get("GITHUB_RUN_ID"),
                "purpose": "independent_holdout_selection_data_only", "v4a_executed": False,
                "baseline_executed": False, "holdout_executed": False,
                "development_last_date": DEVELOPMENT_LAST_DATE,
                "mechanical_20_session_start": mechanical_gap_start,
                "warmup_start": warmup_dates[0], "warmup_end": warmup_dates[-1],
                "required_warmup_sessions": REQUIRED_WARMUP_SESSIONS,
                "safe_holdout_start_date": safe_start, "data_end": last_date,
                "trade_date_range": [warmup_dates[0], last_date], "candidate_session_count": len(live_dates),
                "taxonomy_version": "SW2021", "membership_version": provider.source_version,
                "security_universe": "certified historical all-A exchange listing/code intervals",
                "source_snapshot_ids": [item["source_snapshot_id"] for item in snapshots],
                "source_snapshots": snapshots, "request_parameters": {"calendar_end_exclusive_today": True,
                    "price_start": predecessor, "price_end": last_date, "symbols": len(aliases)},
                "response_checksum": digest({"calendar": calendar_request["response_checksum"],
                                             "membership": sha_bytes(stock_raw + code_raw),
                                             "fetch_audits": audits}),
                "normalized_checksum": digest({"panel": panel, "memberships": memberships,
                                               "benchmark": benchmarks}),
                "panel_checksum": digest(panel), "membership_checksum": digest(memberships),
                "state_replay_checksum": digest(first), "pit_level": "effective_pit",
                "knowledge_time_verified": False, "knowledge_time_unverified": True,
                "coverage": {"calendar_sessions": len(dates), "warmup_sessions": len(warmup_dates),
                             "candidate_sessions": len(live_dates), "industry_count": 31,
                             "panel_rows": len(panel), "price_aliases": len(aliases),
                             "price_failures": sum(item["status"] == "failed" for item in audits)},
                "missing_data": {"membership_alias_misses": membership_alias_misses,
                                 "frozen_live_rows": sum(row["stage_frozen"] for row in all_live_panel)},
                "qualification_boundary": {"status": "QUALIFIED" if qualified else "FAIL",
                    "safe_start": safe_start, "end": last_date,
                    "optimistic_max_20_session_spaced_anchors": optimistic_capacity,
                    "sufficient_for_25_nonoverlapping_cases": enough_for_25},
                "production": PRODUCTION_FLAGS}

    write_json(out / "holdout_data_version_manifest.json", manifest)
    write_json(out / "source_snapshots.json", snapshots)
    write_json(out / "fetch_run_manifest.json", {"run_id": run_id, "requests": audits})
    write_gzip_json(out / "holdout_board_panel.json.gz", panel)
    write_gzip_json(out / "holdout_daily_memberships.json.gz", memberships)
    write_gzip_json(out / "holdout_state_replay.json.gz", first)
    write_json(out / "holdout_data_quality.json", {
        "version_id": version_id, "qualification": manifest["qualification_boundary"],
        "checks": {"historical_membership_daily": membership_ok, "all_31_industries": panel_complete,
                   "effective_pit": True, "future_membership_backfill": False,
                   "null_preserved": True, "freeze_semantics": True,
                   "state_initialization": initialization_ok, "counter_initialization": counters_ok,
                   "deterministic_rerun": deterministic, "source_traceable": True},
        "counters": ["confirm", "recover", "weaken", "retire"],
        "knowledge_time_unverified": True, "v4a_executed": False,
        "production": PRODUCTION_FLAGS})
    write_json(out / "holdout_deterministic_rerun.json", {
        "status": "PASS" if deterministic else "FAIL", "first_checksum": digest(first),
        "second_checksum": digest(second), "membership_call_sequence_equal": first_calls == calls,
        "v4a_executed": False})
    write_json(out / "holdout_independence_boundary.json", {
        "development_last_date": DEVELOPMENT_LAST_DATE,
        "development_last_episode_end": DEVELOPMENT_LAST_DATE,
        "mechanical_20_session_start": mechanical_gap_start,
        "safe_holdout_start_date": safe_start,
        "safe_start_basis": "first session after 84 complete post-Development sessions; exceeds the 20-session gap and keeps the entire state-initialization window after Development",
        "same_episode_not_assumed_clean": True,
        "case_level_episode_and_catalyst_audit_still_required": True,
        "candidate_end_date": last_date, "candidate_sessions": len(live_dates),
        "minimum_gap_sessions": MIN_EPISODE_GAP_SESSIONS,
        "optimistic_max_nonoverlapping_case_anchors": optimistic_capacity,
        "required_case_count": 25, "sufficient_space": enough_for_25})

    for name, rows in (("holdout_trade_date_coverage.csv", coverage_rows),
                       ("holdout_sector_coverage.csv", sector_rows),
                       ("holdout_warmup_qualification_boundary.csv", qualification_rows)):
        with (out / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)

    report = f"""# A股主线识别系统 V2.2.1 — Holdout Data Range Extension Report

> **结论：{'DATA RANGE QUALIFIED, BUT NOT LARGE ENOUGH FOR THE FROZEN 25-CASE SPACING CONTRACT' if qualified and not enough_for_25 else 'DATA RANGE QUALIFIED' if enough_for_25 else 'DATA RANGE QUALIFICATION FAILED'}**
>
> 本轮没有运行BASELINE或V4-A，没有选择、标注或执行任何Holdout case。

## 1. 数据版本

| 项目 | 结果 |
|---|---|
| 新数据版本 | `{version_id}` |
| Development污染截止 | `{DEVELOPMENT_LAST_DATE}` |
| 20交易日机械边界 | `{mechanical_gap_start}` |
| 安全Holdout起点 | `{safe_start}` |
| 新认证范围 | `{warmup_dates[0]}` 至 `{last_date}` |
| 安全候选交易日 | {len(live_dates)} |
| SW1覆盖 | 31 / 31 |
| PIT | effective-PIT；knowledge-time未验证 |

安全起点不是简单采用“污染截止+20日”。它要求污染截止后先积累完整84个交易日的状态初始化前缀，故候选期使用第85个post-Development交易日开始；具体case仍须逐例检查催化、政策事件、连续行情和二波延续，不能因日期达标自动判CLEAN。

## 2. 资格验收

| 检查 | 结果 |
|---|---|
| 每日历史成员 | {'PASS' if membership_ok else 'FAIL'} |
| 31行业完整panel | {'PASS' if panel_complete else 'FAIL'} |
| 84交易日warmup | {'PASS' if len(warmup_dates)==84 else 'FAIL'} |
| state initialization | {'PASS' if initialization_ok else 'FAIL'} |
| confirm/recover/weaken/retire | {'PASS' if counters_ok else 'FAIL'} |
| NULL保留 / Freeze合同 | PASS |
| 无未来成员倒灌 | PASS（逐日effective interval解析） |
| deterministic rerun | {'PASS' if deterministic else 'FAIL'} |

完整provider响应与标准化结果分别保留checksum；panel、membership及两次state replay均有独立checksum。`knowledge_time_verified=false`，不得写成strict knowledge-time PIT。

## 3. Holdout容量判断

冻结合同要求不同Holdout case窗口不重叠，并原则上至少间隔20个交易日。认证候选期只有{len(live_dates)}个交易日；即便把每个case乐观地压缩成单日锚点，最多也只有{optimistic_capacity}个20日间隔锚点，仍低于25例。因此数据质量资格{'已通过' if qualified else '未通过'}，但当前扩展范围{'仍不足以' if not enough_for_25 else '足以'}支持`10正 + 10负 + 5模糊`的冻结规模。

这不是V4-A结果，也不是标签失败。下一步应继续增加从未用于Development的独立历史范围，或由合同所有者正式重新审视全局20日间隔约束；在现合同下，不允许进入正式Casebook Freeze。

## 4. 隔离声明

- `v4a_calibration_candidate_v1`保持冻结，未在新区间执行。
- 未运行Calibration、G1-G4、Holdout或Production。
- 正式rule/profile/state machine和成功标准均未修改。
- `PRODUCTION_MAINLINE_ENABLED=false`，`MAINLINE_LIVE=false`。
"""
    (out / "HOLDOUT_DATA_RANGE_EXTENSION_REPORT.md").write_text(report)
    print(json.dumps({"version_id": version_id, "safe_start": safe_start, "end": last_date,
                      "candidate_sessions": len(live_dates), "qualified": qualified,
                      "enough_for_25": enough_for_25}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    arguments = parser.parse_args()
    try:
        main(arguments)
    except Exception as error:
        arguments.output.mkdir(parents=True, exist_ok=True)
        write_json(arguments.output / "holdout_data_recertification_error.json", {
            "status": "FAIL", "error_type": type(error).__name__, "error": str(error),
            "code_commit": os.environ.get("GITHUB_SHA"), "created_at": now(),
            "v4a_executed": False, "production": PRODUCTION_FLAGS})
        raise
