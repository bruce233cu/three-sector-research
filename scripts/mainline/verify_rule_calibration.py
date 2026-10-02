"""Independent closeout checks for the frozen calibration execution outputs."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/milestone-d-rule-calibration"
SPEC = ROOT / "reports/milestone-d-rule-diagnostic"


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(name: str) -> list[dict]:
    with (OUT / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    result = load("calibration_results.json")
    manifest = load("experiment_manifest.json")
    rerun = load("deterministic_rerun.json")
    baseline = result["baseline"]
    v1 = {arm["arm"]: arm for arm in result["layers"]["V1"]["arms"]}
    b = v1["V1_B_TIERED_EXCEPTION"]
    c = v1["V1_C_CORE_PLUS_SUPPORT"]
    checks = {
        "spec_markdown_checksum": manifest["spec_sha256"] == sha(SPEC / "RULE_CALIBRATION_EXPERIMENT_SPEC.md"),
        "spec_json_checksum": manifest["spec_json_sha256"] == sha(SPEC / "rule_calibration_experiment_spec.json"),
        "baseline_equivalence": baseline["equivalence"]["passed"] and not baseline["equivalence"]["mismatched_cases"],
        "baseline_headline": (baseline["metrics"]["positive_event_s2_cases"], baseline["metrics"]["positive_full_window_s2_cases"], baseline["metrics"]["negative_event_new_s2_cases"], baseline["metrics"]["negative_event_s2_case_days"]) == (5, 6, 1, 11),
        "baseline_state_metrics": (baseline["metrics"]["s0_s1_s0_patterns"], baseline["metrics"]["transitions"], baseline["metrics"]["reversals"], baseline["metrics"]["short_reversals"]) == (117, 341, 276, 174),
        "v1_control_equivalent": v1["V1_A_HARD_CONTROL"]["status"] == "CONTROL_PASS" and v1["V1_A_HARD_CONTROL"]["control_equivalent"],
        "v1_b_failed_preregistered_gates": b["status"] == "FAIL" and b["metrics"]["positive_full_window_s2_cases"] == 6 and b["gate"]["favorable_positive_cases"] == ["P10"],
        "v1_c_failed_negative_guardrails": c["status"] == "FAIL" and c["metrics"]["negative_event_new_s2_cases"] == 2 and c["metrics"]["negative_event_s2_case_days"] == 19,
        "stop_rule_honored": all(not result["layers"][layer]["arms"] for layer in ("V2", "V3", "V4")) and manifest["execution_order"] == ["BASELINE", "V1_A_HARD_CONTROL", "V1_B_TIERED_EXCEPTION", "V1_C_CORE_PLUS_SUPPORT"],
        "final_conclusion_allowed": result["final_conclusion"] == "NO CANDIDATE PASSED",
        "deterministic_rerun": rerun["status"] == "PASS" and all(item["identical"] and len(set(item["checksums"])) == 1 for item in rerun["arms"]),
        "null_and_freeze_contract": rerun["null_default_pass_count"] == 0 and rerun["freeze_transition_violations"] == 0 and b["gate"]["checks"]["input_data_freeze_mask_unchanged"] and c["gate"]["checks"]["input_data_freeze_mask_unchanged"],
        "csv_row_counts": len(rows("version_comparison.csv")) == 4 and len(rows("case_level_delta.csv")) == 100 and len(rows("state_transition_delta.csv")) == 4,
        "production_isolation": manifest["production_writes"] == 0 and not manifest["formal_rule_changed"] and not manifest["formal_profile_changed"],
        "qualification_preserved": result["qualification"] == "CALIBRATION_ONLY_DIAGNOSTIC_ONLY" and result["g5"] == "FAIL" and not result["holdout_executed"],
    }
    output = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
              "failed_checks": [name for name, passed in checks.items() if not passed],
              "scope": "independent artifact and frozen-gate verification; no experiment rerun", "production_writes": 0}
    target = OUT / "validation_checks.json"
    if target.exists():
        raise ValueError("immutable validation output already exists")
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if output["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
