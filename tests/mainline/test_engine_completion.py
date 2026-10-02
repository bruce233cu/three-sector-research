"""Synthetic fixtures validate approved code. Never reported as real events."""
import json
import unittest
from pathlib import Path
from dataclasses import asdict
import pandas as pd
from mainline.engine.completion import completion_features,ols_slope,BREADTH
from mainline.engine.metrics import add_cross_section
from mainline.engine.rules import evaluate_rules
from mainline.engine.state_machine import Checkpoint,advance
from mainline.engine.replay import digest,verified_freeze_gap,replay
from test_engine_metrics import row,RulesTest

ROOT=Path(__file__).resolve().parents[2]
def profile():
    return json.loads((ROOT/'config/parameter_profile_industry_trend_v221_state_completion_v1.json').read_text())


class CompletionFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.days=[str(d.date()) for d in pd.bdate_range('2020-01-02',periods=250)]
        self.hist=[row(d) for d in self.days]
    def calc(self): return completion_features(self.hist[-1],self.hist,self.days)
    def test_ols_exact(self): self.assertAlmostEqual(ols_slope([5,4,3,2,1]),-1.)
    def test_ols_gap_positions(self): self.assertAlmostEqual(ols_slope([0,None,4,6,8]),2.)
    def test_ols_min4(self): self.assertIsNone(ols_slope([1,None,2,None,3]))
    def test_ols_market_length(self): self.assertIsNone(ols_slope([1,2,3,4]))
    def test_rank_deteriorates(self):
        for r,v in zip(self.hist[-3:],[.1,.2,.3]): r['rs_10_pct']=v
        self.assertTrue(self.calc()['rs10_percentile_deteriorating'])
    def test_rank_improves(self):
        for r,v in zip(self.hist[-3:],[.3,.2,.1]): r['rs_10_pct']=v
        self.assertFalse(self.calc()['rs10_percentile_deteriorating'])
    def test_rank_equal_not_deterioration(self):
        for r,v in zip(self.hist[-3:],[.1,.1,.3]): r['rs_10_pct']=v
        self.assertFalse(self.calc()['rs10_percentile_deteriorating'])
    def test_rank_missing_not_skip(self):
        self.hist[-3]['rs_10_pct']=.1;self.hist[-1]['rs_10_pct']=.3
        self.assertIsNone(self.calc()['rs10_percentile_deteriorating'])
    def test_future_not_used(self):
        future=dict(row('2099-01-01'),rs_5=999)
        self.assertEqual(self.calc(),completion_features(self.hist[-1],self.hist+[future],self.days))
    def test_e4_160_boundary(self):
        for r in self.hist[:90]:r['top3_turnover_share']=None
        self.assertIsNotNone(self.calc()['top3_turnover_pct_250'])
        self.hist[90]['top3_turnover_share']=None
        self.assertIsNone(self.calc()['top3_turnover_pct_250'])
    def test_e4_high_boundary(self):
        for i,r in enumerate(self.hist):r['top3_turnover_share']=i/250
        self.assertTrue(self.calc()['e4_high_percentile'])
    def test_e4_sql_ties(self): self.assertEqual(self.calc()['top3_turnover_pct_250'],0.)
    def test_e4_window_excludes_old(self):
        old=row('2019-01-01');old['top3_turnover_share']=999
        self.assertEqual(self.calc(),completion_features(self.hist[-1],[old]+self.hist,self.days))
    def test_median_requires20_valid(self):
        for r in self.hist[:-19]:r['up_ratio']=None
        self.assertIsNone(self.calc()['up_ratio_median20'])
    def test_median_null_not_zero(self):
        self.hist[-2]['up_ratio']=None
        self.assertEqual(self.calc()['up_ratio_median20'],.8)


class CompletionRulesTest(unittest.TestCase):
    def good(self):
        r=RulesTest().good();r['rule_version']=profile()['rule_version']
        r.update(rs5_slope=-.1,rs10_percentile_deteriorating=True,top3_turnover_pct_250=.1)
        for f in BREADTH:r[f+'_lag3']=r[f]+.1;r[f+'_median20']=r[f]+.1
        return r
    def ev(self,r):return evaluate_rules(r,profile())
    def test_weaken_2of3(self):self.assertTrue(self.ev(self.good())['evidence']['weaken'])
    def test_weaken_only1(self):
        r=self.good();r['rs5_slope']=1;r['rs10_percentile_deteriorating']=False
        self.assertFalse(self.ev(r)['evidence']['weaken'])
    def test_breadth_threeof4(self):
        r=self.good();r['up_ratio_lag3']=0
        self.assertTrue(next(x for x in self.ev(r)['rules'] if x['rule_id']=='weaken.breadth')['passed'])
        r['above_ma20_lag3']=0
        self.assertFalse(next(x for x in self.ev(r)['rules'] if x['rule_id']=='weaken.breadth')['passed'])
    def test_breadth_null_not_decline(self):
        r=self.good();r['up_ratio']=None;r['above_ma20']=None
        self.assertIsNone(next(x for x in self.ev(r)['rules'] if x['rule_id']=='weaken.breadth')['passed'])
    def test_retire_2of3(self):
        r=self.good();r.update(rs_10=-.1,rs_20=-.1)
        self.assertTrue(self.ev(r)['evidence']['retire'])
    def test_retire_rank_half_boundary(self):
        r=self.good();r['rs_10_pct']=.5
        self.assertFalse(next(x for x in self.ev(r)['rules'] if x['rule_id']=='retire.rank')['passed'])
        r['rs_10_pct']=.50001
        self.assertTrue(next(x for x in self.ev(r)['rules'] if x['rule_id']=='retire.rank')['passed'])
    def test_recover_requires_positive_confirm(self):
        r=self.good();r['rs_10']=-1
        self.assertFalse(self.ev(r)['evidence']['recover'])
    def test_e4_missing_is_null(self):
        r=self.good();r['top3_turnover_pct_250']=None
        self.assertIsNone(next(x for x in self.ev(r)['rules'] if x['rule_id']=='E4')['passed'])
    def test_versions_and_repeat(self):
        a=self.ev(self.good());self.assertEqual(a,self.ev(self.good()))
        self.assertTrue(all(r['rule_version']==profile()['rule_version'] for r in a['rules']))
        self.assertFalse(any('BUSINESS_RULE_CONFLICT' in (r['reason'] or '') for r in a['rules']))


class CompletedStateTest(unittest.TestCase):
    def setUp(self):
        self.p=profile();self.days=[str(d.date()) for d in pd.bdate_range('2020-01-02',periods=40)]
        self.cp=Checkpoint('fixture_industry',self.p['rule_version'],self.p['profile_id'],self.p['metric_availability_version'],state='S0')
        self.i=0
    def step(self,bad=False,proof=None,**kw):
        e=dict(candidate=True,confirm=False,weaken=False,retire=False,recover=False);e.update(kw)
        r=row(self.days[self.i]);r.update(rule_version=self.p['rule_version'],critical_data_ok=not bad)
        if proof is not None:r['freeze_gap_evidence']=proof
        out,self.cp=advance(self.cp,r,{'evidence':e},self.p,self.days);self.i+=1
        return out
    def confirmed(self):self.step();self.step(confirm=True);self.step(confirm=True)
    def weakened(self):self.confirmed();self.step(weaken=True);self.step(weaken=True);self.step(weaken=True)
    def proof(self,days):
        result=[]
        for d in days:
            x={'trade_date':d,'object_id':self.cp.object_id,'rule_version':self.cp.rule_version,'parameter_profile':self.cp.parameter_profile,
               'critical_data_ok':True,'stage_frozen':False,'source_snapshot_ids':['explicit-synthetic-fixture-only'],
               'evidence':dict(candidate=True,confirm=True,weaken=True,retire=True,recover=True)}
            x['checksum']=digest(x);result.append(x)
        return result
    def test_s0_seed_and_confirmation(self):
        self.assertEqual(self.step()['previous_state'],'S0');self.assertEqual(self.step(confirm=True)['state'],'S1')
        self.assertEqual(self.step(confirm=True)['state'],'S2')
    def test_s2_weaken_consecutive_dwell(self):
        self.confirmed();self.assertEqual(self.step(weaken=True)['state'],'S2')
        self.assertEqual(self.step(weaken=True)['state'],'S2');self.assertEqual(self.step(weaken=True)['state'],'S3')
    def test_recover_two_days(self):
        self.weakened();self.assertEqual(self.step(recover=True)['state'],'S3')
        self.assertEqual(self.step(recover=True)['state'],'S2')
    def test_recover_false_resets(self):
        self.weakened();self.step(recover=True);self.step(recover=False)
        self.assertEqual(self.step(recover=True)['state'],'S3')
    def test_retire_three_and_reentry(self):
        self.weakened();self.step(retire=True);self.assertEqual(self.step(retire=True)['state'],'S3')
        out=self.step(retire=True);old=out['lifecycle_id'];self.assertEqual(out['state'],'S4')
        self.assertIsNotNone(self.cp.lifecycle['end_date']);out=self.step()
        self.assertEqual(out['state'],'S1');self.assertNotEqual(out['lifecycle_id'],old)
        self.assertEqual(out['reentry_count'],1);self.assertEqual(self.cp.lifecycle['prior_lifecycle_id'],old)
    def test_pause(self):
        self.step();self.step(confirm=True);before=self.cp.consecutive.copy()
        out=self.step(bad=True,confirm=None)
        self.assertEqual(self.cp.consecutive,before);self.assertEqual(out['counter_policy'],'paused')
    def test_resume_short_proven_first_day_guard(self):
        self.step();self.step(confirm=True);self.step(bad=True)
        proof=self.proof([self.days[2]])
        out=self.step(confirm=True,proof=proof)
        self.assertEqual(out['counter_policy'],'resumed');self.assertEqual(out['state'],'S1')
        self.assertEqual(out['consecutive_days']['confirm'],2);self.assertIsNone(out['transition'])
        self.assertEqual(self.step(confirm=True)['state'],'S2')
    def test_reset_unproven(self):
        self.step();self.step(confirm=True);self.step(bad=True)
        out=self.step(confirm=True)
        self.assertEqual(out['counter_policy'],'reset_after_unverifiable_gap');self.assertEqual(out['consecutive_days']['confirm'],1)
        self.assertEqual(out['state'],'S1')
    def test_reset_long_gap(self):
        self.step();self.step(confirm=True)
        for _ in range(4):self.step(bad=True)
        out=self.step(confirm=True,proof=self.proof(self.days[2:6]))
        self.assertEqual(out['counter_policy'],'reset_after_unverifiable_gap');self.assertEqual(out['state'],'S1')
    def test_first_day_no_candidate_upgrade(self):
        self.step(candidate=False);self.step(bad=True)
        self.assertEqual(self.step()['state'],'S0');self.assertEqual(self.step()['state'],'S1')
    def test_first_day_no_downgrade(self):
        self.step();self.step(bad=True)
        self.assertEqual(self.step(candidate=False)['state'],'S1');self.assertEqual(self.step(candidate=False)['state'],'S0')
    def test_false_repaired_gap_not_resume(self):
        self.step();self.step(confirm=True);self.step(bad=True)
        proof=self.proof([self.days[2]]);proof[0]['evidence']['confirm']=False;proof[0]['checksum']=digest({k:v for k,v in proof[0].items() if k!='checksum'})
        self.assertEqual(self.step(confirm=True,proof=proof)['counter_policy'],'reset_after_unverifiable_gap')
    def test_tampered_gap_not_resume(self):
        self.step();self.step(confirm=True);self.step(bad=True)
        proof=self.proof([self.days[2]]);proof[0]['checksum']='invalid'
        self.assertEqual(self.step(confirm=True,proof=proof)['counter_policy'],'reset_after_unverifiable_gap')
    def test_checkpoint_and_repeat(self):
        cp=Checkpoint(**asdict(self.cp));r=row(self.days[0]);r['rule_version']=self.p['rule_version']
        e={'evidence':dict(candidate=True,confirm=False,weaken=False,retire=False,recover=False)}
        self.assertEqual(advance(cp,r,e,self.p,self.days),advance(cp,r,e,self.p,self.days))

class ReplayInputTest(unittest.TestCase):
    def test_full_sw1_rank_direction(self):
        rows=[dict(row(),object_id='fixture_'+str(i),rs_10=i) for i in range(31)]
        ranked=add_cross_section(rows)
        self.assertEqual(ranked[0]['rs_10_pct'],1);self.assertEqual(ranked[-1]['rs_10_pct'],0)
    def test_synthetic_not_real_certification(self):
        r=row();r['evidence_kind']='synthetic'
        with self.assertRaisesRegex(ValueError,'synthetic'):replay([r],[r['as_of_date']],profile(),lambda d:None)
    def test_static_target_membership_rejected(self):
        r=row();r['evidence_kind']='real_historical_board'
        with self.assertRaisesRegex(ValueError,'daily membership incomplete'):
            replay([r],[r['as_of_date']],profile(),lambda d:{'trade_date':'future','complete':True})

if __name__=='__main__':unittest.main()
