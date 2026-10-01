"""Decode a captured real Sina SSE calendar; no weekday inference/future guess."""
import argparse
import bisect
import csv
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import py_mini_racer
from akshare.stock.cons import hk_js_decode


def validate_2026(rows):
    """Cross-check source dates against SSE published 2026 holiday notice."""
    closures = [("2026-01-01", "2026-01-03"), ("2026-02-15", "2026-02-23"),
                ("2026-04-04", "2026-04-06"), ("2026-05-01", "2026-05-05"),
                ("2026-06-19", "2026-06-21"), ("2026-09-25", "2026-09-27"),
                ("2026-10-01", "2026-10-07")]
    checked = [r for r in rows if r["cal_date"].startswith("2026-")]
    if len(checked) != 365:
        raise ValueError("2026 official cross-check requires complete year")
    for row in checked:
        key = row["cal_date"]
        expected = date.fromisoformat(key).weekday() < 5 and not any(a <= key <= b for a, b in closures)
        if expected != row["is_open"]:
            raise ValueError("source calendar disagrees with SSE notice: " + key)
    return 0


def build(raw, start, end):
    js = py_mini_racer.MiniRacer()
    js.eval(hk_js_decode)
    decoded = js.call("d", raw.decode().split("=", 1)[1].split(";")[0].replace('"', ""))
    opens = sorted({str(x)[:10] for x in decoded})
    if not opens or start.isoformat() < opens[0] or end.isoformat() > opens[-1]:
        raise ValueError("requested range outside source calendar; refresh source")
    opened = set(opens)
    rows = []
    d = start
    while d <= end:
        key = d.isoformat()
        i = bisect.bisect_left(opens, key)
        rows.append({"exchange": "SSE", "cal_date": key,
                     "is_open": key in opened,
                     "pretrade_date": opens[i-1] if i else None})
        d += timedelta(days=1)
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--start", default="2018-09-01")
    p.add_argument("--end", default="2026-12-31")
    args = p.parse_args()
    raw = Path(args.raw).read_bytes()
    rows = build(raw, date.fromisoformat(args.start), date.fromisoformat(args.end))
    mismatches = validate_2026(rows)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "trading_calendar.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (out / "calendar_rows.json").write_text(json.dumps(rows, separators=(",", ":")))
    manifest = {
        "source_id": "sina_sse_trade_calendar", "dataset_code": "trading_calendar",
        "source_url": "https://finance.sina.com.cn/realstock/company/klc_td_sh.txt",
        "source_version": "sina-klc-td-sh:akshare-1.18.97:fast-close-v1",
        "response_checksum": hashlib.sha256(raw).hexdigest(),
        "calendar_checksum": hashlib.sha256((out / "trading_calendar.csv").read_bytes()).hexdigest(),
        "decoder": "akshare==1.18.97 hk_js_decode; py_mini_racer",
        "first_date": rows[0]["cal_date"], "last_date": rows[-1]["cal_date"],
        "dense_rows": len(rows), "open_rows": sum(r["is_open"] for r in rows),
        "exchange": "SSE", "market_calendar_reference": "SSE",
        "other_exchange_calendar_claim": False,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "pit_level": "effective_pit", "knowledge_time_unverified": True,
        "future_unknown_policy": "out_of_range_is_error_not_closed",
        "official_2026_crosscheck": "https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml",
        "official_2026_mismatch_count": mismatches,
    }
    (out / "calendar_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
