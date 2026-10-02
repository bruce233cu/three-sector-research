"""BOARD-level temporal audit. Does not certify missing stock-level payloads."""
from copy import deepcopy
import math
from mainline.engine.replay import digest
from mainline.backtest.runner import context_replay, resolver_for

def audit(panel,members,dates,profile,context,cutoff='2024-11-15', *, warmup_panel=()):
    bydate={}
    all_board=list(warmup_panel)+panel
    for r in all_board:
        key=(r['as_of_date'],r['object_id'])
        if key in bydate:raise ValueError('duplicate input')
        bydate[key]=r
    for d in dates:
        m=resolver_for(members)(d)
        if set(m['members'])!={r['object_id'] for r in all_board if r['as_of_date']==d}:
            raise ValueError('future/static universe mismatch')
    future_checkpoint=0;frozen_change=0;rank_date=0
    for r in context['rows']:
        s=r['snapshot'];state=r['state'];cp=state['checkpoint'];d=s['as_of_date']
        if cp['last_date']!=d or state['trade_date']!=d:future_checkpoint+=1
        lc=cp.get('lifecycle') or {}
        for field in ['candidate_at','confirmed_at','weakened_at','closed_at','last_transition_date']:
            if lc.get(field) and lc[field]>d:future_checkpoint+=1
        if any(x['trade_date']!=d or x['object_id']!=s['object_id'] for x in r['rules']):rank_date+=1
        if state['stage_frozen'] and (state['transition'] or state['state']!=state['previous_state']):frozen_change+=1
    # Once the complete lookback exists in the archive, reproduce core RS from past returns.
    rs_checks=rs_mismatch=0
    for oid in sorted({r['object_id'] for r in panel}):
        history=[bydate[(d,oid)] for d in dates]
        for i,r in enumerate(history):
            for n in [5,10,20]:
                if i<n-1:continue
                pairs=[(x['sector_return'],x['benchmark_return']) for x in history[i-n+1:i+1]
                       if x['sector_return'] is not None and x['benchmark_return'] is not None]
                expected=math.prod(1+a for a,b in pairs)-math.prod(1+b for a,b in pairs) if len(pairs)/n>=.9 else None
                actual=r['rs_'+str(n)];rs_checks+=1
                if (expected is None)!=(actual is None) or (expected is not None and abs(expected-actual)>1e-12):rs_mismatch+=1
    prefix=context_replay(panel,dates,profile,members,cutoff,warmup_panel=warmup_panel)
    checks=[]
    # Each variant changes post-cutoff information only. Prefix states/rules/checkpoints
    # must equal an independently truncated uninterrupted run for all 31 industries.
    variants=['membership','universe','price','turnover','benchmark','MA','percentile','lifecycle','case_labels']
    expected={'rows':[r for r in context['rows'] if r['snapshot']['as_of_date']<=cutoff],
              'cross_sections':[r for r in context['cross_sections'] if r['trade_date']<=cutoff],
              'seed':'S0','events':[r['state']['transition'] for r in context['rows']
                   if r['snapshot']['as_of_date']<=cutoff and r['state']['transition']]}
    if digest(prefix)!=digest(expected):raise ValueError('prefix influenced by future')
    for name in variants:
        p=deepcopy(panel);m=deepcopy(members)
        for row in p:
            if row['as_of_date']<=cutoff:continue
            if name in ['membership','universe']:m[row['as_of_date']]['members'][row['object_id']]=['future_poison']
            elif name=='price':row.update(sector_return=999.,rs_5=999.,rs_10=999.,rs_20=999.)
            elif name=='turnover':row.update(turnover_share=999.,turnover_intensity=999.)
            elif name=='benchmark':row['benchmark_return']=999.
            elif name=='MA':row.update(above_ma20=999.,above_ma60=999.,new_high_60=999.)
            elif name=='percentile':row['rs_10_pct']=999.
            elif name=='lifecycle':row['lifecycle']={'state':'S2','confirmed_at':'2099-01-01'}
            elif name=='case_labels':row['expected_behavior']='always S2'
        result=context_replay(p,dates,profile,m,cutoff,warmup_panel=warmup_panel)
        checks.append({'input':name,'cutoff':cutoff,'prefix_state_rule_checkpoint_lifecycle_unchanged':digest(result)==digest(prefix)})
    return {'scope':'certified BOARD archive + frozen adapter temporal contract; not independent stock-bar recalc',
        'pit_level':'effective_pit','knowledge_time_unverified':True,
        'strict_knowledge_time_verified':False,'stock_level_PIT_independently_recalculated':False,
        'effective_membership_checks':len(panel),'same_day_rank_and_evidence_violations':rank_date,
        'future_checkpoint_lifecycle_violations':future_checkpoint,'freeze_transition_violations':frozen_change,
        'past_only_core_RS_checks':rs_checks,'past_only_core_RS_mismatches':rs_mismatch,
        'future_sensitivity_checks':checks,'future_leakage_detected':future_checkpoint>0 or rank_date>0 or rs_mismatch>0 or not all(c['prefix_state_rule_checkpoint_lifecycle_unchanged'] for c in checks),
        'raw_source_limitations':['个股原始行情和预热板块未完整归档，无法独立证明每个个股MA与股票池有效时间。','重复采购时间不等于历史已知时间；available_at缺失保持NULL。','标签及旧生命周期只在报告层，输入白名单排除；敏感性检查用于发现执行层前视，不代替上游时点认证。']}
