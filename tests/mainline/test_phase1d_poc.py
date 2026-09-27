from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mainline.cache import ParquetDuckDBCache
from mainline.metrics import SectorMetricInput, calculate_sector_snapshot
from mainline.providers.baostock_window import BaostockWindowProvider


def bars(member_count: int = 10, periods: int = 65) -> pd.DataFrame:
    dates = pd.bdate_range(end="2025-06-30", periods=periods)
    rows = []
    for member in range(member_count):
        for index, trade_date in enumerate(dates):
            rows.append({
                "security_id": f"X{member:03d}.SZ", "trade_date": trade_date.date(),
                "close": 10 + member + index / 100, "amount": 1000 + member * 10,
                "pct_chg": 1.0 if member < 6 else -0.5,
                "circ_mv": 100000 + member * 1000,
            })
    return pd.DataFrame(rows)


class Phase1DPocTests(unittest.TestCase):
    def metric_input(self, frame: pd.DataFrame | None = None) -> SectorMetricInput:
        frame = bars() if frame is None else frame
        benchmark = pd.Series(0.001, index=pd.bdate_range(end="2025-06-30", periods=65).date)
        amounts = pd.Series(1_000_000.0, index=pd.bdate_range(end="2025-06-30", periods=65).date)
        cap = pd.Series(10_000_000.0, index=pd.bdate_range(end="2025-06-30", periods=65).date)
        return SectorMetricInput(date(2025, 6, 30), "sw1_test", "test", "SW2021", tuple(f"X{i:03d}.SZ" for i in range(10)), frame, benchmark, amounts, cap)

    def test_objective_metrics_are_computed_without_status(self):
        result = calculate_sector_snapshot(self.metric_input())
        self.assertAlmostEqual(result["sector_return"], 0.004, places=9)
        self.assertEqual(result["up_ratio"], 0.6)
        self.assertIsNotNone(result["rs_20"])
        self.assertIsNotNone(result["turnover_intensity"])
        self.assertFalse(result["stage_frozen"])

    def test_suspended_member_is_excluded_not_zeroed(self):
        frame = bars()
        mask = (frame.security_id == "X000.SZ") & (frame.trade_date == date(2025, 6, 30))
        frame.loc[mask, ["amount", "pct_chg"]] = [0, None]
        result = calculate_sector_snapshot(self.metric_input(frame))
        self.assertEqual(result["valid_member_count"], 9)
        self.assertAlmostEqual(result["metric_coverage_json"]["sector_return"], 0.9)

    def test_new_stock_with_fifteen_days_is_not_false_in_ma20(self):
        frame = bars()
        frame = frame[~((frame.security_id == "X009.SZ") & (frame.trade_date < sorted(frame.trade_date.unique())[-15]))]
        result = calculate_sector_snapshot(self.metric_input(frame))
        self.assertEqual(result["metric_coverage_json"]["above_ma20"], 0.9)

    def test_missing_member_data_freezes_and_remains_null(self):
        frame = bars()
        frame = frame[frame.security_id.isin(["X000.SZ", "X001.SZ", "X002.SZ", "X003.SZ", "X004.SZ", "X005.SZ"])]
        result = calculate_sector_snapshot(self.metric_input(frame))
        self.assertIsNone(result["sector_return"])
        self.assertTrue(result["stage_frozen"])
        self.assertIn("sector_return_coverage", result["freeze_reason"])

    def test_no_positive_contribution_is_null(self):
        frame = bars()
        frame["pct_chg"] = -1.0
        result = calculate_sector_snapshot(self.metric_input(frame))
        self.assertIsNone(result["top3_return_contribution"])

    def test_schema_anomaly_fails_closed(self):
        frame = bars().drop(columns=["amount"])
        with self.assertRaisesRegex(ValueError, "amount"):
            calculate_sector_snapshot(self.metric_input(frame))

    def test_parquet_cache_is_checksummed_and_duckdb_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = ParquetDuckDBCache(directory)
            artifact = cache.put("bars", "a", bars(2, 3), source_id="fixture", source_version="fixture:v1", fetched_at=datetime.now(timezone.utc))
            restored = cache.read(artifact)
            self.assertEqual(len(restored), 6)
            self.assertEqual(len(artifact.checksum_sha256), 64)

    def test_phase1d_migration_does_not_create_state(self):
        sql = (ROOT / "supabase/migrations/202609270001_mainline_phase1d_objective_snapshots.sql").read_text()
        self.assertIn("hard_status drop not null", sql)
        self.assertIn("pit_level", sql)
        self.assertNotIn("update mainline.daily_mainline_snapshot set hard_status", sql.lower())

    def test_baostock_backup_rejects_unsupported_exchange_without_fabricating_rows(self):
        provider = object.__new__(BaostockWindowProvider)
        result = provider.get_one("830001.BJ", date(2025, 1, 1), date(2025, 6, 30))
        self.assertTrue(result.empty)

    def test_baostock_free_float_market_cap_derivation_preserves_units(self):
        class Result:
            error_code = "0"
            error_msg = ""

            def __init__(self):
                self.done = False

            def next(self):
                if self.done:
                    return False
                self.done = True
                return True

            def get_row_data(self):
                return ["2025-06-30", "sz.000001", "10", "11", "9", "10", "1000000", "10000000", "1", "2", "1"]

        class Client:
            def query_history_k_data_plus(self, *args, **kwargs):
                return Result()

        provider = object.__new__(BaostockWindowProvider)
        provider.bs = Client()
        result = provider.get_one("000001.SZ", date(2025, 6, 30), date(2025, 6, 30))
        self.assertEqual(float(result.iloc[0]["circ_mv"]), 500_000_000.0)


if __name__ == "__main__":
    unittest.main()
