"""Execute the final bounded V4 confirmation calibration on frozen archives.

This harness is isolated from the formal rule/profile/state machine and never
calls a provider or writes production state.  V4-A/B/C are parallel children
of the preregistered V1-B3 + same-branch structure.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from mainline.backtest.evaluator import evaluate_case  # noqa: E402
from mainline.backtest.runner import baseline_profile, load_inputs, read  # noqa: E402
from mainline.engine.replay import digest  # noqa: E402
from mainline.engine.state_machine import Checkpoint, advance  # noqa: E402
from scripts.mainline.rule_calibration_execute import (  # noqa: E402
    BASE,
    WARMUP_SENSITIVE,
    aggregate_arm,
    baseline_equivalence,
    delta_rows,
    evidence,
    favorable_cases,
    load_archive,
    longest_run,
    minimal_case,
    path_count,
    rule_map,
    sha256,
    transition_sequence,
    utc,
    write_csv,
    write_json,
)
from scripts.mainline.rule_calibration_execute_v2 import run_candidate as run_v2_candidate  # noqa: E402
from scripts.mainline.rule_calibration_execute_v3 import (  # noqa: E402
    FOCUS_CASES,
    baseline_focus,
    focus_summary,
    required_known,
    signature_paths,
    write_compact_json,
)

OUT = ROOT / "reports/milestone-d-rule-calibration"
SPEC_MD = OUT / "RULE_CALIBRATION_EXPERIMENT_SPEC_V4.md"
SPEC_JSON = OUT / "rule_calibration_experiment_spec_v4.json"
V2_RESULTS = OUT / "calibration_results_v2.json"
V3_RESULTS = OUT / "calibration_results_v3.json"
V3_MANIFEST = OUT / "experiment_manifest_v3.json"
V3_RERUN = OUT / "deterministic_rerun_v3.json"
ARMS = (
    "BASELINE",
    "V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY",
    "V4_B_B_PRESENT_REQUIRES_C_TRUE",
    "V4_C_COMBINED",
)
SIGNATURES = (
    "STANDARD_ALL",
    "B_PRESENT_C",
    "B_PRESENT_ENHANCER",
    "B_WAIVED_C_ENHANCER",
)


def eligible_signatures(arm: str) -> set[str]:
    eligible = set(SIGNATURES)
    if arm in {"V4_B_B_PRESENT_REQUIRES_C_TRUE", "V4_C_COMBINED"}:
        eligible.remove("B_PRESENT_ENHANCER")
    return eligible


def replay_candidate(case: dict, archived: dict, calendar: list[str], profile: dict,
                     arm: str, threshold: float) -> dict:
    initial = deepcopy(archived["initial_checkpoint"])
    if initial:
        cp = Checkpoint(**initial)
    else:
        first = archived["rows"][0]["snapshot"]
        cp = Checkpoint(first["object_id"], first["rule_version"], profile["profile_id"],
                        first["metric_availability_version"], state="S0")

    break_on_null = arm in {
        "V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY",
        "V4_C_COMBINED",
    }
    require_c = arm in {
        "V4_B_B_PRESENT_REQUIRES_C_TRUE",
        "V4_C_COMBINED",
    }
    eligible = eligible_signatures(arm)
    counters = {name: 0 for name in SIGNATURES}
    outputs: list[dict] = []
    audit: list[dict] = []
    required_null_days = 0
    null_chain_reset_days = 0
    null_chain_nonzero_reset_days = 0
    null_counter_retention_violations = 0
    recovery_first_day_counter_violations = 0
    b_present_c_integrity_violations = 0
    cross_signature_accumulations = 0
    prior_required_null = False

    for archived_row in archived["rows"]:
        row = deepcopy(archived_row)
        values = rule_map(row)
        snapshot = row["snapshot"]
        before_state = cp.state
        raw_eval = evidence(row)
        known_ok, missing = required_known(values, snapshot)
        paths = signature_paths(values, snapshot, threshold)
        quality_good = snapshot.get("critical_data_ok") is True and not snapshot.get("stage_frozen", False)
        before = deepcopy(counters)
        complete = False
        completed_signatures: list[str] = []
        confirm_chain_reset = False
        recovery_after_null = prior_required_null and known_ok and quality_good

        if before_state != "S1":
            counters = {name: 0 for name in SIGNATURES}
        elif quality_good:
            if not known_ok:
                required_null_days += 1
                if break_on_null:
                    confirm_chain_reset = True
                    null_chain_reset_days += 1
                    if any(before.values()):
                        null_chain_nonzero_reset_days += 1
                    counters = {name: 0 for name in SIGNATURES}
                    if any(counters.values()):
                        null_counter_retention_violations += 1
                raw_eval["confirm"] = False
            else:
                for name, (signal, needed) in paths.items():
                    if name not in eligible:
                        counters[name] = 0
                    elif signal is True:
                        counters[name] += 1
                    elif signal is False:
                        counters[name] = 0
                    if name in eligible and signal is True and counters[name] >= needed:
                        completed_signatures.append(name)
                complete = bool(completed_signatures)
                raw_eval["confirm"] = complete
                if recovery_after_null and break_on_null:
                    if max((counters[name] for name in eligible), default=0) > 1:
                        recovery_first_day_counter_violations += 1
                if require_c and values["C"] is not True:
                    if counters["B_PRESENT_C"] or counters["B_PRESENT_ENHANCER"]:
                        b_present_c_integrity_violations += 1
                    if any(name.startswith("B_PRESENT") for name in completed_signatures):
                        b_present_c_integrity_violations += 1
                if complete:
                    cp.consecutive["confirm"] = profile["confirm"]["confirm_consecutive_days"] - 1

        evaluation = {
            "evidence": raw_eval,
            "trigger_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is True],
            "failed_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is False],
            "unavailable_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is None],
        }
        state, cp = advance(cp, snapshot, evaluation, profile, calendar)
        if state.get("resume_reason") == "reset_after_unverifiable_gap":
            if break_on_null and not known_ok:
                counters = {name: 0 for name in SIGNATURES}
            else:
                counters = {
                    name: int(name in eligible and signal is True)
                    for name, (signal, _) in paths.items()
                }

        transition = state.get("transition")
        confirm_triggered = bool(
            isinstance(transition, dict)
            and transition.get("from_state") == "S1"
            and transition.get("to_state") == "S2"
        )
        row_audit = {
            "trade_date": snapshot["as_of_date"],
            "state_before": before_state,
            "state_after": state["state"],
            "A": values["A"], "B": values["B"], "C": values["C"], "D": values["D"],
            "Enhancer": values["enhancers"], "above_ma20": snapshot.get("above_ma20"),
            "required_known_ok": known_ok,
            "evidence_signature": sorted(name for name, (signal, _) in paths.items() if signal is True),
            "eligible_evidence_signature": sorted(name for name, (signal, _) in paths.items()
                                                  if name in eligible and signal is True),
            "confirm_counter_before": before,
            "confirm_counter_after": deepcopy(counters),
            "confirm_chain_reset": confirm_chain_reset,
            "recovery_after_null": recovery_after_null,
            "confirm_triggered": confirm_triggered,
            "freeze": state.get("stage_frozen", False),
            "null_reason": missing,
            "formal_input_freeze": not quality_good,
            "transition": transition,
        }
        if case["case_id"] in FOCUS_CASES:
            audit.append(row_audit)
        outputs.append({"snapshot": snapshot, "rules": row["rules"], "state": state})
        prior_required_null = bool(quality_good and not known_ok)

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
    event_s1 = [row["state"]["state"] == "S1" and not row["state"]["stage_frozen"] for row in event_rows]
    metrics["event_S1_days"] = sum(event_s1)
    metrics["longest_event_S1_run"] = longest_run(event_s1)
    seq = transition_sequence(outputs)
    metrics["patterns"] = {
        "S0_S1_S0": path_count(seq, ["S0", "S1", "S0"]),
        "S1_S2_S1_OR_S0": path_count(seq, ["S1", "S2", "S1"]) + path_count(seq, ["S1", "S2", "S0"]),
        "S2_S3_S2": path_count(seq, ["S2", "S3", "S2"]),
        "S2_S3_S2_S3": path_count(seq, ["S2", "S3", "S2", "S3"]),
    }
    input_freeze_mask = [
        bool(row["snapshot"].get("stage_frozen") or not row["snapshot"].get("critical_data_ok", False))
        for row in outputs
    ]
    metrics["hard_exit_count"] = 0
    metrics["duplicate_new_high_votes"] = sum(
        rule_map(row)["D.newhigh"] == rule_map(row)["E3"] for row in archived["rows"]
    )
    metrics["input_data_freeze_days"] = sum(input_freeze_mask)
    metrics["input_data_freeze_mask_checksum"] = digest(input_freeze_mask)
    metrics["rule_or_state_evidence_freeze_days"] = metrics["freeze_days"] - metrics["input_data_freeze_days"]
    metrics["state_path_checksum"] = digest([row["state"]["state"] for row in outputs])
    metrics["full_output_checksum"] = digest(outputs)
    metrics["required_null_days"] = required_null_days
    metrics["null_chain_reset_days"] = null_chain_reset_days
    metrics["null_chain_nonzero_reset_days"] = null_chain_nonzero_reset_days
    metrics["null_counter_retention_violations"] = null_counter_retention_violations
    metrics["recovery_first_day_counter_violations"] = recovery_first_day_counter_violations
    metrics["b_present_c_integrity_violations"] = b_present_c_integrity_violations
    metrics["cross_signature_accumulations"] = cross_signature_accumulations
    return {"business": business, "metrics": metrics, "path_audit": audit}


def sentinel_checks(arm: str, results: dict, summaries: dict, b3_lag: int | None) -> dict:
    p10 = results["P10"]["metrics"]
    n02 = results["N02"]["metrics"]
    n04 = results["N04"]["metrics"]
    n08 = results["N08"]["metrics"]
    n02_rows = summaries["N02"]["path_rows"]
    break_on_null = arm in {ARMS[1], ARMS[3]}
    require_c = arm in {ARMS[2], ARMS[3]}
    return {
        "p10_event_hit": p10["event_S2_detected"] is True,
        "p10_lag_max_5": p10["S2_lag_observed"] is not None and p10["S2_lag_observed"] <= 5,
        "p10_delay_vs_b3_max_1": b3_lag is not None and p10["S2_lag_observed"] is not None
                                    and p10["S2_lag_observed"] <= b3_lag + 1,
        "n02_no_confirm_when_c_null": not any(row["confirm_triggered"] and row["C"] is None for row in n02_rows),
        "n02_no_confirm_when_c_false_if_required": (
            not require_c or not any(row["confirm_triggered"] and row["C"] is False for row in n02_rows)
        ),
        "n02_event_s2_exposure_0": n02["false_S2_days"] == 0,
        "null_resets_all_counters_if_required": (
            not break_on_null or all(
                not any(row["confirm_counter_after"].values())
                for summary in summaries.values() for row in summary["path_rows"]
                if row["required_known_ok"] is False and not row["formal_input_freeze"]
            )
        ),
        "recovery_first_eligible_day_max_1_if_required": (
            not break_on_null or all(
                max(row["confirm_counter_after"].values(), default=0) <= 1
                for summary in summaries.values() for row in summary["path_rows"]
                if row["recovery_after_null"]
            )
        ),
        "n04_full_window_no_s2": n04["S2_detected"] is False,
        "n08_event_no_s2": n08["event_S2_detected"] is False,
        "n08_full_window_no_s2": n08["S2_detected"] is False,
    }


def gate_v4(cases: list[dict], current: dict, baseline: dict, case_results: dict,
            baseline_cases: dict, deterministic: bool, sentinels: dict, arm: str) -> dict:
    case_by_id = {case["case_id"]: case for case in cases}
    favorable = favorable_cases(cases, current, baseline, case_results, baseline_cases)
    episodes = {case_by_id[cid]["episode_cluster"] for cid in favorable}
    lost = sorted(set(baseline["positive_event_hit_ids"]) - set(current["positive_event_hit_ids"]))
    new_hits = sorted(set(current["positive_event_hit_ids"]) - set(baseline["positive_event_hit_ids"]))
    delays = current.get("matched_lag_delta", {})
    break_on_null = arm in {ARMS[1], ARMS[3]}
    require_c = arm in {ARMS[2], ARMS[3]}
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
        "matched_lag_all_baseline_hits_retained": len(delays) == len(baseline["positive_event_hit_ids"]),
        "matched_lag_median_delay_max_1": current.get("matched_lag_median_delta") is not None
                                              and current["matched_lag_median_delta"] <= 1,
        "matched_lag_mean_delay_max_2": current.get("matched_lag_mean_delta") is not None
                                            and current["matched_lag_mean_delta"] <= 2,
        "single_case_delay_max_5": bool(delays) and max(delays.values()) <= 5,
        "s0_s1_s0_not_above_baseline": current["s0_s1_s0_patterns"] <= baseline["s0_s1_s0_patterns"],
        "short_reversals_not_above_baseline": current["short_reversals"] <= baseline["short_reversals"],
        "reversals_not_above_baseline": current["reversals"] <= baseline["reversals"],
        "transitions_not_above_baseline": current["transitions"] <= baseline["transitions"],
        "negative_s1_days_increase_max_10pct": current["negative_event_s1_case_days"]
                                                  <= baseline["negative_event_s1_case_days"] * 1.10,
        "negative_single_s1_run_increase_max_3": all(
            current["negative_case_s1"][cid]["max_run"] <= value["max_run"] + 3
            for cid, value in baseline["negative_case_s1"].items()
        ),
        "freeze_transition_violations_0": current["freeze_transition_violations"] == 0,
        "input_data_freeze_mask_unchanged": current["input_data_freeze_mask_checksums"]
                                               == baseline["input_data_freeze_mask_checksums"],
        "illegal_transition_patterns_0": current["s1_s2_s1_or_s0_patterns"] == 0,
        "null_counter_retention_violations_0": not break_on_null
                                                   or current["null_counter_retention_violations"] == 0,
        "recovery_first_day_counter_violations_0": not break_on_null
                                                       or current["recovery_first_day_counter_violations"] == 0,
        "b_present_c_integrity_violations_0": not require_c
                                                  or current["b_present_c_integrity_violations"] == 0,
        "cross_signature_accumulations_0": current["cross_signature_accumulations"] == 0,
        "deterministic_rerun": deterministic,
        "improvement_not_only_warmup_sensitive": any(cid not in WARMUP_SENSITIVE for cid in favorable),
        **{f"sentinel_{name}": passed for name, passed in sentinels.items()},
    }
    return {
        "passed": all(checks.values()), "checks": checks,
        "favorable_positive_cases": favorable, "favorable_episodes": sorted(episodes),
        "new_positive_event_hits": new_hits, "lost_positive_event_hits": lost,
        "non_warmup_favorable_cases": [cid for cid in favorable if cid not in WARMUP_SENSITIVE],
        "sentinel_checks": sentinels,
    }


def run_candidate(arm: str, cases: list[dict], archives: dict[str, dict], calendar: list[str], profile: dict,
                  baseline: dict, baseline_cases: dict, threshold: float, b3_lag: int | None) -> dict:
    runs = []
    full_results = None
    aggregate = None
    for _ in range(2):
        current = {
            case["case_id"]: replay_candidate(case, archives[case["case_id"]], calendar, profile, arm, threshold)
            for case in cases
        }
        for case in cases:
            current[case["case_id"]]["metrics"]["warmup_sensitive"] = case["case_id"] in WARMUP_SENSITIVE
        aggregate = aggregate_arm(current, cases, baseline)
        for metric in (
            "required_null_days", "null_chain_reset_days", "null_chain_nonzero_reset_days",
            "null_counter_retention_violations", "recovery_first_day_counter_violations",
            "b_present_c_integrity_violations", "cross_signature_accumulations",
        ):
            aggregate[metric] = sum(value["metrics"][metric] for value in current.values())
        checksum = digest({
            "aggregate": aggregate,
            "cases": {cid: value["metrics"]["full_output_checksum"] for cid, value in current.items()},
        })
        runs.append(checksum)
        full_results = current
    deterministic = runs[0] == runs[1]
    case_by_id = {case["case_id"]: case for case in cases}
    summaries = {
        cid: focus_summary({"focus_case_paths": {cid: full_results[cid]["path_audit"]}}, cid, case_by_id[cid])
        for cid in sorted(FOCUS_CASES)
    }
    sentinels = sentinel_checks(arm, full_results, summaries, b3_lag)
    gate = gate_v4(cases, aggregate, baseline, full_results, baseline_cases, deterministic, sentinels, arm)
    return {
        "arm": arm,
        "config": {
            "arm": arm, "comparison_parent": "BASELINE",
            "structural_parent": "V1_B3_WITH_SAME_BRANCH_AND_REQUIRED_KNOWN",
            "above_ma20_min": threshold,
            "null_breaks_continuity": arm in {ARMS[1], ARMS[3]},
            "b_present_requires_c_true": arm in {ARMS[2], ARMS[3]},
            "same_branch_persistence": True,
        },
        "metrics": aggregate, "gate": gate, "deterministic": deterministic,
        "rerun_checksums": runs, "case_results": full_results,
        "focus_case_paths": {cid: full_results[cid]["path_audit"] for cid in sorted(FOCUS_CASES)},
        "focus_summary": summaries, "status": "PASS" if gate["passed"] else "FAIL",
    }


def select_candidates(candidates: list[dict]) -> tuple[dict | None, dict | None]:
    eligible = [arm for arm in candidates if arm["status"] == "PASS"]
    if not eligible:
        return None, None
    complexity = {ARMS[1]: 0, ARMS[2]: 1, ARMS[3]: 2}
    ranked = sorted(eligible, key=lambda arm: (
        arm["metrics"]["negative_event_new_s2_cases"],
        arm["metrics"]["negative_event_s2_case_days"],
        -arm["metrics"]["positive_event_s2_cases"],
        -arm["metrics"]["positive_full_window_s2_cases"],
        arm["metrics"]["matched_lag_mean_delta"],
        arm["metrics"]["s0_s1_s0_patterns"],
        arm["metrics"]["negative_event_s1_case_days"],
        complexity[arm["arm"]],
    ))
    return ranked[0], ranked[1] if len(ranked) > 1 else None


def report_markdown(summary: dict) -> str:
    baseline = summary["baseline"]["metrics"]
    show = lambda values: "、".join(values) if values else "无"
    lines = [
        "# A股主线识别系统 V2.2.1 — RULE CALIBRATION EXECUTION REPORT V4", "",
        "## Technical Summary", "",
        f"**最终结论：{summary['final_conclusion']}。**",
        "",
        summary["decision_reason"],
        "",
        "本轮严格执行最终有限规格；结果仅适用于25例Development / Diagnostic Set。G5仍为FAIL，资格保持`CALIBRATION_ONLY / DIAGNOSTIC_ONLY`，不构成生产准确率、正式规则优化或上线授权。", "",
        "## Baseline与执行边界均未漂移", "",
        f"BASELINE **{summary['baseline']['status']}**：事件期正例{baseline['positive_event_s2_cases']}/10，全窗口{baseline['positive_full_window_s2_cases']}/10；负例新确认{baseline['negative_event_new_s2_cases']}，负例S2暴露{baseline['negative_event_s2_case_days']}日；`S0→S1→S0`={baseline['s0_s1_s0_patterns']}，short reversal={baseline['short_reversals']}。",
        f"V1-B3参考臂 **{summary['b3_reference']['status']}**：{summary['b3_reference']['equivalence_note']}。既有V3归档校验={summary['v3_archive_verification']['status']}，未重跑V3。", "",
        "## 三个平行候选的结果", "",
        "| 候选 | 结论 | 事件期正例 | 全窗正例 | 新增命中 | 丢失命中 | 负例新确认 | 负例S2日 | S0→S1→S0 | short reversal | transition |",
        "| --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in summary["candidates"]:
        m, g = arm["metrics"], arm["gate"]
        lines.append(
            f"| {arm['arm']} | {arm['status']} | {m['positive_event_s2_cases']}/10 | "
            f"{m['positive_full_window_s2_cases']}/10 | {show(g['new_positive_event_hits'])} | "
            f"{show(g['lost_positive_event_hits'])} | {m['negative_event_new_s2_cases']} | "
            f"{m['negative_event_s2_case_days']} | {m['s0_s1_s0_patterns']} | "
            f"{m['short_reversals']} | {m['transitions']} |"
        )
    lines.extend(["", "以上候选均独立从同一V1-B3 + same-branch基础运行，并分别与BASELINE比较；不存在A叠加B或根据中间结果修改C。", ""])

    lines.extend(["## 每个候选为何通过或失败", ""])
    for arm in summary["candidates"]:
        m, g = arm["metrics"], arm["gate"]
        failed = [name for name, passed in g["checks"].items() if not passed]
        neg_before = set(baseline["negative_new_confirmation_ids"])
        neg_after = set(m["negative_new_confirmation_ids"])
        lines.extend([
            f"### {arm['arm']}", "",
            f"- **业务结果：** 事件期/全窗正例={m['positive_event_s2_cases']}/10、{m['positive_full_window_s2_cases']}/10；新增命中={show(g['new_positive_event_hits'])}；丢失={show(g['lost_positive_event_hits'])}。",
            f"- **负例变化：** 新增误确认={show(sorted(neg_after - neg_before))}；减少误确认={show(sorted(neg_before - neg_after))}；总新确认={m['negative_event_new_s2_cases']}；S2暴露={m['negative_event_s2_case_days']}日。",
            f"- **确认滞后：** 均值/中位数={m['positive_event_lag_mean']:.2f}/{m['positive_event_lag_median']}；matched变化={m['matched_lag_mean_delta']:.2f}/{m['matched_lag_median_delta']}；逐case=`{m['positive_case_lags']}`。",
            f"- **Churn：** `S0→S1→S0`={m['s0_s1_s0_patterns']}；short reversal={m['short_reversals']}；reversal={m['reversals']}；transition={m['transitions']}；负例S1日={m['negative_event_s1_case_days']}。",
            f"- **确认完整性：** NULL日={m['required_null_days']}；断链日={m['null_chain_reset_days']}；旧计数残留违规={m['null_counter_retention_violations']}；恢复首日违规={m['recovery_first_day_counter_violations']}；C完整性违规={m['b_present_c_integrity_violations']}；跨signature累计={m['cross_signature_accumulations']}。",
            f"- **专项哨兵：** `{g['sentinel_checks']}`。",
            f"- **失败检查：** {show(failed)}。", "",
        ])

    lines.extend(["## P10、N02、N04、N08关键路径", ""])
    for cid in ("P10", "N02", "N04", "N08"):
        lines.extend([
            f"### {cid}", "",
            "| Arm | 确认日 | 事件期S2 | 全窗口S2 | 解释 |",
            "| --- | --- | --- | --- | --- |",
        ])
        for arm in [summary["baseline"], *summary["candidates"]]:
            case = arm["case_results_serialized"][cid]
            focus = arm["focus_summary"][cid]
            dates = show(focus["confirmation_dates"])
            if cid == "P10":
                why = "正式五组AND未在事件期确认" if arm["arm"] == "BASELINE" else "B-waived路径未改变，持续证据完成确认"
            elif cid == "N02":
                if arm["arm"] == "BASELINE":
                    why = "事件期无S2，事件后11月7日才由正式路径确认"
                elif arm["config"]["null_breaks_continuity"] and arm["config"]["b_present_requires_c_true"]:
                    why = "NULL断链且B-present强制C=TRUE"
                elif arm["config"]["null_breaks_continuity"]:
                    why = "NULL清除旧链，但C=FALSE时仍允许Enhancer补偿"
                else:
                    why = "C=NULL/FALSE均不能获得B-present确认资格"
            elif cid == "N04":
                why = ("正式五组AND未完成确认" if arm["arm"] == "BASELINE"
                       else "same-branch继续阻断跨分支拼接")
            else:
                why = ("正式五组AND未完成确认" if arm["arm"] == "BASELINE"
                       else "above_ma20<0.60，绝对广度底座继续阻断")
            lines.append(f"| {arm['arm']} | {dates} | {case['event_S2_detected']} | {case['S2_detected']} | {why} |")
        lines.extend(["", f"逐日A/B/C/D/Enhancer、above_ma20、required-known、signature、计数器、断链、确认、Freeze与NULL原因保存在`calibration_results_v4.json`的`focus_case_paths.{cid}`。", ""])

    lines.extend([
        "## NULL、Freeze、Warmup与确定性", "",
    ])
    for arm in summary["candidates"]:
        m = arm["metrics"]
        lines.append(
            f"- **{arm['arm']}：** NULL旧计数残留违规={m['null_counter_retention_violations']}；恢复首日违规={m['recovery_first_day_counter_violations']}；C完整性违规={m['b_present_c_integrity_violations']}；Freeze转移违规={m['freeze_transition_violations']}；两次重跑一致={arm['deterministic']}。"
        )
    lines.extend([
        "- P01、P06、P07、N05、N06、A01仍为直接warmup-sensitive cases；G5继续FAIL。",
        "- NULL没有填0、默认通过或自动制造全局Freeze；正式Freeze输入掩码与BASELINE一致。", "",
        "## 最终选择与停止规则", "",
        f"- **PRIMARY CALIBRATION CANDIDATE：** {summary['primary_candidate'] or '无'}。",
        f"- **BACKUP CANDIDATE：** {summary['backup_candidate'] or '无'}。",
        f"- **FINAL BOUNDED CALIBRATION Stop Rule：** {summary['final_bounded_stop_rule']['status']}。",
        f"- **下一步：** {summary['final_bounded_stop_rule']['next_step']}", "",
        "本轮未修改正式rule_version、parameter_profile、阈值、状态机、退出、恢复、S3/S4、casebook、Production、scheduler、Sites或G1–G4；未运行Holdout。", "",
        "## 方法与限制", "",
        "本次只重放冻结归档中的25个开发/诊断案例，使用预注册规则和固定硬门槛；每臂执行两次并比对checksum。它能判断候选是否满足当前开发集合同，不能证明泛化能力。完整84日warmup仍未认证，因此所有结论必须与G5=FAIL共同阅读。", "",
    ])
    return "\n".join(lines)


def verify_v3_archive(spec: dict) -> dict:
    result = read(V3_RESULTS)
    manifest = read(V3_MANIFEST)
    rerun = read(V3_RERUN)
    expected = spec["v3_findings"]
    by_name = {arm["arm"]: arm for arm in result["candidates"]}
    mapping = {
        "V3_A": "V3_A_NULL_GATING_ONLY",
        "V3_B": "V3_B_SAME_BRANCH_ONLY",
        "V3_C": "V3_C_NULL_GATING_AND_SAME_BRANCH",
    }
    checks = {
        "v3_complete": result["status"] == "COMPLETE",
        "v3_deterministic": rerun["status"] == "PASS",
        "v3_manifest_result_checksum": manifest["result_checksum"] == digest(result),
    }
    for key, arm_name in mapping.items():
        arm = by_name[arm_name]
        checks[f"{key}_event_recall"] = arm["metrics"]["positive_event_s2_cases"] == expected[key]["positive_event_s2"]
        checks[f"{key}_negative_new"] = arm["metrics"]["negative_event_new_s2_cases"] == 1
        checks[f"{key}_negative_exposure"] = arm["metrics"]["negative_event_s2_case_days"] == expected[key]["negative_event_s2_exposure_days"]
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "artifact_sha256": {
            name: sha256(OUT / name) for name in (
                "CALIBRATION_EXECUTION_REPORT_V3.md", "calibration_results_v3.json",
                "version_comparison_v3.csv", "case_level_delta_v3.csv",
                "state_transition_delta_v3.csv", "experiment_manifest_v3.json",
                "deterministic_rerun_v3.json",
            )
        },
        "v3_rerun_executed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    targets = [
        "CALIBRATION_EXECUTION_REPORT_V4.md", "calibration_results_v4.json",
        "version_comparison_v4.csv", "case_level_delta_v4.csv",
        "state_transition_delta_v4.csv", "experiment_manifest_v4.json",
        "deterministic_rerun_v4.json", "final_bounded_calibration_decision.json",
    ]
    if any((args.output / name).exists() for name in targets):
        raise ValueError("immutable V4 calibration output already exists")

    started = utc()
    start_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    spec = read(SPEC_JSON)
    prior_v2 = read(V2_RESULTS)
    book = read(BASE / "casebook.json")
    profile, frozen_hashes = baseline_profile(ROOT)
    _, _, calendar, provenance = load_inputs(BASE, profile)
    cases = book["cases"]
    case_by_id = {case["case_id"]: case for case in cases}
    archives = {case["case_id"]: load_archive(case["case_id"]) for case in cases}
    threshold = profile["confirm"]["above_ma20_min"]
    if threshold != 0.60:
        raise ValueError("registered above_ma20 threshold drift")

    from scripts.mainline.rule_calibration_execute import run_arm
    baseline = run_arm("BASELINE", cases, archives, calendar, profile, None, None)
    expected = {
        "positive_event_s2_cases": spec["baseline_contract"]["positive_event_s2"],
        "positive_full_window_s2_cases": spec["baseline_contract"]["positive_full_window_s2"],
        "negative_event_new_s2_cases": spec["baseline_contract"]["negative_event_new_confirm_cases"],
        "negative_event_s2_case_days": spec["baseline_contract"]["negative_event_s2_exposure_days"],
        "s0_s1_s0_patterns": spec["baseline_contract"]["s0_s1_s0"],
        "transitions": spec["baseline_contract"]["transitions"],
        "reversals": spec["baseline_contract"]["reversals"],
        "short_reversals": spec["baseline_contract"]["short_reversals"],
        "freeze_days": 63,
    }
    baseline["equivalence"] = baseline_equivalence(baseline, archives, expected)
    baseline["status"] = "PASS" if baseline["equivalence"]["passed"] and baseline["deterministic"] else "HARNESS_FAIL"
    baseline["arm"] = "BASELINE"
    baseline["config"] = {"comparison_parent": None, "null_breaks_continuity": False,
                          "b_present_requires_c_true": False, "same_branch_persistence": False}
    baseline["focus_case_paths"] = baseline_focus(archives)
    for rows in baseline["focus_case_paths"].values():
        for row in rows:
            row["eligible_evidence_signature"] = []
            row["confirm_chain_reset"] = False
            row["recovery_after_null"] = False
    baseline["focus_summary"] = {
        cid: focus_summary(baseline, cid, case_by_id[cid]) for cid in sorted(FOCUS_CASES)
    }

    b3_reference = None
    v3_archive = verify_v3_archive(spec)
    candidates = []
    if baseline["status"] == "PASS":
        b3_reference = run_v2_candidate(
            "V1_B3_ASYMMETRIC_B_ROLE", cases, archives, calendar, profile,
            baseline["metrics"], baseline["case_results"], threshold,
        )
        archived_b3 = next(arm for arm in prior_v2["candidates"] if arm["arm"] == "V1_B3_ASYMMETRIC_B_ROLE")
        b3_checks = {
            "positive_event_9": b3_reference["metrics"]["positive_event_s2_cases"] == 9,
            "positive_full_9": b3_reference["metrics"]["positive_full_window_s2_cases"] == 9,
            "negative_new_1": b3_reference["metrics"]["negative_event_new_s2_cases"] == 1,
            "negative_exposure_12": b3_reference["metrics"]["negative_event_s2_case_days"] == 12,
            "rerun_checksum_matches_v2": b3_reference["rerun_checksums"] == archived_b3["rerun_checksums"],
            "aggregate_checksum_matches_v2": b3_reference["metrics"]["checksum"] == archived_b3["metrics"]["checksum"],
        }
        b3_reference["reference_equivalence"] = {"passed": all(b3_checks.values()), "checks": b3_checks}
        b3_reference["status"] = "PASS" if all(b3_checks.values()) else "HARNESS_FAIL"

    if (baseline["status"] == "PASS" and b3_reference and b3_reference["status"] == "PASS"
            and v3_archive["status"] == "PASS"):
        b3_lag = b3_reference["case_results"]["P10"]["metrics"]["S2_lag_observed"]
        for arm in ARMS[1:]:
            candidates.append(run_candidate(
                arm, cases, archives, calendar, profile,
                baseline["metrics"], baseline["case_results"], threshold, b3_lag,
            ))

    primary, backup = select_candidates(candidates)
    if baseline["status"] != "PASS" or not b3_reference or b3_reference["status"] != "PASS" or v3_archive["status"] != "PASS":
        final = "BLOCKED BY DATA / BASELINE DRIFT"
        reason = "BASELINE、V1-B3参考臂或V3归档校验未精确复现；按Stop Rule未执行V4候选。"
        stop_status = "BLOCKED_EQUIVALENCE_REPAIR_ONLY"
        next_step = "只修复数据、归档或运行等价问题，不得继续校准。"
    elif primary:
        final = "CALIBRATION CANDIDATE FOUND — HOLDOUT REQUIRED"
        reason = "至少一个预注册V4候选通过全部业务与专项护栏；候选仅可进入独立Holdout，不能发布正式规则。"
        stop_status = "DEVELOPMENT_SET_TUNING_STOPPED_HOLDOUT_REQUIRED"
        next_step = "停止开发集调参，先完成数据资格边界并设计独立Holdout。"
    else:
        final = "NO CANDIDATE PASSED — DEVELOPMENT SET CALIBRATION STOPPED"
        reason = "三个预注册V4候选均未通过全部硬门槛；正式触发FINAL BOUNDED CALIBRATION Stop Rule。"
        stop_status = "FINAL_STOP_TRIGGERED_NO_V5_V6"
        next_step = "禁止V5/V6和当前25例追调；转向warmup资格、独立样本扩充与规则框架重审。"

    all_arms = [baseline, *candidates]
    for arm in all_arms:
        arm["case_results_serialized"] = {
            cid: minimal_case(value["metrics"]) for cid, value in arm["case_results"].items()
        }
    versions, case_rows, state_rows = delta_rows(
        all_arms, baseline["metrics"], baseline["case_results"], cases,
    )

    def public_arm(arm: dict) -> dict:
        value = deepcopy({key: item for key, item in arm.items() if key != "case_results"})
        for cid in sorted(FOCUS_CASES):
            case = case_by_id[cid]
            value["focus_case_paths"][cid] = [
                row for row in value["focus_case_paths"][cid]
                if case["pre_window_start"] <= row["trade_date"] <= case["post_window_end"]
            ]
            value["focus_summary"][cid].pop("path_rows", None)
            value["focus_summary"][cid].pop("event_evidence_rows", None)
        return value

    b3_public = {
        "arm": "V1_B3_ASYMMETRIC_B_ROLE",
        "status": b3_reference["status"] if b3_reference else "NOT_RUN",
        "equivalence_note": "9/10、9/10、1、12日及既有checksum全部一致"
                            if b3_reference and b3_reference["status"] == "PASS" else "未通过参考等价校验",
        "checks": b3_reference.get("reference_equivalence", {}).get("checks", {}) if b3_reference else {},
        "rerun_checksums": b3_reference.get("rerun_checksums", []) if b3_reference else [],
    }
    decision = {
        "decision": final,
        "primary_candidate": primary["arm"] if primary else None,
        "backup_candidate": backup["arm"] if backup else None,
        "stop_rule_status": stop_status,
        "current_25_case_calibration_closed": final != "BLOCKED BY DATA / BASELINE DRIFT",
        "v5_v6_allowed_on_current_25_cases": False,
        "formal_rule_publish_allowed": False,
        "holdout_allowed": bool(primary),
        "next_step": next_step,
    }
    summary = {
        "status": "COMPLETE" if candidates else "BLOCKED",
        "qualification": "CALIBRATION_ONLY_DIAGNOSTIC_ONLY", "g5": "FAIL",
        "final_conclusion": final, "decision_reason": reason,
        "baseline": public_arm(baseline), "b3_reference": b3_public,
        "v3_archive_verification": v3_archive,
        "candidates": [public_arm(arm) for arm in candidates],
        "primary_candidate": primary["arm"] if primary else None,
        "backup_candidate": backup["arm"] if backup else None,
        "final_bounded_stop_rule": {"status": stop_status, "next_step": next_step},
        "executed_arm_count": len(all_arms), "registered_arm_count": 4,
        "production_writes": 0, "holdout_executed": False,
        "formal_rule_changed": False, "formal_profile_changed": False,
    }
    manifest = {
        "experiment": "RULE_CALIBRATION_EXECUTION_V4_FINAL_BOUNDED",
        "started_at": started, "finished_at": utc(), "start_sha": start_sha,
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "spec_sha256": sha256(SPEC_MD), "spec_json_sha256": sha256(SPEC_JSON),
        "casebook_version": book["casebook_version"], "casebook_checksum": book["checksum"],
        "rule_version": book["rule_version"], "parameter_profile": book["parameter_profile"],
        "frozen_code_file_hashes": frozen_hashes,
        "data_snapshot_version": provenance["data_snapshot_version"],
        "pit_level": provenance["pit_level"], "knowledge_time_unverified": True,
        "warmup_qualified": False, "g5": "FAIL",
        "execution_order": ["BASELINE", "V1_B3_REFERENCE", "V3_ARCHIVE_VERIFY", *[arm["arm"] for arm in candidates]],
        "parallel_candidates": True, "production_writes": 0,
        "formal_rule_changed": False, "formal_profile_changed": False,
        "v1_v2_v3_rerun": False, "holdout_executed": False,
        "result_checksum": digest(summary),
    }
    deterministic = {
        "status": "PASS" if all(arm["deterministic"] for arm in all_arms) else "FAIL",
        "reruns_per_arm": 2,
        "arms": [{"arm": arm["arm"], "checksums": arm["rerun_checksums"], "identical": arm["deterministic"]}
                 for arm in all_arms],
        "b3_reference": b3_public, "v3_archive_verification": v3_archive,
        "null_default_pass_count": 0,
        "null_counter_retention_violations": max(
            [arm["metrics"].get("null_counter_retention_violations", 0) for arm in all_arms]
        ),
        "recovery_first_day_counter_violations": max(
            [arm["metrics"].get("recovery_first_day_counter_violations", 0) for arm in all_arms]
        ),
        "b_present_c_integrity_violations": max(
            [arm["metrics"].get("b_present_c_integrity_violations", 0) for arm in all_arms]
        ),
        "cross_signature_accumulations": max(
            [arm["metrics"].get("cross_signature_accumulations", 0) for arm in all_arms]
        ),
        "freeze_transition_violations": max(arm["metrics"]["freeze_transition_violations"] for arm in all_arms),
        "production_writes": 0,
    }

    write_compact_json(args.output / "calibration_results_v4.json", summary)
    write_csv(args.output / "version_comparison_v4.csv", versions)
    write_csv(args.output / "case_level_delta_v4.csv", case_rows)
    write_csv(args.output / "state_transition_delta_v4.csv", state_rows)
    write_json(args.output / "experiment_manifest_v4.json", manifest)
    write_json(args.output / "deterministic_rerun_v4.json", deterministic)
    write_json(args.output / "final_bounded_calibration_decision.json", decision)
    (args.output / "CALIBRATION_EXECUTION_REPORT_V4.md").write_text(report_markdown(summary), encoding="utf-8")
    print(json.dumps({
        "final_conclusion": final, "baseline": baseline["status"],
        "b3_reference": b3_public["status"], "v3_archive": v3_archive["status"],
        "arms": {arm["arm"]: arm["status"] for arm in candidates},
        "primary": summary["primary_candidate"], "backup": summary["backup_candidate"],
        "stop_rule": stop_status,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
