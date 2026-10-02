"""Compare immutable case versions without changing labels, rules or evaluation."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from mainline.backtest.runner import read,write
from mainline.backtest.evaluator import evaluate_case,aggregate
from mainline.engine.replay import digest

def compare(cold,full,output):
    archived=read(cold/'case_metrics.json')
    book=read(ROOT/'reports/milestone-d-baseline-v1/casebook.json')
    calendar=read(ROOT/'reports/milestone-a-fast-close/calendar_input.json')
    normalized=[evaluate_case(c,read(cold/(c['case_id']+'.json.gz')),calendar,
        book['expected_negative_stable_s2_min_sessions'],book['short_reversal_max_sessions']) for c in book['cases']]
    a={r['case_id']:r for r in normalized}
    b={r['case_id']:r for r in read(full/'case_metrics.json')}
    if set(a)!=set(b) or len(a)!=25:raise ValueError('case set changed')
    rows=[]
    fields=['first_S1_date','first_S2_date','peak_state','transition_count','lifecycle_count',
            'freeze_days','MISS','miss_category','false_S2_days','false_confirmation_count',
            'S2_lag_observed','reversal_count','short_interval_reversal_count']
    for cid in sorted(a):
        x,y=a[cid],b[cid]
        old=read(cold/(cid+'.json.gz'));new=read(full/(cid+'.json.gz'))
        for key in ['casebook_checksum','rule_version','parameter_profile','frozen_code_file_hashes']:
            if old['manifest'][key]!=new['manifest'][key]:raise ValueError('frozen contract changed: '+key)
        if new['manifest']['baseline_equivalence_status']!='FULL_CERTIFIED_WARMUP_RESTORED':raise ValueError('not full warmup')
        path=lambda r:[{'date':t['date'],'state':t['state']} for t in r['timeline']]
        oldr={k:x[k] for k in fields};oldr['state_path']=path(x)
        newr={k:y[k] for k in fields};newr['state_path']=path(y)
        rows.append({'case_id':cid,'case_name':x['case_name'],'case_type':x['case_type'],
          'cold_start_result':oldr,'full_warmup_result':newr,
          'state_path_changed':oldr['state_path']!=newr['state_path'],
          'first_S1_changed':x['first_S1_date']!=y['first_S1_date'],
          'first_S2_changed':x['first_S2_date']!=y['first_S2_date'],
          'miss_changed':(x['MISS'],x['miss_category'])!=(y['MISS'],y['miss_category']),
          'false_positive_changed':(x['false_S2_days'],x['false_confirmation_count'])!=(y['false_S2_days'],y['false_confirmation_count']),
          'lag_changed':x['S2_lag_observed']!=y['S2_lag_observed'],
          'lifecycle_changed':old['manifest']['component_checksums']['lifecycles']!=new['manifest']['component_checksums']['lifecycles'],
          'transition_changed':x['transition_count']!=y['transition_count'],
          'freeze_changed':x['freeze_days']!=y['freeze_days'],
          'churn_changed':(x['reversal_count'],x['short_interval_reversal_count'])!=(y['reversal_count'],y['short_interval_reversal_count'])})
    counts={k:sum(r[k] for r in rows) for k in rows[0] if k.endswith('_changed')}
    summary={'cases':rows,'change_counts':counts,'cold_start_status':'DIAGNOSTIC_ONLY',
        'formal_baseline':'full_warmup','cold_start_bias':'limited' if not any(counts.values()) else 'observed; see case-level changes',
        'cold_start_archived_aggregate':read(cold/'aggregate_metrics.json')['overall'],
        'cold_start_aggregate':aggregate(normalized)['overall'],
        'same_evaluator_comparison':True,
        'cold_metrics_recomputed_from_immutable_state_business_only':True,
        'cold_original_results_modified':False,
        'metric_contract_adjustment_cases':[r['case_id'] for r in normalized if next(x for x in archived if x['case_id']==r['case_id'])['transition_count']!=r['transition_count']],
        'full_warmup_aggregate':read(full/'aggregate_metrics.json')['overall'],
        'warmup_effect':{'miss_resolved':sum(a[c]['MISS'] and not b[c]['MISS'] for c in a),
            'miss_added':sum(not a[c]['MISS'] and b[c]['MISS'] for c in a),
            'false_positive_cases_resolved':sum(a[c]['case_type']=='negative' and a[c]['false_S2_days']>0 and b[c]['false_S2_days']==0 for c in a),
            'lag_changed_cases':[r['case_id'] for r in rows if r['lag_changed']]},
        'pit_level':'effective_pit','knowledge_time_unverified':True,'production_writes':0}
    write(output/'cold_metrics_same_evaluator.json',normalized)
    summary['checksum']=digest(summary);write(output/'FULL_WARMUP_vs_COLD_START_DIFF.json',summary)
    lines=['# FULL WARMUP vs COLD START DIFF','','Cold-start 全部保留为 DIAGNOSTIC_ONLY；正式 Baseline 使用完整认证预热结果。比较双方采用同一版评估器，原冷启动文件未覆盖；评估口径修订单独记录，避免把统计变化误归因于预热。',
        '', '| Case | 类型 | S1 首日（旧→新） | S2 首日（旧→新） | 漏报（旧→新） | 误报天（旧→新） | 路径变化 | 生命周期变化 |',
        '|---|---|---|---|---|---|---|---|']
    for r in rows:
        x,y=r['cold_start_result'],r['full_warmup_result']
        pair=lambda k:f"{x[k]} → {y[k]}"
        lines.append(f"| {r['case_id']} | {r['case_type']} | {pair('first_S1_date')} | {pair('first_S2_date')} | {pair('MISS')} | {pair('false_S2_days')} | {r['state_path_changed']} | {r['lifecycle_changed']} |")
    lines+=['','逐日状态路径、滞后、反复、Freeze 和生命周期数详见同名 JSON；空值保持 NULL。',
        '', '只在规则、数据窗口、样本和标签相同的条件下归因于新增预热输入；不能据此推断规则已经优秀。']
    write(output/'diff_manifest.json',{'checksum':summary['checksum'],'production_writes':0})
    (output/'FULL_WARMUP_vs_COLD_START_DIFF.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cold',type=Path,required=True);p.add_argument('--full',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();compare(a.cold,a.full,a.output)
