"""Explicit synthetic evidence tests the transition kernel, not business G3.

Every fixture uses a fictional object/profile. Unknown production predicates
are not certified by these tests. Resume reset is a fixture-only assumption.
"""
import unittest
from dataclasses import asdict
import pandas as pd
from mainline.engine.state_machine import Checkpoint,advance,validate_transition
from test_engine_metrics import profile,row

class StateMachineKernelTest(unittest.TestCase):
    def setUp(self):
        self.days=[str(x.date()) for x in pd.bdate_range('2020-01-02',periods=30)]
        self.profile=profile();r=row()
        self.cp=Checkpoint(r['object_id'],r['rule_version'],self.profile['profile_id'],r['metric_availability_version'],state='S0')
        self.index=0
    def step(self,*,candidate=True,confirm=False,weaken=False,retire=False,recover=False,bad=False,resume=None):
        r=row(self.days[self.index]);r['critical_data_ok']=not bad
        e={'evidence':dict(candidate=candidate,confirm=confirm,weaken=weaken,retire=retire,recover=recover)}
        output,self.cp=advance(self.cp,r,e,self.profile,self.days,resume_policy=resume)
        self.index+=1
        return output
    def confirmed(self):
        self.step();self.step(confirm=True);return self.step(confirm=True)
    def weakened(self):
        self.confirmed();self.step(weaken=True);self.step(weaken=True);return self.step(weaken=True)
    def retired(self):
        self.weakened();self.step(retire=True);self.step(retire=True);return self.step(retire=True)
    def test_s0_hold(self):self.assertEqual(self.step(candidate=False)['state'],'S0')
    def test_s0_s1(self):self.assertEqual(self.step()['transition']['to_state'],'S1')
    def test_s1_s2_consecutive(self):
        self.step();self.assertEqual(self.step(confirm=True)['state'],'S1');self.assertEqual(self.step(confirm=True)['state'],'S2')
    def test_s2_s3_dwell(self):
        self.confirmed();self.assertEqual(self.step(weaken=True)['state'],'S2')
        self.assertEqual(self.step(weaken=True)['state'],'S2');self.assertEqual(self.step(weaken=True)['state'],'S3')
    def test_s3_s4_consecutive(self):
        self.weakened();self.assertEqual(self.step(retire=True)['state'],'S3')
        self.assertEqual(self.step(retire=True)['state'],'S3');self.assertEqual(self.step(retire=True)['state'],'S4')
    def test_legal_candidate_downgrade(self):
        self.step();self.assertEqual(self.step(candidate=False)['state'],'S0')
    def test_no_illegal_jumps(self):
        for a,b in [('S0','S2'),('S1','S3'),('S2','S4'),('S3','S0'),('S4','S2')]:
            with self.assertRaises(ValueError):validate_transition(a,b)
    def test_consecutive_reset(self):
        self.step();self.step(confirm=True);self.step(confirm=False)
        self.assertEqual(self.cp.consecutive['confirm'],0);self.assertEqual(self.step(confirm=True)['state'],'S1')
    def test_debounce(self):
        self.step();x=self.step(confirm=True)
        self.assertEqual(x['debounce_status'],'waiting_consecutive_days');self.assertEqual(x['debounce_days'],1)
    def test_single_bad_day_cannot_downgrade(self):
        self.confirmed();self.assertEqual(self.step(weaken=True,retire=True)['state'],'S2')
    def test_freeze_preserves_state_and_counters(self):
        self.confirmed();old=asdict(self.cp);x=self.step(bad=True,weaken=True)
        self.assertEqual(x['state'],'S2');self.assertIsNone(x['transition']);self.assertEqual(self.cp.consecutive,old['consecutive'])
        self.assertTrue(x['stage_frozen']);self.assertIsNotNone(x['freeze_started_at'])
    def test_resume_default_cannot_guess_policy(self):
        self.confirmed();self.step(bad=True);x=self.step(weaken=True)
        self.assertTrue(x['stage_frozen']);self.assertEqual(x['state'],'S2');self.assertIsNotNone(x['freeze_ended_at'])
    def test_explicit_fixture_resume_resets(self):
        self.step();self.step(confirm=True);self.step(bad=True);x=self.step(confirm=True,resume='reset')
        self.assertEqual(x['state'],'S1');self.assertEqual(x['consecutive_days']['confirm'],1)
        self.assertEqual(self.step(confirm=True)['state'],'S2')
    def test_lifecycle_first_creation(self):
        self.step();self.assertIsNotNone(self.cp.lifecycle['lifecycle_id']);self.assertEqual(self.cp.lifecycle['start_date'],self.days[0])
    def test_lifecycle_end(self):
        self.retired();self.assertEqual(self.cp.lifecycle['current_state'],'S4');self.assertIsNotNone(self.cp.lifecycle['end_date'])
    def test_lifecycle_reentry_new_uuid(self):
        self.retired();old=self.cp.lifecycle['lifecycle_id'];x=self.step()
        self.assertEqual(x['state'],'S1');self.assertNotEqual(x['lifecycle_id'],old)
        self.assertEqual(self.cp.lifecycle['prior_lifecycle_id'],old);self.assertEqual(x['reentry_count'],1)
    def test_s4_stays_without_new_candidate(self):
        self.retired();self.assertEqual(self.step(candidate=False)['state'],'S4')
    def test_candidate_end_creates_new_lifecycle(self):
        self.step();old=self.cp.lifecycle['lifecycle_id'];self.step(candidate=False);self.step()
        self.assertNotEqual(self.cp.lifecycle['lifecycle_id'],old)
    def test_recover_kernel_explicit_evidence(self):
        self.weakened();self.assertEqual(self.step(recover=True)['state'],'S2')
    def test_unknown_not_false(self):
        x=self.step(candidate=None);self.assertEqual(x['state'],'S0');self.assertTrue(x['stage_frozen']);self.assertIsNone(x['transition'])
    def test_no_historical_state_seed_fabrication(self):
        self.cp.state=None;self.assertIsNone(self.step()['state'])
    def test_checkpoint_serialization(self):
        self.confirmed();self.cp=Checkpoint(**asdict(self.cp));self.assertEqual(self.step()['previous_state'],'S2')
    def test_missing_market_day_rejected(self):
        self.step();self.index=2
        with self.assertRaises(ValueError):self.step()
    def test_version_boundary_rejected(self):
        self.cp.rule_version='different'
        with self.assertRaises(ValueError):self.step()
    def test_falsey_nonboolean_rejected(self):
        with self.assertRaises(ValueError):self.step(candidate=0)
    def test_same_input_deterministic(self):
        r=row(self.days[0]);e={'evidence':dict(candidate=True,confirm=False,weaken=False,retire=False,recover=False)}
        self.assertEqual(advance(self.cp,r,e,self.profile,self.days),advance(self.cp,r,e,self.profile,self.days))

if __name__=='__main__':unittest.main()
