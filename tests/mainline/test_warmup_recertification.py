import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "warmup_recertification", ROOT / "scripts/mainline/backtest_recertify_warmup.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WarmupRecertificationTest(unittest.TestCase):
    def frame(self):
        return pd.DataFrame([{
            "security_id": "000001.SZ", "trade_date": "2024-05-06",
            "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2,
            "volume": 1000.0, "amount": 10200.0, "pct_chg": 2.0,
            "circ_mv": float("nan"),
        }])

    def test_new_response_may_differ_but_is_never_called_old_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            response = b"current-provider-response"
            audit = {"unit_check_ok": True, "no_trade_dates": [],
                     "response_checksum": MODULE.sha_bytes(response)}
            def fake_parquet(frame, target, **kwargs):
                Path(target).touch()
            with patch.object(MODULE, "fetch_decode", return_value=(self.frame(), audit, response)), \
                    patch.object(pd.DataFrame, "to_parquet", fake_parquet):
                frame, result = MODULE.recertify_one(
                    "000001.SZ", {"raw_payload_checksum": "old-checksum"}, Path(folder),
                    MODULE.date(2024, 4, 30), MODULE.date(2024, 8, 30), ["2024-05-06"]
                )
            self.assertEqual(len(frame), 1)
            self.assertEqual(result["status"], "success")
            self.assertFalse(result["matches_old_certified_response"])
            self.assertEqual(result["certification_relation"], "NEW_DATA_VERSION_NOT_OLD_RECOVERY")
            self.assertEqual((Path(folder) / "000001.SZ.response.bin").read_bytes(), response)

    def test_cached_raw_and_normalized_checksums_are_enforced(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            frame = self.frame().drop(columns=["circ_mv"])
            (path / "000001.SZ.parquet").touch()
            raw = b"current-provider-response"
            (path / "000001.SZ.response.bin").write_bytes(raw)
            audit = {"unit_check_ok": True, "no_trade_dates": [],
                     "response_checksum": MODULE.sha_bytes(raw),
                     "normalized_checksum": MODULE.digest(
                         frame.astype(object).where(pd.notna(frame), None).to_dict("records")
                     )}
            (path / "000001.SZ.json").write_text(json.dumps(audit))
            with patch.object(MODULE, "fetch_decode") as fetch, \
                    patch.object(pd, "read_parquet", return_value=frame):
                loaded, result = MODULE.recertify_one(
                    "000001.SZ", {"raw_payload_checksum": "old-checksum"}, path,
                    MODULE.date(2024, 4, 30), MODULE.date(2024, 8, 30), ["2024-05-06"]
                )
            fetch.assert_not_called()
            self.assertEqual(len(loaded), 1)
            self.assertTrue(result["cache_reused"])
            self.assertEqual(result["request_count"], 0)

    def test_old_failed_source_without_checksum_can_enter_new_version(self):
        with tempfile.TemporaryDirectory() as folder:
            response = b"newly-certifiable-provider-response"
            audit = {"unit_check_ok": True, "no_trade_dates": [],
                     "response_checksum": MODULE.sha_bytes(response)}
            def fake_parquet(frame, target, **kwargs):
                Path(target).touch()
            with patch.object(MODULE, "fetch_decode", return_value=(self.frame(), audit, response)), \
                    patch.object(pd.DataFrame, "to_parquet", fake_parquet):
                frame, result = MODULE.recertify_one(
                    "000001.SZ", {"status": "failed"}, Path(folder),
                    MODULE.date(2024, 4, 30), MODULE.date(2024, 8, 30), ["2024-05-06"]
                )
            self.assertEqual(len(frame), 1)
            self.assertIsNone(result["old_certified_response_checksum"])
            self.assertFalse(result["matches_old_certified_response"])
            self.assertEqual(result["status"], "success")

    def test_old_explicit_provider_failure_stays_null_when_current_response_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            empty = self.frame().iloc[:0]
            response = b"current-empty-provider-response"
            audit = {"unit_check_ok": False, "no_trade_dates": [],
                     "response_checksum": MODULE.sha_bytes(response)}
            def fake_parquet(frame, target, **kwargs):
                Path(target).touch()
            with patch.object(MODULE, "fetch_decode", return_value=(empty, audit, response)), \
                    patch.object(pd.DataFrame, "to_parquet", fake_parquet):
                frame, result = MODULE.recertify_one(
                    "000416.SZ", {"status": "failed"}, Path(folder),
                    MODULE.date(2024, 4, 30), MODULE.date(2024, 8, 30), ["2024-05-06"]
                )
            self.assertTrue(frame.empty)
            self.assertEqual(result["status"], "valid_provider_unavailable_preserved_null")
            self.assertNotEqual(result["status"], "success")


if __name__ == "__main__":
    unittest.main()
