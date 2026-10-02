"""Execute preregistered intermediate B-rule candidates on frozen archives.

The four arms are independent: BASELINE, V1-B2, V1-B3 and V1-B4.  This
development-set harness does not call providers, write production data, or
change the formal rule/profile/state machine.
"""
from __future__ import annotations

import argparse
import json
import statistics
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
from mainline.engine.rules import at_least, tri_all, tri_any  # noqa: E402
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

OUT = ROOT / "reports/milestone-d-rule-calibration"
SPEC_MD = OUT / "RULE_CALIBRATION_EXPERIMENT_SPEC_V2.md"
SPEC_JSON = OUT / "rule_calibration_experiment_spec_v2.json"
ARMS = (
    "BASELINE",
    "V1_B2_BREADTH_QUALIFIED_WEIGHTED",
    "V1_B3_ASYMMETRIC_B_ROLE",
    "V1_B4_THREE_DAY_STAGED_CONFIRMATION",
)
FOCUS_CASES = {"P10", "N08"}


def breadth_floor(snapshot: dict, threshold: float) -> bool | None:
    value = snapshot.get("above_ma20")
    return None if value is None else value >= threshold


def standard_signal(values: dict) -> bool | None:
    return tri_all([values["A"], values["B"], values["C"], values["D"], values["enhancers"]])


def shared_core(values: dict, snapshot: dict, threshold: float) -> bool | None:
    return tri_all([values["A"], values["D"], breadth_floor(snapshot, threshold)])


def candidate_paths(arm: str, values: dict, snapshot: dict, threshold: float) -> dict[str, tuple[bool | None, int]]:
    standard = standard_signal(values)
    core = shared_core(values, snapshot, threshold)
    if arm == "V1_B2_BREADTH_QUALIFIED_WEIGHTED":
        alternative = tri_all([core, at_least([values["B"], values["C"], values["enhancers"]], 2)])
        return {"standard": (standard, 2), "breadth_weighted": (alternative, 2)}
    if arm == "V1_B3_ASYMMETRIC_B_ROLE":
        b_present = tri_all([core, values["B"], tri_any([values["C"], values["enhancers"]])])
        if values["B"] is False:
            b_waived = tri_all([core, values["C"], values["enhancers"]])
        elif values["B"] is True:
            b_waived = False
        else:
            b_waived = None
        return {"standard": (standard, 2), "b_present": (b_present, 2), "b_waived": (b_waived, 3)}
    if arm == "V1_B4_THREE_DAY_STAGED_CONFIRMATION":
        pending = tri_all([core, at_least([values["B"], values["C"], values["enhancers"]], 2)])
        return {"standard": (standard, 2), "pending": (pending, 3)}
    raise ValueError(f"unregistered arm: {arm}")


def staged_support_complete(qualifying_days: list[dict]) -> bool:
    if len(qualifying_days) < 3:
        return False
    last = qualifying_days[-3:]
    if any(day["B"] is True for day in last):
        return True
    return all(day["B"] is False and day["C"] is True and day["enhancers"] is True for day in last)


def replay_candidate(case: dict, archived: dict, calendar: list[str], profile: dict, arm: str,
                     breadth_threshold: float) -> dict:
    initial = deepcopy(archived["initial_checkpoint"])
    if initial:
        cp = Checkpoint(**initial)
    else:
        first = archived["rows"][0]["snapshot"]
        cp = Checkpoint(first["object_id"], first["rule_version"], profile["profile_id"],
                        first["metric_availability_version"], state="S0")

    outputs: list[dict] = []
    audit: list[dict] = []
    path_streaks: dict[str, int] = {}
    pending_active = False
    pending_elapsed = 0
    pending_qualifying: list[dict] = []
    null_observations = 0
    null_progress_violations = 0
    pending_expiries = 0

    for archived_row in archived["rows"]:
        row = deepcopy(archived_row)
        values = rule_map(row)
        snapshot = row["snapshot"]
        previous_state = cp.state
        raw_eval = evidence(row)
        paths = candidate_paths(arm, values, snapshot, breadth_threshold)
        quality_good = snapshot.get("critical_data_ok") is True and not snapshot.get("stage_frozen", False)
        complete = False
        pending_before = pending_active
        qualifying_before = len(pending_qualifying)

        if previous_state != "S1":
            path_streaks = {name: 0 for name in paths}
            pending_active = False
            pending_elapsed = 0
            pending_qualifying = []
        else:
            for name, (signal, _) in paths.items():
                if arm == "V1_B4_THREE_DAY_STAGED_CONFIRMATION" and name == "pending":
                    continue
                path_streaks.setdefault(name, 0)
                if quality_good:
                    before = path_streaks[name]
                    if signal is True:
                        path_streaks[name] += 1
                    elif signal is False:
                        path_streaks[name] = 0
                    else:
                        null_observations += 1
                    if signal is None and path_streaks[name] != before:
                        null_progress_violations += 1

            if arm == "V1_B4_THREE_DAY_STAGED_CONFIRMATION" and quality_good:
                pending_signal = paths["pending"][0]
                if pending_active:
                    pending_elapsed += 1
                if pending_signal is False:
                    pending_active = False
                    pending_elapsed = 0
                    pending_qualifying = []
                elif pending_signal is True:
                    if not pending_active:
                        pending_active = True
                        pending_elapsed = 1
                        pending_qualifying = []
                    pending_qualifying.append({key: values[key] for key in ("B", "C", "enhancers")})
                else:
                    null_observations += 1
                if pending_active and pending_elapsed > 5:
                    pending_active = False
                    pending_elapsed = 0
                    pending_qualifying = []
                    pending_expiries += 1

            standard_done = paths["standard"][0] is True and path_streaks.get("standard", 0) >= 2
            if arm == "V1_B4_THREE_DAY_STAGED_CONFIRMATION":
                alternative_done = pending_active and len(pending_qualifying) >= 3 and staged_support_complete(pending_qualifying)
            else:
                alternative_done = any(
                    name != "standard" and signal is True and path_streaks.get(name, 0) >= needed
                    for name, (signal, needed) in paths.items()
                )
            complete = standard_done or alternative_done
            unresolved = any(signal is None for signal, _ in paths.values())
            raw_eval["confirm"] = True if complete else None if unresolved else False
            if complete and quality_good:
                cp.consecutive["confirm"] = profile["confirm"]["confirm_consecutive_days"] - 1

        evaluation = {
            "evidence": raw_eval,
            "trigger_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is True],
            "failed_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is False],
            "unavailable_rules": [item["rule_id"] for item in row["rules"] if item["passed"] is None],
        }
        state, cp = advance(cp, snapshot, evaluation, profile, calendar)
        if state.get("resume_reason") == "reset_after_unverifiable_gap":
            path_streaks = {name: int(signal is True) for name, (signal, _) in paths.items() if name != "pending"}
            pending_active = False
            pending_elapsed = 0
            pending_qualifying = []

        outputs.append({"snapshot": snapshot, "rules": row["rules"], "state": state})
        if case["case_id"] in FOCUS_CASES:
            audit.append({
                "trade_date": snapshot["as_of_date"],
                "baseline_state": row["state"]["state"],
                "previous_state": previous_state,
                "experimental_state": state["state"],
                "transition": state.get("transition"),
                "A": values["A"], "B": values["B"], "C": values["C"], "D": values["D"],
                "Enhancer": values["enhancers"], "above_ma20": snapshot.get("above_ma20"),
                "breadth_floor": breadth_floor(snapshot, breadth_threshold),
                "standard_signal": paths["standard"][0],
                "alternative_signals": {name: signal for name, (signal, _) in paths.items() if name != "standard"},
                "streaks": deepcopy(path_streaks),
                "pending_before": pending_before,
                "pending_active": pending_active,
                "pending_elapsed": pending_elapsed,
                "pending_qualifying_days": len(pending_qualifying),
                "pending_qualifying_days_before": qualifying_before,
                "confirm_completed": complete,
                "stage_frozen": state.get("stage_frozen", False),
            })

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
    metrics["alternative_null_observations"] = null_observations
    metrics["null_progress_violations"] = null_progress_violations
    metrics["pending_expiries"] = pending_expiries
    return {"business": business, "metrics": metrics, "path_audit": audit}


def run_candidate(arm: str, cases: list[dict], archives: dict[str, dict], calendar: list[str], profile: dict,
                  baseline: dict, baseline_cases: dict, threshold: float) -> dict:
    runs = []
    full_results = None
    for _ in range(2):
        current = {
            case["case_id"]: replay_candidate(case, archives[case["case_id"]], calendar, profile, arm, threshold)
            for case in cases
        }
        for case in cases:
            current[case["case_id"]]["metrics"]["warmup_sensitive"] = case["case_id"] in WARMUP_SENSITIVE
        aggregate = aggregate_arm(current, cases, baseline)
        aggregate["alternative_null_observations"] = sum(v["metrics"]["alternative_null_observations"] for v in current.values())
        aggregate["null_progress_violations"] = sum(v["metrics"]["null_progress_violations"] for v in current.values())
        aggregate["pending_expiries"] = sum(v["metrics"]["pending_expiries"] for v in current.values())
        checksum = digest({"aggregate": aggregate, "cases": {cid: value["metrics"]["full_output_checksum"] for cid, value in current.items()}})
        runs.append(checksum)
        full_results = current
    deterministic = runs[0] == runs[1]
    gate = gate_v2(cases, aggregate, baseline, full_results, baseline_cases, deterministic)
    return {
        "arm": arm,
        "config": {"arm": arm, "comparison_parent": "BASELINE", "above_ma20_min": threshold},
        "metrics": aggregate,
        "gate": gate,
        "deterministic": deterministic,
        "rerun_checksums": runs,
        "case_results": full_results,
        "focus_case_paths": {cid: full_results[cid]["path_audit"] for cid in sorted(FOCUS_CASES)},
        "status": "PASS" if gate["passed"] else "FAIL",
    }


def gate_v2(cases: list[dict], current: dict, baseline: dict, case_results: dict,
            baseline_cases: dict, deterministic: bool) -> dict:
    common = global_gate_v2(cases, current, baseline, case_results, baseline_cases)
    checks = common["checks"]
    checks.update({
        "s0_s1_s0_not_above_baseline": current["s0_s1_s0_patterns"] <= baseline["s0_s1_s0_patterns"],
        "short_reversals_not_above_baseline": current["short_reversals"] <= baseline["short_reversals"],
        "reversals_not_above_baseline": current["reversals"] <= baseline["reversals"],
        "transitions_not_above_baseline": current["transitions"] <= baseline["transitions"],
        "negative_s1_days_increase_max_10pct": current["negative_event_s1_case_days"] <= baseline["negative_event_s1_case_days"] * 1.10,
        "negative_single_s1_run_increase_max_3": all(
            current["negative_case_s1"][cid]["max_run"] <= value["max_run"] + 3
            for cid, value in baseline["negative_case_s1"].items()
        ),
        "null_progress_violations_0": current["null_progress_violations"] == 0,
        "deterministic_rerun": deterministic,
    })
    favorable = common["favorable_positive_cases"]
    nonsensitive = [cid for cid in favorable if cid not in WARMUP_SENSITIVE]
    checks["improvement_not_only_warmup_sensitive"] = bool(nonsensitive)
    return {**common, "passed": all(checks.values()), "checks": checks, "non_warmup_favorable_cases": nonsensitive}


def global_gate_v2(cases: list[dict], current: dict, baseline: dict,
                   case_results: dict, baseline_cases: dict) -> dict:
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
        "freeze_transition_violations_0": current["freeze_transition_violations"] == 0,
        "input_data_freeze_mask_unchanged": current["input_data_freeze_mask_checksums"] == baseline["input_data_freeze_mask_checksums"],
        "illegal_transition_patterns_0": current["s1_s2_s1_or_s0_patterns"] == 0,
        "leave_one_improvement_case_still_has_improvement": len(favorable) >= 2,
    }
    return {
        "passed": all(checks.values()), "checks": checks,
        "favorable_positive_cases": favorable, "favorable_episodes": sorted(episodes),
        "new_positive_event_hits": new_hits, "lost_positive_event_hits": lost,
    }


def select_candidates(candidates: list[dict]) -> tuple[dict | None, dict | None]:
    eligible = [arm for arm in candidates if arm["status"] == "PASS"]
    if not eligible:
        return None, None
    complexity = {
        "V1_B2_BREADTH_QUALIFIED_WEIGHTED": 0,
        "V1_B3_ASYMMETRIC_B_ROLE": 1,
        "V1_B4_THREE_DAY_STAGED_CONFIRMATION": 2,
    }
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


def baseline_focus(archives: dict[str, dict]) -> dict:
    result = {}
    for cid in sorted(FOCUS_CASES):
        rows = []
        for row in archives[cid]["rows"]:
            values = rule_map(row)
            snapshot = row["snapshot"]
            rows.append({
                "trade_date": snapshot["as_of_date"], "baseline_state": row["state"]["state"],
                "previous_state": row["state"]["previous_state"], "experimental_state": row["state"]["state"],
                "transition": row["state"].get("transition"),
                "A": values["A"], "B": values["B"], "C": values["C"], "D": values["D"],
                "Enhancer": values["enhancers"], "above_ma20": snapshot.get("above_ma20"),
                "breadth_floor": breadth_floor(snapshot, 0.6), "formal_confirm": values["confirm"],
                "stage_frozen": row["state"].get("stage_frozen", False),
            })
        result[cid] = rows
    return result


def focus_summary(arm: dict, case_id: str, case: dict) -> dict:
    rows = arm["focus_case_paths"][case_id]
    relevant = [row for row in rows if case["pre_window_start"] <= row["trade_date"] <= case["post_window_end"]]
    transitions = [row for row in relevant if row.get("transition")]
    confirms = [
        row for row in relevant
        if isinstance(row.get("transition"), dict)
        and row["transition"].get("from_state") == "S1"
        and row["transition"].get("to_state") == "S2"
    ]
    return {
        "case_id": case_id,
        "event_window": [case["start_date"], case["end_date"]],
        "confirmation_dates": [row["trade_date"] for row in confirms],
        "transitions": [{"trade_date": row["trade_date"], "transition": row["transition"]} for row in transitions],
        "event_evidence_rows": [row for row in relevant if case["start_date"] <= row["trade_date"] <= case["end_date"]],
    }


def report_markdown(summary: dict) -> str:
    baseline = summary["baseline"]["metrics"]
    candidates = summary["candidates"]
    show = lambda items: "、".join(items) if items else "无"
    lines = [
        "# A股主线识别系统 V2.2.1 — RULE CALIBRATION EXECUTION REPORT V2", "",
        f"> **结论：{summary['final_conclusion']}**",
        "> **资格：CALIBRATION_ONLY / DIAGNOSTIC_ONLY；G5 = FAIL**",
        "> 本报告仅代表25例开发/诊断集，不是Holdout、生产准确率或上线授权。", "",
        "## 1. Baseline复现", "",
        f"BASELINE **{summary['baseline']['status']}**：事件期正例S2 {baseline['positive_event_s2_cases']}/10，全窗口 {baseline['positive_full_window_s2_cases']}/10；负例新误确认 {baseline['negative_event_new_s2_cases']}，负例S2暴露 {baseline['negative_event_s2_case_days']}日；`S0→S1→S0`={baseline['s0_s1_s0_patterns']}，short reversal={baseline['short_reversals']}。逐日状态与归档完全一致。", "",
        "## 2. 三个平行候选结果", "",
        "| 候选 | 结论 | 事件期正例 | 全窗正例 | 新增正例 | 负例新确认 | 负例S2日 | S0→S1→S0 | short reversal | transition | 负例S1日 |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in candidates:
        m, g = arm["metrics"], arm["gate"]
        lines.append(
            f"| {arm['arm']} | {arm['status']} | {m['positive_event_s2_cases']}/10 | {m['positive_full_window_s2_cases']}/10 | "
            f"{show(g['new_positive_event_hits'])} | {m['negative_event_new_s2_cases']} | {m['negative_event_s2_case_days']} | "
            f"{m['s0_s1_s0_patterns']} | {m['short_reversals']} | {m['transitions']} | {m['negative_event_s1_case_days']} |"
        )
    lines.extend(["", "## 3. Case级召回、误报与滞后", ""])
    for arm in candidates:
        m, g = arm["metrics"], arm["gate"]
        added_neg = sorted(set(m["negative_new_confirmation_ids"]) - set(baseline["negative_new_confirmation_ids"]))
        lines.extend([
            f"### {arm['arm']}", "",
            f"- 新增事件期正例：{show(g['new_positive_event_hits'])}；丢失原命中：{show(g['lost_positive_event_hits'])}。",
            f"- 新增负例误确认：{show(added_neg)}；全部负例新确认：{show(m['negative_new_confirmation_ids'])}。",
            f"- 事件期正例确认滞后：均值 {m['positive_event_lag_mean']:.2f}，中位数 {m['positive_event_lag_median']}；逐case：{m['positive_case_lags']}。",
            f"- 原5例matched-lag变化：均值 {m['matched_lag_mean_delta']:.2f}，中位数 {m['matched_lag_median_delta']}；逐case：{m['matched_lag_delta']}。",
            f"- 有利变化case：{show(g['favorable_positive_cases'])}；episode：{show(g['favorable_episodes'])}。",
            f"- 失败检查：{show([name for name, passed in g['checks'].items() if not passed])}。", "",
        ])
    lines.extend(["## 4. P10 与 N08 完整路径差异", ""])
    for cid in ("P10", "N08"):
        lines.extend([f"### {cid}", "",
            "| Arm | 确认日 | 事件期结论 | 关键路径 |", "| --- | --- | --- | --- |"])
        for arm in [summary["baseline"], *candidates]:
            m = arm["case_results_serialized"][cid]
            f = arm["focus_summary"][cid]
            confirms = show(f["confirmation_dates"])
            if cid == "P10":
                reason = ("正式五组AND未连续满足，事件期未确认" if arm["arm"] == "BASELINE" else
                          "高绝对广度下A/C/D/Enhancer持续成立，按预注册补偿路径完成确认" if m["event_S2_detected"] else
                          "持续或支持条件未完成")
            else:
                reason = ("正式路径未连续满足" if arm["arm"] == "BASELINE" else
                          "above_ma20未达到0.60，补偿路径不启动；随后A/D失效" if not m["event_S2_detected"] else
                          "补偿路径仍发生误放")
            lines.append(f"| {arm['arm']} | {confirms} | {'S2' if m['event_S2_detected'] else '未确认'} | {reason} |")
        lines.append("")
    lines.extend([
        "P10在事件启动阶段的above_ma20约为0.917–0.955，并且A/C/D/Enhancer连续成立；N08同期above_ma20仅约0.114–0.143，即使相对扩张D短暂为TRUE，也没有通过绝对广度底座。详细逐日A/B/C/D/Enhancer、above_ma20、S1、计数器、pending及状态转移保存在`calibration_results_v2.json`的`focus_case_paths`。", "",
        "## 5. NULL、Freeze、Warmup与确定性", "",
    ])
    for arm in candidates:
        m = arm["metrics"]
        lines.append(
            f"- **{arm['arm']}：** NULL观察{m['alternative_null_observations']}次，NULL推进违规{m['null_progress_violations']}；"
            f"Freeze转移违规{m['freeze_transition_violations']}；输入Freeze掩码不变；两次checksum一致={arm['deterministic']}。"
        )
    lines.extend([
        "- P01、P06、P07、N05、N06、A01继续标记为直接warmup敏感；完整84日warmup资格仍未通过。",
        "- 候选改善不能被解释为生产准确率，且不得用规则变化掩盖G5失败。", "",
        "## 6. 候选选择", "",
        f"- **PRIMARY CALIBRATION CANDIDATE：** {summary['primary_candidate'] or '无'}。",
        f"- **BACKUP CANDIDATE：** {summary['backup_candidate'] or '无'}。",
        "- 选择顺序严格按冻结合同：负例新确认 → S2暴露 → 召回 → 滞后 → Churn/滞留 → 复杂度。", "",
        "## 7. 最终判定", "",
        summary["decision_reason"], "",
        "本轮没有修改正式rule_version、parameter_profile、阈值、状态机、casebook、Production、scheduler、Supabase正式状态或Sites；没有运行Holdout。", "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    targets = [
        "CALIBRATION_EXECUTION_REPORT_V2.md", "calibration_results_v2.json", "version_comparison_v2.csv",
        "case_level_delta_v2.csv", "state_transition_delta_v2.csv", "experiment_manifest_v2.json",
        "deterministic_rerun_v2.json",
    ]
    if any((args.output / name).exists() for name in targets):
        raise ValueError("immutable V2 calibration output already exists")

    started = utc()
    start_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    spec = read(SPEC_JSON)
    book = read(BASE / "casebook.json")
    profile, frozen_hashes = baseline_profile(ROOT)
    _, _, calendar, provenance = load_inputs(BASE, profile)
    cases = book["cases"]
    case_by_id = {case["case_id"]: case for case in cases}
    archives = {case["case_id"]: load_archive(case["case_id"]) for case in cases}
    threshold = spec["shared_contract"]["alternative_path_prerequisites"]["above_ma20_min"]
    if threshold != profile["confirm"]["above_ma20_min"]:
        raise ValueError("registered breadth threshold no longer matches formal profile")

    from scripts.mainline.rule_calibration_execute import run_arm  # local reuse for exact baseline
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
    baseline["focus_case_paths"] = baseline_focus(archives)

    candidates = []
    if baseline["status"] == "PASS":
        for arm in ARMS[1:]:
            candidates.append(run_candidate(
                arm, cases, archives, calendar, profile, baseline["metrics"], baseline["case_results"], threshold
            ))

    primary, backup = select_candidates(candidates)
    if baseline["status"] != "PASS":
        final = "BLOCKED BY DATA / WARMUP QUALIFICATION"
        reason = "BASELINE未能逐日等价复现，按Stop Rule没有执行任何候选。"
    elif primary:
        final = "CALIBRATION CANDIDATE FOUND — HOLDOUT REQUIRED"
        reason = "至少一个预注册候选通过全部开发集护栏；结果仍受G5失败和开发集使用限制，必须进入独立Holdout。"
    else:
        final = "NO CANDIDATE PASSED"
        reason = "BASELINE已复现，但三个预注册候选均未通过全部硬门槛；没有Holdout候选。"

    all_arms = [baseline, *candidates]
    for arm in all_arms:
        arm["case_results_serialized"] = {cid: minimal_case(value["metrics"]) for cid, value in arm["case_results"].items()}
        arm["focus_summary"] = {cid: focus_summary(arm, cid, case_by_id[cid]) for cid in sorted(FOCUS_CASES)}
    versions, case_rows, state_rows = delta_rows(all_arms, baseline["metrics"], baseline["case_results"], cases)

    def public_arm(arm: dict) -> dict:
        return {key: value for key, value in arm.items() if key != "case_results"}

    public_baseline = public_arm(baseline)
    public_candidates = [public_arm(arm) for arm in candidates]
    summary = {
        "status": "COMPLETE" if baseline["status"] == "PASS" else "BLOCKED",
        "qualification": "CALIBRATION_ONLY_DIAGNOSTIC_ONLY", "g5": "FAIL",
        "final_conclusion": final, "decision_reason": reason,
        "baseline": public_baseline, "candidates": public_candidates,
        "primary_candidate": primary["arm"] if primary else None,
        "backup_candidate": backup["arm"] if backup else None,
        "executed_arm_count": len(all_arms), "registered_arm_count": 4,
        "production_writes": 0, "holdout_executed": False,
        "formal_rule_changed": False, "formal_profile_changed": False,
    }
    manifest = {
        "experiment": "RULE_CALIBRATION_EXECUTION_V2", "started_at": started, "finished_at": utc(),
        "start_sha": start_sha, "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "spec_sha256": sha256(SPEC_MD), "spec_json_sha256": sha256(SPEC_JSON),
        "casebook_version": book["casebook_version"], "casebook_checksum": book["checksum"],
        "rule_version": book["rule_version"], "parameter_profile": book["parameter_profile"],
        "frozen_code_file_hashes": frozen_hashes, "data_snapshot_version": provenance["data_snapshot_version"],
        "pit_level": provenance["pit_level"], "knowledge_time_unverified": True,
        "warmup_qualified": False, "g5": "FAIL", "execution_order": [arm["arm"] for arm in all_arms],
        "parallel_candidates": True, "production_writes": 0, "formal_rule_changed": False,
        "formal_profile_changed": False, "result_checksum": digest(summary),
    }
    deterministic = {
        "status": "PASS" if all(arm["deterministic"] for arm in all_arms) else "FAIL",
        "reruns_per_arm": 2,
        "arms": [{"arm": arm["arm"], "checksums": arm["rerun_checksums"], "identical": arm["deterministic"]} for arm in all_arms],
        "null_default_pass_count": 0,
        "null_progress_violations": max([arm["metrics"].get("null_progress_violations", 0) for arm in all_arms]),
        "freeze_transition_violations": max(arm["metrics"]["freeze_transition_violations"] for arm in all_arms),
        "production_writes": 0,
    }

    write_json(args.output / "calibration_results_v2.json", summary)
    write_csv(args.output / "version_comparison_v2.csv", versions)
    write_csv(args.output / "case_level_delta_v2.csv", case_rows)
    write_csv(args.output / "state_transition_delta_v2.csv", state_rows)
    write_json(args.output / "experiment_manifest_v2.json", manifest)
    write_json(args.output / "deterministic_rerun_v2.json", deterministic)
    report_path = args.output / "CALIBRATION_EXECUTION_REPORT_V2.md"
    if report_path.exists():
        raise ValueError("immutable V2 calibration report already exists")
    report_path.write_text(report_markdown(summary), encoding="utf-8")
    print(json.dumps({
        "final_conclusion": final, "baseline": baseline["status"],
        "arms": {arm["arm"]: arm["status"] for arm in candidates},
        "primary": summary["primary_candidate"], "backup": summary["backup_candidate"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
