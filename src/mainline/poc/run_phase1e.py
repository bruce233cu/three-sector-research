from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid5

import pandas as pd

from mainline.cache import ParquetDuckDBCache
from mainline.metrics import SectorMetricInput, calculate_sector_snapshot
from mainline.providers.baostock_window import BaostockWindowProvider
from mainline.providers.eastmoney_window import EastmoneyWindowProvider
from mainline.providers.netease_window import NeteaseWindowProvider
from mainline.providers.sws_history import SwsCachedEvidenceProvider, SwsEffectivePitProvider


RUN_NAMESPACE = UUID("2b66a24b-cdd7-4ab0-b281-f083f1ed9b88")
SOURCE_NAMESPACE = UUID("84031db7-18fe-48f1-94de-3f6df02f57c9")
BAR_COLUMNS = [
    "security_id", "trade_date", "open", "high", "low", "close", "volume",
    "amount", "pct_chg", "turnover_rate", "circ_mv", "circ_mv_derivation",
    "source_id", "source_version",
]


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=_jsonable) + "\n",
        encoding="utf-8",
    )


def _jsonable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def load_partial_samples(path: Path) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected_tables = {"mainline.phase1d_sample_runs", "mainline.daily_mainline_snapshot"}
    if set(payload.get("source_tables") or []) != expected_tables:
        raise ValueError("Phase 1E input must be sourced from both frozen Phase 1D result tables")
    samples = payload.get("samples") or []
    if not samples or any(row.get("status") != "PARTIAL" for row in samples):
        raise ValueError("Phase 1E input may contain only current PARTIAL samples")
    ids = [row.get("sample_id") for row in samples]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate sample_id in Phase 1E input")
    if payload.get("source_row_count") != len(samples):
        raise ValueError("source_row_count does not match the database-derived sample list")
    return payload, samples


def _bounded_provider_fetch(provider, security_ids: list[str], start_date: date, end_date: date,
                            *, min_probe_ratio: float = 0.80, probe_size: int = 12):
    """Use one health probe and at most one batch attempt for a provider.

    Successful probe rows are retained. A failed probe opens the circuit for the
    rest of the batch, preventing a dead public endpoint from consuming the
    complete sample budget one timeout at a time.
    """
    if not security_ids:
        return pd.DataFrame(columns=BAR_COLUMNS), {}, {
            "probe_count": 0, "probe_success_ratio": 1.0, "circuit_open": False,
        }
    ordered = sorted(set(security_ids))
    probe_ids = ordered[:probe_size]
    probe_rows, probe_errors = provider.get_many(probe_ids, start_date, end_date)
    probe_success = set(probe_ids).difference(probe_errors)
    ratio = len(probe_success) / len(probe_ids)
    frames = [probe_rows] if not probe_rows.empty else []
    errors = dict(probe_errors)
    if ratio >= min_probe_ratio:
        remaining = [sid for sid in ordered if sid not in probe_success]
        rows, batch_errors = provider.get_many(remaining, start_date, end_date)
        if not rows.empty:
            frames.append(rows)
        errors.update(batch_errors)
    else:
        reason = f"circuit_open:probe_success_ratio={ratio:.4f}<{min_probe_ratio:.4f}"
        errors.update({sid: errors.get(sid, reason) for sid in ordered if sid not in probe_success})
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=BAR_COLUMNS)
    return combined, errors, {
        "probe_count": len(probe_ids),
        "probe_success_ratio": ratio,
        "circuit_open": ratio < min_probe_ratio,
        "requested_security_count": len(ordered),
        "returned_security_count": int(combined["security_id"].nunique()) if not combined.empty else 0,
    }


def coverage_fields(snapshot: dict) -> dict:
    coverage = snapshot.get("metric_coverage_json") or {}
    ma20 = float(coverage.get("above_ma20") or 0.0)
    ma60 = float(coverage.get("above_ma60") or 0.0)
    high60 = float(coverage.get("new_high_60") or 0.0)
    return {
        "window_coverage": min(ma20, ma60, high60),
        "MA20_coverage": ma20,
        "MA60_coverage": ma60,
        "NEW_HIGH60_coverage": high60,
    }


def run_one(sample: dict, output_dir: Path, cache_dir: Path, membership_path: Path) -> dict:
    started = time.monotonic()
    output_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc)
    trade_date = date.fromisoformat(sample["trade_date"])
    code = sample["taxonomy_code"]
    name = sample["industry_name"]

    membership_provider = SwsCachedEvidenceProvider(membership_path)
    membership = membership_provider.snapshot(trade_date, code, name)
    if membership.frame.empty:
        # Phase 1D's immutable fallback contains only the shards that completed
        # its bounded run.  Reuse it first, then use the existing official SWS
        # adapter for database-selected PARTIAL samples absent from that cache.
        membership_provider = SwsEffectivePitProvider()
        membership = membership_provider.snapshot(trade_date, code, name)
    if membership.frame.empty:
        raise RuntimeError(f"database-selected sample has no cached audited membership: {sample['sample_id']}")
    member_ids = sorted(membership.frame["security_id"].unique())
    if len(member_ids) != int(sample["member_count"]):
        raise RuntimeError(
            f"membership drift for {sample['sample_id']}: database={sample['member_count']} cache={len(member_ids)}"
        )

    cache = ParquetDuckDBCache(cache_dir)
    membership_frame = membership.frame.copy()
    membership_frame["snapshot_date"] = trade_date
    membership_frame["taxonomy_code"] = code
    membership_frame["taxonomy_name"] = name
    membership_frame["taxonomy_version"] = membership.taxonomy_version
    membership_artifact = cache.put(
        "membership_snapshot", sample["sample_id"], membership_frame,
        source_id=membership_provider.source_id, source_version=membership.source_version,
        fetched_at=fetched_at,
    )

    window_start = trade_date - timedelta(days=120)
    frames: list[pd.DataFrame] = []
    provider_audit: list[dict] = []

    primary = EastmoneyWindowProvider(workers=6, retries=1, timeout_seconds=12)
    primary_rows, primary_errors, primary_audit = _bounded_provider_fetch(
        primary, member_ids, window_start, trade_date,
    )
    if not primary_rows.empty:
        frames.append(primary_rows)
    unresolved = sorted(primary_errors)
    provider_audit.append({"source_id": primary.source_id, **primary_audit, "unresolved_count": len(unresolved)})

    secondary = NeteaseWindowProvider(workers=8, retries=1, timeout_seconds=12)
    secondary_rows, secondary_errors, secondary_audit = _bounded_provider_fetch(
        secondary, unresolved, window_start, trade_date,
    )
    if not secondary_rows.empty:
        frames.append(secondary_rows)
    unresolved = sorted(secondary_errors)
    provider_audit.append({"source_id": secondary.source_id, **secondary_audit, "unresolved_count": len(unresolved)})

    backup = BaostockWindowProvider(workers=4)
    backup_available, backup_reason = backup.healthcheck()
    if backup_available:
        backup_rows, backup_errors = backup.get_many(unresolved, window_start, trade_date)
    else:
        backup_rows = pd.DataFrame(columns=BAR_COLUMNS)
        backup_errors = {sid: f"circuit_open:{backup_reason}" for sid in unresolved}
    if not backup_rows.empty:
        frames.append(backup_rows)
    provider_audit.append({
        "source_id": backup.source_id,
        "healthcheck_ok": backup_available,
        "healthcheck_reason": backup_reason,
        "requested_security_count": len(unresolved),
        "returned_security_count": int(backup_rows["security_id"].nunique()) if not backup_rows.empty else 0,
        "unresolved_count": len(backup_errors),
    })

    bars = (
        pd.concat(frames, ignore_index=True).drop_duplicates(["security_id", "trade_date"], keep="first")
        if frames else pd.DataFrame(columns=BAR_COLUMNS)
    )
    bars_artifact = cache.put(
        "stock_window", sample["sample_id"], bars,
        source_id=f"{primary.source_id}+{secondary.source_id}+{backup.source_id}",
        source_version=f"{primary.source_version}+{secondary.source_version}+{backup.source_version}",
        fetched_at=fetched_at,
    )

    benchmark = primary.get_sw_index("801003")
    benchmark_artifact = cache.put(
        "benchmark_window", f"801003:{trade_date.isoformat()}", benchmark,
        source_id="sws_official_index_api", source_version="sws-index-publish-trend-v2-cny",
        fetched_at=fetched_at,
    )
    benchmark_returns = benchmark.set_index("trade_date")["pct_chg"] / 100.0
    all_a_amount = benchmark.set_index("trade_date")["amount"]
    snapshot = calculate_sector_snapshot(SectorMetricInput(
        trade_date=trade_date,
        object_id=sample["object_id"],
        taxonomy_code=code,
        taxonomy_version=membership.taxonomy_version,
        member_ids=tuple(member_ids),
        member_bars=bars,
        benchmark_returns=benchmark_returns,
        all_a_amount=all_a_amount,
        all_a_circ_mv=None,
    ))

    source_artifacts = [membership_artifact, bars_artifact, benchmark_artifact]
    source_snapshot_ids = [str(uuid5(SOURCE_NAMESPACE, item.checksum_sha256)) for item in source_artifacts]
    basis = {
        "sample_id": sample["sample_id"],
        "source_checksums": [item.checksum_sha256 for item in source_artifacts],
        "code_commit": os.getenv("GITHUB_SHA") or "local-uncommitted",
        "contract": "mainline-v2.2-phase1e",
    }
    run_id = str(uuid5(RUN_NAMESPACE, hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()))
    snapshot.update({
        "pit_level": membership.pit_level,
        "knowledge_time_unverified": membership.knowledge_time_unverified,
        "source_ids": [membership_provider.source_id, primary.source_id, secondary.source_id, backup.source_id, "sws_official_index_api"],
        "source_versions": [membership.source_version, primary.source_version, secondary.source_version, backup.source_version, "sws-index-publish-trend-v2-cny"],
        "source_checksums": basis["source_checksums"],
        "source_snapshot_ids": source_snapshot_ids,
        "run_id": run_id,
        "rule_version": "mainline_v2.2.0",
        "profile_id": "industry_trend_v2_2_1",
        "hard_status": None,
        "candidate_flag": False,
        "confirmed_flag": False,
        "cache_checksum": bars_artifact.checksum_sha256,
    })
    cov = coverage_fields(snapshot)
    final_status = "SUCCESS" if snapshot["critical_data_ok"] and not snapshot["stage_frozen"] else "PARTIAL"
    result = {
        "sample_id": sample["sample_id"],
        "trade_date": sample["trade_date"],
        "taxonomy": {"code": code, "name": name, "version": membership.taxonomy_version},
        "member_count": snapshot["member_count"],
        "valid_member_count": snapshot["valid_member_count"],
        **cov,
        "critical_data_ok": snapshot["critical_data_ok"],
        "stage_frozen": snapshot["stage_frozen"],
        "freeze_reason": snapshot["freeze_reason"],
        "source_snapshot_ids": source_snapshot_ids,
        "run_id": run_id,
        "final_status": final_status,
        "failure_class": None if final_status == "SUCCESS" else "historical_market_window_insufficient",
        "unresolved_security_count": len(backup_errors),
        "provider_audit": provider_audit,
        "duration_seconds": round(time.monotonic() - started, 3),
        "cache_status": "parquet_duckdb_audited",
        "code_commit": basis["code_commit"],
    }
    source_rows = [{
        "source_snapshot_id": source_snapshot_ids[index],
        "source_id": item.source_id,
        "dataset_code": item.dataset,
        "source_version": item.source_version,
        "fetched_at": item.fetched_at,
        "response_checksum": item.checksum_sha256,
        "row_count": item.row_count,
        "raw_location": item.parquet_path,
        "historical_capability": "historical_full" if item.dataset != "membership_snapshot" else "historical_partial",
        "metadata": {"sample_id": sample["sample_id"], "cache_key": item.cache_key, "phase": "Phase 1E"},
    } for index, item in enumerate(source_artifacts)]

    _write(output_dir / "sample_result.json", result)
    _write(output_dir / "sector_snapshot.json", snapshot)
    _write(output_dir / "source_snapshots.json", source_rows)
    _write(output_dir / "membership_evidence.json", membership_frame.to_dict(orient="records"))
    _write(output_dir / "run_manifest.json", {**basis, **result, "full_a_history_persisted": False})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-file", type=Path, required=True)
    parser.add_argument("--sample-position", type=int, required=True)
    parser.add_argument("--membership-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    args = parser.parse_args()
    _payload, samples = load_partial_samples(args.sample_file)
    if args.sample_position < 0 or args.sample_position >= len(samples):
        raise ValueError("sample position is outside the database-derived PARTIAL list")
    print(json.dumps(
        run_one(samples[args.sample_position], args.output_dir, args.cache_dir, args.membership_file),
        ensure_ascii=False, indent=2, default=_jsonable,
    ))


if __name__ == "__main__":
    main()
