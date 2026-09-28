from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid5


RUN_NAMESPACE = UUID("f80b56da-9062-4b84-9e83-afef08cae930")
SOURCE_NAMESPACE = UUID("84031db7-18fe-48f1-94de-3f6df02f57c9")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dedupe(rows: list[dict], fields: tuple[str, ...]) -> list[dict]:
    seen = set()
    output = []
    for row in rows:
        key = tuple(row.get(field) for field in fields)
        if key not in seen:
            seen.add(key)
            output.append(row)
    return output


def aggregate(input_dir: Path, output_dir: Path, code_commit: str | None = None) -> dict:
    summary_paths = sorted(input_dir.rglob("poc_summary.json"))
    if not summary_paths:
        raise RuntimeError(f"no Phase 1D shard summaries found under {input_dir}")

    summaries = [_read(path) for path in summary_paths]
    snapshots: list[dict] = []
    memberships: list[dict] = []
    taxonomies: list[dict] = []
    traces: list[dict] = []
    anomaly_tests: list[dict] = []
    failures: list[dict] = []
    source_snapshots: list[dict] = []
    rerun_samples: list[dict] = []

    for summary_path, summary in zip(summary_paths, summaries):
        folder = summary_path.parent
        snapshots.extend(_read(folder / "sector_snapshots.json"))
        memberships.extend(_read(folder / "membership_evidence.json"))
        taxonomies.extend(_read(folder / "taxonomy_definitions.json"))
        traces.extend(_read(folder / "calculation_traces.json"))
        anomaly_tests.extend(_read(folder / "anomaly_tests.json"))
        failures.extend(summary.get("failures") or [])
        rerun_samples.extend(summary.get("rerun_samples") or [])
        for artifact in summary.get("cache_artifacts") or []:
            checksum = artifact["checksum_sha256"]
            source_snapshots.append({
                "id": str(uuid5(SOURCE_NAMESPACE, checksum)),
                "dataset": artifact["dataset"],
                "source_id": artifact["source_id"],
                "source_version": artifact["source_version"],
                "fetched_at": artifact["fetched_at"],
                "checksum_sha256": checksum,
                "row_count": artifact["row_count"],
                "cache_key": artifact["cache_key"],
            })

    source_snapshots = _dedupe(source_snapshots, ("id",))
    source_ids_by_checksum = {row["checksum_sha256"]: row["id"] for row in source_snapshots}
    # Never let a degraded retry overwrite stronger real evidence. For each
    # sector-day prefer: critical data OK, then not frozen, then higher valid
    # member coverage. Missing samples can still be filled by a bounded retry.
    best: dict[tuple, dict] = {}
    for row in snapshots:
        key = (row["as_of_date"], row["taxonomy_code"])
        member_count = int(row.get("member_count") or 0)
        coverage = (int(row.get("valid_member_count") or 0) / member_count) if member_count else 0.0
        quality = (bool(row.get("critical_data_ok")), not bool(row.get("stage_frozen")), coverage)
        current = best.get(key)
        if current is None or quality > current[0]:
            best[key] = (quality, row)
    snapshots = sorted((value[1] for value in best.values()), key=lambda row: (row["as_of_date"], row["taxonomy_code"]))
    global_basis = {
        "metric_contract": "V2.2-section-6",
        "samples": [(row["as_of_date"], row["taxonomy_code"]) for row in snapshots],
        "source_checksums": sorted(source_ids_by_checksum),
        "parameter_profile": "industry_trend_v2_2_1",
        "code_commit": code_commit or os.getenv("GITHUB_SHA") or "local-uncommitted",
    }
    run_fingerprint = hashlib.sha256(json.dumps(global_basis, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    run_id = str(uuid5(RUN_NAMESPACE, run_fingerprint))
    for row in snapshots:
        row["run_id"] = run_id
        row["source_snapshot_ids"] = [source_ids_by_checksum[value] for value in row.get("source_checksums", []) if value in source_ids_by_checksum]
        row["code_commit"] = global_basis["code_commit"]

    result_checksum = hashlib.sha256(json.dumps(snapshots, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    rerun_samples = _dedupe(rerun_samples, ("trade_date", "taxonomy_code"))[:3]
    matrix = [(row["as_of_date"], row["taxonomy_code"]) for row in snapshots]
    dates = sorted({row[0] for row in matrix})
    per_date_counts = {trade_date: sum(1 for row in matrix if row[0] == trade_date) for trade_date in dates}
    summary = {
        "phase": "Phase 1D",
        "run_id": run_id,
        "run_fingerprint": run_fingerprint,
        "code_commit": global_basis["code_commit"],
        "target_snapshot_count": 15,
        "actual_snapshot_count": len(snapshots),
        "per_date_snapshot_counts": per_date_counts,
        "frozen_snapshot_count": sum(bool(row.get("stage_frozen")) for row in snapshots),
        "effective_pit_count": sum(row.get("pit_level") == "effective_pit" for row in snapshots),
        "strict_knowledge_pit_count": sum(row.get("pit_level") == "strict_knowledge_pit" for row in snapshots),
        "result_checksum": result_checksum,
        "rerun_samples": rerun_samples,
        "rerun_identical": len(rerun_samples) >= 3 and all(row.get("identical") for row in rerun_samples),
        "full_a_history_persisted": False,
        "stock_rows_cached_only": sum(int(row.get("stock_rows_cached_only") or 0) for row in summaries),
        "stock_rows_written_to_supabase": 0,
        "source_snapshot_count": len(source_snapshots),
        "failures": failures,
        "anomaly_test_count": len(anomaly_tests),
        "anomaly_tests_passed": sum(bool(row.get("pass")) for row in anomaly_tests),
        "gate_ready_for_database_write": (
            len(snapshots) == 15
            and len(dates) == 5
            and all(count >= 3 for count in per_date_counts.values())
            and len(rerun_samples) >= 3
            and all(row.get("identical") for row in rerun_samples)
        ),
        "success_snapshot_count": sum(bool(row.get("critical_data_ok")) and not bool(row.get("stage_frozen")) for row in snapshots),
        "partial_snapshot_count": sum(not (bool(row.get("critical_data_ok")) and not bool(row.get("stage_frozen"))) for row in snapshots),
        "minimum_12_sample_closure_met": (
            sum(bool(row.get("critical_data_ok")) and not bool(row.get("stage_frozen")) for row in snapshots) >= 12
            and len(dates) == 5
            and len(rerun_samples) >= 3
            and all(row.get("identical") for row in rerun_samples)
        ),
    }

    _write(output_dir / "poc_summary.json", summary)
    _write(output_dir / "sector_snapshots.json", snapshots)
    _write(output_dir / "membership_evidence.json", _dedupe(memberships, ("snapshot_date", "taxonomy_code", "security_id")))
    _write(output_dir / "taxonomy_definitions.json", _dedupe(taxonomies, ("taxonomy_version", "taxonomy_code")))
    _write(output_dir / "calculation_traces.json", traces[:3])
    _write(output_dir / "anomaly_tests.json", anomaly_tests)
    _write(output_dir / "source_snapshots.json", source_snapshots)
    _write(output_dir / "run_manifest.json", {**global_basis, **summary})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--code-commit")
    args = parser.parse_args()
    print(json.dumps(aggregate(args.input_dir, args.output_dir, args.code_commit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
