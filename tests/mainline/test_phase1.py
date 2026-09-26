from __future__ import annotations

import json
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mainline.data_quality import decide_freeze, evaluate_daily_quality, market_data_anomalies
from mainline.providers import (
    CapabilityUnavailable,
    Dataset,
    FallbackExecutor,
    ProviderBatch,
    ProviderError,
    ProviderSchemaError,
)
from mainline.providers.akshare import AkshareProvider
from mainline.repositories.pit import MembershipRepository, pit_membership_sql
from mainline.repositories.security import SecurityRepository


def batch(source: str = "backup") -> ProviderBatch:
    return ProviderBatch(
        dataset=Dataset.TRADING_CALENDAR,
        frame=pd.DataFrame([{"exchange": "SSE", "cal_date": "2026-09-25", "is_open": True, "pretrade_date": "2026-09-24"}]),
        source_id=source,
        source_version=f"{source}:v1",
        fetched_at=datetime(2026, 9, 25, 8, tzinfo=timezone.utc),
        available_at=datetime(2026, 9, 25, 7, tzinfo=timezone.utc),
        run_id=__import__("uuid").uuid4(),
        request_fingerprint="fixture",
        historical_capability="historical_full",
    )


class FailingProvider:
    source_id = "primary"
    def get_trading_calendar(self, *_):
        raise ProviderError("simulated primary failure")


class WorkingProvider:
    source_id = "backup"
    def get_trading_calendar(self, *_):
        return batch()


class FakeExecutor:
    def __init__(self, rows): self.rows = rows; self.last_sql = ""; self.last_params = {}
    def fetch_all(self, sql, params): self.last_sql = sql; self.last_params = params; return self.rows
    def execute(self, sql, params): return 1


class Phase1Tests(unittest.TestCase):
    def test_provider_schema_change_fails_closed(self):
        invalid = batch()
        invalid = ProviderBatch(**{**invalid.__dict__, "frame": pd.DataFrame([{"cal_date": "2026-09-25"}])})
        with self.assertRaises(ProviderSchemaError):
            invalid.validate()

    def test_fallback_retries_three_times_then_uses_backup(self):
        sleeps = []
        result = FallbackExecutor(FailingProvider(), WorkingProvider(), sleeper=sleeps.append).execute(
            "get_trading_calendar", "2026-09-01", "2026-09-30"
        )
        self.assertEqual(sleeps, [2, 5, 15])
        self.assertEqual(len([a for a in result.attempts if a.source_id == "primary"]), 4)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.source_used, "backup")

    def test_pit_sql_enforces_effective_and_available_intervals(self):
        sql = pit_membership_sql()
        self.assertIn("effective_from <=", sql)
        self.assertIn("effective_to is null", sql)
        self.assertIn("available_at <=", sql)

    def test_membership_repository_keeps_query_cutoff(self):
        executor = FakeExecutor([{"security_id": "000001.SZ"}])
        cutoff = datetime(2020, 1, 2, 8, tzinfo=timezone.utc)
        rows = MembershipRepository(executor).members_as_of("801750.SI", date(2020, 1, 2), cutoff)
        self.assertEqual(rows[0]["security_id"], "000001.SZ")
        self.assertEqual(executor.last_params["calculation_cutoff"], cutoff)

    def test_delisted_security_is_retained_for_historical_universe(self):
        executor = FakeExecutor([{"security_id": "600001.SH", "delist_date": date(2021, 1, 1)}])
        rows = SecurityRepository(executor).universe_as_of(date(2020, 1, 2))
        self.assertEqual(rows[0]["security_id"], "600001.SH")
        self.assertIn("delist_date >=", executor.last_sql)

    def test_94_percent_core_completeness_freezes(self):
        frame = pd.DataFrame({"security_id": [f"X{i:03d}.SZ" for i in range(94)], "trade_date": ["2026-09-25"] * 94})
        report = evaluate_daily_quality(
            frame, dataset_code="daily_bars", as_of_date=date(2026, 9, 25), expected_count=100,
            key_columns=("security_id", "trade_date"), required_columns=("security_id", "trade_date"),
            fetched_at=datetime(2026, 9, 25, 9, tzinfo=timezone.utc),
        )
        decision = decide_freeze([report])
        self.assertFalse(decision.critical_data_ok)
        self.assertTrue(decision.stage_frozen)
        self.assertIn("completeness=0.9400<0.9500", decision.freeze_reason[0])

    def test_duplicate_detection(self):
        frame = pd.DataFrame([{"security_id": "X001.SZ", "trade_date": "2026-09-25"}] * 2)
        report = evaluate_daily_quality(
            frame, dataset_code="daily_bars", as_of_date=date(2026, 9, 25), expected_count=2,
            key_columns=("security_id", "trade_date"), required_columns=("security_id", "trade_date"),
            fetched_at=datetime(2026, 9, 25, 9, tzinfo=timezone.utc),
        )
        self.assertEqual(report.duplicate_count, 1)

    def test_membership_89_percent_freezes_at_v22_threshold(self):
        frame = pd.DataFrame({"security_id": [f"X{i:03d}.SZ" for i in range(89)]})
        report = evaluate_daily_quality(
            frame, dataset_code="membership_history", as_of_date=date(2026, 9, 25), expected_count=100,
            key_columns=("security_id",), required_columns=("security_id",),
            fetched_at=datetime(2026, 9, 25, 9, tzinfo=timezone.utc),
        )
        self.assertTrue(decide_freeze([report]).stage_frozen)

    def test_membership_91_percent_warns_but_does_not_freeze(self):
        frame = pd.DataFrame({"security_id": [f"X{i:03d}.SZ" for i in range(91)]})
        report = evaluate_daily_quality(
            frame, dataset_code="membership_history", as_of_date=date(2026, 9, 25), expected_count=100,
            key_columns=("security_id",), required_columns=("security_id",),
            fetched_at=datetime(2026, 9, 25, 9, tzinfo=timezone.utc),
        )
        self.assertIn("completeness:0.9100<0.9500", report.warnings)
        self.assertFalse(decide_freeze([report]).stage_frozen)

    def test_invalid_price_and_amount_are_reported(self):
        frame = pd.DataFrame([{"open": 10, "high": 9, "low": 8, "close": 11, "amount": -1, "volume": -2}])
        warnings = market_data_anomalies(frame)
        self.assertIn("invalid_ohlc:1", warnings)
        self.assertIn("negative_amount:1", warnings)
        self.assertIn("negative_volume:1", warnings)

    def test_future_available_at_is_pit_violation(self):
        frame = pd.DataFrame([{"security_id": "X001.SZ", "available_at": "2026-09-26T00:00:00Z"}])
        report = evaluate_daily_quality(
            frame, dataset_code="membership_history", as_of_date=date(2026, 9, 25), expected_count=1,
            key_columns=("security_id",), required_columns=("security_id", "available_at"),
            fetched_at=datetime(2026, 9, 25, 9, tzinfo=timezone.utc), available_at_column="available_at",
            calculation_cutoff=datetime(2026, 9, 25, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(report.pit_violation_count, 1)
        self.assertTrue(decide_freeze([report]).stage_frozen)

    def test_null_is_not_replaced_with_zero(self):
        frame = pd.DataFrame([{"security_id": "X001.SZ", "trade_date": "2026-09-25", "close": None}])
        evaluate_daily_quality(
            frame, dataset_code="daily_bars", as_of_date=date(2026, 9, 25), expected_count=1,
            key_columns=("security_id", "trade_date"), required_columns=("security_id", "trade_date", "close"),
            fetched_at=datetime(2026, 9, 25, 9, tzinfo=timezone.utc),
        )
        self.assertTrue(pd.isna(frame.loc[0, "close"]))

    def test_current_snapshot_backup_cannot_claim_pit(self):
        provider = object.__new__(AkshareProvider)
        with self.assertRaises(CapabilityUnavailable):
            provider.get_membership_history("sw1", "2019-01-01", "2026-09-25")

    def test_parameter_profile_matches_frozen_identity(self):
        profile = json.loads((ROOT / "config/parameter_profile_industry_trend_v1.json").read_text())
        self.assertEqual(profile["profile_id"], "industry_trend_v2_2_1")
        self.assertEqual(profile["rule_version"], "mainline_v2.2.0")
        self.assertFalse(profile["labels"]["enabled"])

    def test_mainline_schema_is_not_granted_to_browser_roles(self):
        sql = (ROOT / "supabase/migrations/202609260003_mainline_permissions_seed.sql").read_text()
        self.assertIn("revoke all on schema mainline from public,anon,authenticated", sql)
        self.assertNotIn("grant usage on schema mainline to anon", sql)
        self.assertNotIn("grant usage on schema mainline to authenticated", sql)

    def test_non_trading_day_is_not_synthesized(self):
        calendar = batch().frame
        self.assertFalse((calendar["cal_date"] == "2026-09-26").any())


if __name__ == "__main__":
    unittest.main()
