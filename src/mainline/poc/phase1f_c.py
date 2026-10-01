"""External POC orchestration. Frozen calculator is the single metric engine."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import multiprocessing as mp
import platform
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pandas as pd

from mainline.metrics import SectorMetricInput, calculate_sector_snapshot
from mainline.providers.phase1f_free import FIELDS, worker


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return clean(value.item())
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if pd.isna(value) or (isinstance(value, float) and not math.isfinite(value)):
        return None
    return value


def encoded(value):
    return json.dumps(clean(value), ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value) + b"\n")


def frame_records(f):
    return clean(f.sort_values(["security_id", "trade_date"]).to_dict("records")) if len(f) else []


def preflight(root, bundle):
    integrity = json.loads((bundle / "integrity.json").read_text(encoding="utf-8"))
    for relative, expected in integrity["files"].items():
        path = root / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("input/code checksum mismatch: " + relative)
    config = json.loads((bundle / "config.json").read_text(encoding="utf-8"))
    from mainline.providers.sws_history import SwsCachedEvidenceProvider
    provider = SwsCachedEvidenceProvider(bundle / "membership.json")
    snapshots = []
    for sample in config["samples"]:
        snap = provider.snapshot(date.fromisoformat(sample["trade_date"]), sample["taxonomy_code"], sample["industry_name"])
        f = snap.frame
        d = snap.trade_date
        if len(f) != sample["member_count"] or f.security_id.duplicated().any():
            raise ValueError("membership count/uniqueness mismatch: " + sample["sample_id"])
        if not ((f.effective_from <= d) & (f.effective_to.isna() | (f.effective_to >= d))).all():
            raise ValueError("membership effective-PIT violation")
        if snap.pit_level != "effective_pit" or not snap.knowledge_time_unverified:
            raise ValueError("PIT marker drift")
        snapshots.append(snap)
    return config, snapshots, integrity


class IsolatedClient:
    def __init__(self, name, config, servers=None):
        self.name, self.config, self.servers = name, config, servers
        self.process = None
        self.pipe = None
        self.info = None

    def start(self, timeout=45):
        if self.process is not None and self.process.is_alive():
            return self.info
        ctx = mp.get_context("spawn")
        self.pipe, child = ctx.Pipe()
        self.process = ctx.Process(target=worker, args=(child, self.name, self.config, self.servers), daemon=True)
        self.process.start()
        child.close()
        if not self.pipe.poll(timeout):
            self.close()
            return {"ok": False, "error": "timeout:provider initialization"}
        try:
            self.info = self.pipe.recv()
        except EOFError:
            self.info = {"ok": False, "error": "provider process exited during initialization"}
        return self.info

    def fetch(self, sid, start, end, budget=None):
        began = time.monotonic()
        allowed = min(self.config["timeout_seconds"], budget if budget is not None else 1e9)
        info = self.start(timeout=allowed)
        if not info["ok"]:
            return info
        try:
            self.pipe.send((sid, start, end))
            remaining = max(0,allowed-(time.monotonic()-began))
            if not self.pipe.poll(remaining):
                self.close()
                return {"ok": False, "error": "timeout:security fetch", "elapsed_time": time.monotonic()-began}
            return self.pipe.recv()
        except (EOFError, BrokenPipeError, OSError) as e:
            self.close()
            return {"ok": False, "error": "worker_error:" + str(e)}

    def close(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(2)
            self.process = None
        if self.pipe:
            self.pipe.close()
            self.pipe = None


def benchmark_worker(pipe):
    try:
        # Existing method calls only SWS 801003, never Eastmoney stock endpoints.
        from mainline.providers.eastmoney_window import EastmoneyWindowProvider
        f = EastmoneyWindowProvider(retries=2, timeout_seconds=10).get_sw_index("801003")
        pipe.send({"ok": True, "frame": f})
    except Exception as e:
        pipe.send({"ok": False, "error": f"{type(e).__name__}:{e}"})


def get_benchmark(path=None):
    if path:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("source_id") != "sws_official_index_api" or payload.get("amount_unit") != "CNY":
            raise ValueError("benchmark file must include existing SWS source/amount unit")
        rows = payload["rows"]
        if digest(rows) != payload["checksum"]:
            raise ValueError("benchmark checksum mismatch")
        f = pd.DataFrame(rows)
        f.trade_date = pd.to_datetime(f.trade_date).dt.date
        return f, payload
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe()
    process = ctx.Process(target=benchmark_worker, args=(child,), daemon=True)
    process.start()
    child.close()
    try:
        if not parent.poll(35):
            raise TimeoutError("benchmark source timeout")
        result = parent.recv()
        if not result["ok"]:
            raise RuntimeError(result["error"])
        return result["frame"], {"source_id": "sws_official_index_api",
            "source_version": "sws-index-publish-trend-v2-cny", "amount_unit": "CNY",
            "endpoint": "https://www.swsresearch.com/institute-sw/api/index_publish/trend/",
            "tls_policy": "unchanged existing adapter (verify=False); transport authenticity unverified"}
    finally:
        if process.is_alive():
            process.terminate()
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join(2)
        parent.close()


def stats(results):
    errors = [r for r in results if not r["ok"]]
    return {"request_count": len(results), "success_count": len(results)-len(errors),
        "failure_count": len(errors), "timeout_count": sum("timeout" in r.get("error", "").lower() for r in errors),
        "empty_result_count": sum(r.get("error") == "empty" for r in errors), "error_count": len(errors),
        "transport_request_count": sum(r.get("audit", {}).get("page_requests", 0) for r in results),
        "transport_count_complete": not bool(errors)}


def fetch_checked(client, sid, start, end, budget=None):
    result = client.fetch(sid, start, end, budget)
    if result["ok"] and result["frame"].empty:
        result = {"ok": False, "error": "empty", "audit": result["audit"]}
    if result["ok"] and not result["audit"]["unit_check_ok"]:
        result = {"ok": False, "error": "unit_validation_failed", "audit": result["audit"]}
    return result


def health_check(client, config, snapshots):
    began = time.monotonic()
    probes = []
    # Five securities spanning all three historical dates. Two independent calls.
    for i, snap in enumerate(snapshots):
        for sid in sorted(snap.frame.security_id)[:2 if i < 2 else 1]:
            probes.append((sid, snap.trade_date))
    results, details = [], []
    for sid, end in probes:
        pair = [fetch_checked(client, sid, end-timedelta(days=120), end) for _ in range(2)]
        results.extend(pair)
        enough = all(r["ok"] and len(r["frame"].close.dropna()) >= 60 and
                     (r["frame"].trade_date == end).any() for r in pair)
        identical = bool(enough and digest(frame_records(pair[0]["frame"])) == digest(frame_records(pair[1]["frame"])))
        details.append({"security_id": sid, "trade_date": end, "window_ok": bool(enough),
            "repeat_identical": identical, "calls": [{k:v for k,v in r.items() if k != "frame"} for r in pair]})
    ratio = sum(d["window_ok"] and d["repeat_identical"] for d in details)/len(details)
    # Every historical date must be supported; first date may tolerate one failure.
    dates_ok = all(any(d["trade_date"] == s.trade_date and d["window_ok"] and d["repeat_identical"] for d in details) for s in snapshots)
    counts = stats(results)
    return {"provider": client.name, **(client.info or {}), **counts, "empty_count":counts["empty_result_count"], "probes": details,
        "elapsed_time": time.monotonic()-began, "success_ratio": ratio,
        "health_pass": bool(ratio >= config["health_min_success_ratio"] and dates_ok)}


def calculate(sample, membership, bars, benchmark):
    d = membership.trade_date
    if len(bars) and (bars.trade_date.max() > d or not set(bars.security_id).issubset(set(membership.frame.security_id))):
        raise ValueError("future date or non-member row")
    b = benchmark[benchmark.trade_date <= d].sort_values("trade_date")
    dates = list(b.trade_date.tail(60))
    if len(dates) != 60 or dates[-1] != d or b.trade_date.duplicated().any():
        raise ValueError("trusted benchmark calendar lacks 60 sessions/target")
    # Only exact final 60 market sessions enter frozen breadth calculator.
    # Missing suspension dates are NOT filled or replaced by older closes.
    window = bars[bars.trade_date.isin(dates)].copy()
    returns = b.set_index("trade_date")["pct_chg"] / 100
    amount = b.set_index("trade_date")["amount"]
    snap = calculate_sector_snapshot(SectorMetricInput(d, sample["object_id"], sample["taxonomy_code"],
        membership.taxonomy_version, tuple(sorted(membership.frame.security_id)), window, returns, amount, None))
    coverage = snap["metric_coverage_json"]
    latest = window[window.trade_date == d]
    n = len(membership.frame)
    groups = {sid:g for sid,g in window.groupby("security_id")}
    exact = {}
    for size, key in [(20,"MA20_coverage"),(60,"MA60_coverage"),(60,"NEW_HIGH60_coverage")]:
        wanted = set(dates[-size:])
        exact[key] = sum(wanted.issubset(set(g.loc[g.close.notna(), "trade_date"])) for g in groups.values())/n
    # Diagnostic coverage does NOT redefine frozen metric values. If legacy
    # calculator admits stale/gapped closes, do not claim a complete closure.
    agrees = all(abs(exact[key]-coverage[metric]) < 1e-12 for key,metric in [
        ("MA20_coverage","above_ma20"),("MA60_coverage","above_ma60"),("NEW_HIGH60_coverage","new_high_60")])
    snap.update({"sample_id": sample["sample_id"], "trade_date": d, "taxonomy": sample["industry_name"],
        **exact, "window_coverage": min(exact.values()),
        "OHLCV_coverage": latest.dropna(subset=["open","high","low","close","volume"]).security_id.nunique()/n,
        "amount_coverage": latest.loc[latest.amount.notna(), "security_id"].nunique()/n,
        "circ_mv_coverage": latest.loc[latest.circ_mv.notna(), "security_id"].nunique()/n,
        "frozen_coverage_agrees_with_exact_window": agrees,
        "pit_level": membership.pit_level, "knowledge_time_unverified": True,
        "circ_mv_gap": ["turnover_cap_deviation","top3_return_contribution"],
        "null_fill_policy": "no_zero_no_ffill_no_future", "future_rows_used": False})
    needed = ["sector_return","benchmark_return","rs_5","rs_10","rs_20","turnover_share",
              "turnover_intensity","up_ratio","above_ma20","above_ma60","new_high_60","top3_turnover_share"]
    snap["market_window_pass"] = bool(min(exact.values()) >= .7 and agrees and snap["critical_data_ok"]
        and not snap["stage_frozen"] and all(snap[k] is not None for k in needed)
        and snap["OHLCV_coverage"] >= .7 and snap["amount_coverage"] >= .7)
    snap["full_metric_set_complete"] = not snap["circ_mv_gap"]
    return clean(snap)


def run_sample(client, config, sample, membership, benchmark, out, deadline, repetition):
    began = time.monotonic()
    sample_deadline = min(deadline, began+config["sample_budget_seconds"])
    frames, results, errors, source_rows = [], [], [], []
    d = membership.trade_date
    for i, sid in enumerate(sorted(membership.frame.security_id)):
        if time.monotonic() >= sample_deadline:
            errors.append({"security_id": sid, "reason": "budget_exhausted_unattempted", "repetition": repetition})
            continue
        result = fetch_checked(client, sid, d-timedelta(days=config["window_calendar_days"]), d,
                               sample_deadline-time.monotonic())
        results.append(result)
        if result["ok"]:
            f = result["frame"]
            frames.append(f)
            records = frame_records(f)
            checksum = digest(records)
            write(out / "cache" / client.name / str(repetition) / sample["sample_id"].replace(":","_") / (sid+".json"), records)
            source_rows.append({"security_id": sid, "row_count": len(f), "response_checksum": checksum,
                               "audit": result["audit"], "fetched_at": datetime.now(timezone.utc)})
        else:
            errors.append({"security_id": sid, "reason": result["error"], "repetition": repetition})
        if (i+1) % 25 == 0:
            print(f"{client.name} repeat={repetition} {sample['sample_id']} {i+1}/{len(membership.frame)}", flush=True)
    bars = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=FIELDS)
    checksum = digest(frame_records(bars))
    source_id = str(uuid5(NAMESPACE_URL, client.name+sample["sample_id"]+checksum))
    try:
        snap = calculate(sample, membership, bars, benchmark)
        recomputed = calculate(sample, membership, bars, benchmark)
        snap["same_input_recompute_identical"] = digest(snap) == digest(recomputed)
        snap["market_window_pass"] = snap["market_window_pass"] and snap["same_input_recompute_identical"]
    except Exception as e:
        # Not a replacement Freeze rule: computation unavailable is a POC wrapper status.
        snap = {**sample, "valid_member_count": None, "market_window_pass": False,
            "critical_data_ok": None, "stage_frozen": None, "freeze_reason": None,
            "calculation_status": "BLOCKED_INPUT", "calculation_error": str(e),
            **{k:None for k in ["window_coverage","MA20_coverage","MA60_coverage","NEW_HIGH60_coverage",
                               "OHLCV_coverage","amount_coverage","circ_mv_coverage"]}}
    snap.update({"provider": client.name, "library_version": (client.info or {}).get("library_version"),
        "repetition": repetition, **stats(results), "elapsed_time": time.monotonic()-began,
        "source_snapshot_ids": [source_id], "window_checksum": checksum,
        "budget_exhausted": any(e["reason"] == "budget_exhausted_unattempted" for e in errors)})
    snap["run_id"] = str(uuid5(NAMESPACE_URL, "phase1fc:"+digest({"sample":sample,"provider":client.name,
        "version":snap["library_version"],"membership":digest(clean(membership.frame.to_dict("records"))),"bars":checksum})))
    source = {"source_snapshot_id":source_id,"source_id":client.name,"sample_id":sample["sample_id"],
        "source_version":snap["library_version"], "repetition":repetition,"response_checksum":checksum,
        "securities":source_rows,"endpoint":(client.info or {}).get("endpoint"),"adjust":"unadjusted"}
    return snap, errors, source


def compare(first, second):
    ignored = {"repetition","elapsed_time","run_id","source_snapshot_ids"}
    keys = sorted((set(first)|set(second))-ignored)
    diff = {k:{"first":first.get(k),"second":second.get(k)} for k in keys if first.get(k) != second.get(k)}
    return {"identical": not diff, "differences":diff,
        "note":"No timing equality required; errors/counts/metrics/window checksum compared. Fresh fetch twice."}


def verify_results(folder):
    hashes = json.loads((folder / "checksums.json").read_text(encoding="utf-8"))
    for name, expected in hashes.items():
        if Path(name).name != name or hashlib.sha256((folder/name).read_bytes()).hexdigest() != expected:
            raise ValueError("result file checksum mismatch: " + name)
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    return {"checksums_ok":True,"status":summary["status"],"production_write_allowed":False}


def finalize(out, summary, metrics, health, errors, sources, env, integrity):
    write(out/"summary.json", summary)
    write(out/"metrics_output.json", metrics)
    write(out/"provider_health.json", health)
    write(out/"errors.json", errors)
    write(out/"source_manifest.json", sources)
    write(out/"environment.json", env)
    write(out/"coverage_report.json", [{k:v for k,v in r.items() if "coverage" in k or k in ["sample_id","provider","repetition"]} for r in metrics])
    write(out/"run_manifest.json", {"job_name":"phase1f_c_external_poc","run_id":str(uuid5(NAMESPACE_URL,digest(metrics))),
        "status":summary["status"],"runs":[{"sample_id":r["sample_id"],"run_id":r["run_id"],
        "source_snapshot_ids":r["source_snapshot_ids"]} for r in metrics],"input_integrity":integrity,
        "code_commit":env["git_sha"],"rule_version":"mainline_v2.2.0","profile_id":"industry_trend_v2_2_1",
        "source_snapshot_ids":sorted({sid for r in metrics for sid in r["source_snapshot_ids"]}),
        "parameter_hash":integrity.get("files",{}).get("config/parameter_profile_industry_trend_v1.json"),
        "production_writes":False})
    csv_rows = [{k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v) for k,v in r.items()} for r in metrics]
    pd.DataFrame(csv_rows).to_csv(out/"samples.csv", index=False, encoding="utf-8-sig")
    write(out/"checksums.json", {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name != "checksums.json"})
    # Return package excludes ephemeral stock cache. Local replay evidence remains
    # in cache until user explicitly cleans it, not a DB or permanent asset.
    import zipfile
    with zipfile.ZipFile(out/"phase1f_c_results.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.iterdir()):
            if p.is_file() and p.suffix in [".json",".csv"]:
                z.write(p,p.name)


def main(root, bundle):
    parser = argparse.ArgumentParser(description="Mainline external-only 3-sector POC (no DB)")
    parser.add_argument("--preflight", action="store_true", help="offline inputs/code validation; no行情 requests")
    parser.add_argument("--health-check", action="store_true", help="external health only; no sector batch")
    parser.add_argument("--external-network-approved", action="store_true")
    parser.add_argument("--servers-file", type=Path, help="optional JSON list of authorized TDX name/host/port")
    parser.add_argument("--benchmark-file", type=Path, help="existing trusted SWS JSON export, no guessed benchmark")
    parser.add_argument("--verify", type=Path, help="offline verify result hashes; not production acceptance")
    parser.add_argument("--clean-cache", type=Path, help="delete ONLY marked run's ephemeral cache")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_results(args.verify),ensure_ascii=False))
        return 0
    if args.clean_cache:
        folder = args.clean_cache.resolve()
        allowed = (root/"artifacts"/"phase1f_c").resolve()
        if folder.parent != allowed or not (folder/"summary.json").is_file():
            raise ValueError("cleanup accepts only one marked artifacts/phase1f_c/<run> folder")
        cache = folder/"cache"
        if cache.is_symlink() or cache.resolve().parent != folder:
            raise ValueError("unsafe cache target")
        if cache.is_dir():
            shutil.rmtree(cache)
        print("已删除该run临时个股缓存；结果报告保留。缓存删除后不可恢复，需重新获取。")
        return 0
    config, snapshots, integrity = preflight(root,bundle)
    if args.preflight:
        print(json.dumps({"status":"OFFLINE_PACKAGE_CHECK_PASS","samples":[
            {"sample_id":s["sample_id"],"members":len(m.frame)} for s,m in zip(config["samples"],snapshots)],
            "real_provider_poc":"NOT_STARTED","gate":"UNCHANGED"},ensure_ascii=False))
        return 0
    if not args.external_network_approved:
        parser.error("仅在外部可联网环境加 --external-network-approved；Work只运行 --preflight")
    out = root/"artifacts"/"phase1f_c"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True)
    env = {"OS":platform.platform(),"Python":sys.version,"timezone":str(datetime.now().astimezone().tzinfo),
        "execution_time":datetime.now(timezone.utc),"dependencies":{
            d.metadata["Name"]:d.version for d in importlib.metadata.distributions()},
        "git_branch":"mainline-phase1e","git_sha":integrity["base_commit"],
        "code_identity":"integrity.json files are authoritative (ZIP may have no .git)"}
    try:
        env["git_sha"] = subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,stderr=subprocess.DEVNULL,text=True).strip()
        env["git_branch"] = subprocess.check_output(["git","branch","--show-current"],cwd=root,stderr=subprocess.DEVNULL,text=True).strip()
    except (OSError,subprocess.CalledProcessError):
        pass
    metrics, health, errors, sources = [], [], [], []
    membership_sources = {}
    for sample,membership in zip(config["samples"],snapshots):
        checksum = digest(clean(membership.frame.to_dict("records")))
        source_id = str(uuid5(NAMESPACE_URL,"membership:"+sample["sample_id"]+checksum))
        membership_sources[sample["sample_id"]] = source_id
        sources.append({"source_snapshot_id":source_id,"source_id":"sws_official_cached_membership_evidence",
            "dataset_code":"membership_snapshot","sample_id":sample["sample_id"],"row_count":len(membership.frame),
            "response_checksum":checksum,"source_version":membership.source_version,
            "pit_level":membership.pit_level,"knowledge_time_unverified":True,
            "export_file_checksum":integrity["files"][str((bundle/"membership.json").relative_to(root))]})
    summary = {"status":"POC_NOT_STARTED","gate":"UNCHANGED","recommended_provider":None,
        "sample_scope":config["samples"],
        "production_write_allowed":False,"scope":"three fixed sector samples; stock rows ephemeral",
        "excluded_provider":"qstock uses Eastmoney historical upstream",
        "circ_mv_gap":["turnover_cap_deviation","top3_return_contribution"]}
    servers = json.loads(args.servers_file.read_text()) if args.servers_file else None
    benchmark = None
    benchmark_source_id = None
    if not args.health_check:
        try:
            benchmark, evidence = get_benchmark(args.benchmark_file)
            wanted = set()
            for s in snapshots:
                wanted.update(benchmark.loc[(benchmark.trade_date <= s.trade_date) &
                    (benchmark.trade_date >= s.trade_date-timedelta(days=120)),"trade_date"])
            benchmark = benchmark[benchmark.trade_date.isin(wanted)].copy()
            benchmark_checksum = digest(clean(benchmark.to_dict("records")))
            benchmark_source_id = str(uuid5(NAMESPACE_URL,"sws-benchmark:"+benchmark_checksum))
            sources.append({**evidence,"source_snapshot_id":benchmark_source_id,"response_checksum":benchmark_checksum,
                            "rows":clean(benchmark.to_dict("records"))})
        except Exception as e:
            summary.update(status="BLOCKED_BENCHMARK_INPUT",reason=str(e))
            finalize(out,summary,metrics,health,errors,sources,env,integrity)
            print(out)
            return 2
    for name in config["provider_order"]:
        client = IsolatedClient(name,config,servers)
        try:
            init = client.start()
            if not init["ok"]:
                health.append({"provider":name,"health_pass":False,"initialization":init,
                    "library_version":None,"endpoint":None,"request_count":0,"success_count":0,
                    "failure_count":0,"timeout_count":0,"empty_count":0,"empty_result_count":0,
                    "error_count":0,"elapsed_time":None,"note":"initialization failed; zero security fetch attempts"})
                if "DEPENDENCY:" in init.get("error","") or "ModuleNotFoundError" in init.get("error",""):
                    summary.update(status="BLOCKED_DEPENDENCY",reason=init["error"])
                    break
                continue
            h = health_check(client,config,snapshots)
            health.append(h)
            write(out/"provider_health.json",health)
            if args.health_check:
                if h["health_pass"]:
                    summary.update(status="HEALTH_PASS_ONLY",recommended_provider=name)
                    break
                continue
            if not h["health_pass"]:
                continue
            deadline = time.monotonic()+config["provider_budget_seconds"]
            repeated = []
            for rep in range(1,config["repetitions"]+1):
                batch = []
                for sample,membership in zip(config["samples"],snapshots):
                    result, err, source = run_sample(client,config,sample,membership,benchmark,out,deadline,rep)
                    result["source_snapshot_ids"] += [membership_sources[sample["sample_id"]],benchmark_source_id]
                    batch.append(result)
                    metrics.append(result)
                    errors.extend({"sample_id":sample["sample_id"],"provider":name,**x} for x in err)
                    sources.append(source)
                    write(out/"metrics_output.json",metrics)
                    write(out/"errors.json",errors)
                repeated.append(batch)
            comparisons = [compare(a,b) for a,b in zip(*repeated)]
            summary.setdefault("repeat_comparisons",{})[name] = comparisons
            if all(r["market_window_pass"] for batch in repeated for r in batch) and all(c["identical"] for c in comparisons):
                summary.update(status="MARKET_WINDOW_POC_PASS_CIRC_MV_GAP",recommended_provider=name,
                    full_metric_set_complete=False,formal_G1_ready=False)
                break
            if any(r["budget_exhausted"] for batch in repeated for r in batch):
                summary.update(status="INCONCLUSIVE_BUDGET",reason="bounded execution; do not infer source cannot provide history")
                break
        finally:
            client.close()
    if summary["status"] == "POC_NOT_STARTED":
        summary["status"] = "POC_NOT_PASSED_REVIEW_ERRORS" if not args.health_check else "HEALTH_NOT_PASSED"
    summary["executed_sample_count"] = len({r["sample_id"] for r in metrics})
    summary["executed_sample_rounds"] = len(metrics)
    env["provider_versions"] = {h["provider"]:h.get("library_version") for h in health}
    finalize(out,summary,metrics,health,errors,sources,env,integrity)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print("交回结果包：",out/"phase1f_c_results.zip")
    return 0 if summary["recommended_provider"] else 2
