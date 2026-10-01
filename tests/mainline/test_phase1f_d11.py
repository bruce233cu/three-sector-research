"""Synthetic offline regression: fixed market sessions, never source evidence."""
from dataclasses import replace
from test_phase1f_c import fixture
from mainline.metrics import SectorMetricInput, calculate_sector_snapshot
import unittest


class ExactCalendarTests(unittest.TestCase):
    def input(self):
        s,m,bars,b=fixture()
        return SectorMetricInput(m.trade_date,s['object_id'],s['taxonomy_code'],m.taxonomy_version,
            tuple(m.frame.security_id),bars,b.set_index('trade_date').pct_chg/100,
            b.set_index('trade_date').amount,market_trading_dates=tuple(b.trade_date))

    def test_gap_cannot_borrow_21st_close(self):
        x=self.input();sid=x.member_ids[0];gap=x.market_trading_dates[-8]
        x=replace(x,member_bars=x.member_bars[~((x.member_bars.security_id==sid)&(x.member_bars.trade_date==gap))])
        r=calculate_sector_snapshot(x)
        self.assertEqual(r['metric_coverage_json']['above_ma20'],.75)
        self.assertEqual(r['metric_coverage_json']['above_ma60'],.75)
        self.assertEqual(r['metric_coverage_json']['new_high_60'],.75)

    def test_gap_outside_20_only_affects_60(self):
        x=self.input();sid=x.member_ids[0];gap=x.market_trading_dates[-30]
        r=calculate_sector_snapshot(replace(x,member_bars=x.member_bars[~((x.member_bars.security_id==sid)&(x.member_bars.trade_date==gap))]))
        self.assertEqual(r['metric_coverage_json']['above_ma20'],1)
        self.assertEqual(r['metric_coverage_json']['above_ma60'],.75)

    def test_target_suspension_is_invalid_and_freezes(self):
        x=self.input();drop=x.member_ids[:2]
        r=calculate_sector_snapshot(replace(x,member_bars=x.member_bars[~((x.member_bars.security_id.isin(drop))&(x.member_bars.trade_date==x.trade_date))]))
        self.assertEqual(r['metric_coverage_json']['above_ma20'],.5)
        self.assertTrue(r['stage_frozen']);self.assertIsNone(r['above_ma20'])

    def test_unknown_target_calendar_is_rejected(self):
        x=self.input()
        with self.assertRaises(ValueError):calculate_sector_snapshot(replace(x,market_trading_dates=x.market_trading_dates[:-1]))

    def test_future_observations_do_not_change_breadth(self):
        import pandas as pd
        x=self.input();future=x.member_bars.iloc[:1].copy();future.trade_date=x.trade_date+pd.Timedelta(days=10);future.close=999
        r=calculate_sector_snapshot(replace(x,member_bars=pd.concat([x.member_bars,future])))
        self.assertEqual(r['above_ma20'],calculate_sector_snapshot(x)['above_ma20'])

    def test_duplicate_date_is_rejected(self):
        import pandas as pd
        x=self.input()
        with self.assertRaises(ValueError):calculate_sector_snapshot(replace(x,member_bars=pd.concat([x.member_bars,x.member_bars.iloc[:1]])))


if __name__=='__main__':unittest.main()

class FullRunnerOfflineTest(unittest.TestCase):
    def test_three_sample_finalization_and_membership_hashes(self):
        import importlib.util
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('d11',root/'scripts/mainline/phase1f_d11_run.py')
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        config,snaps,integrity=runner.c.preflight(root,root/'scripts/mainline/phase1f_c')
        fixture_results=[{'sample_id':x['sample_id'],'trade_date':x['trade_date'],'repetition':rep,'run_id':'synthetic:'+x['sample_id'],'source_snapshot_ids':['synthetic'],'market_window_pass':False,'valid_member_count':None} for rep in (1,2) for x in config['samples']]
        def result(client,config,sample,membership,benchmark,out,deadline,rep):
            value=dict(next(x for x in fixture_results if x['sample_id']==sample['sample_id'] and x['repetition']==rep))
            return value,[],{'repetition':rep,'sample_id':sample['sample_id'],'securities':[]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner.c,'health_check',return_value={'health_pass':True}),patch.object(runner.c,'run_sample',side_effect=result),patch.object(runner.c.IsolatedClient,'close'):
            out=Path(tmp);runner.full(out,config,snaps,integrity,{'git_sha':'OFFLINE_TEST'})
            rows=json.loads((out/'metrics_output.json').read_text())
            self.assertEqual(len(rows),6)
            self.assertEqual(len({x['run_id'] for x in rows}),3)
            self.assertTrue(runner.c.verify_results(out)['checksums_ok'])
