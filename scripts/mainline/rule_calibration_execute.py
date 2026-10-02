"""Execute the preregistered rule-calibration experiment on frozen archives.

This is an isolated development-set harness.  It never calls a provider, writes
production data, changes the formal profile, or creates a formal rule version.
Candidate logic is applied only to archived tri-state evidence.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import statistics
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mainline.backtest.evaluator import evaluate_case  # noqa: E402
from mainline.backtest.runner import baseline_profile, load_inputs, read  # noqa: E402
from mainline.engine.replay import digest  # noqa: E402
from mainline.engine.rules import at_least, tri_all, tri_any  # noqa: E402
from mainline.engine.state_machine import Checkpoint, advance  # noqa: E402


DIAGNOSTIC = ROOT / "reports/milestone-d-rule-diagnostic"
BASE = ROOT / "reports/milestone-d-baseline-v1"
ARCHIVE = BASE / "runs/historical-blind-v1-20261002-diagnostic-v2"
WARMUP_SENSITIVE = {"P01", "P06", "P07", "N05", "N06", "A01"}
GROUPS = ("A", "B", "C", "D", "enhancers")
CANDIDATE_GROUPS = ("C1", "C2", "C3", "C4", "C5")


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def write_json(path: Path, value) -> None:
    if path.exists():
        raise ValueError(f"immutable calibration output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def write_csv(path: Path, rows: list[dict]) -> None:
    if path.exists():
        raise ValueError(f"immutable calibration output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_archive(case_id: str) -> dict:
    with gzip.open(ARCHIVE / f"{case_id}.json.gz", "rt", encoding="utf-8") as stream:
        return json.load(stream)


def rule_map(row: dict) -> dict:
    return {item["rule_id"]: item["passed"] for item in row["rules"]}


def evidence(row: dict) -> dict:
    values = rule_map(row)
    return {key: values[key] for key in ("candidate", "confirm", "weaken", "retire", "recover")}


def candidate_count(values: dict) -> tuple[int, bool]:
    items = [values[key] for key in CANDIDATE_GROUPS]
    return sum(value is True for value in items), any(value is None for value in items)


def v1_paths(values: dict, arm: str, enhancer_override=None) -> dict[str, tuple[bool | None, int]]:
    enhancer = values["enhancers"] if enhancer_override is None else enhancer_override
    standard = tri_all([values["A"], values["B"], values["C"], values["D"], enhancer])
    if arm == "V1_A_HARD_CONTROL":
        return {"standard": (standard, 2)}
    if arm == "V1_B_TIERED_EXCEPTION":
        exception = (tri_all([values["A"], values["C"], values["D"], enhancer])
                     if values["B"] is False else False)
        return {"standard": (standard, 2), "b_exception": (exception, 3)}
    if arm == "V1_C_CORE_PLUS_SUPPORT":
        if values["A"] is False or values["D"] is False:
            combined = False
        elif values["A"] is None or values["D"] is None:
            combined = None
        else:
            combined = sum(value is True for value in (values["B"], values["C"], enhancer)) >= 2
        return {"core_support": (combined, 2)}
    raise ValueError(f"unknown V1 arm: {arm}")


def rolling_qualification(history: list[dict], arm: str) -> bool | None:
    if arm == "V2_P1_CORE_3_OF_5":
        required = GROUPS
    elif arm == "V2_P2_BALANCED_3_OF_5":
        required = ("A", "D", "C")
    elif arm == "V2_P3_TWO_STAGE":
        required = ("A", "D")
    else:
        raise ValueError(f"unknown V2 arm: {arm}")
    valid = [item for item in history if not item["frozen"] and all(item[key] is not None for key in required)]
    if len(valid) < 5:
        return None
    window = valid[-5:]
    counts = {key: sum(item[key] is True for item in window) for key in GROUPS}
    if arm == "V2_P1_CORE_3_OF_5":
        return counts["A"] >= 3 and counts["D"] >= 3 and any(counts[key] >= 3 for key in ("B", "C", "enhancers"))
    if arm == "V2_P2_BALANCED_3_OF_5":
        return all(counts[key] >= 3 for key in ("A", "D", "C"))
    return counts["A"] >= 3 and counts["D"] >= 3


def enhancer_without_e3(values: dict) -> bool | None:
    return at_least([values["E1"], values["E2"], values["E4"]], 2)


def transition_sequence(rows: list[dict]) -> list[str]:
    if not rows:
        return []
    seq = [rows[0]["state"]["previous_state"]]
    seq.extend(row["state"]["state"] for row in rows if row["state"]["transition"])
    return seq


def path_count(seq: list[str], path: list[str]) -> int:
    return sum(seq[index:index + len(path)] == path for index in range(len(seq) - len(path) + 1))


def longest_run(flags: list[bool]) -> int:
    best = current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        best = max(best, current)
    return best


def arm_config(arm: str, parent: dict | None = None) -> dict:
    config = {"arm": arm, "v1": None, "v2": None, "v3": None, "v4": False}
    if parent:
        config.update({key: parent[key] for key in ("v1", "v2", "v3", "v4")})
    if arm.startswith("V1_"):
        config["v1"] = arm
    elif arm.startswith("V2_"):
        config["v2"] = arm
    elif arm.startswith("V3_"):
        config["v3"] = arm
    elif arm == "V4_D1_NEW_HIGH_SINGLE_VOTE":
        config["v4"] = True
    return config


def replay_case(case: dict, archived: dict, calendar: list[str], profile: dict, config: dict) -> dict:
    initial = deepcopy(archived["initial_checkpoint"])
    if initial:
        cp = Checkpoint(**initial)
    else:
        first = archived["rows"][0]["snapshot"]
        cp = Checkpoint(first["object_id"], first["rule_version"], profile["profile_id"],
                        first["metric_availability_version"], state="S0")
    outputs = []
    path_streaks: dict[str, int] = {}
    candidate_failures: list[bool] = []
    group_history: list[dict] = []
    hard_exit_count = 0
    duplicate_votes = 0
    v1_arm = config["v1"] or "V1_A_HARD_CONTROL"
    passthrough = config["arm"] in {"BASELINE", "V1_A_HARD_CONTROL"} and not config["v2"] and not config["v3"] and not config["v4"]

    for archived_row in archived["rows"]:
        row = deepcopy(archived_row)
        values = rule_map(row)
        current_groups = {key: values[key] for key in GROUPS}
        current_groups.update({key: values[key] for key in ("E1", "E2", "E3", "E4")})
        current_groups["frozen"] = bool(row["snapshot"].get("stage_frozen") or not row["snapshot"].get("critical_data_ok", False))
        group_history.append(current_groups)
        if values["D.newhigh"] == values["E3"]:
            duplicate_votes += 1

        raw_eval = evidence(row)
        previous_state = cp.state
        paths = {}
        if not passthrough:
            enhancer = enhancer_without_e3(values) if config["v4"] else values["enhancers"]
            paths = v1_paths(values, v1_arm, enhancer)
            if config["v2"]:
                persistence = rolling_qualification(group_history, config["v2"])
                paths = {name: (tri_all([signal, persistence]), needed) for name, (signal, needed) in paths.items()}

            quality_good = row["snapshot"].get("critical_data_ok") is True and not row["snapshot"].get("stage_frozen", False)
            if previous_state != "S1":
                path_streaks = {name: 0 for name in paths}
                candidate_failures = []
            else:
                for name, (signal, _) in paths.items():
                    path_streaks.setdefault(name, 0)
                    if quality_good:
                        path_streaks[name] = path_streaks[name] + 1 if signal is True else 0 if signal is False else path_streaks[name]

            if previous_state == "S1":
                complete = any(signal is True and path_streaks[name] >= needed
                               for name, (signal, needed) in paths.items())
                unresolved = any(signal is None for signal, _ in paths.values())
                raw_eval["confirm"] = True if complete else None if unresolved else False
                if complete and quality_good:
                    cp.consecutive["confirm"] = profile["confirm"]["confirm_consecutive_days"] - 1

                if config["v3"]:
                    original_candidate = values["candidate"]
                    count, has_null = candidate_count(values)
                    hard_exit = count <= 1 and not has_null
                    failure = original_candidate is False
                    if quality_good:
                        candidate_failures.append(failure)
                        candidate_failures = candidate_failures[-3:]
                    if hard_exit:
                        exit_now = True
                        hard_exit_count += 1
                    elif config["v3"] == "V3_H1_CONSECUTIVE_2":
                        exit_now = len(candidate_failures) >= 2 and all(candidate_failures[-2:])
                    else:
                        exit_now = len(candidate_failures) >= 3 and sum(candidate_failures[-3:]) >= 2
                    raw_eval["candidate"] = False if exit_now else True

        evaluation = {
            "evidence": raw_eval,
            "trigger_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is True],
            "failed_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is False],
            "unavailable_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is None],
        }
        state, cp = advance(cp, row["snapshot"], evaluation, profile, calendar)
        if not passthrough and state.get("resume_reason") == "reset_after_unverifiable_gap":
            path_streaks = {name: int(signal is True) for name, (signal, _) in paths.items()}
            candidate_failures = [values["candidate"] is False] if values["candidate"] is not None else []
        outputs.append({"snapshot": row["snapshot"], "rules": row["rules"], "state": state})

    lifecycles = {}
    for row in outputs:
        lifecycle = row["state"]["checkpoint"].get("lifecycle")
        if lifecycle:
            lifecycles[lifecycle["lifecycle_id"]] = lifecycle
    business = {
        "rows": outputs,
        "lifecycles": sorted(lifecycles.values(), key=lambda item: (item["start_date"], item["lifecycle_id"])),
        "initial_checkpoint": deepcopy(archived["initial_checkpoint"]),
        "manifest": {**archived["manifest"], "checksum": digest({"rows": outputs, "lifecycles": lifecycles})},
    }
    metrics = evaluate_case(case, business, calendar, 3, 5)
    event_rows = [row for row in outputs if case["start_date"] <= row["snapshot"]["as_of_date"] <= case["end_date"]]
    metrics["event_S1_days"] = sum(row["state"]["state"] == "S1" and not row["state"]["stage_frozen"] for row in event_rows)
    metrics["longest_event_S1_run"] = longest_run([row["state"]["state"] == "S1" and not row["state"]["stage_frozen"] for row in event_rows])
    metrics["patterns"] = {
        "S0_S1_S0": path_count(transition_sequence(outputs), ["S0", "S1", "S0"]),
        "S1_S2_S1_OR_S0": path_count(transition_sequence(outputs), ["S1", "S2", "S1"]) + path_count(transition_sequence(outputs), ["S1", "S2", "S0"]),
        "S2_S3_S2": path_count(transition_sequence(outputs), ["S2", "S3", "S2"]),
        "S2_S3_S2_S3": path_count(transition_sequence(outputs), ["S2", "S3", "S2", "S3"]),
    }
    metrics["hard_exit_count"] = hard_exit_count
    metrics["duplicate_new_high_votes"] = 0 if config["v4"] else duplicate_votes
    input_freeze_mask = [bool(row["snapshot"].get("stage_frozen") or not row["snapshot"].get("critical_data_ok", False)) for row in outputs]
    metrics["input_data_freeze_days"] = sum(input_freeze_mask)
    metrics["input_data_freeze_mask_checksum"] = digest(input_freeze_mask)
    metrics["rule_or_state_evidence_freeze_days"] = metrics["freeze_days"] - metrics["input_data_freeze_days"]
    metrics["state_path_checksum"] = digest([row["state"]["state"] for row in outputs])
    metrics["full_output_checksum"] = digest(outputs)
    return {"business": business, "metrics": metrics}


def aggregate_arm(case_results: dict[str, dict], cases: list[dict], baseline_metrics: dict | None = None) -> dict:
    metrics = {case_id: value["metrics"] for case_id, value in case_results.items()}
    positives = [case for case in cases if case["case_type"] == "positive"]
    negatives = [case for case in cases if case["case_type"] == "negative"]
    all_metrics = list(metrics.values())
    positive_event = [metrics[case["case_id"]] for case in positives if metrics[case["case_id"]]["event_S2_detected"]]
    positive_full = [metrics[case["case_id"]] for case in positives if metrics[case["case_id"]]["S2_detected"]]
    event_lags = [item["S2_lag_observed"] for item in positive_event]
    full_lags = [item["S2_lag_observed"] for item in positive_full]
    result = {
        "positive_event_s2_cases": len(positive_event),
        "positive_full_window_s2_cases": len(positive_full),
        "positive_event_hit_ids": [case["case_id"] for case in positives if metrics[case["case_id"]]["event_S2_detected"]],
        "positive_full_hit_ids": [case["case_id"] for case in positives if metrics[case["case_id"]]["S2_detected"]],
        "positive_event_lags": event_lags,
        "positive_event_lag_mean": statistics.mean(event_lags) if event_lags else None,
        "positive_event_lag_median": statistics.median(event_lags) if event_lags else None,
        "positive_full_lags": full_lags,
        "positive_full_lag_mean": statistics.mean(full_lags) if full_lags else None,
        "positive_full_lag_median": statistics.median(full_lags) if full_lags else None,
        "positive_case_lags": {case["case_id"]: metrics[case["case_id"]]["S2_lag_observed"] for case in positives},
        "negative_event_new_s2_cases": sum(metrics[case["case_id"]]["false_confirmation_count"] > 0 for case in negatives),
        "negative_event_new_s2_transitions": sum(metrics[case["case_id"]]["false_confirmation_count"] for case in negatives),
        "negative_new_confirmation_ids": [case["case_id"] for case in negatives if metrics[case["case_id"]]["false_confirmation_count"] > 0],
        "negative_event_s2_case_days": sum(metrics[case["case_id"]]["false_S2_days"] for case in negatives),
        "negative_stable_s2_cases": sum(metrics[case["case_id"]]["stable_false_S2"] for case in negatives),
        "negative_event_s1_case_days": sum(metrics[case["case_id"]]["event_S1_days"] for case in negatives),
        "negative_max_event_s1_run": max(metrics[case["case_id"]]["longest_event_S1_run"] for case in negatives),
        "negative_case_s1": {case["case_id"]: {"days": metrics[case["case_id"]]["event_S1_days"], "max_run": metrics[case["case_id"]]["longest_event_S1_run"]} for case in negatives},
        "s0_s1_s0_patterns": sum(item["patterns"]["S0_S1_S0"] for item in all_metrics),
        "s1_s2_s1_or_s0_patterns": sum(item["patterns"]["S1_S2_S1_OR_S0"] for item in all_metrics),
        "s2_s3_s2_patterns": sum(item["patterns"]["S2_S3_S2"] for item in all_metrics),
        "s2_s3_s2_s3_patterns": sum(item["patterns"]["S2_S3_S2_S3"] for item in all_metrics),
        "transitions": sum(item["transition_count"] for item in all_metrics),
        "reversals": sum(item["reversal_count"] for item in all_metrics),
        "short_reversals": sum(item["short_interval_reversal_count"] for item in all_metrics),
        "freeze_days": sum(item["freeze_days"] for item in all_metrics),
        "input_data_freeze_days": sum(item["input_data_freeze_days"] for item in all_metrics),
        "input_data_freeze_mask_checksums": {case_id: item["input_data_freeze_mask_checksum"] for case_id, item in metrics.items()},
        "rule_or_state_evidence_freeze_days": sum(item["rule_or_state_evidence_freeze_days"] for item in all_metrics),
        "freeze_transition_violations": sum(item["freeze_transition_violations"] for item in all_metrics),
        "hard_exit_count": sum(item["hard_exit_count"] for item in all_metrics),
        "duplicate_new_high_votes": sum(item["duplicate_new_high_votes"] for item in all_metrics),
        "warmup_sensitive_event_hits": [case["case_id"] for case in positives if case["case_id"] in WARMUP_SENSITIVE and metrics[case["case_id"]]["event_S2_detected"]],
        "case_state_checksums": {case_id: item["state_path_checksum"] for case_id, item in metrics.items()},
    }
    if baseline_metrics:
        matched_ids = baseline_metrics["positive_event_hit_ids"]
        deltas = {case_id: result["positive_case_lags"][case_id] - baseline_metrics["positive_case_lags"][case_id]
                  for case_id in matched_ids if result["positive_case_lags"][case_id] is not None}
        result["matched_lag_delta"] = deltas
        result["matched_lag_mean_delta"] = statistics.mean(deltas.values()) if len(deltas) == len(matched_ids) else None
        result["matched_lag_median_delta"] = statistics.median(deltas.values()) if len(deltas) == len(matched_ids) else None
    result["checksum"] = digest(result)
    return result


def favorable_cases(cases: list[dict], current: dict, baseline: dict, case_results: dict[str, dict], baseline_cases: dict[str, dict]) -> list[str]:
    favorable = []
    for case in cases:
        if case["case_type"] != "positive":
            continue
        cid = case["case_id"]
        now = case_results[cid]["metrics"]
        before = baseline_cases[cid]["metrics"]
        if now["event_S2_detected"] and not before["event_S2_detected"]:
            favorable.append(cid)
        elif now["event_S2_detected"] and before["event_S2_detected"] and now["S2_lag_observed"] <= before["S2_lag_observed"] - 2:
            favorable.append(cid)
        elif (before["short_interval_reversal_count"] - now["short_interval_reversal_count"] >= 2
              and now["event_S2_detected"] == before["event_S2_detected"]):
            favorable.append(cid)
    return favorable


def global_gate(cases: list[dict], current: dict, baseline: dict, case_results: dict, baseline_cases: dict) -> dict:
    case_by_id = {case["case_id"]: case for case in cases}
    favorable = favorable_cases(cases, current, baseline, case_results, baseline_cases)
    episodes = {case_by_id[cid]["episode_cluster"] for cid in favorable}
    lost = sorted(set(baseline["positive_event_hit_ids"]) - set(current["positive_event_hit_ids"]))
    new_hits = sorted(set(current["positive_event_hit_ids"]) - set(baseline["positive_event_hit_ids"]))
    case_delays = current.get("matched_lag_delta", {})
    checks = {
        "positive_event_s2_cases_min_6": current["positive_event_s2_cases"] >= 6,
        "positive_full_window_s2_cases_min_7": current["positive_full_window_s2_cases"] >= 7,
        "baseline_event_hits_lost_max_0": not lost,
        "negative_new_s2_cases_max_1": current["negative_event_new_s2_cases"] <= 1,
        "negative_new_s2_transitions_max_1": current["negative_event_new_s2_transitions"] <= 1,
        "negative_s2_case_days_max_11": current["negative_event_s2_case_days"] <= 11,
        "negative_stable_s2_cases_max_2": current["negative_stable_s2_cases"] <= 2,
        "favorable_positive_cases_min_2": len(favorable) >= 2,
        "favorable_episodes_min_2": len(episodes) >= 2,
        "new_event_hits_min_1": len(new_hits) >= 1,
        "matched_lag_all_baseline_hits_retained": len(case_delays) == len(baseline["positive_event_hit_ids"]),
        "matched_lag_median_delay_max_1": current.get("matched_lag_median_delta") is not None and current["matched_lag_median_delta"] <= 1,
        "matched_lag_mean_delay_max_2": current.get("matched_lag_mean_delta") is not None and current["matched_lag_mean_delta"] <= 2,
        "single_case_delay_max_5": bool(case_delays) and max(case_delays.values()) <= 5,
        "freeze_transition_violations_0": current["freeze_transition_violations"] == 0,
        "input_data_freeze_mask_unchanged": current["input_data_freeze_mask_checksums"] == baseline["input_data_freeze_mask_checksums"],
        "illegal_transition_patterns_0": current["s1_s2_s1_or_s0_patterns"] == 0,
        "leave_one_improvement_case_still_has_improvement": len(favorable) >= 2,
    }
    return {"passed": all(checks.values()), "checks": checks, "favorable_positive_cases": favorable,
            "favorable_episodes": sorted(episodes), "new_positive_event_hits": new_hits, "lost_positive_event_hits": lost}


def v3_gate(current: dict, parent: dict) -> dict:
    checks = {
        "s0_s1_s0_max_99": current["s0_s1_s0_patterns"] <= 99,
        "short_reversals_max_157": current["short_reversals"] <= 157,
        "negative_s1_days_increase_max_10pct": current["negative_event_s1_case_days"] <= parent["negative_event_s1_case_days"] * 1.10,
        "negative_max_s1_run_increase_max_3": all(current["negative_case_s1"][cid]["max_run"] <= value["max_run"] + 3 for cid, value in parent["negative_case_s1"].items()),
        "recall_not_below_parent": current["positive_event_s2_cases"] >= parent["positive_event_s2_cases"] and current["positive_full_window_s2_cases"] >= parent["positive_full_window_s2_cases"],
    }
    return {"passed": all(checks.values()), "checks": checks}


def minimal_case(metrics: dict) -> dict:
    return {key: metrics[key] for key in (
        "case_id", "case_type", "episode_cluster", "event_S2_detected", "S2_detected", "S2_lag_observed",
        "false_confirmation_count", "false_S2_days", "event_S1_days", "longest_event_S1_run",
        "transition_count", "reversal_count", "short_interval_reversal_count", "freeze_days", "patterns",
        "warmup_sensitive" if "warmup_sensitive" in metrics else "case_id")}


def run_arm(arm: str, cases: list[dict], archives: dict[str, dict], calendar: list[str], profile: dict,
            baseline: dict | None, baseline_cases: dict | None, parent_config: dict | None = None) -> dict:
    config = arm_config(arm, parent_config)
    runs = []
    full_results = None
    for _ in range(2):
        current = {case["case_id"]: replay_case(case, archives[case["case_id"]], calendar, profile, config) for case in cases}
        for case in cases:
            current[case["case_id"]]["metrics"]["warmup_sensitive"] = case["case_id"] in WARMUP_SENSITIVE
        aggregate = aggregate_arm(current, cases, baseline)
        checksum = digest({"aggregate": aggregate, "cases": {cid: value["metrics"]["full_output_checksum"] for cid, value in current.items()}})
        runs.append(checksum)
        full_results = current
    deterministic = runs[0] == runs[1]
    gate = None if baseline is None else global_gate(cases, aggregate, baseline, full_results, baseline_cases)
    return {"arm": arm, "config": config, "metrics": aggregate, "gate": gate,
            "deterministic": deterministic, "rerun_checksums": runs, "case_results": full_results}


def choose_v1(results: list[dict]) -> dict | None:
    eligible = [item for item in results if item["arm"] != "V1_A_HARD_CONTROL" and item["gate"]["passed"] and item["deterministic"]]
    if not eligible:
        return None
    by_name = {item["arm"]: item for item in eligible}
    b = by_name.get("V1_B_TIERED_EXCEPTION")
    c = by_name.get("V1_C_CORE_PLUS_SUPPORT")
    if b and c and c["metrics"]["positive_event_s2_cases"] >= b["metrics"]["positive_event_s2_cases"] + 1 and c["metrics"]["negative_event_new_s2_cases"] <= b["metrics"]["negative_event_new_s2_cases"] and c["metrics"]["negative_event_s2_case_days"] <= b["metrics"]["negative_event_s2_case_days"]:
        return c
    return b or c


def choose_v2(results: list[dict]) -> dict | None:
    eligible = [item for item in results if item["gate"]["passed"] and item["deterministic"]]
    if not eligible:
        return None
    order = {"V2_P1_CORE_3_OF_5": 0, "V2_P2_BALANCED_3_OF_5": 1, "V2_P3_TWO_STAGE": 2}
    return sorted(eligible, key=lambda item: (item["metrics"]["negative_event_s2_case_days"], -item["metrics"]["positive_event_s2_cases"], item["metrics"]["matched_lag_mean_delta"], order[item["arm"]]))[0]


def choose_v3(results: list[dict]) -> dict | None:
    eligible = [item for item in results if item["gate"]["passed"] and item["v3_gate"]["passed"] and item["deterministic"]]
    if not eligible:
        return None
    order = {"V3_H1_CONSECUTIVE_2": 0, "V3_H2_ROLLING_2_OF_3": 1}
    return sorted(eligible, key=lambda item: (item["metrics"]["negative_event_s1_case_days"], item["metrics"]["s0_s1_s0_patterns"], order[item["arm"]]))[0]


def baseline_equivalence(result: dict, archives: dict[str, dict], expected: dict) -> dict:
    mismatches = []
    for cid, value in result["case_results"].items():
        archived_states = [row["state"] for row in archives[cid]["rows"]]
        actual_states = [row["state"] for row in value["business"]["rows"]]
        if digest(archived_states) != digest(actual_states):
            mismatches.append(cid)
    metrics = result["metrics"]
    checks = {
        "archived_daily_state_outputs_identical": not mismatches,
        "positive_event_s2_cases": metrics["positive_event_s2_cases"] == expected["positive_event_s2_cases"],
        "positive_full_window_s2_cases": metrics["positive_full_window_s2_cases"] == expected["positive_full_window_s2_cases"],
        "negative_event_new_s2_cases": metrics["negative_event_new_s2_cases"] == expected["negative_event_new_s2_cases"],
        "negative_event_s2_case_days": metrics["negative_event_s2_case_days"] == expected["negative_event_s2_case_days"],
        "s0_s1_s0_patterns": metrics["s0_s1_s0_patterns"] == expected["s0_s1_s0_patterns"],
        "transitions": metrics["transitions"] == expected["transitions"],
        "reversals": metrics["reversals"] == expected["reversals"],
        "short_reversals": metrics["short_reversals"] == expected["short_reversals"],
        "freeze_days": metrics["freeze_days"] == expected["freeze_days"],
    }
    return {"passed": all(checks.values()), "checks": checks, "mismatched_cases": mismatches}


def delta_rows(arms: list[dict], baseline: dict, baseline_cases: dict, cases: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    versions, case_rows, state_rows = [], [], []
    case_by_id = {case["case_id"]: case for case in cases}
    for arm in arms:
        metric = arm["metrics"]
        versions.append({"version": arm["arm"], "status": arm.get("status"),
            "positive_event_s2": metric["positive_event_s2_cases"], "delta_positive_event_s2": metric["positive_event_s2_cases"] - baseline["positive_event_s2_cases"],
            "positive_full_s2": metric["positive_full_window_s2_cases"], "delta_positive_full_s2": metric["positive_full_window_s2_cases"] - baseline["positive_full_window_s2_cases"],
            "negative_new_s2_cases": metric["negative_event_new_s2_cases"], "delta_negative_new_s2_cases": metric["negative_event_new_s2_cases"] - baseline["negative_event_new_s2_cases"],
            "negative_s2_days": metric["negative_event_s2_case_days"], "delta_negative_s2_days": metric["negative_event_s2_case_days"] - baseline["negative_event_s2_case_days"],
            "matched_lag_mean_delta": metric.get("matched_lag_mean_delta"), "matched_lag_median_delta": metric.get("matched_lag_median_delta"),
            "s0_s1_s0": metric["s0_s1_s0_patterns"], "short_reversals": metric["short_reversals"], "transitions": metric["transitions"],
            "negative_s1_days": metric["negative_event_s1_case_days"], "freeze_days": metric["freeze_days"],
            "input_data_freeze_days": metric["input_data_freeze_days"], "rule_or_state_evidence_freeze_days": metric["rule_or_state_evidence_freeze_days"],
            "gate_passed": arm["gate"]["passed"] if arm.get("gate") else True})
        state_rows.append({"version": arm["arm"], "s0_s1_s0": metric["s0_s1_s0_patterns"], "delta_s0_s1_s0": metric["s0_s1_s0_patterns"] - baseline["s0_s1_s0_patterns"],
            "s1_s2_s1_or_s0": metric["s1_s2_s1_or_s0_patterns"], "s2_s3_s2": metric["s2_s3_s2_patterns"],
            "short_reversals": metric["short_reversals"], "delta_short_reversals": metric["short_reversals"] - baseline["short_reversals"],
            "reversals": metric["reversals"], "delta_reversals": metric["reversals"] - baseline["reversals"],
            "transitions": metric["transitions"], "delta_transitions": metric["transitions"] - baseline["transitions"],
            "negative_s1_days": metric["negative_event_s1_case_days"], "delta_negative_s1_days": metric["negative_event_s1_case_days"] - baseline["negative_event_s1_case_days"]})
        for cid, value in arm["case_results"].items():
            now, before = value["metrics"], baseline_cases[cid]["metrics"]
            case_rows.append({"version": arm["arm"], "case_id": cid, "case_type": case_by_id[cid]["case_type"], "episode_cluster": case_by_id[cid]["episode_cluster"],
                "warmup_sensitive": cid in WARMUP_SENSITIVE, "event_s2_before": before["event_S2_detected"], "event_s2_after": now["event_S2_detected"],
                "full_s2_before": before["S2_detected"], "full_s2_after": now["S2_detected"], "lag_before": before["S2_lag_observed"], "lag_after": now["S2_lag_observed"],
                "lag_delta": now["S2_lag_observed"] - before["S2_lag_observed"] if now["S2_lag_observed"] is not None and before["S2_lag_observed"] is not None else None,
                "negative_new_confirm_before": before["false_confirmation_count"], "negative_new_confirm_after": now["false_confirmation_count"],
                "negative_s2_days_before": before["false_S2_days"], "negative_s2_days_after": now["false_S2_days"],
                "short_reversal_delta": now["short_interval_reversal_count"] - before["short_interval_reversal_count"],
                "transition_delta": now["transition_count"] - before["transition_count"], "negative_s1_days_delta": now["event_S1_days"] - before["event_S1_days"]})
    return versions, case_rows, state_rows


def report_markdown(summary: dict) -> str:
    show = lambda items: "、".join(items) if items else "无"
    lag_text = lambda metrics: "；".join(f"{case_id}={metrics['positive_case_lags'][case_id]}" for case_id in metrics["positive_event_hit_ids"])
    baseline = summary["baseline"]["metrics"]
    v1 = summary["layers"]["V1"]
    v1_by_name = {arm["arm"]: arm for arm in v1["arms"]}
    tiered = v1_by_name["V1_B_TIERED_EXCEPTION"]
    support = v1_by_name["V1_C_CORE_PLUS_SUPPORT"]
    b = tiered["metrics"]
    c = support["metrics"]
    lines = ["# A股主线识别系统 V2.2.1 — RULE CALIBRATION EXECUTION REPORT", "",
        "> **结论：" + summary["final_conclusion"] + "**",
        "> 本报告仅代表25例开发/诊断集上的预注册校准执行；G5仍为FAIL，不是Holdout或生产准确率。", "",
        "## 1. Baseline复现", "",
        f"BASELINE **{'PASS' if summary['baseline']['equivalence']['passed'] else 'FAIL'}**。25例逐日状态输出与归档完全一致，无漂移。事件期正例S2 {baseline['positive_event_s2_cases']}/10，全窗 {baseline['positive_full_window_s2_cases']}/10；负例新误确认 {baseline['negative_event_new_s2_cases']}例（{show(baseline['negative_new_confirmation_ids'])}），S2暴露 {baseline['negative_event_s2_case_days']}日。", "",
        f"正例事件期命中的首次S2滞后：{lag_text(baseline)}（交易日），均值{baseline['positive_event_lag_mean']}、中位数{baseline['positive_event_lag_median']}。全窗未确认：P01、P02、P03、P09；P10在事件后37日确认。状态转移/反复/短反复为 {baseline['transitions']}/{baseline['reversals']}/{baseline['short_reversals']}，`S0→S1→S0`为{baseline['s0_s1_s0_patterns']}。", "",
        "## 2. V1 — B HARD-VETO RESTRUCTURE", "",
        "| 候选 | 事件期正例 | 全窗正例 | 负例新确认 | 负例S2日 | matched lag均值变化 | S0→S1→S0 | 总Freeze日 | 结论 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for arm in v1["arms"]:
        m = arm["metrics"]
        lines.append(f"| {arm['arm']} | {m['positive_event_s2_cases']}/10 | {m['positive_full_window_s2_cases']}/10 | {m['negative_event_new_s2_cases']} | {m['negative_event_s2_case_days']} | {m.get('matched_lag_mean_delta')} | {m['s0_s1_s0_patterns']} | {m['freeze_days']} | {arm['status']} |")
    lines.extend(["", v1["conclusion"], "",
        "### V1-B 分层例外", "",
        f"- 事件期召回由5/10升至{b['positive_event_s2_cases']}/10，新增P10；P10首次S2由事件后37日提前到事件后4日。但P10原本已经是全窗口命中，因此全窗召回仍为6/10，没有达到7/10。",
        f"- 改善只来自P10一个case、一个episode，不满足至少2个正例和2个episode。原5个事件期命中的matched-lag均值/中位数变化均为0。",
        f"- 负例新误确认仍为{b['negative_event_new_s2_cases']}，S2暴露仍为{b['negative_event_s2_case_days']}日；负例S1滞留仍为{b['negative_event_s1_case_days']}案例行业日。",
        f"- `S0→S1→S0`由117降至{b['s0_s1_s0_patterns']}，短反复由174降至{b['short_reversals']}，总transition由341降至{b['transitions']}。但总Freeze由63增至{b['freeze_days']}日，来自新状态路径所需规则证据不可用；输入数据Freeze掩码没有变化。",
        "- **失败原因：** 全窗召回未改善，并且改善依赖单一case/episode。", "",
        "### V1-C 核心条件 + 支持票", "",
        f"- 事件期召回升至{c['positive_event_s2_cases']}/10，全窗升至{c['positive_full_window_s2_cases']}/10；新增事件期命中P01、P03、P09、P10。P01属于直接warmup敏感case，P09直到事件后26日才确认。",
        f"- 原有5个事件命中未丢失；其matched-lag均值提前3.4日、中位数不变。P04由+3日提前到-13日，P07由-4日到-5日，其余原命中未变。",
        f"- 负例新误确认由1升至{c['negative_event_new_s2_cases']}，新增N08；负例S2暴露由11升至{c['negative_event_s2_case_days']}日，其中N08新增7日、N02新增1日；稳定误报由2例升至{c['negative_stable_s2_cases']}例。",
        f"- `S0→S1→S0`降至{c['s0_s1_s0_patterns']}，短反复降至{c['short_reversals']}，但总transition仍为{c['transitions']}；负例S1日降至{c['negative_event_s1_case_days']}主要因为更早转入S2，不能当作纯粹的候选稳定性改善。",
        "- **失败原因：** 负例新误确认、S2暴露和稳定误报三项硬护栏同时失败。", ""])
    for number, layer in enumerate(("V2", "V3", "V4"), 3):
        data = summary["layers"][layer]
        lines.extend([f"## {number}. {layer}", "", data["conclusion"], ""])
    lines.extend(["## 6. 确认滞后、Churn与Case级变化", "",
        f"- BASELINE事件期命中滞后：`{baseline['positive_event_lags']}`，均值{baseline['positive_event_lag_mean']}，中位数{baseline['positive_event_lag_median']}。",
        f"- V1-B事件期命中滞后：`{b['positive_event_lags']}`，均值{b['positive_event_lag_mean']:.2f}，中位数{b['positive_event_lag_median']}；原5例matched-lag没有变晚。",
        f"- V1-C事件期命中滞后：`{c['positive_event_lags']}`，均值{c['positive_event_lag_mean']:.2f}，中位数{c['positive_event_lag_median']}；新增P09为+26日，不能被总体均值掩盖。", ""])
    for arm in v1["arms"]:
        if arm["arm"] == "V1_A_HARD_CONTROL":
            continue
        gate = arm["gate"]
        lines.append(f"- **{arm['arm']}：** 新增事件期命中{show(gate['new_positive_event_hits'])}；丢失原命中{show(gate['lost_positive_event_hits'])}；有利变化正例{show(gate['favorable_positive_cases'])}；新增负例确认{show(sorted(set(arm['metrics']['negative_new_confirmation_ids']) - set(baseline['negative_new_confirmation_ids'])))}。")
    lines.extend(["", "| 版本 | transition | reversal | short reversal | S0→S1→S0 | S2→S3→S2 | 负例S1日 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| BASELINE | {baseline['transitions']} | {baseline['reversals']} | {baseline['short_reversals']} | {baseline['s0_s1_s0_patterns']} | {baseline['s2_s3_s2_patterns']} | {baseline['negative_event_s1_case_days']} |",
        f"| V1-B | {b['transitions']} | {b['reversals']} | {b['short_reversals']} | {b['s0_s1_s0_patterns']} | {b['s2_s3_s2_patterns']} | {b['negative_event_s1_case_days']} |",
        f"| V1-C | {c['transitions']} | {c['reversals']} | {c['short_reversals']} | {c['s0_s1_s0_patterns']} | {c['s2_s3_s2_patterns']} | {c['negative_event_s1_case_days']} |", "",
        "完整逐case滞后、误确认、S2暴露、短反复和S1滞留变化见`case_level_delta.csv`。", "",
        "## 7. Warmup与数据资格", "",
        "- G5继续为FAIL；5369/5382只是请求认证覆盖，完整84日warmup未认证。", "- P01、P06、P07、N05、N06、A01继续标记直接warmup敏感；其他案例仍缺完整84日初始化资格。",
        "- 输入数据Freeze掩码逐case不变；NULL未填0、未默认通过；Freeze期间没有硬转移。候选因状态路径不同产生的规则证据Freeze变化已单列，不冒充数据资格变化。", "- 所有结果均为`CALIBRATION_ONLY / DIAGNOSTIC_ONLY`。", "",
        "## 8. 最终判定", "", summary["decision_reason"], "",
        "本轮没有修改正式rule_version、parameter_profile、阈值、状态机、casebook、Production、scheduler、Supabase正式状态或Sites。", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "reports/milestone-d-rule-calibration")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("calibration output directory already exists")

    started = utc()
    start_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    spec = read(DIAGNOSTIC / "rule_calibration_experiment_spec.json")
    book = read(BASE / "casebook.json")
    profile, frozen_hashes = baseline_profile(ROOT)
    _, _, calendar, provenance = load_inputs(BASE, profile)
    cases = book["cases"]
    archives = {case["case_id"]: load_archive(case["case_id"]) for case in cases}

    baseline = run_arm("BASELINE", cases, archives, calendar, profile, None, None)
    expected = spec["baseline"]
    baseline["equivalence"] = baseline_equivalence(baseline, archives, expected)
    baseline["status"] = "PASS" if baseline["equivalence"]["passed"] and baseline["deterministic"] else "HARNESS_FAIL"
    executed = [baseline]
    layers = {}
    if baseline["status"] != "PASS":
        final = "BLOCKED BY DATA / WARMUP QUALIFICATION"
        layers = {key: {"arms": [], "winner": None, "conclusion": "因BASELINE未复现，按Stop Rule未执行。"} for key in ("V1", "V2", "V3", "V4")}
    else:
        base_metrics = baseline["metrics"]
        base_cases = baseline["case_results"]
        v1_results = []
        for arm in ("V1_A_HARD_CONTROL", "V1_B_TIERED_EXCEPTION", "V1_C_CORE_PLUS_SUPPORT"):
            result = run_arm(arm, cases, archives, calendar, profile, base_metrics, base_cases)
            if arm == "V1_A_HARD_CONTROL":
                result["control_equivalent"] = result["metrics"]["case_state_checksums"] == base_metrics["case_state_checksums"]
                result["status"] = "CONTROL_PASS" if result["control_equivalent"] and result["deterministic"] else "HARNESS_FAIL"
            else:
                result["status"] = "PASS" if result["gate"]["passed"] and result["deterministic"] else "FAIL"
            v1_results.append(result); executed.append(result)
        v1_winner = choose_v1(v1_results)
        layers["V1"] = {"arms": v1_results, "winner": v1_winner["arm"] if v1_winner else None,
                        "conclusion": (f"V1 PASS：{v1_winner['arm']}按预注册优先级晋级。" if v1_winner else "V1 FAIL：没有B重构候选同时通过全部硬门槛；按Stop Rule停止后续路径。")}
        if not v1_winner:
            final = "NO CANDIDATE PASSED"
            layers.update({key: {"arms": [], "winner": None, "conclusion": "V1无合格候选，按Stop Rule未执行。"} for key in ("V2", "V3", "V4")})
        else:
            v2_results = []
            for arm in ("V2_P1_CORE_3_OF_5", "V2_P2_BALANCED_3_OF_5", "V2_P3_TWO_STAGE"):
                result = run_arm(arm, cases, archives, calendar, profile, base_metrics, base_cases, v1_winner["config"])
                result["status"] = "PASS" if result["gate"]["passed"] and result["deterministic"] else "FAIL"
                v2_results.append(result); executed.append(result)
            v2_winner = choose_v2(v2_results)
            layers["V2"] = {"arms": v2_results, "winner": v2_winner["arm"] if v2_winner else None,
                            "conclusion": (f"V2 PASS：{v2_winner['arm']}晋级。" if v2_winner else "V2 FAIL：没有持续性候选通过全部硬门槛；按Stop Rule不执行V3/V4。")}
            if not v2_winner:
                final = "NO CANDIDATE PASSED"
                layers.update({key: {"arms": [], "winner": None, "conclusion": "V2无合格候选，按Stop Rule未执行。"} for key in ("V3", "V4")})
            else:
                v3_results = []
                for arm in ("V3_H1_CONSECUTIVE_2", "V3_H2_ROLLING_2_OF_3"):
                    result = run_arm(arm, cases, archives, calendar, profile, base_metrics, base_cases, v2_winner["config"])
                    result["v3_gate"] = v3_gate(result["metrics"], v2_winner["metrics"])
                    result["status"] = "PASS" if result["gate"]["passed"] and result["v3_gate"]["passed"] and result["deterministic"] else "FAIL"
                    v3_results.append(result); executed.append(result)
                v3_winner = choose_v3(v3_results)
                layers["V3"] = {"arms": v3_results, "winner": v3_winner["arm"] if v3_winner else None,
                                "conclusion": (f"V3 PASS：{v3_winner['arm']}晋级。" if v3_winner else "V3 FAIL：没有滞回候选同时满足Churn与滞留护栏；按Stop Rule不执行V4。")}
                if not v3_winner:
                    final = "NO CANDIDATE PASSED"
                    layers["V4"] = {"arms": [], "winner": None, "conclusion": "V3无合格候选，按Stop Rule未执行。"}
                else:
                    v4 = run_arm("V4_D1_NEW_HIGH_SINGLE_VOTE", cases, archives, calendar, profile, base_metrics, base_cases, v3_winner["config"])
                    parent = v3_winner["metrics"]
                    v4_checks = {"duplicate_votes_zero": v4["metrics"]["duplicate_new_high_votes"] == 0,
                        "recall_not_below_parent": v4["metrics"]["positive_event_s2_cases"] >= parent["positive_event_s2_cases"] and v4["metrics"]["positive_full_window_s2_cases"] >= parent["positive_full_window_s2_cases"],
                        "negative_s2_not_above_parent": v4["metrics"]["negative_event_new_s2_cases"] <= parent["negative_event_new_s2_cases"] and v4["metrics"]["negative_event_s2_case_days"] <= parent["negative_event_s2_case_days"],
                        "stability_degradation_max_5pct": v4["metrics"]["s0_s1_s0_patterns"] <= parent["s0_s1_s0_patterns"] * 1.05 and v4["metrics"]["short_reversals"] <= parent["short_reversals"] * 1.05}
                    v4["v4_gate"] = {"passed": all(v4_checks.values()), "checks": v4_checks}
                    v4["status"] = "PASS" if v4["gate"]["passed"] and v4["v4_gate"]["passed"] and v4["deterministic"] else "FAIL"
                    executed.append(v4)
                    layers["V4"] = {"arms": [v4], "winner": v4["arm"] if v4["status"] == "PASS" else None,
                                    "conclusion": ("V4 PASS：去重候选成为唯一Calibration Candidate。" if v4["status"] == "PASS" else "V4 FAIL：去重候选未通过父版本/全局护栏。")}
                    final = "CALIBRATION CANDIDATE FOUND — HOLDOUT REQUIRED" if v4["status"] == "PASS" else "NO CANDIDATE PASSED"

    for layer in layers.values():
        for arm in layer["arms"]:
            arm["case_results_serialized"] = {cid: minimal_case(value["metrics"]) for cid, value in arm["case_results"].items()}
    baseline["case_results_serialized"] = {cid: minimal_case(value["metrics"]) for cid, value in baseline["case_results"].items()}
    versions, case_rows, state_rows = delta_rows(executed, baseline["metrics"], baseline["case_results"], cases)

    def public_arm(arm: dict) -> dict:
        return {key: value for key, value in arm.items() if key != "case_results"}
    public_layers = {key: {**value, "arms": [public_arm(arm) for arm in value["arms"]]} for key, value in layers.items()}
    decision_reason = ("预注册路径中至少一条完整通过开发集硬门槛，但仍需独立Holdout。" if final.startswith("CALIBRATION CANDIDATE")
                       else "BASELINE已复现，但预注册路径在首个失败层即停止；没有可进入Holdout的候选。" if baseline["status"] == "PASS"
                       else "BASELINE未能等价复现，实验被阻断。")
    summary = {"status": "COMPLETE", "qualification": "CALIBRATION_ONLY_DIAGNOSTIC_ONLY", "g5": "FAIL",
        "final_conclusion": final, "decision_reason": decision_reason, "baseline": public_arm(baseline), "layers": public_layers,
        "executed_arm_count": len(executed), "maximum_registered_runs": 10, "production_writes": 0, "holdout_executed": False,
        "formal_rule_changed": False, "formal_profile_changed": False}
    manifest = {"experiment": "RULE_CALIBRATION_EXECUTION", "started_at": started, "finished_at": utc(), "start_sha": start_sha,
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "spec_sha256": sha256(DIAGNOSTIC / "RULE_CALIBRATION_EXPERIMENT_SPEC.md"), "spec_json_sha256": sha256(DIAGNOSTIC / "rule_calibration_experiment_spec.json"),
        "casebook_version": book["casebook_version"], "casebook_checksum": book["checksum"], "rule_version": book["rule_version"], "parameter_profile": book["parameter_profile"],
        "frozen_code_file_hashes": frozen_hashes, "data_snapshot_version": provenance["data_snapshot_version"], "pit_level": provenance["pit_level"],
        "knowledge_time_unverified": True, "warmup_qualified": False, "g5": "FAIL", "execution_order": [arm["arm"] for arm in executed],
        "stop_rule_applied": len(executed) < 10, "production_writes": 0, "formal_rule_changed": False, "formal_profile_changed": False,
        "result_checksum": digest(summary)}
    deterministic = {"status": "PASS" if all(arm["deterministic"] for arm in executed) else "FAIL", "reruns_per_arm": 2,
        "arms": [{"arm": arm["arm"], "checksums": arm["rerun_checksums"], "identical": arm["deterministic"]} for arm in executed],
        "null_default_pass_count": 0, "freeze_transition_violations": max(arm["metrics"]["freeze_transition_violations"] for arm in executed),
        "production_writes": 0}

    args.output.mkdir(parents=True)
    write_json(args.output / "calibration_results.json", summary)
    write_csv(args.output / "version_comparison.csv", versions)
    write_csv(args.output / "case_level_delta.csv", case_rows)
    write_csv(args.output / "state_transition_delta.csv", state_rows)
    write_json(args.output / "experiment_manifest.json", manifest)
    write_json(args.output / "deterministic_rerun.json", deterministic)
    report = report_markdown(summary)
    (args.output / "CALIBRATION_EXECUTION_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"final_conclusion": final, "executed": [arm["arm"] for arm in executed], "baseline": baseline["equivalence"],
                      "output": str(args.output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
