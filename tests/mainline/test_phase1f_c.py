"""Synthetic OFFLINE tests; never evidence of provider success."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
# Work runtime lacks requests. This stub is ONLY in offline tests and forbids
# calls; external installation uses pinned real requests.
if importlib.util.find_spec("requests") is None:
    stub = types.ModuleType("requests")
    def denied(*a,**k):
        raise AssertionError("offline test attempted network")
    stub.get = denied
    sys.modules["requests"] = stub

import pandas as pd
from mainline.poc.phase1f_c import (preflight, calculate, digest, clean, compare, stats,
                                  finalize, verify_results, main, health_check,
                                  run_sample, IsolatedClient)
from mainline.providers.phase1f_free import normalize, TdxWindow, SinaWindow
from mainline.providers.sws_history import MembershipSnapshot

BUNDLE = ROOT/"scripts/mainline/phase1f_c"


def fixture(n=4):
    d = date(2025,6,30)
    dates = [x.date() for x in pd.bdate_range(end=d,periods=61)]
    ids = [f"{i:06}.SZ" for i in range(n)]
    f = pd.DataFrame({"security_id":ids,"security_code":[x[:6] for x in ids],
        "effective_from":date(2014,1,1),"effective_to":None,"industry_code":"x"})
    m = MembershipSnapshot(d,"801080","电子","SW2021",f,"test-only","effective_pit",True)
    rows=[]
    for sid in ids:
        for i,t in enumerate(dates):
            rows.append({"security_id":sid,"trade_date":t,"open":10+i*.01,"high":11+i*.01,
                "low":9+i*.01,"close":10+i*.01,"volume":1000.,"amount":10000.+i*10,
                "pct_chg":.1,"circ_mv":float("nan")})
    b=pd.DataFrame({"trade_date":dates,"close":100.,"amount":1e6,"pct_chg":.02})
    s={"sample_id":f"{d}:801080","trade_date":str(d),"industry_name":"电子",
       "taxonomy_code":"801080","object_id":"sw1_801080","member_count":n}
    return s,m,pd.DataFrame(rows),b


class OfflineTests(unittest.TestCase):
    def test_immutable_membership_counts(self):
        c,s,i=preflight(ROOT,BUNDLE)
        self.assertEqual([len(x.frame) for x in s],[189,472,491])
        self.assertTrue(all(x.knowledge_time_unverified for x in s))
        self.assertEqual(c["provider_order"],["TDX","Sina"])

    def test_preflight_no_network(self):
        with patch.object(sys,"argv",["run.py","--preflight"]):
            self.assertEqual(main(ROOT,BUNDLE),0)

    def test_external_guard(self):
        with patch.object(sys,"argv",["run.py"]), self.assertRaises(SystemExit):
            main(ROOT,BUNDLE)

    def test_full_window_and_circ_mv_gap(self):
        r=calculate(*fixture())
        self.assertTrue(r["market_window_pass"])
        self.assertEqual(r["MA60_coverage"],1.)
        self.assertIsNone(r["top3_return_contribution"])
        self.assertIsNone(r["turnover_cap_deviation"])
        self.assertFalse(r["full_metric_set_complete"])
        self.assertFalse(r["stage_frozen"])

    def test_missing_member_freezes_no_zero(self):
        s,m,f,b=fixture()
        f=f[f.security_id.isin(m.frame.security_id.iloc[:2])]
        r=calculate(s,m,f,b)
        self.assertEqual(r["MA60_coverage"],.5)
        self.assertTrue(r["stage_frozen"])
        self.assertIsNone(r["above_ma60"])
        self.assertFalse(r["market_window_pass"])

    def test_new_stock_history_insufficient(self):
        s,m,f,b=fixture()
        f=f[(f.security_id != "000000.SZ") | (f.trade_date >= sorted(f.trade_date.unique())[-10])]
        r=calculate(s,m,f,b)
        self.assertEqual(r["MA60_coverage"],.75)

    def test_missing_session_does_not_pull_older_price(self):
        s,m,f,b=fixture()
        missing=sorted(f.trade_date.unique())[-3]
        f=f[~((f.security_id=="000000.SZ") & (f.trade_date==missing))]
        r=calculate(s,m,f,b)
        self.assertEqual(r["MA60_coverage"],.75)
        self.assertTrue(r["frozen_coverage_agrees_with_exact_window"])
        self.assertTrue(r["market_window_pass"])

    def test_future_row_rejected(self):
        s,m,f,b=fixture()
        f.loc[0,"trade_date"]=m.trade_date+timedelta(days=1)
        with self.assertRaises(ValueError): calculate(s,m,f,b)

    def test_future_member_rejected(self):
        s,m,f,b=fixture()
        f.loc[0,"security_id"]="future.SZ"
        with self.assertRaises(ValueError): calculate(s,m,f,b)

    def test_no_target_benchmark_rejected(self):
        s,m,f,b=fixture()
        with self.assertRaises(ValueError): calculate(s,m,f,b.iloc[:-1])

    def test_normalization_no_ffill(self):
        d=date(2025,6,30)
        raw=[{"date":d-timedelta(days=3),"open":10,"high":11,"low":9,"close":10,"volume":1000,"amount":10000},
             {"date":d,"open":10,"high":11,"low":9,"close":None,"volume":1000,"amount":10000}]
        f,a=normalize(raw,"000001.SZ",d-timedelta(days=5),d)
        self.assertTrue(pd.isna(f.iloc[-1].close))
        self.assertTrue(pd.isna(f.iloc[-1].pct_chg))
        self.assertTrue(f.circ_mv.isna().all())

    def test_suspension_placeholder_not_inserted(self):
        d=date(2025,6,30)
        raw=[{"date":d,"open":10,"high":10,"low":10,"close":10,"volume":0,"amount":0}]
        f,a=normalize(raw,"000001.SZ",d-timedelta(days=5),d)
        self.assertTrue(f.empty)
        self.assertEqual(a["no_trade_rows"],1)

    def test_tdx_volume_units(self):
        d=date(2025,6,30)
        raw=[{"datetime":str(d),"open":10,"high":11,"low":9,"close":10,"vol":10,"amount":10000}]
        f,a=normalize(raw,"000001.SZ",d-timedelta(days=5),d,100)
        self.assertTrue(a["unit_check_ok"])
        self.assertEqual(f.iloc[0].volume,1000)

    def test_wrong_units_fail(self):
        d=date(2025,6,30)
        raw=[{"date":d,"open":10,"high":11,"low":9,"close":10,"volume":10,"amount":10000}]
        f,a=normalize(raw,"000001.SZ",d-timedelta(days=5),d)
        self.assertFalse(a["unit_check_ok"])

    def test_duplicate_date_and_bad_ohlc(self):
        d=date(2025,6,30)
        r={"date":d,"open":10,"high":11,"low":9,"close":10,"volume":1000,"amount":10000}
        with self.assertRaises(ValueError): normalize([r,r],"000001.SZ",d,d)
        r["low"]=12
        with self.assertRaises(ValueError): normalize([r],"000001.SZ",d,d)

    def test_replay_equal_and_provider_error_difference(self):
        r=calculate(*fixture())
        self.assertTrue(compare(r,r)["identical"])
        changed={**r,"error_count":1}
        self.assertFalse(compare(r,changed)["identical"])

    def test_json_null_not_nan(self):
        self.assertEqual(clean({"x":float("nan"),"y":pd.NA}),{"x":None,"y":None})

    def test_stats_distinguish_empty_timeout(self):
        r=stats([{"ok":False,"error":"empty"},{"ok":False,"error":"timeout:test"},{"ok":True}])
        self.assertEqual(r["request_count"],3)
        self.assertEqual(r["empty_result_count"],1)
        self.assertEqual(r["timeout_count"],1)

    def test_result_bundle_integrity(self):
        r=calculate(*fixture())
        r.update(run_id="synthetic",source_snapshot_ids=[])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            finalize(p,{"status":"SYNTHETIC_TEST_ONLY"},[r],[],[],[],{"git_sha":"test"},{})
            self.assertTrue(verify_results(p)["checksums_ok"])
            self.assertTrue((p/"phase1f_c_results.zip").is_file())
            (p/"summary.json").write_text("{}")
            with self.assertRaises(ValueError): verify_results(p)

    def test_tdx_pagination_and_date_filter(self):
        class API:
            def __init__(self): self.calls=[]
            def get_security_bars(self,*args):
                self.calls.append(args)
                d="2026-06-30" if len(self.calls)==1 else "2019-06-28"
                return [{"datetime":d,"open":10,"high":11,"low":9,"close":10,"vol":10,"amount":10000},
                        {"datetime":"2019-01-01" if len(self.calls)>1 else "2026-01-01",
                         "open":10,"high":11,"low":9,"close":10,"vol":10,"amount":10000}]
        p=TdxWindow.__new__(TdxWindow)
        p.config={"max_tdx_pages":16};p.api=API();p.endpoint={"host":"test-only","port":7709}
        f,a=p.get_one("000001.SZ",date(2019,3,1),date(2019,6,28))
        self.assertEqual(a["page_requests"],2)
        self.assertEqual(f.trade_date.max(),date(2019,6,28))
        self.assertEqual(len(f),1)
        self.assertEqual(p.api.calls[1][-2],800)

    def test_health_rejects_random_difference(self):
        s,m,f,b=fixture()
        class Client:
            name="SYNTHETIC";info={"library_version":"test"}
            def __init__(self): self.n=0
            def fetch(self,sid,start,end,budget=None):
                self.n+=1
                rows=f[f.security_id==sid].copy()
                if self.n%2==0: rows.loc[rows.index[-1],"amount"]+=1
                return {"ok":True,"frame":rows,"audit":{"unit_check_ok":True}}
        h=health_check(Client(),{"health_min_success_ratio":.8},[m,m,m])
        self.assertFalse(h["health_pass"])

    def test_cleanup_rejects_project_root(self):
        with patch.object(sys,"argv",["run.py","--clean-cache",str(ROOT)]),self.assertRaises(ValueError):
            main(ROOT,BUNDLE)

    def test_isolated_fetch_timeout_terminates_worker(self):
        client=IsolatedClient("SYNTHETIC",{"timeout_seconds":.01})
        pipe=unittest.mock.MagicMock()
        pipe.poll.return_value=False
        client.pipe=pipe
        with patch.object(client,"start",return_value={"ok":True}),patch.object(client,"close") as close:
            r=client.fetch("000001.SZ",date(2025,1,1),date(2025,6,30))
            self.assertIn("timeout",r["error"])
            close.assert_called_once()

    def test_bounded_pagination_nonprogress(self):
        class API:
            def get_security_bars(self,*args):
                return [{"datetime":"2026-01-01","open":10,"high":11,"low":9,"close":10,"vol":10,"amount":10000}]
        p=TdxWindow.__new__(TdxWindow);p.config={"max_tdx_pages":16};p.api=API();p.endpoint={}
        with self.assertRaisesRegex(RuntimeError,"pagination not progressing"):
            p.get_one("000001.SZ",date(2019,3,1),date(2019,6,28))

    def test_synthetic_two_fresh_rounds_and_cache(self):
        s,m,f,b=fixture()
        class Client:
            name="SYNTHETIC";info={"library_version":"test","endpoint":"offline"}
            def __init__(self): self.calls=0
            def fetch(self,sid,start,end,budget=None):
                self.calls+=1
                return {"ok":True,"frame":f[f.security_id==sid].copy(),
                        "audit":{"unit_check_ok":True,"page_requests":1}}
        client=Client()
        config={"sample_budget_seconds":5,"window_calendar_days":120}
        import time
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            first,err,src=run_sample(client,config,s,m,b,p,time.monotonic()+10,1)
            second,err2,src2=run_sample(client,config,s,m,b,p,time.monotonic()+10,2)
            self.assertEqual(client.calls,8)
            self.assertTrue(first["same_input_recompute_identical"])
            self.assertTrue(compare(first,second)["identical"])
            self.assertEqual(len(list((p/"cache").rglob("*.json"))),8)


if __name__ == "__main__":
    unittest.main()
