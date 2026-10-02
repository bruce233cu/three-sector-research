"""Independent contract checks for RULE CALIBRATION EXECUTION V2 artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/milestone-d-rule-calibration"
EXPECTED_ARMS = [
    "BASELINE",
    "V1_B2_BREADTH_QUALIFIED_WEIGHTED",
    "V1_B3_ASYMMETRIC_B_ROLE",
    "V1_B4_THREE_DAY_STAGED_CONFIRMATION",
]
ALLOWED_CONCLUSIONS = {
    "NO CANDIDATE PASSED",
    "CALIBRATION CANDIDATE FOUND — HOLDOUT REQUIRED",
    "BLOCKED BY DATA / WARMUP QUALIFICATION",
}


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    result = load("calibration_results_v2.json")
    manifest = load("experiment_manifest_v2.json")
    rerun = load("deterministic_rerun_v2.json")
    prior_manifest = load("experiment_manifest.json")
    spec = load("rule_calibration_experiment_spec_v2.json")
    baseline = result["baseline"]
    candidates = result["candidates"]
    arms = [baseline["arm"], *[arm["arm"] for arm in candidates]]

    checks = {
        "allowed_final_conclusion": result["final_conclusion"] in ALLOWED_CONCLUSIONS,
        "all_registered_arms_executed_in_order": arms == EXPECTED_ARMS,
        "candidates_are_parallel_to_baseline": all(arm["config"]["comparison_parent"] == "BASELINE" for arm in candidates),
        "baseline_equivalence_passed": baseline["status"] == "PASS" and baseline["equivalence"]["passed"],
        "baseline_positive_event_5": baseline["metrics"]["positive_event_s2_cases"] == 5,
        "baseline_positive_full_6": baseline["metrics"]["positive_full_window_s2_cases"] == 6,
        "baseline_negative_new_1": baseline["metrics"]["negative_event_new_s2_cases"] == 1,
        "baseline_negative_exposure_11": baseline["metrics"]["negative_event_s2_case_days"] == 11,
        "baseline_s0_s1_s0_117": baseline["metrics"]["s0_s1_s0_patterns"] == 117,
        "baseline_short_reversal_174": baseline["metrics"]["short_reversals"] == 174,
        "all_candidate_gates_present": all(arm.get("gate") and isinstance(arm["gate"]["checks"], dict) for arm in candidates),
        "status_matches_gate": all((arm["status"] == "PASS") == arm["gate"]["passed"] for arm in candidates),
        "deterministic_all_arms": rerun["status"] == "PASS" and all(item["identical"] for item in rerun["arms"]),
        "null_never_advances": rerun["null_progress_violations"] == 0,
        "freeze_never_transitions": rerun["freeze_transition_violations"] == 0,
        "no_production_writes": manifest["production_writes"] == 0 and result["production_writes"] == 0,
        "formal_rule_unchanged": not manifest["formal_rule_changed"] and not result["formal_rule_changed"],
        "formal_profile_unchanged": not manifest["formal_profile_changed"] and not result["formal_profile_changed"],
        "production_hashes_unchanged_from_v1": manifest["frozen_code_file_hashes"] == prior_manifest["frozen_code_file_hashes"],
        "spec_hash_matches": manifest["spec_sha256"] == sha256(OUT / "RULE_CALIBRATION_EXPERIMENT_SPEC_V2.md"),
        "spec_json_hash_matches": manifest["spec_json_sha256"] == sha256(OUT / "rule_calibration_experiment_spec_v2.json"),
        "g5_remains_fail": result["g5"] == "FAIL" and manifest["g5"] == "FAIL",
        "holdout_not_executed": result["holdout_executed"] is False,
        "p10_n08_paths_present": all(
            cid in arm["focus_case_paths"] and arm["focus_case_paths"][cid]
            for arm in [baseline, *candidates] for cid in ("P10", "N08")
        ),
        "breadth_threshold_reused": all(
            arm["config"]["above_ma20_min"] == spec["shared_contract"]["alternative_path_prerequisites"]["above_ma20_min"]
            for arm in candidates
        ),
    }

    primary = result["primary_candidate"]
    passed = [arm["arm"] for arm in candidates if arm["status"] == "PASS"]
    checks["candidate_selection_consistent"] = (primary in passed if passed else primary is None)
    checks["conclusion_consistent"] = (
        (result["final_conclusion"].startswith("CALIBRATION CANDIDATE") and bool(passed))
        or (result["final_conclusion"] == "NO CANDIDATE PASSED" and not passed)
        or (result["final_conclusion"].startswith("BLOCKED") and baseline["status"] != "PASS")
    )

    with (OUT / "version_comparison_v2.csv").open(newline="", encoding="utf-8") as stream:
        version_rows = list(csv.DictReader(stream))
    with (OUT / "case_level_delta_v2.csv").open(newline="", encoding="utf-8") as stream:
        case_rows = list(csv.DictReader(stream))
    with (OUT / "state_transition_delta_v2.csv").open(newline="", encoding="utf-8") as stream:
        state_rows = list(csv.DictReader(stream))
    checks.update({
        "version_csv_has_4_rows": len(version_rows) == 4,
        "case_delta_has_100_rows": len(case_rows) == 100,
        "state_delta_has_4_rows": len(state_rows) == 4,
        "csv_arm_order_matches": [row["version"] for row in version_rows] == EXPECTED_ARMS,
        "report_exists": (OUT / "CALIBRATION_EXECUTION_REPORT_V2.md").is_file(),
    })

    failures = [name for name, passed_check in checks.items() if not passed_check]
    print(json.dumps({"status": "PASS" if not failures else "FAIL", "checks": checks, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
