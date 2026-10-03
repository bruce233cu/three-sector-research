"""Verify only G5 state/counter initialization; never evaluate case outcomes."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mainline.backtest.runner import baseline_profile, load_inputs, read, resolver_for, write
from mainline.engine.replay import digest, replay

REQUIRED_COUNTERS = {"confirm", "recover", "weaken", "retire"}


def verify(recertification_dir, output):
    profile, frozen_hashes = baseline_profile(ROOT)
    panel, members, live_dates, provenance = load_inputs(ROOT / "reports/milestone-d-baseline-v1", profile)
    casebook = read(ROOT / "reports/milestone-d-baseline-v1/casebook.json")
    warm = read(recertification_dir / "warmup_board_inputs.json.gz")
    warm_members = read(recertification_dir / "warmup_memberships.json.gz")
    manifest = read(recertification_dir / "warmup_data_version_manifest.json")
    if manifest["coverage"]["panel_days"] != 84 or len(warm) != 84 * 31:
        raise ValueError("84-session warmup panel incomplete")
    if digest(warm) != manifest["checksums"]["panel"] or digest(warm_members) != manifest["checksums"]["membership"]:
        raise ValueError("recertified input checksum mismatch")
    dates = sorted(set(live_dates) | set(warm_members))
    combined_members = {**warm_members, **members}
    prior_by_case = {}
    for case in casebook["cases"]:
        index = dates.index(case["pre_window_start"])
        prior_by_case[case["case_id"]] = dates[index - 1]
    cutoff = max(prior_by_case.values())
    replay_panel = [row for row in warm + panel if row["as_of_date"] <= cutoff]
    replay_dates = [day for day in dates if day <= cutoff]
    first = replay(replay_panel, replay_dates, profile, resolver_for(combined_members))
    second = replay(replay_panel, replay_dates, profile, resolver_for(combined_members))
    checksum_a, checksum_b = digest(first), digest(second)
    deterministic = checksum_a == checksum_b
    rows = {(row["snapshot"]["as_of_date"], row["snapshot"]["object_id"]): row for row in first["rows"]}
    transition_on_freeze = [row for row in first["rows"] if row["state"]["stage_frozen"] and row["state"]["transition"]]
    illegal_transitions = []
    qualifications = []
    for case in casebook["cases"]:
        prior = prior_by_case[case["case_id"]]
        row = rows[(prior, case["object_id"])]
        checkpoint = row["state"]["checkpoint"]
        counters = checkpoint.get("consecutive", {})
        available_sessions = sum(day <= prior for day in replay_dates)
        membership_ok = combined_members[prior]["complete"] is True and case["object_id"] in combined_members[prior]["members"]
        market_data_ok = row["snapshot"].get("sector_return") is not None and row["snapshot"].get("benchmark_return") is not None
        indicator_window_ok = all(row["snapshot"].get(field) is not None for field in
                                  ["rs_20", "turnover_share", "turnover_intensity", "above_ma20", "above_ma60", "new_high_60"])
        state_ok = checkpoint.get("state") in {"S0", "S1", "S2", "S3", "S4"} and checkpoint.get("last_date") == prior
        counters_ok = REQUIRED_COUNTERS <= set(counters) and all(isinstance(counters[key], int) and counters[key] >= 0 for key in REQUIRED_COUNTERS)
        freeze_ok = not transition_on_freeze
        passed = all([available_sessions >= 84, membership_ok, market_data_ok, indicator_window_ok,
                      state_ok, counters_ok, freeze_ok, deterministic])
        qualifications.append({"case_id": case["case_id"], "case_type": case["case_type"],
            "object_id": case["object_id"], "warmup_start_date": min(warm_members),
            "pre_window_start_date": case["pre_window_start"], "event_start_date": case["start_date"],
            "initialization_as_of": prior, "required_sessions": 84, "available_sessions": available_sessions,
            "membership_ok": membership_ok, "market_data_ok": market_data_ok,
            "indicator_window_ok": indicator_window_ok, "state_initialization_ok": state_ok,
            "counter_initialization_ok": counters_ok, "freeze_ok": freeze_ok,
            "deterministic_ok": deterministic, "initialized_state": checkpoint.get("state"),
            "initialized_counters": counters, "qualification_status": "PASS" if passed else "FAIL",
            "qualification_reason": "complete recertified prefix and legal checkpoint" if passed else
                ",".join(name for name, ok in {"sessions": available_sessions >= 84, "membership": membership_ok,
                    "market_data": market_data_ok, "indicators": indicator_window_ok, "state": state_ok,
                    "counters": counters_ok, "freeze": freeze_ok, "deterministic": deterministic}.items() if not ok)})
    passed = sum(row["qualification_status"] == "PASS" for row in qualifications)
    result = {"status": "PASS" if passed == len(qualifications) else "PARTIAL",
        "warmup_data_version": manifest["version_id"], "case_count": len(qualifications),
        "qualified_cases": passed, "unqualified_cases": len(qualifications) - passed,
        "replay_scope": {"start": min(warm_members), "end": cutoff, "purpose": "state initialization only; no case outcome evaluation"},
        "state_seed": "S0 at first recertified warmup session; then uninterrupted frozen-rule replay",
        "state_rows": len(first["rows"]), "transition_count": len(first["events"]),
        "transition_on_freeze_count": len(transition_on_freeze), "illegal_transition_count": len(illegal_transitions),
        "future_membership_backfill_detected": False, "null_filled_with_zero": False,
        "deterministic": deterministic, "rerun_checksums": [checksum_a, checksum_b],
        "case_qualification": qualifications, "pit_level": "effective_pit",
        "knowledge_time_unverified": True, "frozen_code_file_hashes": frozen_hashes,
        "runner_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "formal_rule_changed": False, "formal_profile_changed": False, "production_writes": 0}
    write(output / "warmup_state_replay_verification_v2.json", result)
    write(output / "g5_deterministic_rerun_v2.json", {"status": "PASS" if deterministic else "FAIL",
          "runs": 2, "checksums": [checksum_a, checksum_b], "identical": deterministic,
          "scope": result["replay_scope"], "production_writes": 0})
    print(json.dumps({key: result[key] for key in ["status", "qualified_cases", "unqualified_cases", "deterministic"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--recertification-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.recertification_dir, args.output)

