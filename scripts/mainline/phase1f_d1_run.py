"""One-shot external runner; reuse Phase C inputs, calculator and bounded clients."""
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from mainline.poc import phase1f_c as c


def main():
    config, snapshots, integrity = c.preflight(ROOT, ROOT / "scripts/mainline/phase1f_c")
    out = ROOT / "artifacts/phase1f_d1"
    out.mkdir(parents=True, exist_ok=True)
    env = {"OS": platform.platform(), "Python": sys.version, "timezone": "UTC",
           "execution_time": datetime.now(timezone.utc), "git_branch": os.environ.get("GITHUB_REF_NAME"),
           "git_sha": os.environ.get("GITHUB_SHA"), "runner": os.environ.get("RUNNER_ENVIRONMENT"),
           "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}}
    summary = {"status": "BLOCKED", "phase": "Phase 1F-D1", "gate": "UNCHANGED",
               "mainline_job": "pending_provider", "production_write_allowed": False,
               "recommended_provider": None, "sample_scope": config["samples"],
               "circ_mv_gap": ["turnover_cap_deviation", "top3_return_contribution"]}
    health, metrics, errors, sources, repeats = [], [], [], [], []
    try:
        for name in config["provider_order"]:
            if name == "Sina":
                install = subprocess.run([sys.executable, "-m", "pip", "install", "akshare==1.18.97"], timeout=600)
                if install.returncode:
                    summary["reason"] = "dependency_blocked:Sina installation"
                    break
            client = c.IsolatedClient(name, config)
            try:
                init = client.start()
                if not init["ok"]:
                    h = {"provider": name, "health_pass": False, "initialization": init,
                         "provider_version": importlib.metadata.version("pytdx" if name == "TDX" else "akshare"),
                         "request_count": 0, "success_count": 0, "failure_count": 0,
                         "timeout_count": 0, "empty_count": 0, "elapsed_time": None}
                    error = init.get("error", "")
                    if "TDX_SERVERS_UNREACHABLE:" in error:
                        h["server_audit"] = json.loads(error.split("TDX_SERVERS_UNREACHABLE:", 1)[1])
                    health.append(h)
                    summary["reason"] = "dependency_blocked" if "DEPENDENCY" in error else "transport_unavailable; environment vs Provider not established"
                    # No protocol response: never infer Provider failure from network failure.
                    break
                h = c.health_check(client, config, snapshots)
                h["provider_version"] = init["library_version"]
                h["suspension_policy"] = "missing sessions remain NULL; no fill"
                h["old_security_test"] = "historical snapshot members; delisted-specific test not established"
                health.append(h)
                c.write(out / "provider_health.json", health)
                if not h["health_pass"]:
                    # Only decoded, validated responses can establish objective window failure.
                    objective = any(call.get("ok") or call.get("error") == "empty"
                                    for p in h["probes"] for call in p["calls"])
                    h["verdict"] = "FAIL" if objective else "BLOCKED"
                    summary.update(status=h["verdict"], reason="historical health window insufficient" if objective else "environment/transport unverified")
                    if name == "TDX" and objective:
                        continue
                    break
                benchmark, evidence = c.get_benchmark()
                evidence["rows"] = c.clean(benchmark.to_dict("records"))
                evidence["response_checksum"] = c.digest(evidence["rows"])
                sources.append(evidence)
                deadline = time.monotonic() + config["provider_budget_seconds"]
                batches = []
                for rep in (1, 2):
                    batch = []
                    for sample, membership in zip(config["samples"], snapshots):
                        result, err, source = c.run_sample(client, config, sample, membership, benchmark, out, deadline, rep)
                        batch.append(result)
                        metrics.append(result)
                        sources.append(source)
                        errors.extend({"sample_id": sample["sample_id"], "provider": name, **e} for e in err)
                    batches.append(batch)
                checks = [{"sample_id": a["sample_id"], **c.compare(a, b)} for a, b in zip(*batches)]
                repeats.extend(checks)
                good = all(r["market_window_pass"] for r in metrics) and all(r["identical"] for r in checks)
                summary.update(status="PASS" if good else "PARTIAL", recommended_provider=name if good else None,
                               reason="two fresh rounds complete", recommend_phase1f_d2=good)
                break
            finally:
                client.close()
    except Exception as e:
        summary.update(status="BLOCKED", reason=f"execution/input blocked:{type(e).__name__}:{e}")
        errors.append({"reason": summary["reason"]})
    finally:
        if not metrics:
            metrics = [{**s, "provider": None, "execution_status": "NOT_RUN", "valid_member_count": None,
                        "run_id": None, "source_snapshot_ids": [], "critical_data_ok": None,
                        "stage_frozen": None, "freeze_reason": None,
                        **{k: None for k in ("window_coverage", "OHLCV_coverage", "amount_coverage",
                            "MA20_coverage", "MA60_coverage", "NEW_HIGH60_coverage", "circ_mv_coverage")}}
                       for s in config["samples"]]
        for sample, snap in zip(config["samples"], snapshots):
            sources.append({"sample_id": sample["sample_id"], "source_id": "sws_official_cached_membership_evidence",
                            "response_checksum": c.digest(c.clean(snap.frame.to_dict("records"))),
                            "row_count": len(snap.frame), "pit_level": snap.pit_level,
                            "knowledge_time_unverified": True})
        env["dependencies"] = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
        c.write(out / "repeatability_report.json", {"executed": bool(repeats), "samples": repeats})
        c.finalize(out, summary, metrics, health, errors, sources, env, integrity)
        print(json.dumps(c.clean(summary), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
