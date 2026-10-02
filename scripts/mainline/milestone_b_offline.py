"""Offline evidence run. Reuses G1 artifacts, never imports a Provider.

Real continuous BAR windows are evidence for metrics/repeatability. Their
membership ledger lacks a completeness certificate for every intermediate day;
they are NOT asserted to be certified historical state transitions.
"""
from __future__ import annotations
import sys,json,hashlib,uuid,os
from pathlib import Path
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from mainline.engine.metrics import finalize_metrics,add_cross_section,metric_availability
from mainline.engine.rules import evaluate_rules
from mainline.engine.state_machine import Checkpoint,advance

OUT=ROOT/'reports/milestone-b-engine'
RUN=str(uuid.uuid5(uuid.NAMESPACE_URL,'milestone-b-offline:'+os.environ.get('CODE_COMMIT','local')))
REPEAT=str(uuid.uuid5(uuid.NAMESPACE_URL,RUN+':repeat'))
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def checksum(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def write(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    profile=json.loads((ROOT/'config/parameter_profile_industry_trend_v221_engine_audit.json').read_text())
    inputs=json.loads((OUT/'input_snapshots.json').read_text())
    benchmarks=json.loads((ROOT/'reports/v221-benchmark-close/all_a_equal_weight_benchmark.json').read_text())
    bench={r['trade_date']:r for r in benchmarks}
    calendar=json.loads((ROOT/'reports/milestone-a-fast-close/calendar_input.json').read_text())
    source=ROOT/'reports/milestone-a-final-close'
    membership=json.loads((source/'membership_snapshot.json').read_text())
    bars=pd.read_json(source/'stock_window.json');bars.trade_date=pd.to_datetime(bars.trade_date).dt.strftime('%Y-%m-%d')
    source_checksum=hashlib.sha256((source/'stock_window.json').read_bytes()).hexdigest()
    histories={};panel=[]
    for target in inputs:
        day=target['as_of_date'];dates=[d for d in calendar if d<=day][-60:]
        members=[m for m in membership if m['snapshot_date']==day and m['taxonomy_code']==target['taxonomy_code']]
        ids={m['security_id'] for m in members}
        frame=bars[bars.security_id.isin(ids)&bars.trade_date.isin(dates)].copy()
        if frame.duplicated(['security_id','trade_date']).any():raise ValueError('cached duplicate stock/day')
        closes=frame.pivot(index='trade_date',columns='security_id',values='close').reindex(dates)
        ma20=closes.rolling(20,min_periods=20).mean();ma60=closes.rolling(60,min_periods=60).mean()
        high60=closes.rolling(60,min_periods=60).max()
        rows=[]
        for d in dates:
            eligible={m['security_id'] for m in members if m['effective_from']<=d and (m['effective_to'] is None or m['effective_to']>=d)}
            today=frame[(frame.trade_date==d)&frame.security_id.isin(eligible)]
            valid=today[today.amount.gt(0)&today.pct_chg.notna()]
            den=len(eligible);count=valid.security_id.nunique();cov=count/den if den else None
            b=bench[d];amount=today[today.amount.gt(0)].amount
            total=float(amount.sum()) if len(amount) else None
            r=dict(as_of_date=d,object_id=target['object_id'],object_type='industry',taxonomy_code=target['taxonomy_code'],
                taxonomy_version=target['taxonomy_version'],rule_version='mainline_v2.2.1',profile_id=profile['profile_id'],
                member_count=den,valid_member_count=int(count),sector_return=float(valid.pct_chg.mean()/100) if cov is not None and cov>=.70 else None,
                benchmark_return=b['benchmark_return'],turnover_share=total/b['all_a_amount'] if total is not None and b['all_a_amount'] else None,
                up_ratio=float((valid.pct_chg>0).mean()) if cov is not None and cov>=.70 else None,
                top3_turnover_share=float(amount.nlargest(3).sum()/total) if len(amount)>=3 and total else None,
                critical_data_ok=False,stage_frozen=True,freeze_reason='continuous_membership_completeness_not_certified',
                run_id=RUN,source_snapshot_ids=target['source_snapshot_ids'],metric_coverage_json={'sector_return':cov},
                pit_level='effective_intervals_partial_window',knowledge_time_unverified=True,
                input_evidence={'real_bars':True,'membership_members_from_fixed_target_snapshot':day,
                                'intermediate_membership_completeness_certified':False})
            for field,average in [('above_ma20',ma20),('above_ma60',ma60),('new_high_60',high60)]:
                columns=[sid for sid in sorted(eligible) if sid in closes.columns]
                current=closes.loc[d,columns];ref=average.loc[d,columns]
                ok=current.notna()&ref.notna();n=int(ok.sum());coverage=n/den if den else None
                passes=(current[ok]>=ref[ok]) if field=='new_high_60' else current[ok]>ref[ok]
                r[field]=float(passes.mean()) if n and coverage>=.70 else None
                r['metric_coverage_json'][field]=coverage
            joined=[x for x in rows]+[r]
            for n in [5,10,20]:
                pairs=[(x['sector_return'],x['benchmark_return']) for x in joined[-n:] if x['sector_return'] is not None and x['benchmark_return'] is not None]
                r['rs_'+str(n)]=float(np.prod([1+a for a,b in pairs])-np.prod([1+b for a,b in pairs])) if len(pairs)/n>=.90 else None
                r['metric_coverage_json']['rs_'+str(n)]=len(pairs)/n
            shares=[x['turnover_share'] for x in joined[-60:] if x['turnover_share'] is not None]
            median=float(np.median(shares)) if len(shares)>=40 else None
            r['turnover_intensity']=r['turnover_share']/median if median and median>0 and r['turnover_share'] is not None else None
            r=finalize_metrics(r,rows,dates)
            rows.append(r);panel.append(r)
        histories[(day,target['object_id'])]=rows
    panel=add_cross_section(panel)
    write('real_board_window_diagnostics.json',panel)
    snapshots=[]
    for original in inputs:
        updated=finalize_metrics(original,histories[(original['as_of_date'],original['object_id'])],calendar)
        updated.update(profile_id=profile['profile_id'],metric_availability_version=profile['metric_availability_version'],run_id=RUN,recompute_run_id=REPEAT)
        # Intermediate membership completeness is unverified: extra history-based
        # values stay in diagnostic panel, not certified input to live decisions.
        provisional={k:updated.get(k) for k in ['rs_3','win_5','win_10','turnover_pct_60','turnover_pct_250','turnover_share_mean20','above_ma20_lag3','above_ma60_lag3','new_high_60_lag3','turnover_not_three_valid_days_down']}
        for key in provisional:updated[key]=None
        updated['metric_diagnostics']={'history_derived_features':{'status':'unavailable','reason':'continuous_membership_completeness_not_certified','diagnostic_values':provisional}}
        snapshots.append(updated)
    snapshots=add_cross_section(snapshots)
    integration=[];checks=[];rule_rows=[]
    for updated in snapshots:
        metrics=['sector_return','benchmark_return','rs_5','rs_10','rs_20','turnover_share','turnover_intensity','up_ratio','above_ma20','above_ma60','new_high_60','top3_turnover_share','turnover_cap_deviation','top3_return_contribution','rs_5_pct','rs_10_pct','win_5','win_10','turnover_pct_60']
        updated['metric_availability']=metric_availability(updated,metrics)
        evaluation=evaluate_rules(updated,profile)
        cp=Checkpoint(updated['object_id'],updated['rule_version'],profile['profile_id'],profile['metric_availability_version'])
        a,_=advance(cp,updated,evaluation,profile,calendar);b,_=advance(cp,updated,evaluate_rules(updated,profile),profile,calendar)
        original=next(x for x in inputs if x['as_of_date']==updated['as_of_date'] and x['object_id']==updated['object_id'])
        core_unchanged=all(updated[k]==original[k] for k in metrics[:12])
        updated['hard_status']=a['state'];updated['previous_status']=a['previous_state'];updated['lifecycle_id']=a['lifecycle_id']
        updated['stage_frozen']=a['stage_frozen'];updated['freeze_reason']=a['freeze_reason']
        updated['decision_reason']={**updated['decision_reason'],'engine_state':a,'engine_rules':evaluation,
            'metric_availability_version':profile['metric_availability_version'],'parent_run_id':original['run_id'],
            'status':'ENGINE_BLOCKED','parameter_profile':profile['profile_id'],'parameter_hash':profile['calculation_parameter_hash'],
            'scope':'audit_only_no_production_state','repeat_checksum':checksum(b),'code_commit':os.environ.get('CODE_COMMIT','local')}
        updated['cache_checksum']=checksum({k:v for k,v in updated.items() if k!='cache_checksum'})
        integration.append(a);rule_rows.extend(evaluation['rules'])
        checks.append(dict(sample_id=updated['as_of_date']+':'+updated['object_id'],repeat_identical=a==b,
            rules_repeat_identical=evaluation==evaluate_rules({**updated,'stage_frozen':False},profile),
            core_unchanged=core_unchanged,state_checksum=checksum(a),repeat_state_checksum=checksum(b)))
    # Whole real consecutive windows: explicit unknown initial state, no fake
    # upgrades from isolated S0 seeds. Every duplicate run has the same outcome.
    series_states=[];series_checks=[]
    for key,history in histories.items():
        cp=Checkpoint(history[0]['object_id'],'mainline_v2.2.1',profile['profile_id'],profile['metric_availability_version'])
        cp2=Checkpoint(**cp.__dict__)
        for r in history:
            e=evaluate_rules(r,profile);a,cp=advance(cp,r,e,profile,calendar);b,cp2=advance(cp2,r,e,profile,calendar)
            series_states.append(a);series_checks.append(a==b)
    write('engine_snapshots.json',snapshots);write('rule_results.json',rule_rows);write('integration_states.json',integration);write('integration_checks.json',checks)
    write('time_series_states.json',series_states)
    summary={'real_board_rows':len(panel),'windows':len(histories),'sessions_per_window':60,
        'deterministic_rows':sum(series_checks),'certified_state_transitions':0,'certified_intermediate_membership':False,
        'real_price_and_benchmark_inputs':True,'false_zero_fills':0,'historical_seed_state':'unknown_preserved_NULL'}
    write('time_series_checks.json',summary)
    write('input_provenance.json',{'database_profile':'industry_trend_v2_2_1_benchmark_close','database_run':'7fe5ad62-ab71-4759-a334-08dffe980d97',
        'database_rows':len(inputs),'stock_cache_sha256':source_checksum,'membership_cache_sha256':hashlib.sha256((source/'membership_snapshot.json').read_bytes()).hexdigest(),
        'benchmark_aggregate_sha256':hashlib.sha256((ROOT/'reports/v221-benchmark-close/all_a_equal_weight_benchmark.json').read_bytes()).hexdigest(),
        'provider_calls':0,'stock_rows_persisted':0,'source_snapshot_ids':sorted({i for x in inputs for i in x['source_snapshot_ids']}),
        'board_window_evidence_grade':'real_prices_real_benchmark_partial_membership_completeness_not_accepted_as_live_state',
        'run_id':RUN,'recompute_run_id':REPEAT,'code_commit':os.environ.get('CODE_COMMIT','local'),'parameter_hash':profile['calculation_parameter_hash']})
    print(json.dumps({'integration_samples':len(integration),'core_unchanged':sum(x['core_unchanged'] for x in checks),
                      'state_repeat_identical':sum(x['repeat_identical'] for x in checks),'time_series':summary}))

if __name__=='__main__':main()
