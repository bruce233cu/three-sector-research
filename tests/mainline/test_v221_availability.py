"""Regression checks for NULL policy, old-version isolation and core Freeze."""
import unittest
from datetime import date, timedelta

import pandas as pd

from mainline.metrics.availability import calculate_v221_snapshot
from mainline.metrics.sector import SectorMetricInput, calculate_sector_snapshot


class AvailabilityTest(unittest.TestCase):
    def value(self, missing=False):
        dates = tuple(date(2025, 1, 1) + timedelta(days=i) for i in range(60))
        rows = [dict(security_id=sid, trade_date=d, close=10+i/10,
                     amount=100, pct_chg=1, circ_mv=1000)
                for i, d in enumerate(dates) for sid in ("A", "B", "C")]
        if missing:
            rows = [r for r in rows if r["security_id"] == "A"]
        return SectorMetricInput(dates[-1], "test", "test", "test",
                                 ("A", "B", "C"), pd.DataFrame(rows),
                                 pd.Series(0.001, index=dates),
                                 pd.Series(1000., index=dates),
                                 pd.Series(10000., index=dates), dates)

    def test_deferred_never_uses_input_market_cap_and_preserves_core(self):
        value = self.value()
        old = calculate_sector_snapshot(value)
        new = calculate_v221_snapshot(value)
        self.assertIsNotNone(old["turnover_cap_deviation"])
        self.assertIsNotNone(old["top3_return_contribution"])
        for key in ("turnover_cap_deviation", "top3_return_contribution"):
            self.assertIsNone(new[key])
            self.assertEqual(new["metric_coverage_json"][key], 0)
        for key in ("sector_return", "rs_20", "above_ma60", "turnover_share"):
            self.assertEqual(new[key], old[key])
        self.assertFalse(new["stage_frozen"])
        self.assertEqual(new, calculate_v221_snapshot(value))
        self.assertEqual(old, calculate_sector_snapshot(value))
        self.assertEqual(value.member_bars.circ_mv.iloc[0], 1000)
        self.assertEqual(new["rule_version"], "mainline_v2.2.1")
        self.assertIn("metric_availability_version", new["decision_reason"])

    def test_core_missing_still_freezes(self):
        result = calculate_v221_snapshot(self.value(missing=True))
        self.assertTrue(result["stage_frozen"])
        self.assertFalse(result["critical_data_ok"])
        self.assertIsNone(result["sector_return"])
        self.assertIsNone(result["above_ma60"])
        self.assertNotIn("circ_mv", result["freeze_reason"])


if __name__ == "__main__":
    unittest.main()
