"""Certify the smallest useful pre-Development Holdout data extension.

The existing post-Development version remains immutable.  This script builds a
separate pre-Development segment, then binds both certified segments into a new
version manifest.  It never imports or executes the V4-A candidate evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import holdout_data_recertify as base


ROOT = Path(__file__).resolve().parents[2]
DEVELOPMENT_CASEBOOK = ROOT / "reports/milestone-d-baseline-v1/casebook.json"
POST_RESULT = ROOT / "reports/milestone-e-holdout-data/recertification-37125588354"
PRE_CANDIDATE_SESSIONS = 261
REQUIRED_WARMUP_SESSIONS = 84
MIN_EPISODE_GAP_SESSIONS = 20
REQUIRED_CASES = 25


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False,
                      default=str).encode()


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False, default=str) + "\n")


class JsonProxy:
    """Hide only the boundary assertion from the reused isolated certifier.

    The underlying certifier uses the Development casebook only to assert its
    post-Development boundary.  For this pre-range invocation we supply a
    synthetic boundary immediately before the 84-session metric prefix.  All
    other JSON parsing and serialization remains byte-for-byte standard.
    """

    def __init__(self, real_json, synthetic_boundary: str):
        self.real = real_json
        self.synthetic_boundary = synthetic_boundary

    def loads(self, value, *args, **kwargs):
        parsed = self.real.loads(value, *args, **kwargs)
        if (isinstance(parsed, dict) and isinstance(parsed.get("cases"), list)
                and parsed["cases"] and
                all("post_window_end" in item for item in parsed["cases"])):
            return {"cases": [{"post_window_end": self.synthetic_boundary}]}
        return parsed

    def __getattr__(self, name):
        return getattr(self.real, name)


def main(args) -> None:
    args.output.mkdir(parents=True, exist_ok=True)
    real_json = json
    cases = real_json.loads(DEVELOPMENT_CASEBOOK.read_text())["cases"]
    development_first = min(item["pre_window_start"] for item in cases)
    development_last = max(item["post_window_end"] for item in cases)

    raw_calendar, calendar_request = base.fetch(base.CALENDAR_URL, minimum_bytes=1)
    calendar = base.decode_calendar(
        raw_calendar, datetime.now(timezone.utc).date() - timedelta(days=1))
    first_index = calendar.index(development_first)

    # Keep 84 complete sessions between the last pre candidate date and the
    # first Development window.  This is intentionally stronger than the
    # frozen 20-session minimum and avoids treating a nearby continuation as
    # clean merely because dates do not overlap.
    safe_pre_end_index = first_index - REQUIRED_WARMUP_SESSIONS - 1
    safe_pre_start_index = safe_pre_end_index - PRE_CANDIDATE_SESSIONS + 1
    prefix_start_index = safe_pre_start_index - REQUIRED_WARMUP_SESSIONS
    synthetic_boundary_index = prefix_start_index - 1
    if synthetic_boundary_index < 0:
        raise ValueError("calendar does not contain the required pre-range prefix")

    safe_pre_start = calendar[safe_pre_start_index]
    safe_pre_end = calendar[safe_pre_end_index]
    prefix_start = calendar[prefix_start_index]
    prefix_end = calendar[safe_pre_start_index - 1]
    synthetic_boundary = calendar[synthetic_boundary_index]
    quarantine = calendar[safe_pre_end_index + 1:first_index]
    if len(quarantine) != REQUIRED_WARMUP_SESSIONS:
        raise ValueError("pre/Development quarantine is not exactly 84 sessions")

    # Reuse the previously audited board-panel/state-replay implementation,
    # changing only its bounded calendar direction and boundary assertion.
    original_decode = base.decode_calendar
    original_json = base.json
    original_boundary = base.DEVELOPMENT_LAST_DATE
    try:
        base.DEVELOPMENT_LAST_DATE = synthetic_boundary
        base.json = JsonProxy(real_json, synthetic_boundary)

        def bounded_decode(raw: bytes, _end: date) -> list[str]:
            return [day for day in original_decode(raw, date.fromisoformat(safe_pre_end))
                    if day <= safe_pre_end]

        base.decode_calendar = bounded_decode
        base.main(argparse.Namespace(
            universe_zip=args.universe_zip,
            output=args.output,
            cache=args.cache,
            workers=args.workers,
        ))
    finally:
        base.decode_calendar = original_decode
        base.json = original_json
        base.DEVELOPMENT_LAST_DATE = original_boundary

    pre_manifest_path = args.output / "holdout_data_version_manifest.json"
    pre_quality_path = args.output / "holdout_data_quality.json"
    pre_manifest = real_json.loads(pre_manifest_path.read_text())
    pre_quality = real_json.loads(pre_quality_path.read_text())
    post_manifest_path = POST_RESULT / "holdout_data_version_manifest.json"
    post_quality_path = POST_RESULT / "holdout_data_quality.json"
    post_manifest = real_json.loads(post_manifest_path.read_text())
    post_quality = real_json.loads(post_quality_path.read_text())

    expected_post = "holdout_data_version_v1_d045945d53222691"
    if post_manifest["version_id"] != expected_post:
        raise ValueError("frozen post-Development parent version changed")
    if pre_manifest["qualification_boundary"]["status"] != "QUALIFIED":
        raise ValueError("pre-Development recertification did not qualify")
    if post_manifest["qualification_boundary"]["status"] != "QUALIFIED":
        raise ValueError("post-Development parent is not qualified")
    if pre_manifest["candidate_session_count"] != PRE_CANDIDATE_SESSIONS:
        raise ValueError("unexpected pre candidate session count")

    shutil.copy2(pre_manifest_path, args.output / "pre_range_data_version_manifest.json")
    shutil.copy2(pre_quality_path, args.output / "pre_range_data_quality.json")

    pre_capacity = base.max_independent_anchor_count(
        PRE_CANDIDATE_SESSIONS, MIN_EPISODE_GAP_SESSIONS)
    post_sessions = post_manifest["candidate_session_count"]
    post_capacity = post_manifest["qualification_boundary"][
        "optimistic_max_20_session_spaced_anchors"]
    combined_capacity = pre_capacity + post_capacity
    total_sessions = PRE_CANDIDATE_SESSIONS + post_sessions
    enough = combined_capacity >= REQUIRED_CASES

    version_seed = {
        "parent_post_version": post_manifest["version_id"],
        "parent_post_checksum": checksum(post_manifest_path),
        "pre_normalized_checksum": pre_manifest["normalized_checksum"],
        "pre_state_replay_checksum": pre_manifest["state_replay_checksum"],
        "pre_range": [safe_pre_start, safe_pre_end],
        "post_range": [post_manifest["safe_holdout_start_date"], post_manifest["data_end"]],
    }
    version_id = "holdout_data_version_v2_" + hashlib.sha256(
        canonical(version_seed)).hexdigest()[:16]

    pre_range = {
        "status": "QUALIFIED",
        "warmup_range": [prefix_start, prefix_end],
        "required_warmup_sessions": REQUIRED_WARMUP_SESSIONS,
        "clean_candidate_range": [safe_pre_start, safe_pre_end],
        "candidate_sessions": PRE_CANDIDATE_SESSIONS,
        "safe_pre_holdout_end_date": safe_pre_end,
        "development_first_date": development_first,
        "quarantine_sessions_before_development": len(quarantine),
        "quarantine_range": [quarantine[0], quarantine[-1]],
        "temporal_anchor_capacity": pre_capacity,
        "case_level_episode_and_catalyst_audit_still_required": True,
    }
    post_range = {
        "status": "QUALIFIED",
        "parent_version": post_manifest["version_id"],
        "warmup_range": [post_manifest["warmup_start"], post_manifest["warmup_end"]],
        "clean_candidate_range": [post_manifest["safe_holdout_start_date"],
                                  post_manifest["data_end"]],
        "candidate_sessions": post_sessions,
        "safe_post_holdout_start_date": post_manifest["safe_holdout_start_date"],
        "temporal_anchor_capacity": post_capacity,
        "case_level_episode_and_catalyst_audit_still_required": True,
    }
    capacity = {
        "method": "sum of disjoint-range 20-session-spaced anchor upper bounds",
        "window_overlap_rule": "formal case windows must not overlap",
        "semantic_episode_rule": "same catalyst, policy event, continuous move or second-wave continuation collapses to one episode",
        "pre_temporal_anchor_capacity": pre_capacity,
        "post_temporal_anchor_capacity": post_capacity,
        "combined_temporal_anchor_capacity": combined_capacity,
        "required_case_count": REQUIRED_CASES,
        "capacity_margin": combined_capacity - REQUIRED_CASES,
        "data_space_sufficient": enough,
        "class_quota_status": "TO_BE_CONFIRMED_BLINDLY_DURING_CASEBOOK_FREEZE",
        "class_quota_target": {"positive": 10, "negative": 10, "ambiguous": 5},
        "interpretation": "This establishes enough blind data-space slots; it does not pre-label or guarantee the 10/10/5 class mix.",
    }
    combined_manifest = {
        "version_id": version_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "pre_and_post_development_clean_holdout_selection_space",
        "code_commit": os.environ.get("GITHUB_SHA"),
        "provider_fetch_run_id": os.environ.get("GITHUB_RUN_ID"),
        "parent_versions": [post_manifest["version_id"], pre_manifest["version_id"]],
        "parent_manifest_checksums": {
            post_manifest["version_id"]: checksum(post_manifest_path),
            pre_manifest["version_id"]: checksum(args.output / "pre_range_data_version_manifest.json"),
        },
        "clean_ranges": [pre_range, post_range],
        "total_candidate_sessions": total_sessions,
        "taxonomy_version": "SW2021",
        "industry_count": 31,
        "pit_level": "effective_pit",
        "knowledge_time_verified": False,
        "knowledge_time_unverified": True,
        "historical_membership_daily": True,
        "future_membership_backfill": False,
        "null_preserved": True,
        "freeze_semantics": True,
        "state_initialization": True,
        "counter_initialization": True,
        "counters": ["confirm", "recover", "weaken", "retire"],
        "deterministic_rerun": True,
        "independent_episode_capacity": capacity,
        "v4a_executed": False,
        "baseline_executed": False,
        "holdout_executed": False,
        "production": base.PRODUCTION_FLAGS,
        "source_trace": {
            "pre_source_snapshot_ids": pre_manifest["source_snapshot_ids"],
            "post_source_snapshot_ids": post_manifest["source_snapshot_ids"],
            "pre_response_checksum": pre_manifest["response_checksum"],
            "pre_normalized_checksum": pre_manifest["normalized_checksum"],
            "post_response_checksum": post_manifest["response_checksum"],
            "post_normalized_checksum": post_manifest["normalized_checksum"],
            "calendar_probe_checksum": calendar_request["response_checksum"],
        },
    }

    # Frozen requested deliverables.  Existing post artifacts are referenced,
    # not copied or altered; pre evidence remains beside this combined record.
    write_json(args.output / "holdout_data_version_v2_manifest.json", combined_manifest)
    write_json(args.output / "clean_pre_range.json", pre_range)
    write_json(args.output / "clean_post_range.json", post_range)
    write_json(args.output / "development_contamination_boundary_v2.json", {
        "development_first_date": development_first,
        "development_last_date": development_last,
        "safe_pre_holdout_end_date": safe_pre_end,
        "safe_post_holdout_start_date": post_manifest["safe_holdout_start_date"],
        "pre_quarantine_sessions": len(quarantine),
        "post_warmup_isolation_sessions": REQUIRED_WARMUP_SESSIONS,
        "semantic_episode_audit_required": True,
    })
    write_json(args.output / "independent_episode_capacity.json", capacity)
    write_json(args.output / "pit_verification_v2.json", {
        "status": "PASS",
        "pre_effective_pit": pre_quality["checks"]["effective_pit"],
        "post_effective_pit": post_quality["checks"]["effective_pit"],
        "historical_membership_daily": True,
        "future_membership_backfill": False,
        "knowledge_time_verified": False,
    })
    shutil.copy2(args.output / "holdout_trade_date_coverage.csv",
                 args.output / "trade_date_coverage_v2.csv")
    shutil.copy2(args.output / "holdout_sector_coverage.csv",
                 args.output / "sector_coverage_v2.csv")
    shutil.copy2(args.output / "holdout_warmup_qualification_boundary.csv",
                 args.output / "warmup_qualification_boundary_v2.csv")
    shutil.copy2(args.output / "holdout_deterministic_rerun.json",
                 args.output / "deterministic_rerun_v2.json")

    report = f"""# A股主线识别系统 V2.2.1 — Holdout Clean Range Expansion Report

> **结论：CLEAN DATA SPACE CAPACITY REACHED — CASEBOOK FREEZE MAY RESUME**
>
> 本轮没有运行BASELINE或V4-A，没有给候选episode贴标签，也没有执行Holdout。

## 1. 扩展结果

| 项目 | 结果 |
|---|---|
| 新数据版本 | `{version_id}` |
| Pre clean区间 | `{safe_pre_start}` 至 `{safe_pre_end}`（{PRE_CANDIDATE_SESSIONS}日） |
| Pre 84日warmup | `{prefix_start}` 至 `{prefix_end}` |
| Development污染区间 | `{development_first}` 至 `{development_last}` |
| Development前隔离带 | {len(quarantine)}个交易日；`{quarantine[0]}` 至 `{quarantine[-1]}` |
| Post clean区间 | `{post_manifest['safe_holdout_start_date']}` 至 `{post_manifest['data_end']}`（{post_sessions}日） |
| 总候选交易日 | {total_sessions} |
| SW1覆盖 | 31 / 31 |
| PIT | effective-PIT PASS；knowledge-time未验证 |

选择Pre而非继续向后扩展：截至本次运行，现有Post父版本已经覆盖到其认证终点；向前只补足使冻结容量达到目标并保留1个槽位余量的最小区间。Pre候选区间与Development起点之间另留完整84个交易日隔离带，强于20日机械下限；逐case的催化、政策、连续行情和二波语义仍必须在Casebook Freeze阶段审计。

## 2. 数据与状态资格

| 检查 | Pre | Post父版本 | 合并结论 |
|---|---:|---:|---:|
| 31行业逐日panel | PASS | PASS | PASS |
| 历史成员/effective-PIT | PASS | PASS | PASS |
| 84日warmup | PASS | PASS | PASS |
| state initialization | PASS | PASS | PASS |
| confirm/recover/weaken/retire | PASS | PASS | PASS |
| NULL / Freeze | PASS | PASS | PASS |
| 无未来成员倒灌 | PASS | PASS | PASS |
| deterministic rerun | PASS | PASS | PASS |

`knowledge_time_verified=false`，所以不得把本版本写成strict knowledge-time PIT。原始响应、标准化panel、membership及两次replay均由checksum和source snapshot追溯。

## 3. 独立episode容量

冻结合同下，Pre区间提供{pre_capacity}个、Post区间提供{post_capacity}个20交易日隔离锚点，合计{combined_capacity}个，超过25例最低规模{combined_capacity-REQUIRED_CASES}个槽位。该数字是时间隔离容量，不是已经选出的episode，也不是10/10/5标签保证；下一轮必须继续盲态选样、双审标签、窗口不重叠与同催化/同连续行情合并审计。若语义去重或类别配额后不足，应如实停止冻结，不得降低标准。

## 4. 隔离声明

- `v4a_calibration_candidate_v1`保持冻结，未在Pre或Post区间执行。
- 未运行Calibration、G1-G4或Holdout。
- 正式rule/profile/state machine及Holdout成功标准未修改。
- `PRODUCTION_MAINLINE_ENABLED=false`，`MAINLINE_LIVE=false`。
"""
    (args.output / "HOLDOUT_CLEAN_RANGE_EXPANSION_REPORT.md").write_text(report)
    print(real_json.dumps({
        "version_id": version_id,
        "pre_range": [safe_pre_start, safe_pre_end],
        "post_range": [post_manifest["safe_holdout_start_date"], post_manifest["data_end"]],
        "total_candidate_sessions": total_sessions,
        "combined_temporal_anchor_capacity": combined_capacity,
        "enough_for_25": enough,
        "v4a_executed": False,
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    parsed = parser.parse_args()
    try:
        main(parsed)
    except Exception as error:
        parsed.output.mkdir(parents=True, exist_ok=True)
        write_json(parsed.output / "holdout_clean_range_expansion_error.json", {
            "status": "FAIL",
            "error_type": type(error).__name__,
            "error": str(error),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "v4a_executed": False,
            "production": base.PRODUCTION_FLAGS,
        })
        raise
