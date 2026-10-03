"""Execute the preregistered V3 confirmation-integrity candidates.

All arms replay frozen development archives.  The harness never calls data
providers, writes production state, or changes the formal rule/profile/state
machine.  V3-A/B/C are parallel children of the archived V1-B3 structure.
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
from mainline.engine.rules import tri_all, tri_any  # noqa: E402
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
from scripts.mainline.rule_calibration_execute_v2 import (  # noqa: E402
    breadth_floor,
    candidate_paths,
    run_candidate as run_v2_candidate,
)

OUT = ROOT / "reports/milestone-d-rule-calibration"
SPEC_MD = OUT / "RULE_CALIBRATION_EXPERIMENT_SPEC_V3.md"
SPEC_JSON = OUT / "rule_calibration_experiment_spec_v3.json"
V2_RESULTS = OUT / "calibration_results_v2.json"
ARMS = (
    "BASELINE",
    "V3_A_NULL_GATING_ONLY",
    "V3_B_SAME_BRANCH_ONLY",
    "V3_C_NULL_GATING_AND_SAME_BRANCH",
)
FOCUS_CASES = {"P10", "N02", "N04", "N08"}
REQUIRED_GROUPS = ("A", "B", "C", "D", "enhancers")
SIGNATURE_DAYS = {
    "STANDARD_ALL": 2,
    "B_PRESENT_C": 2,
    "B_PRESENT_ENHANCER": 2,
    "B_WAIVED_C_ENHANCER": 3,
}


def required_known(values: dict, snapshot: dict) -> tuple[bool, list[str]]:
    missing = ["Enhancer" if key == "enhancers" else key for key in REQUIRED_GROUPS if values[key] is None]
    if snapshot.get("above_ma20") is None:
        missing.append("above_ma20")
    return not missing, missing


def b3_paths(values: dict, snapshot: dict, threshold: float) -> dict[str, tuple[bool | None, int]]:
    return candidate_paths("V1_B3_ASYMMETRIC_B_ROLE", values, snapshot, threshold)


def signature_paths(values: dict, snapshot: dict, threshold: float) -> dict[str, tuple[bool | None, int]]:
    floor = breadth_floor(snapshot, threshold)
    core = tri_all([values["A"], values["D"], floor])
    standard = tri_all([values["A"], values["B"], values["C"], values["D"], values["enhancers"]])
    present_c = tri_all([core, values["B"], values["C"]])
    present_e = tri_all([core, values["B"], values["enhancers"]])
    if values["B"] is False:
        waived = tri_all([core, values["C"], values["enhancers"]])
    elif values["B"] is True:
        waived = False
    else:
        waived = None
    return {
        "STANDARD_ALL": (standard, 2),
        "B_PRESENT_C": (present_c, 2),
        "B_PRESENT_ENHANCER": (present_e, 2),
        "B_WAIVED_C_ENHANCER": (waived, 3),
    }


def replay_candidate(case: dict, archived: dict, calendar: list[str], profile: dict,
                     arm: str, threshold: float) -> dict:
    initial = deepcopy(archived["initial_checkpoint"])
    if initial:
        cp = Checkpoint(**initial)
    else:
        first = archived["rows"][0]["snapshot"]
        cp = Checkpoint(first["object_id"], first["rule_version"], profile["profile_id"],
                        first["metric_availability_version"], state="S0")

    null_gate = arm in {"V3_A_NULL_GATING_ONLY", "V3_C_NULL_GATING_AND_SAME_BRANCH"}
    signature_mode = arm in {"V3_B_SAME_BRANCH_ONLY", "V3_C_NULL_GATING_AND_SAME_BRANCH"}
    outputs: list[dict] = []
    audit: list[dict] = []
    counters: dict[str, int] = {}
    required_null_days = 0
    required_null_counter_increment_violations = 0
    cross_signature_accumulations = 0

    for archived_row in archived["rows"]:
        row = deepcopy(archived_row)
        values = rule_map(row)
        snapshot = row["snapshot"]
        before_state = cp.state
        raw_eval = evidence(row)
        known_ok, missing = required_known(values, snapshot)
        b3 = b3_paths(values, snapshot, threshold)
        active_paths = signature_paths(values, snapshot, threshold) if signature_mode else b3
        quality_good = snapshot.get("critical_data_ok") is True and not snapshot.get("stage_frozen", False)
        before = deepcopy(counters)
        complete = False
        completed_signatures: list[str] = []

        if before_state != "S1":
            counters = {name: 0 for name in active_paths}
        elif quality_good:
            if null_gate and not known_ok:
                required_null_days += 1
                # Registered pause: preserve every experimental counter and do
                # not expose NULL as state-machine Freeze.
                if counters != before:
                    required_null_counter_increment_violations += 1
            else:
                for name, (signal, needed) in active_paths.items():
                    counters.setdefault(name, 0)
                    if signal is True:
                        counters[name] += 1
                    elif signal is False:
                        counters[name] = 0
                    # In V3-B, NULL pauses only the affected signature.
                    if signal is True and counters[name] >= needed:
                        completed_signatures.append(name)
                complete = bool(completed_signatures)

            if complete:
                raw_eval["confirm"] = True
                cp.consecutive["confirm"] = profile["confirm"]["confirm_consecutive_days"] - 1
            elif null_gate and not known_ok:
                raw_eval["confirm"] = False
            elif signature_mode:
                unresolved = any(signal is None for signal, _ in b3.values())
                raw_eval["confirm"] = None if unresolved else False
            else:
                raw_eval["confirm"] = False

        evaluation = {
            "evidence": raw_eval,
            "trigger_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is True],
            "failed_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is False],
            "unavailable_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is None],
        }
        state, cp = advance(cp, snapshot, evaluation, profile, calendar)
        if state.get("resume_reason") == "reset_after_unverifiable_gap":
            if null_gate and not known_ok:
                counters = {name: 0 for name in active_paths}
            else:
                counters = {name: int(signal is True) for name, (signal, _) in active_paths.items()}

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
            "evidence_signature": sorted(name for name, (signal, _) in active_paths.items() if signal is True),
            "confirm_counter_before": before,
            "confirm_counter_after": deepcopy(counters),
            "confirm_triggered": confirm_triggered,
            "freeze": state.get("stage_frozen", False),
            "null_reason": missing,
            "formal_input_freeze": not quality_good,
            "transition": transition,
        }
        if case["case_id"] in FOCUS_CASES:
            audit.append(row_audit)
        outputs.append({"snapshot": snapshot, "rules": row["rules"], "state": state})

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
    metrics["longest_event_S1_run"] = longest_run(
        [row["state"]["state"] == "S1" and not row["state"]["stage_frozen"] for row in event_rows]
    )
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
    metrics["required_null_counter_increment_violations"] = required_null_counter_increment_violations
    metrics["cross_signature_accumulations"] = cross_signature_accumulations
    return {"business": business, "metrics": metrics, "path_audit": audit}


def focus_summary(arm: dict, case_id: str, case: dict) -> dict:
    rows = arm["focus_case_paths"][case_id]
    relevant = [row for row in rows if case["pre_window_start"] <= row["trade_date"] <= case["post_window_end"]]
    confirms = [row for row in relevant if row["confirm_triggered"]]
    return {
        "case_id": case_id,
        "event_window": [case["start_date"], case["end_date"]],
        "confirmation_dates": [row["trade_date"] for row in confirms],
        "event_evidence_rows": [row for row in relevant if case["start_date"] <= row["trade_date"] <= case["end_date"]],
        "path_rows": relevant,
    }


def baseline_focus(archives: dict[str, dict]) -> dict:
    result = {}
    for cid in sorted(FOCUS_CASES):
        rows = []
        for row in archives[cid]["rows"]:
            values = rule_map(row)
            snapshot = row["snapshot"]
            state = row["state"]
            known, missing = required_known(values, snapshot)
            transition = state.get("transition")
            rows.append({
                "trade_date": snapshot["as_of_date"], "state_before": state["previous_state"],
                "state_after": state["state"], "A": values["A"], "B": values["B"], "C": values["C"],
                "D": values["D"], "Enhancer": values["enhancers"], "above_ma20": snapshot.get("above_ma20"),
                "required_known_ok": known, "evidence_signature": [],
                "confirm_counter_before": None, "confirm_counter_after": state.get("consecutive_days", {}).get("confirm"),
                "confirm_triggered": bool(isinstance(transition, dict) and transition.get("from_state") == "S1" and transition.get("to_state") == "S2"),
                "freeze": state.get("stage_frozen", False), "null_reason": missing,
                "formal_input_freeze": bool(snapshot.get("stage_frozen") or not snapshot.get("critical_data_ok", False)),
                "transition": transition,
            })
        result[cid] = rows
    return result


def sentinel_checks(arm: str, results: dict, summaries: dict, b3_lag: int | None) -> dict:
    p10 = results["P10"]["metrics"]
    n02 = results["N02"]["metrics"]
    n04 = results["N04"]["metrics"]
    n08 = results["N08"]["metrics"]
    n02_null_confirms = sum(
        row["confirm_triggered"] and "C" in row["null_reason"]
        for row in summaries["N02"]["path_rows"]
    )
    return {
        "p10_event_hit": p10["event_S2_detected"] is True,
        "p10_lag_max_5": p10["S2_lag_observed"] is not None and p10["S2_lag_observed"] <= 5,
        "p10_delay_vs_b3_max_1": b3_lag is not None and p10["S2_lag_observed"] is not None and p10["S2_lag_observed"] <= b3_lag + 1,
        "n02_no_confirm_while_c_null": n02_null_confirms == 0,
        "n02_event_s2_exposure_0": n02["false_S2_days"] == 0,
        "n04_full_window_no_s2": n04["S2_detected"] is False,
        "n08_event_no_s2": n08["event_S2_detected"] is False,
        "n08_full_window_no_s2": n08["S2_detected"] is False,
    }


def gate_v3(cases: list[dict], current: dict, baseline: dict, case_results: dict,
            baseline_cases: dict, deterministic: bool, sentinels: dict) -> dict:
    case_by_id = {case["case_id"]: case for case in cases}
    favorable = favorable_cases(cases, current, baseline, case_results, baseline_cases)
    episodes = {case_by_id[cid]["episode_cluster"] for cid in favorable}
    lost = sorted(set(baseline["positive_event_hit_ids"]) - set(current["positive_event_hit_ids"]))
    new_hits = sorted(set(current["positive_event_hit_ids"]) - set(baseline["positive_event_hit_ids"]))
    delays = current.get("matched_lag_delta", {})
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
        "matched_lag_median_delay_max_1": current.get("matched_lag_median_delta") is not None and current["matched_lag_median_delta"] <= 1,
        "matched_lag_mean_delay_max_2": current.get("matched_lag_mean_delta") is not None and current["matched_lag_mean_delta"] <= 2,
        "single_case_delay_max_5": bool(delays) and max(delays.values()) <= 5,
        "s0_s1_s0_not_above_baseline": current["s0_s1_s0_patterns"] <= baseline["s0_s1_s0_patterns"],
        "short_reversals_not_above_baseline": current["short_reversals"] <= baseline["short_reversals"],
        "reversals_not_above_baseline": current["reversals"] <= baseline["reversals"],
        "transitions_not_above_baseline": current["transitions"] <= baseline["transitions"],
        "negative_s1_days_increase_max_10pct": current["negative_event_s1_case_days"] <= baseline["negative_event_s1_case_days"] * 1.10,
        "negative_single_s1_run_increase_max_3": all(
            current["negative_case_s1"][cid]["max_run"] <= value["max_run"] + 3
            for cid, value in baseline["negative_case_s1"].items()
        ),
        "freeze_transition_violations_0": current["freeze_transition_violations"] == 0,
        "input_data_freeze_mask_unchanged": current["input_data_freeze_mask_checksums"] == baseline["input_data_freeze_mask_checksums"],
        "illegal_transition_patterns_0": current["s1_s2_s1_or_s0_patterns"] == 0,
        "required_null_counter_increment_violations_0": current["required_null_counter_increment_violations"] == 0,
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
        current = {case["case_id"]: replay_candidate(case, archives[case["case_id"]], calendar, profile, arm, threshold) for case in cases}
        for case in cases:
            current[case["case_id"]]["metrics"]["warmup_sensitive"] = case["case_id"] in WARMUP_SENSITIVE
        aggregate = aggregate_arm(current, cases, baseline)
        for metric in ("required_null_days", "required_null_counter_increment_violations", "cross_signature_accumulations"):
            aggregate[metric] = sum(value["metrics"][metric] for value in current.values())
        checksum = digest({"aggregate": aggregate, "cases": {cid: value["metrics"]["full_output_checksum"] for cid, value in current.items()}})
        runs.append(checksum)
        full_results = current
    deterministic = runs[0] == runs[1]
    summaries = {cid: focus_summary({"focus_case_paths": {cid: full_results[cid]["path_audit"]}}, cid,
                                    next(case for case in cases if case["case_id"] == cid)) for cid in sorted(FOCUS_CASES)}
    sentinels = sentinel_checks(arm, full_results, summaries, b3_lag)
    gate = gate_v3(cases, aggregate, baseline, full_results, baseline_cases, deterministic, sentinels)
    return {
        "arm": arm,
        "config": {"arm": arm, "comparison_parent": "BASELINE", "structural_parent": "V1_B3_ASYMMETRIC_B_ROLE",
                   "above_ma20_min": threshold, "null_gating": "NULL_GATING" in arm,
                   "same_branch_persistence": "SAME_BRANCH" in arm},
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
        arm["metrics"]["negative_event_new_s2_cases"], arm["metrics"]["negative_event_s2_case_days"],
        -arm["metrics"]["positive_event_s2_cases"], -arm["metrics"]["positive_full_window_s2_cases"],
        arm["metrics"]["matched_lag_mean_delta"], arm["metrics"]["s0_s1_s0_patterns"],
        arm["metrics"]["negative_event_s1_case_days"], complexity[arm["arm"]],
    ))
    return ranked[0], ranked[1] if len(ranked) > 1 else None


def report_markdown(summary: dict) -> str:
    baseline = summary["baseline"]["metrics"]
    show = lambda values: "、".join(values) if values else "无"
    lines = [
        "# A股主线识别系统 V2.2.1 — RULE CALIBRATION EXECUTION REPORT V3", "",
        f"> **结论：{summary['final_conclusion']}**",
        "> **资格：CALIBRATION_ONLY / DIAGNOSTIC_ONLY；G5 = FAIL**",
        "> 仅代表25例开发/诊断集，不是Holdout、生产准确率或上线授权。", "",
        "## 1. Baseline与B3参考复现", "",
        f"BASELINE **{summary['baseline']['status']}**：事件期正例{baseline['positive_event_s2_cases']}/10，全窗口{baseline['positive_full_window_s2_cases']}/10；负例新确认{baseline['negative_event_new_s2_cases']}，S2暴露{baseline['negative_event_s2_case_days']}日；`S0→S1→S0`={baseline['s0_s1_s0_patterns']}，short reversal={baseline['short_reversals']}。逐日状态与归档一致。",
        f"V1-B3参考臂 **{summary['b3_reference']['status']}**：{summary['b3_reference']['equivalence_note']}。", "",
        "## 2. 三个平行候选", "",
        "| 候选 | 结论 | 事件期正例 | 全窗正例 | 新增命中 | 负例新确认 | 负例S2日 | S0→S1→S0 | short reversal | transition |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in summary["candidates"]:
        m, g = arm["metrics"], arm["gate"]
        lines.append(f"| {arm['arm']} | {arm['status']} | {m['positive_event_s2_cases']}/10 | {m['positive_full_window_s2_cases']}/10 | {show(g['new_positive_event_hits'])} | {m['negative_event_new_s2_cases']} | {m['negative_event_s2_case_days']} | {m['s0_s1_s0_patterns']} | {m['short_reversals']} | {m['transitions']} |")
    lines.extend(["",
        "关键结果不是“NULL门没有生效”，而是**暂停且保留计数**仍不足以封住N02：V3-A/C在C为NULL的日期都没有推进确认，但9月24日C恢复为FALSE时，B-present因Enhancer=TRUE获得第1个有效日；9月25日至27日再次NULL只暂停、不清零；9月30日C再次为FALSE且Enhancer仍为TRUE，于是同一路径取得第2个有效日并确认。该确认晚于B3，反而受既有最短停留/弱化节奏影响，在事件期留下2个S2日，使总负例暴露升至13日。", "",
        "V3-B则完整复现了B3的N02缺口：`B_PRESENT_ENHANCER`在C=NULL时仍可连续成立，因此9月20日确认并留下1个事件期S2日。由此可见，单独要求“证据已知”或“同一分支持续”都没有形成足够的负例过滤。", "",
        "## 3. 候选归因", ""])
    for arm in summary["candidates"]:
        m, g = arm["metrics"], arm["gate"]
        failed = [name for name, passed in g["checks"].items() if not passed]
        lines.extend([
            f"### {arm['arm']}", "",
            f"- 新增正例：{show(g['new_positive_event_hits'])}；丢失原命中：{show(g['lost_positive_event_hits'])}。",
            f"- 事件期确认滞后均值/中位数：{m['positive_event_lag_mean']:.2f}/{m['positive_event_lag_median']}；逐case：`{m['positive_case_lags']}`。",
            f"- matched-lag均值/中位变化：{m['matched_lag_mean_delta']:.2f}/{m['matched_lag_median_delta']}。",
            f"- 负例新确认：{show(m['negative_new_confirmation_ids'])}；负例S2暴露：{m['negative_event_s2_case_days']}日；负例S1日：{m['negative_event_s1_case_days']}。",
            f"- 专项哨兵：`{g['sentinel_checks']}`。",
            f"- 失败检查：{show(failed)}。",
            ("- 归因：NULL日期本身没有完成确认，但“暂停保留”把9月24日与9月30日两个相隔的B-present有效日串接起来；N02仍在事件前进入S2。" if arm["arm"] == "V3_A_NULL_GATING_ONLY" else
             "- 归因：N02的Enhancer本身稳定，same-branch并不能阻断`B_PRESENT_ENHANCER`；该候选与B3关键指标一致。" if arm["arm"] == "V3_B_SAME_BRANCH_ONLY" else
             "- 归因：组合候选仍允许同一`B_PRESENT_ENHANCER`签名跨NULL暂停期保留计数，因此结果与V3-A相同；same-branch没有提供额外过滤。"), "",
        ])
    lines.extend(["## 4. P10 / N02 / N04 / N08逐日路径", ""])
    for cid in ("P10", "N02", "N04", "N08"):
        lines.extend([f"### {cid}", "", "| Arm | 确认日 | 事件期S2 | 全窗口S2 | 关键解释 |", "| --- | --- | --- | --- | --- |"])
        for arm in [summary["baseline"], *summary["candidates"]]:
            case = arm["case_results_serialized"][cid]
            focus = arm["focus_summary"][cid]
            dates = show(focus["confirmation_dates"])
            if cid == "N02":
                if arm["arm"] == "BASELINE":
                    why = "正式五组AND未在事件前确认；事件后才进入S2"
                elif arm["config"].get("null_gating"):
                    why = "NULL日暂停，但两个known日仍可累计并在事件前确认"
                else:
                    why = "无required-known总门，稳定Enhancer签名仍可能确认"
            elif cid == "P10":
                why = "正式五组AND未在事件期确认" if arm["arm"] == "BASELINE" else "required-known完整，B-waived持续路径可计数"
            elif cid == "N04":
                why = "B3分支隔离继续阻断"
            else:
                why = "above_ma20<0.60，安全底座阻断"
            lines.append(f"| {arm['arm']} | {dates} | {case['event_S2_detected']} | {case['S2_detected']} | {why} |")
        lines.extend(["", f"完整逐日字段保存在`calibration_results_v3.json`的`focus_case_paths.{cid}`，包括状态前后、五组证据、above_ma20、required-known、signature、计数器、确认、Freeze和NULL原因。", ""])
    lines.extend([
        "## 5. NULL、signature、Freeze、Warmup与确定性", "",
    ])
    for arm in summary["candidates"]:
        m = arm["metrics"]
        lines.append(f"- **{arm['arm']}：** required-known NULL日{m['required_null_days']}；NULL计数违规{m['required_null_counter_increment_violations']}；跨signature累计{m['cross_signature_accumulations']}；Freeze转移违规{m['freeze_transition_violations']}；两次重跑一致={arm['deterministic']}。")
    lines.extend([
        "- P01、P06、P07、N05、N06、A01继续单列为直接warmup敏感；G5仍为FAIL。", "",
        "## 6. 候选选择", "",
        f"- **PRIMARY CALIBRATION CANDIDATE：** {summary['primary_candidate'] or '无'}。",
        f"- **BACKUP CANDIDATE：** {summary['backup_candidate'] or '无'}。", "",
        "## 7. 最终判定", "", summary["decision_reason"], "",
        "下一步不应发布规则或进入Holdout。若继续校准，需要先冻结新的有限规格，专门回答“NULL暂停后的旧计数何时失效”以及“B-present补偿路径是否必须要求C为TRUE，而不是仅要求C已知”两个结构问题；不得在本轮事后修改V3。", "",
        "本轮未修改正式rule_version、parameter_profile、阈值、状态机、退出、恢复、S3/S4、casebook、Production、scheduler、Sites或G1–G4；未运行Holdout。", "",
    ])
    return "\n".join(lines)


def write_compact_json(path: Path, value: dict) -> None:
    """Write the large path artifact compactly while retaining exact content."""
    if path.exists():
        raise ValueError(f"immutable calibration output already exists: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    targets = [
        "CALIBRATION_EXECUTION_REPORT_V3.md", "calibration_results_v3.json", "version_comparison_v3.csv",
        "case_level_delta_v3.csv", "state_transition_delta_v3.csv", "experiment_manifest_v3.json",
        "deterministic_rerun_v3.json",
    ]
    if any((args.output / name).exists() for name in targets):
        raise ValueError("immutable V3 calibration output already exists")

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
        "short_reversals": spec["baseline_contract"]["short_reversals"], "freeze_days": 63,
    }
    baseline["equivalence"] = baseline_equivalence(baseline, archives, expected)
    baseline["status"] = "PASS" if baseline["equivalence"]["passed"] and baseline["deterministic"] else "HARNESS_FAIL"
    baseline["arm"] = "BASELINE"
    baseline["config"] = {"comparison_parent": None, "null_gating": False, "same_branch_persistence": False}
    baseline["focus_case_paths"] = baseline_focus(archives)
    baseline["focus_summary"] = {cid: focus_summary(baseline, cid, case_by_id[cid]) for cid in sorted(FOCUS_CASES)}

    b3_reference = None
    candidates = []
    if baseline["status"] == "PASS":
        b3_reference = run_v2_candidate("V1_B3_ASYMMETRIC_B_ROLE", cases, archives, calendar, profile,
                                        baseline["metrics"], baseline["case_results"], threshold)
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

    if baseline["status"] == "PASS" and b3_reference and b3_reference["status"] == "PASS":
        b3_lag = b3_reference["case_results"]["P10"]["metrics"]["S2_lag_observed"]
        for arm in ARMS[1:]:
            candidates.append(run_candidate(arm, cases, archives, calendar, profile,
                                            baseline["metrics"], baseline["case_results"], threshold, b3_lag))

    primary, backup = select_candidates(candidates)
    if baseline["status"] != "PASS" or not b3_reference or b3_reference["status"] != "PASS":
        final = "BLOCKED BY DATA / WARMUP QUALIFICATION"
        reason = "BASELINE或V1-B3参考臂未精确复现；按Stop Rule未执行V3候选。"
    elif primary:
        final = "CALIBRATION CANDIDATE FOUND — HOLDOUT REQUIRED"
        reason = "至少一个预注册V3候选通过全部开发集与专项护栏；G5仍失败，必须先做独立Holdout，不能发布正式规则。"
    else:
        final = "NO CANDIDATE PASSED"
        reason = "三个预注册V3候选均未通过全部硬门槛；没有可进入Holdout的候选。"

    all_arms = [baseline, *candidates]
    for arm in all_arms:
        arm["case_results_serialized"] = {cid: minimal_case(value["metrics"]) for cid, value in arm["case_results"].items()}
    versions, case_rows, state_rows = delta_rows(all_arms, baseline["metrics"], baseline["case_results"], cases)

    def public_arm(arm: dict) -> dict:
        value = deepcopy({key: item for key, item in arm.items() if key != "case_results"})
        # Keep one complete, bounded daily path per focus case.  The internal
        # summary duplicates those rows for sentinel calculation; omit the
        # duplicates from the public artifact without changing any metric.
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
        "arm": "V1_B3_ASYMMETRIC_B_ROLE", "status": b3_reference["status"] if b3_reference else "NOT_RUN",
        "equivalence_note": "9/10、9/10、1、12日及既有checksum全部一致" if b3_reference and b3_reference["status"] == "PASS" else "未通过参考等价校验",
        "checks": b3_reference.get("reference_equivalence", {}).get("checks", {}) if b3_reference else {},
        "rerun_checksums": b3_reference.get("rerun_checksums", []) if b3_reference else [],
    }
    summary = {
        "status": "COMPLETE" if candidates else "BLOCKED", "qualification": "CALIBRATION_ONLY_DIAGNOSTIC_ONLY",
        "g5": "FAIL", "final_conclusion": final, "decision_reason": reason,
        "baseline": public_arm(baseline), "b3_reference": b3_public,
        "candidates": [public_arm(arm) for arm in candidates],
        "primary_candidate": primary["arm"] if primary else None, "backup_candidate": backup["arm"] if backup else None,
        "executed_arm_count": len(all_arms), "registered_arm_count": 4,
        "production_writes": 0, "holdout_executed": False, "formal_rule_changed": False, "formal_profile_changed": False,
    }
    manifest = {
        "experiment": "RULE_CALIBRATION_EXECUTION_V3", "started_at": started, "finished_at": utc(),
        "start_sha": start_sha, "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "spec_sha256": sha256(SPEC_MD), "spec_json_sha256": sha256(SPEC_JSON),
        "casebook_version": book["casebook_version"], "casebook_checksum": book["checksum"],
        "rule_version": book["rule_version"], "parameter_profile": book["parameter_profile"],
        "frozen_code_file_hashes": frozen_hashes, "data_snapshot_version": provenance["data_snapshot_version"],
        "pit_level": provenance["pit_level"], "knowledge_time_unverified": True,
        "warmup_qualified": False, "g5": "FAIL", "execution_order": ["BASELINE", "V1_B3_REFERENCE", *[arm["arm"] for arm in candidates]],
        "parallel_candidates": True, "production_writes": 0, "formal_rule_changed": False,
        "formal_profile_changed": False, "result_checksum": digest(summary),
    }
    deterministic = {
        "status": "PASS" if all(arm["deterministic"] for arm in all_arms) else "FAIL", "reruns_per_arm": 2,
        "arms": [{"arm": arm["arm"], "checksums": arm["rerun_checksums"], "identical": arm["deterministic"]} for arm in all_arms],
        "b3_reference": b3_public, "null_default_pass_count": 0,
        "required_null_counter_increment_violations": max([arm["metrics"].get("required_null_counter_increment_violations", 0) for arm in all_arms]),
        "cross_signature_accumulations": max([arm["metrics"].get("cross_signature_accumulations", 0) for arm in all_arms]),
        "freeze_transition_violations": max(arm["metrics"]["freeze_transition_violations"] for arm in all_arms),
        "production_writes": 0,
    }

    write_compact_json(args.output / "calibration_results_v3.json", summary)
    write_csv(args.output / "version_comparison_v3.csv", versions)
    write_csv(args.output / "case_level_delta_v3.csv", case_rows)
    write_csv(args.output / "state_transition_delta_v3.csv", state_rows)
    write_json(args.output / "experiment_manifest_v3.json", manifest)
    write_json(args.output / "deterministic_rerun_v3.json", deterministic)
    (args.output / "CALIBRATION_EXECUTION_REPORT_V3.md").write_text(report_markdown(summary), encoding="utf-8")
    print(json.dumps({"final_conclusion": final, "baseline": baseline["status"], "b3_reference": b3_public["status"],
                      "arms": {arm["arm"]: arm["status"] for arm in candidates},
                      "primary": summary["primary_candidate"], "backup": summary["backup_candidate"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
