import unittest
import pandas as pd
from mainline.engine.metrics import finalize_metrics,add_cross_section,sql_percent_rank,metric_availability
from mainline.engine.rules import evaluate_rules,tri_all,tri_any,at_least

def profile():
    return {'profile_id':'fixture_profile','candidate':{'rs5_cross_section_pct_max':.2,'rs10_min':0.,'win5_min':.6,'turnover_intensity_min':1.,'candidate_min_pass_count':3},
        'confirm':{'rs10_cross_section_pct_max':.3,'rs10_min':0.,'win5_min':.8,'win10_min':.7,'turnover_pct60_min':.6,'above_ma20_min':.6,'breadth_min_pass_count':2,'enhancer_min_pass_count':2,'confirm_consecutive_days':2},
        'weaken':{'deterioration_group_min':2,'consecutive_days':2,'min_dwell_days_after_confirm':3},
        'retire':{'core_deterioration_group_min':2,'consecutive_days':3,'rs10_cross_section_pct_exit':.5,'enhancer_min_pass_count':1}}

def row(day='2020-01-02'):
    return {'as_of_date':day,'object_id':'fixture_industry','object_type':'industry','taxonomy_version':'fixture_SW',
        'rule_version':'mainline_v2.2.1','metric_availability_version':'mainline_metric_availability_v2.2.1_deferred_circ_mv',
        'critical_data_ok':True,'stage_frozen':False,'sector_return':.02,'benchmark_return':.01,
        'turnover_share':.05,'turnover_intensity':1.2,'rs_5':.04,'rs_10':.05,'rs_20':.06,
        'up_ratio':.8,'above_ma20':.7,'above_ma60':.8,'new_high_60':.3,'top3_turnover_share':.2}

class MetricsFinalizationTest(unittest.TestCase):
    def setUp(self):
        self.days=[str(d.date()) for d in pd.bdate_range('2020-01-02',periods=250)]
        self.history=[row(d) for d in self.days]
    def calc(self,h=None):return finalize_metrics(self.history[-1],h or self.history,self.days)
    def test_win_and_rs3(self):
        r=self.calc();self.assertEqual(r['win_5'],1);self.assertEqual(r['win_10'],1)
        self.assertAlmostEqual(r['rs_3'],1.02**3-1.01**3)
    def test_win_equal_is_not_win(self):
        for r in self.history:r['sector_return']=.01
        self.assertEqual(self.calc()['win_5'],0.)
    def test_win_minimum_4_8(self):
        self.history[-2]['sector_return']=None
        self.assertEqual(self.calc()['win_5'],1.)
        self.history[-3]['sector_return']=None
        self.assertIsNone(self.calc()['win_5']);self.assertEqual(self.calc()['win_10'],1.)
        self.history[-4]['sector_return']=None
        self.assertIsNone(self.calc()['win_10'])
    def test_missing_calendar_days_not_stretched(self):
        self.assertIsNone(self.calc(self.history[:-5])['win_5'])
    def test_percentile_sql_ties(self):
        self.assertEqual(sql_percent_rank({'a':1,'b':1,'c':3}),{'a':0.,'b':0.,'c':1.})
    def test_turnover_60_and250_minimum(self):
        self.assertEqual(self.calc()['turnover_pct_60'],0.)
        for r in self.history[-59:-20]:r['turnover_share']=None
        self.assertIsNone(self.calc()['turnover_pct_60'])
        for r in self.history[:100]:r['turnover_share']=None
        self.assertIsNone(self.calc()['turnover_pct_250'])
    def test_nonfinite_null(self):
        self.assertEqual(sql_percent_rank({'a':float('inf'),'b':None}),{'a':None,'b':None})
    def test_rank_min10_direction_and_version(self):
        rows=[dict(row(),object_id='fixture_'+str(i),rs_5=i,rs_10=i,rs_20=i) for i in range(10)]
        self.assertIsNone(add_cross_section(rows[:9])[0]['rs_5_pct'])
        r=add_cross_section(rows);self.assertEqual(r[-1]['rs_5_pct'],0.);self.assertEqual(r[0]['rs_5_pct'],1.)
        rows[-1]['taxonomy_version']='different';self.assertIsNone(add_cross_section(rows)[0]['rs_5_pct'])
    def test_rank_duplicate_rejected(self):
        with self.assertRaises(ValueError):add_cross_section([row(),row()])
    def test_availability_null_not_zero_and_deferred(self):
        r=row();r.update(rs_5=None,rs_10=0,turnover_cap_deviation=55)
        av=metric_availability(r,['rs_5','rs_10','turnover_cap_deviation'])
        self.assertEqual(av['rs_5']['status'],'unavailable');self.assertEqual(av['rs_10']['status'],'available')
        self.assertEqual(av['turnover_cap_deviation']['status'],'deferred');self.assertIsNone(av['turnover_cap_deviation']['value'])
    def test_availability_freeze(self):
        r=row();r['stage_frozen']=True
        self.assertEqual(metric_availability(r,['rs_5'])['rs_5']['status'],'frozen')
    def test_lag_exact_three_market_days(self):
        self.history[-4]['new_high_60']=.123
        self.assertEqual(self.calc()['new_high_60_lag3'],.123)
    def test_share_three_valid_not_future(self):
        for r,v in zip(self.history[-3:],[.1,.08,.05]):r['turnover_share']=v
        self.assertFalse(self.calc()['turnover_not_three_valid_days_down'])
    def test_core_values_preserved_and_repeat(self):
        r=self.calc();self.assertEqual(r['rs_5'],self.history[-1]['rs_5']);self.assertEqual(r,self.calc())
        self.assertIsNone(r['turnover_cap_deviation']);self.assertIsNone(r['top3_return_contribution'])
    def test_mixed_object_and_taxonomy_rejected(self):
        self.history[0]['taxonomy_version']='different'
        with self.assertRaises(ValueError):self.calc()

class RulesTest(unittest.TestCase):
    def good(self):
        r=row();r.update(rs_5_pct=.1,rs_10_pct=.1,win_5=1.,win_10=1.,turnover_pct_60=.8,
            turnover_share_mean20=.04,turnover_not_three_valid_days_down=True,all_a_up_ratio=.5,
            all_a_above_ma20=.5,above_ma60_lag3=.6,new_high_60_lag3=.1)
        return r
    def test_tri_state(self):
        self.assertIsNone(tri_all([True,None]));self.assertFalse(tri_all([False,None]));self.assertTrue(tri_any([True,None]))
        self.assertIsNone(at_least([True,True,None],3));self.assertTrue(at_least([True,True,None],2))
    def test_candidate_confirm_expanded(self):
        ev=evaluate_rules(self.good(),profile());self.assertTrue(ev['evidence']['candidate']);self.assertTrue(ev['evidence']['confirm'])
        self.assertTrue(all('actual_value' in r and 'reason' in r for r in ev['rules']))
    def test_candidate_valid_conditions_below4(self):
        r=self.good();r['rs_5_pct']=None;r['win_5']=None
        self.assertIsNone(evaluate_rules(r,profile())['evidence']['candidate'])
    def test_exact_zero_is_false_not_null(self):
        r=self.good();r['rs_10']=0
        x=next(x for x in evaluate_rules(r,profile())['rules'] if x['rule_id']=='C2')
        self.assertFalse(x['passed']);r['rs_10']=None
        self.assertIsNone(next(x for x in evaluate_rules(r,profile())['rules'] if x['rule_id']=='C2')['passed'])
    def test_deferred_does_not_enter_rules(self):
        r=self.good();a=evaluate_rules(r,profile());r.update(turnover_cap_deviation=100,top3_return_contribution=100)
        self.assertEqual(a,evaluate_rules(r,profile()))
    def test_unquantified_conditions_not_invented(self):
        e=evaluate_rules(self.good(),profile())
        self.assertIsNone(e['evidence']['weaken']);self.assertIsNone(e['evidence']['retire']);self.assertIsNone(e['evidence']['recover'])

if __name__=='__main__':unittest.main()
