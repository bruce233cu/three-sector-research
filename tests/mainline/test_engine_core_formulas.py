"""Analytical fixtures cover preserved G1 formulas; no provider calls."""
import unittest
from dataclasses import replace
from datetime import date
import pandas as pd
from mainline.metrics.availability import calculate_v221_snapshot
from mainline.metrics.sector import SectorMetricInput

class CoreFormulaTest(unittest.TestCase):
    def setUp(self):
        self.days=tuple(pd.bdate_range('2020-01-02',periods=60).date)
        bars=pd.DataFrame([{'security_id':str(s),'trade_date':d,'close':10+i,
                           'amount':100*(s+1),'pct_chg':s+1} for i,d in enumerate(self.days) for s in range(3)])
        self.v=SectorMetricInput(self.days[-1],'fixture','fixture','fixture',('0','1','2'),bars,
            pd.Series(.01,index=self.days),pd.Series(1000.,index=self.days),market_trading_dates=self.days)
    def test_sector_and_rs_formula(self):
        r=calculate_v221_snapshot(self.v);self.assertAlmostEqual(r['sector_return'],.02)
        for n in [5,10,20]:self.assertAlmostEqual(r['rs_'+str(n)],1.02**n-1.01**n)
    def test_turnover_formula(self):
        r=calculate_v221_snapshot(self.v);self.assertAlmostEqual(r['turnover_share'],.6);self.assertEqual(r['turnover_intensity'],1.)
    def test_breadth_and_high_formula(self):
        r=calculate_v221_snapshot(self.v)
        for m in ['up_ratio','above_ma20','above_ma60','new_high_60']:self.assertEqual(r[m],1.)
    def test_top3_formula(self):self.assertEqual(calculate_v221_snapshot(self.v)['top3_turnover_share'],1.)
    def test_amount_denominator_zero_is_null(self):
        amount=pd.Series(0.,index=self.days)
        r=calculate_v221_snapshot(replace(self.v,all_a_amount=amount));self.assertIsNone(r['turnover_share']);self.assertIsNone(r['turnover_intensity'])
    def test_missing_member_coverage_null(self):
        b=self.v.member_bars[self.v.member_bars.security_id=='0']
        r=calculate_v221_snapshot(replace(self.v,member_bars=b));self.assertTrue(r['stage_frozen']);self.assertIsNone(r['sector_return'])
        self.assertAlmostEqual(r['metric_coverage_json']['sector_return'],1/3)
    def test_new_share_short_history_not_false(self):
        b=self.v.member_bars[~((self.v.member_bars.security_id=='0')&(self.v.member_bars.trade_date<self.days[-15]))]
        r=calculate_v221_snapshot(replace(self.v,member_bars=b));self.assertAlmostEqual(r['metric_coverage_json']['above_ma20'],2/3)
        self.assertIsNone(r['above_ma20'])
    def test_exact_calendar_gap_not_borrowed(self):
        b=self.v.member_bars[~((self.v.member_bars.security_id=='0')&(self.v.member_bars.trade_date==self.days[-8]))]
        r=calculate_v221_snapshot(replace(self.v,member_bars=b));self.assertAlmostEqual(r['metric_coverage_json']['above_ma60'],2/3)
    def test_deferred_force_null(self):
        b=self.v.member_bars.copy();b['circ_mv']=100
        r=calculate_v221_snapshot(replace(self.v,member_bars=b,all_a_circ_mv=pd.Series(1000.,index=self.days)))
        self.assertIsNone(r['turnover_cap_deviation']);self.assertIsNone(r['top3_return_contribution'])
    def test_rs90_boundary(self):
        b=self.v.benchmark_returns.copy();b.iloc[-3:-1]=float('nan')
        r=calculate_v221_snapshot(replace(self.v,benchmark_returns=b));self.assertIsNotNone(r['rs_20'])
        b.iloc[-4]=float('nan');self.assertIsNone(calculate_v221_snapshot(replace(self.v,benchmark_returns=b))['rs_20'])
    def test_top3_less3_is_null(self):
        b=self.v.member_bars[self.v.member_bars.security_id!='2']
        self.assertIsNone(calculate_v221_snapshot(replace(self.v,member_ids=('0','1'),member_bars=b))['top3_turnover_share'])

if __name__=='__main__':unittest.main()
