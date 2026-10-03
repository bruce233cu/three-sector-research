"""Certify one minimal pre-range used only to complete positive Holdout labels.

The frozen 23-case draft, V4-A, Production, and prior data versions remain
immutable.  This wrapper reuses the audited isolated data certifier and stops
after 100 candidate sessions ending twenty sessions before the earliest locked
Holdout case.  It never imports or executes any candidate evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import holdout_data_recertify as base

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "reports/milestone-e-holdout-data/clean-range-37129071892/holdout_data_version_v2_manifest.json"
DRAFT = ROOT / "reports/milestone-e-holdout/holdout_casebook_draft_v2.json"
REQUIRED_WARMUP = 84
CANDIDATE_SESSIONS = 100
MIN_GAP = 20


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


class JsonProxy:
    def __init__(self, real, boundary): self.real, self.boundary = real, boundary
    def loads(self, value, *args, **kwargs):
        parsed = self.real.loads(value, *args, **kwargs)
        if isinstance(parsed, dict) and parsed.get("cases") and all("post_window_end" in x for x in parsed["cases"]):
            return {"cases": [{"post_window_end": self.boundary}]}
        return parsed
    def __getattr__(self, name): return getattr(self.real, name)


def main(args):
    args.output.mkdir(parents=True, exist_ok=True)
    parent = json.loads(PARENT.read_text())
    draft = json.loads(DRAFT.read_text())
    if draft["status"] != "DRAFT_NOT_FROZEN" or draft["draft_counts"] != {"positive": 8, "negative": 10, "ambiguous": 5}:
        raise ValueError("frozen draft boundary changed")
    if parent["version_id"] != "holdout_data_version_v2_e3e1ab3c8a78a26d":
        raise ValueError("parent data version changed")

    raw, _ = base.fetch(base.CALENDAR_URL, minimum_bytes=1)
    calendar = base.decode_calendar(raw, datetime.now(timezone.utc).date() - timedelta(days=1))
    earliest = min(x["event_start"] for x in draft["cases"])
    safe_end_i = calendar.index(earliest) - MIN_GAP
    safe_end = calendar[safe_end_i]
    safe_start_i = safe_end_i - CANDIDATE_SESSIONS + 1
    prefix_start_i = safe_start_i - REQUIRED_WARMUP
    synthetic_i = prefix_start_i - 1
    if synthetic_i < 0: raise ValueError("calendar prefix unavailable")
    safe_start, prefix_start = calendar[safe_start_i], calendar[prefix_start_i]
    synthetic = calendar[synthetic_i]

    original_decode, original_json, original_boundary = base.decode_calendar, base.json, base.DEVELOPMENT_LAST_DATE
    try:
        base.DEVELOPMENT_LAST_DATE = synthetic
        base.json = JsonProxy(json, synthetic)
        def bounded_decode(payload, _end):
            return [x for x in original_decode(payload, date.fromisoformat(safe_end)) if x <= safe_end]
        base.decode_calendar = bounded_decode
        base.main(argparse.Namespace(universe_zip=args.universe_zip, output=args.output,
                                     cache=args.cache, workers=args.workers))
    finally:
        base.decode_calendar, base.json, base.DEVELOPMENT_LAST_DATE = original_decode, original_json, original_boundary

    segment_path = args.output / "holdout_data_version_manifest.json"
    segment = json.loads(segment_path.read_text())
    if segment["qualification_boundary"]["status"] != "QUALIFIED" or segment["candidate_session_count"] != CANDIDATE_SESSIONS:
        raise ValueError("positive extension segment did not qualify")
    seed = {"parent": parent["version_id"], "parent_checksum": sha(PARENT),
            "segment": segment["version_id"], "segment_checksum": sha(segment_path),
            "range": [safe_start, safe_end]}
    version_id = "holdout_data_version_v3_" + hashlib.sha256(canonical(seed)).hexdigest()[:16]
    manifest = {
      "version_id": version_id, "created_at": datetime.now(timezone.utc).isoformat(),
      "purpose": "positive_holdout_completion_minimal_pre_extension",
      "code_commit": os.environ.get("GITHUB_SHA"), "provider_fetch_run_id": os.environ.get("GITHUB_RUN_ID"),
      "parent_version": parent["version_id"], "parent_manifest_checksum": sha(PARENT),
      "extension_segment_version": segment["version_id"], "extension_manifest_checksum": sha(segment_path),
      "extension_warmup_range": [prefix_start, calendar[safe_start_i-1]],
      "extension_clean_candidate_range": [safe_start, safe_end],
      "extension_candidate_sessions": CANDIDATE_SESSIONS, "required_warmup_sessions": REQUIRED_WARMUP,
      "minimum_gap_to_locked_case_sessions": MIN_GAP, "earliest_locked_case_start": earliest,
      "pit_level": segment["pit_level"], "knowledge_time_verified": False,
      "historical_membership_daily": True, "future_membership_backfill": False,
      "null_preserved": True, "freeze_semantics": True, "state_initialization": True,
      "counter_initialization": True, "deterministic_rerun": True,
      "v4a_executed": False, "holdout_executed": False,
      "production": {"PRODUCTION_MAINLINE_ENABLED": False, "MAINLINE_LIVE": False}
    }
    write(args.output / "holdout_data_version_v3_manifest.json", manifest)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--universe-zip", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--workers", type=int, default=16)
    main(p.parse_args())
