import unittest
from datetime import date
import pandas as pd
from mainline.metrics.benchmark import calculate_benchmark_day, calculate_v221_with_benchmark
from mainline.metrics.sector import SectorMetricInput

class BenchmarkContractTest(unittest.TestCase):
    def inputs(self, valid):
        u = pd.DataFrame({"security_id": [str(i) for i in range(100)], "share_type": "A",
                          "list_date": "2010-01-01", "delist_date": None})
        b = pd.DataFrame({"security_id": [str(i) for i in range(valid)],
                          "daily_return": [.01] * valid, "amount": [10.] * valid})
        return u, b

    def compute(self, u, b, **kw):
        return calculate_benchmark_day(date(2020,1,2),u,b,universe_verified=True,
                                       returns_verified=True,**kw)

    def test_exact_threshold(self):
        self.assertAlmostEqual(self.compute(*self.inputs(95)).benchmark_return,.01)
        below=self.compute(*self.inputs(94))
        self.assertIsNone(below.benchmark_return)
        self.assertEqual(below.benchmark_coverage,.94)

    def test_unknown_universe(self):
        u,b=self.inputs(100)
        r=calculate_benchmark_day(date(2020,1,2),u,b,universe_verified=False,returns_verified=True)
        self.assertIsNone(r.benchmark_coverage)
        self.assertIsNone(r.benchmark_return)

    def test_historical_and_share_type(self):
        u,b=self.inputs(100)
        u.loc[0,'list_date']='2021-01-01'
        u.loc[1,'share_type']='B'
        u.loc[2,'delist_date']='2020-01-01'
        u.loc[3,'delist_date']='2020-01-02'
        r=self.compute(u,b)
        self.assertEqual(r.universe_count,97)
        self.assertEqual(r.valid_count,97)

    def test_missing_not_zero_and_duplicate_rejected(self):
        u,b=self.inputs(95)
        b.loc[0,'amount']=0
        self.assertIsNone(self.compute(u,b).benchmark_return)
        with self.assertRaises(ValueError): self.compute(u,pd.concat([b,b.iloc[:1]]))

    def test_equal_weight_and_nonfinite(self):
        u,b=self.inputs(100)
        b.loc[0,'amount']=1e9
        b.loc[0,'daily_return']=.11
        self.assertAlmostEqual(self.compute(u,b).benchmark_return,.011)
        b.loc[:5,'daily_return']=float('inf')
        self.assertIsNone(self.compute(u,b).benchmark_return)

    def test_freeze_exact_window_and_repeatability(self):
        dates=tuple(pd.bdate_range('2019-10-01',periods=60).date)
        u,b=self.inputs(100)
        days=[calculate_benchmark_day(d,u,b,universe_verified=True,returns_verified=True) for d in dates]
        bars=pd.DataFrame([{'security_id':'0','trade_date':d,'close':100+i,'amount':10.,'pct_chg':1.}
                           for i,d in enumerate(dates)])
        v=SectorMetricInput(dates[-1],'test','test','test',('0',),bars,pd.Series({dates[-1]:.5}),
                            market_trading_dates=dates)
        good=calculate_v221_with_benchmark(v,days)
        self.assertAlmostEqual(good['benchmark_return'],.01)
        self.assertEqual(good['rs_20'],0.)
        self.assertEqual(good,calculate_v221_with_benchmark(v,days))
        # Three missing dates in the exact 20-day window must not stretch backward.
        bad_days=days[:-3]+[calculate_benchmark_day(d,u,b.iloc[:94],universe_verified=True,
                                                  returns_verified=True) for d in dates[-3:]]
        bad=calculate_v221_with_benchmark(v,bad_days)
        self.assertIsNone(bad['benchmark_return'])
        self.assertIsNone(bad['rs_20'])
        self.assertEqual(bad['metric_coverage_json']['rs_20'],.85)
        self.assertTrue(bad['stage_frozen'])
        self.assertIsNone(bad['turnover_cap_deviation'])

if __name__=='__main__': unittest.main()
