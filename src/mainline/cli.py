from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date, datetime, timezone

from .data_quality import decide_freeze, evaluate_daily_quality
from .providers.akshare import AkshareProvider
from .providers.tushare import TushareProvider


def _batch_summary(batch) -> dict:
    return {
        "dataset": batch.dataset.value,
        "source_used": batch.source_id,
        "source_version": batch.source_version,
        "fetched_at": batch.fetched_at.isoformat(),
        "historical_capability": batch.historical_capability,
        "request_fingerprint": batch.request_fingerprint,
        "row_count": len(batch.frame),
        "columns": list(batch.frame.columns),
    }


def provider_probe(args: argparse.Namespace) -> int:
    provider = AkshareProvider() if args.provider == "akshare" else TushareProvider()
    if args.dataset == "trading_calendar":
        batch = provider.get_trading_calendar(args.start_date, args.end_date)
    elif args.dataset == "index_daily":
        batch = provider.get_index_daily(args.object_id, args.start_date, args.end_date)
    elif args.dataset == "membership_history":
        batch = provider.get_membership_history("sw1", args.start_date, args.end_date)
    else:
        raise SystemExit(f"unsupported probe dataset: {args.dataset}")
    print(json.dumps(_batch_summary(batch), ensure_ascii=False, indent=2))
    return 0


def freeze_probe(args: argparse.Namespace) -> int:
    import pandas as pd

    actual = int(args.expected * args.completeness)
    frame = pd.DataFrame({"security_id": [f"fixture-{i}" for i in range(actual)]})
    report = evaluate_daily_quality(
        frame, dataset_code=args.dataset, as_of_date=date.fromisoformat(args.as_of_date),
        expected_count=args.expected, key_columns=("security_id",), required_columns=("security_id",),
        fetched_at=datetime.now(timezone.utc),
    )
    decision = decide_freeze([report])
    print(json.dumps({"quality": asdict(report), "freeze": asdict(decision)}, default=str, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="V2.2 Phase 1 provider and data-quality runner")
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser("provider-probe")
    probe.add_argument("--provider", choices=("tushare", "akshare"), required=True)
    probe.add_argument("--dataset", choices=("trading_calendar", "index_daily", "membership_history"), required=True)
    probe.add_argument("--start-date", required=True)
    probe.add_argument("--end-date", required=True)
    probe.add_argument("--object-id", default="000300.SH")
    probe.set_defaults(func=provider_probe)
    freeze = sub.add_parser("freeze-probe")
    freeze.add_argument("--dataset", default="daily_bars")
    freeze.add_argument("--as-of-date", required=True)
    freeze.add_argument("--expected", type=int, required=True)
    freeze.add_argument("--completeness", type=float, required=True)
    freeze.set_defaults(func=freeze_probe)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
