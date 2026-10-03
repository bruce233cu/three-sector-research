"""Independent contract checks for final bounded RULE CALIBRATION EXECUTION V4."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/milestone-d-rule-calibration"
EXPECTED_ARMS = [
    "BASELINE",
    "V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY",
    "V4_B_B_PRESENT_REQUIRES_C_TRUE",
    "V4_C_COMBINED",
]
FOCUS = {"P10", "N02", "N04", "N08"}
PATH_FIELDS = {
    "trade_date", "state_before", "state_after", "A", "B", "C", "D", "Enhancer",
    "above_ma20", "required_known_ok", "evidence_signature", "eligible_evidence_signature",
    "confirm_counter_before", "confirm_counter_after", "confirm_chain_reset",
    "confirm_triggered", "freeze", "null_reason",
}
ALLOWED = {
    "CALIBRATION CANDIDATE FOUND — HOLDOUT REQUIRED",
    "NO CANDIDATE PASSED — DEVELOPMENT SET CALIBRATION STOPPED",
    "BLOCKED BY DATA / BASELINE DRIFT",
}


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    result = load("calibration_results_v4.json")
    manifest = load("experiment_manifest_v4.json")
    rerun = load("deterministic_rerun_v4.json")
    decision = load("final_bounded_calibration_decision.json")
    spec = load("rule_calibration_experiment_spec_v4.json")
    v3_manifest = load("experiment_manifest_v3.json")
    baseline = result["baseline"]
    candidates = result["candidates"]
    arms = [baseline["arm"], *[arm["arm"] for arm in candidates]]
    checks = {
        "allowed_final_conclusion": result["final_conclusion"] in ALLOWED,
        "all_registered_arms_executed_in_order": arms == EXPECTED_ARMS,
        "parallel_to_baseline": all(arm["config"]["comparison_parent"] == "BASELINE" for arm in candidates),
        "common_structural_parent": all(
            arm["config"]["structural_parent"] == "V1_B3_WITH_SAME_BRANCH_AND_REQUIRED_KNOWN"
            for arm in candidates
        ),
        "baseline_equivalence": baseline["status"] == "PASS" and baseline["equivalence"]["passed"],
        "baseline_5_6_1_11": (
            baseline["metrics"]["positive_event_s2_cases"],
            baseline["metrics"]["positive_full_window_s2_cases"],
            baseline["metrics"]["negative_event_new_s2_cases"],
            baseline["metrics"]["negative_event_s2_case_days"],
        ) == (5, 6, 1, 11),
        "baseline_churn_117_174": (
            baseline["metrics"]["s0_s1_s0_patterns"], baseline["metrics"]["short_reversals"],
        ) == (117, 174),
        "b3_reference_equivalence": result["b3_reference"]["status"] == "PASS"
                                        and all(result["b3_reference"]["checks"].values()),
        "v3_archive_verified_without_rerun": result["v3_archive_verification"]["status"] == "PASS"
                                               and result["v3_archive_verification"]["v3_rerun_executed"] is False,
        "candidate_gates_present": all(isinstance(arm.get("gate", {}).get("checks"), dict) for arm in candidates),
        "status_matches_gate": all((arm["status"] == "PASS") == arm["gate"]["passed"] for arm in candidates),
        "candidate_contract_flags": [
            (arm["config"]["null_breaks_continuity"], arm["config"]["b_present_requires_c_true"])
            for arm in candidates
        ] == [(True, False), (False, True), (True, True)],
        "same_branch_all": all(arm["config"]["same_branch_persistence"] for arm in candidates),
        "threshold_unchanged": all(arm["config"]["above_ma20_min"] == 0.60 for arm in candidates),
        "all_focus_paths_present": all(FOCUS <= set(arm["focus_case_paths"]) for arm in [baseline, *candidates]),
        "focus_path_schema_complete": all(
            rows and all(PATH_FIELDS <= set(row) for row in rows)
            for arm in [baseline, *candidates] for rows in arm["focus_case_paths"].values()
        ),
        "all_specialized_sentinels_present": all(
            all(name in arm["gate"]["sentinel_checks"] for name in (
                "p10_event_hit", "n02_no_confirm_when_c_null", "n02_event_s2_exposure_0",
                "n04_full_window_no_s2", "n08_full_window_no_s2",
            )) for arm in candidates
        ),
        "deterministic_all": rerun["status"] == "PASS" and all(item["identical"] for item in rerun["arms"]),
        "null_counter_integrity": rerun["null_counter_retention_violations"] == 0,
        "recovery_counter_integrity": rerun["recovery_first_day_counter_violations"] == 0,
        "c_integrity": rerun["b_present_c_integrity_violations"] == 0,
        "signature_integrity": rerun["cross_signature_accumulations"] == 0,
        "freeze_integrity": rerun["freeze_transition_violations"] == 0,
        "no_production_writes": manifest["production_writes"] == result["production_writes"] == 0,
        "formal_rule_unchanged": not manifest["formal_rule_changed"] and not result["formal_rule_changed"],
        "formal_profile_unchanged": not manifest["formal_profile_changed"] and not result["formal_profile_changed"],
        "frozen_hashes_unchanged_from_v3": manifest["frozen_code_file_hashes"] == v3_manifest["frozen_code_file_hashes"],
        "spec_hash_matches": manifest["spec_sha256"] == sha256(OUT / "RULE_CALIBRATION_EXPERIMENT_SPEC_V4.md"),
        "spec_json_hash_matches": manifest["spec_json_sha256"] == sha256(OUT / "rule_calibration_experiment_spec_v4.json"),
        "g5_remains_fail": result["g5"] == manifest["g5"] == "FAIL",
        "holdout_not_executed": result["holdout_executed"] is False and manifest["holdout_executed"] is False,
        "registered_candidate_count_3": len(spec["candidates"]) == len(candidates) == 3,
        "v1_v2_v3_not_rerun": manifest["v1_v2_v3_rerun"] is False,
        "v5_v6_forbidden": decision["v5_v6_allowed_on_current_25_cases"] is False,
        "formal_publish_forbidden": decision["formal_rule_publish_allowed"] is False,
    }
    passed = [arm["arm"] for arm in candidates if arm["status"] == "PASS"]
    checks["candidate_selection_consistent"] = result["primary_candidate"] in passed if passed else result["primary_candidate"] is None
    checks["conclusion_consistent"] = (
        result["final_conclusion"].startswith("CALIBRATION CANDIDATE") and bool(passed)
        or result["final_conclusion"].startswith("NO CANDIDATE PASSED") and not passed
        or result["final_conclusion"].startswith("BLOCKED") and baseline["status"] != "PASS"
    )
    checks["decision_matches_result"] = decision["decision"] == result["final_conclusion"]
    with (OUT / "version_comparison_v4.csv").open(newline="", encoding="utf-8") as stream:
        versions = list(csv.DictReader(stream))
    with (OUT / "case_level_delta_v4.csv").open(newline="", encoding="utf-8") as stream:
        cases = list(csv.DictReader(stream))
    with (OUT / "state_transition_delta_v4.csv").open(newline="", encoding="utf-8") as stream:
        states = list(csv.DictReader(stream))
    checks.update({
        "version_csv_4_rows": len(versions) == 4,
        "case_csv_100_rows": len(cases) == 100,
        "state_csv_4_rows": len(states) == 4,
        "csv_order": [row["version"] for row in versions] == EXPECTED_ARMS,
        "report_exists": (OUT / "CALIBRATION_EXECUTION_REPORT_V4.md").is_file(),
    })
    failures = [name for name, passed_check in checks.items() if not passed_check]
    print(json.dumps({
        "status": "PASS" if not failures else "FAIL",
        "checks": checks, "failures": failures,
    }, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
