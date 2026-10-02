"""D-specific contract tests. Fixtures are not historical market observations."""
import unittest, tempfile, inspect
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from mainline.backtest import runner
from mainline.backtest.evaluator import fraction,longest_run,churn,evaluate_case,aggregate
from mainline.engine.replay import digest

ROOT=Path(__file__).resolve().parents[2]
D=ROOT/'reports/milestone-d-baseline-v1'

class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile,cls.hashes=runner.baseline_profile(ROOT)
        cls.panel,cls.members,cls.dates,cls.prov=runner.load_inputs(D,cls.profile)
        cls.book=runner.read(D/'casebook.json')

    def test_01_casebook_schema_and_frozen_count(self):
        self.assertEqual(runner.validate_book(self.book,self.dates),{'positive':10,'negative':10,'ambiguous':5})
    def test_02_changed_label_rejected(self):
        b=deepcopy(self.book);b['cases'][0]['case_type']='negative'
        with self.assertRaises(ValueError):runner.validate_book(b,self.dates)
    def test_03_baseline_rule_and_profile_fixed(self):
        self.assertEqual(self.profile['rule_version'],runner.RULE)
        self.assertEqual(self.profile['profile_id'],runner.PROFILE)
        self.assertEqual(len(self.hashes),7)
    def test_04_no_labels_old_states_or_ranks_in_input(self):
        forbidden={'state','checkpoint','lifecycle','expected_behavior','case_type','rs_10_pct','top3_turnover_pct_250'}
        self.assertFalse(any(forbidden&set(r) for r in self.panel))
    def test_05_membership_cannot_borrow_future_date(self):
        m=deepcopy(self.members);m[self.dates[0]]['trade_date']=self.dates[1]
        with self.assertRaises(ValueError):runner.resolver_for(m)(self.dates[0])
    def test_06_membership_checksum_cannot_accept_future_pool(self):
        m=deepcopy(self.members);day=self.dates[0];oid=next(iter(m[day]['members']))
        m[day]['members'][oid]=['future-stock']
        with self.assertRaises(ValueError):runner.resolver_for(m)(day)
    def test_07_market_order_and_checkpoint_dates(self):
        result=runner.context_replay(self.panel,self.dates,self.profile,self.members,self.dates[2])
        ds=[r['state']['trade_date'] for r in result['rows']]
        self.assertEqual(ds,sorted(ds));self.assertEqual(len(result['rows']),93)
        self.assertTrue(all(r['state']['checkpoint']['last_date']==r['snapshot']['as_of_date'] for r in result['rows']))
    def test_08_future_rows_excluded_from_execution(self):
        p=deepcopy(self.panel)
        for r in p:
            if r['as_of_date']>self.dates[2]:r['sector_return']=99999
        a=runner.context_replay(p,self.dates,self.profile,self.members,self.dates[2])
        b=runner.context_replay(self.panel,self.dates,self.profile,self.members,self.dates[2])
        self.assertEqual(digest(a),digest(b))
    def test_09_duplicate_market_input_rejected(self):
        p=deepcopy(self.panel);p.append(deepcopy(p[0]))
        with self.assertRaises(ValueError):runner.context_replay(p,self.dates,self.profile,self.members,self.dates[2])
    def test_10_result_write_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'run.json';runner.write(p,{'x':1})
            with self.assertRaises(ValueError):runner.write(p,{'x':2})
    def test_11_no_database_or_dispatch_writer(self):
        source=inspect.getsource(runner)
        for value in ['requests.','execute_sql','gateway(','SUPABASE','workflow_dispatch']:
            self.assertNotIn(value,source)
    def test_12_null_denominator_not_zero(self):
        self.assertIsNone(fraction(0,0));self.assertEqual(fraction(2,4),.5)
    def test_13_stable_confirmation_formula(self):
        self.assertEqual(longest_run([True,True,False,True,True,True]),3)
    def test_14_churn_direct_reversal_and_short_interval(self):
        states=['S0','S1','S0','S1','S2','S3','S2']
        c=churn(states,[str(i) for i in range(len(states))])
        self.assertEqual(c['transition_count'],6);self.assertEqual(c['reversal_count'],3)
        self.assertEqual(c['short_interval_reversal_count'],3);self.assertEqual(c['direct_A_B_A_count'],3)
    def metrics_fixture(self,typ,states):
        # Use certified rows only to obtain the real evidence schema; override states
        # here solely to test evaluator arithmetic, never emit these as case results.
        context=runner.context_replay(self.panel,self.dates,self.profile,self.members,self.dates[2])
        oid=self.book['cases'][0]['object_id'];rows=deepcopy([r for r in context['rows'] if r['snapshot']['object_id']==oid])
        for i,(r,s) in enumerate(zip(rows,states)):
            prev=states[i-1] if i else s;r['state'].update(state=s,previous_state=prev,stage_frozen=False,transition=None)
            if s!=prev:r['state']['transition']={'from_state':prev,'to_state':s,'trigger_date':self.dates[i],'lifecycle_id':'arithmetic-only'}
        case={**self.book['cases'][0],'case_type':typ,'pre_window_start':self.dates[0],
              'post_window_end':self.dates[2],'start_date':self.dates[1],'end_date':self.dates[2]}
        b={'rows':rows,'lifecycles':[],'manifest':{'checksum':'arithmetic-only-fixture'}}
        return evaluate_case(case,b,self.dates)
    def test_15_miss_detection_lag_and_coverage(self):
        r=self.metrics_fixture('positive',['S0','S1','S1'])
        self.assertTrue(r['MISS']);self.assertEqual(r['miss_category'],'S1_without_S2')
        self.assertEqual(r['S1_lag_observed'],0);self.assertIsNone(r['S2_lag_observed'])
        self.assertEqual(r['coverage']['knowledge_time_unverified_ratio'],1.)
        self.assertEqual(r['coverage']['strict_pit_coverage'],0.)
        self.assertIsNone(r['coverage']['deferred_metrics']['turnover_cap_deviation'])
    def test_16_false_positive_lifecycle_freeze_and_aggregate(self):
        r=self.metrics_fixture('negative',['S1','S2','S2'])
        self.assertEqual(r['false_S2_days'],2);self.assertEqual(r['false_confirmation_count'],1)
        self.assertEqual(r['S2_lag_observed'],0);self.assertFalse(r['stable_false_S2'])
        self.assertEqual(r['duplicate_lifecycle_count'],0);self.assertEqual(r['freeze_transition_violations'],0)
        a=aggregate([r]);self.assertEqual(a['overall']['negative_false_S2_days'],2)

    def test_17_first_case_day_transition_is_not_lost(self):
        r=churn(['S1','S0'],['d0','d1'],initial_previous_state='S0')
        self.assertEqual(r['transition_count'],2);self.assertEqual(r['reversal_count'],1)
        self.assertEqual(r['short_interval_reversal_count'],1);self.assertEqual(r['direct_A_B_A_count'],1)

if __name__=='__main__':unittest.main()
