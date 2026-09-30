from __future__ import annotations

import argparse
import json
from pathlib import Path

from mainline.poc.run_phase1e import load_partial_samples


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def aggregate(sample_file: Path, input_dir: Path, output_dir: Path) -> dict:
    source, expected = load_partial_samples(sample_file)
    expected_by_id = {row["sample_id"]: row for row in expected}
    results = {}
    snapshots = {}
    source_rows = {}
    for result_path in sorted(input_dir.rglob("sample_result.json")):
        result = _read(result_path)
        sample_id = result.get("sample_id")
        if sample_id not in expected_by_id:
            continue
        current = results.get(sample_id)
        quality = (result.get("final_status") == "SUCCESS", float(result.get("window_coverage") or 0.0))
        current_quality = (
            current and current.get("final_status") == "SUCCESS",
            float((current or {}).get("window_coverage") or 0.0),
        )
        if current is None or quality > current_quality:
            results[sample_id] = result
            snapshot_path = result_path.with_name("sector_snapshot.json")
            if snapshot_path.exists():
                snapshots[sample_id] = _read(snapshot_path)
            source_path = result_path.with_name("source_snapshots.json")
            if source_path.exists():
                for row in _read(source_path):
                    source_rows[row["source_snapshot_id"]] = row

    final_rows = []
    for expected_row in expected:
        sample_id = expected_row["sample_id"]
        if sample_id in results:
            final_rows.append(results[sample_id])
            continue
        final_rows.append({
            "sample_id": sample_id,
            "trade_date": expected_row["trade_date"],
            "taxonomy": {
                "code": expected_row["taxonomy_code"], "name": expected_row["industry_name"],
                "version": expected_row.get("taxonomy_version"),
            },
            "member_count": expected_row.get("member_count"),
            "valid_member_count": expected_row.get("valid_member_count"),
            "window_coverage": float(expected_row.get("coverage") or 0.0),
            "MA20_coverage": None, "MA60_coverage": None, "NEW_HIGH60_coverage": None,
            "critical_data_ok": False, "stage_frozen": True,
            "freeze_reason": "Phase 1E bounded runner did not produce a result",
            "source_snapshot_ids": expected_row.get("source_snapshot_ids") or [],
            "run_id": expected_row.get("run_id"), "final_status": "PARTIAL",
            "failure_class": "bounded_runner_failure", "unresolved_security_count": None,
        })

    success = sum(row["final_status"] == "SUCCESS" for row in final_rows)
    fail = sum(row["final_status"] == "FAIL" for row in final_rows)
    summary = {
        "title": "A股主线识别系统 V2.2 — Phase 1E 交付结果",
        "original_partial_count": len(expected),
        "converted_to_success_count": success,
        "remaining_partial_count": len(expected) - success - fail,
        "fail_count": fail,
        "source_tables": source["source_tables"],
        "schema_modified": False,
        "full_a_history_persisted": False,
        "sample_result_count": len(results),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write(output_dir / "phase1e_summary.json", summary)
    _write(output_dir / "phase1e_results.json", final_rows)
    _write(output_dir / "sector_snapshots.json", [snapshots[k] for k in sorted(snapshots)])
    _write(output_dir / "source_snapshots.json", list(source_rows.values()))
    lines = [
        "# 《A股主线识别系统 V2.2 — Phase 1E 交付结果》", "",
        f"- 原PARTIAL数量：{summary['original_partial_count']}",
        f"- 转SUCCESS数量：{summary['converted_to_success_count']}",
        f"- 仍PARTIAL数量：{summary['remaining_partial_count']}",
        f"- FAIL数量：{summary['fail_count']}",
        "- Supabase schema修改：否", "",
        "| sample_id | 行业 | 成员/有效 | 窗口覆盖 | MA20 | MA60 | NEW_HIGH60 | critical | Freeze | 最终状态 | 原因 |", 
        "|---|---|---:|---:|---:|---:|---:|---|---|---|---|",
    ]
    def pct(value):
        return "NULL" if value is None else f"{float(value):.2%}"
    for row in final_rows:
        lines.append(
            f"| {row['sample_id']} | {row['taxonomy']['name']} | {row.get('valid_member_count')}/{row.get('member_count')} "
            f"| {pct(row.get('window_coverage'))} | {pct(row.get('MA20_coverage'))} | {pct(row.get('MA60_coverage'))} "
            f"| {pct(row.get('NEW_HIGH60_coverage'))} | {row.get('critical_data_ok')} | {row.get('stage_frozen')} "
            f"| {row['final_status']} | {row.get('freeze_reason') or '-'} |"
        )
    (output_dir / "PHASE1E_DELIVERY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-file", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(aggregate(args.sample_file, args.input_dir, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
