"""Transparent event/full-window statistics; ambiguous labels are not scored."""
from collections import Counter, defaultdict
from statistics import mean, median
import math
from mainline.engine.replay import digest

def fraction(n,d):return n/d if d else None

def longest_run(values):
    best=current=0
    for v in values:
        current=current+1 if v else 0;best=max(best,current)
    return best

def churn(states, dates, max_interval=5):
    changes=[(i,states[i-1],states[i]) for i in range(1,len(states)) if states[i]!=states[i-1]]
    # A reversal revisits any already seen state in the current observed window.
    # Count exact A->B->A separately; do not assume every new lifecycle is wrong.
    seen={states[0]};reversals=short=0;last_index={states[0]:0}
    for i,a,b in changes:
        if b in seen:
            reversals+=1
            if i-last_index[b]<=max_interval:short+=1
        seen.add(b)
        last_index[a]=i-1;last_index[b]=i
    direct=sum(changes[i][1]==changes[i-1][2] and changes[i][2]==changes[i-1][1]
               for i in range(1,len(changes)))
    rolling=max((sum(dates.index(d)>=dates.index(day)-19 and dates.index(d)<=dates.index(day)
                for d in [dates[x[0]] for x in changes]) for day in dates),default=0)
    return {'transition_count':len(changes),'reversal_count':reversals,
            'short_interval_reversal_count':short,'direct_A_B_A_count':direct,
            'max_transitions_in_20_sessions':rolling}

def evaluate_case(case, business, calendar, stable_min=3, short_interval=5):
    rows=business['rows'];days=[r['snapshot']['as_of_date'] for r in rows]
    if not rows or days!=sorted(set(days)):raise ValueError('empty/unordered case')
    expected=[d for d in calendar if case['pre_window_start']<=d<=case['post_window_end']]
    if days!=expected:raise ValueError('case calendar gap')
    event=[r for r in rows if case['start_date']<=r['snapshot']['as_of_date']<=case['end_date']]
    states=[r['state']['state'] for r in rows];evstates=[r['state']['state'] for r in event]
    first=lambda st:next((r['snapshot']['as_of_date'] for r in rows if r['state']['state']==st),None)
    first_event=lambda st:next((r['snapshot']['as_of_date'] for r in event if r['state']['state']==st),None)
    transitions=[r['state']['transition'] for r in rows if r['state']['transition']]
    event_transitions=[r['state']['transition'] for r in event if r['state']['transition']]
    freezes=[r for r in rows if r['state']['stage_frozen']]
    frozen_changes=[r for r in freezes if r['state']['transition'] is not None]
    lc=business['lifecycles'];lcids=[x['lifecycle_id'] for x in lc]
    if len(lcids)!=len(set(lcids)):raise ValueError('duplicate lifecycle identity')
    known_first=lambda field:min([x[field] for x in lc if x.get(field)] or [None])
    lag=lambda d:calendar.index(d)-calendar.index(case['start_date']) if d else None
    core_fields=['sector_return','benchmark_return','rs_5','rs_10','rs_20','up_ratio','above_ma20','above_ma60','new_high_60','turnover_share']
    rule_count=sum(len(r['rules']) for r in rows)
    membership=fraction(sum(bool(r['snapshot'].get('membership_checksum')) and r['snapshot'].get('member_count',0)>0 for r in rows),len(rows))
    core=fraction(sum(r['snapshot'].get(k) is not None for r in rows for k in core_fields),len(rows)*len(core_fields))
    missing_core=[r for r in rows if any(r['snapshot'].get(k) is None for k in core_fields)]
    overlays=['turnover_pct_60','turnover_pct_250','top3_turnover_pct_250','rs5_slope','up_ratio_median20']
    coverage={'membership_resolution':membership,
        'valid_member_price_ratio_mean':mean(r['snapshot']['valid_member_count']/r['snapshot']['member_count'] for r in rows),
        'benchmark':fraction(sum(r['snapshot'].get('benchmark_return') is not None for r in rows),len(rows)),
        'benchmark_cross_section_ratio_mean':mean(r['snapshot']['metric_coverage_json']['benchmark'] for r in rows),
        'core_metric':core,
        'overlay_availability':{f:fraction(sum(r['snapshot'].get(f) is not None for r in rows),len(rows)) for f in overlays},
        'deferred_metrics':{'turnover_cap_deviation':None,'top3_return_contribution':None},
        'rule_evidence_records':fraction(sum(bool(r['rules']) for r in rows),len(rows)),
        'rule_predicates_known':fraction(sum(x['passed'] is not None for r in rows for x in r['rules']),rule_count),
        'source':fraction(sum(bool(r['snapshot']['source_snapshot_ids']) for r in rows),len(rows)),
        'knowledge_time_unverified_ratio':1.0,'strict_pit_coverage':0.0,'effective_pit_board_coverage':membership}
    detected='S2' in states;event_detected='S2' in evstates
    if detected:miss=None if event_detected else 'confirmed_outside_event_window'
    elif len(missing_core)==len(rows):miss='data_insufficient_unassessable'
    elif not any(s=='S1' for s in states):miss='never_S1'
    elif len(freezes)>len(rows)/2:miss='freeze_heavy_unconfirmed'
    else:miss='S1_without_S2'
    # False confirmations count new S1->S2 only; S3->S2 recoveries are separate.
    confirmations=sum(t['from_state']=='S1' and t['to_state']=='S2' for t in event_transitions)
    inherited=evstates[0]=='S2' and event[0]['state']['previous_state']=='S2'
    s2count=evstates.count('S2');stable=longest_run([s=='S2' for s in evstates])
    frozen_reason=Counter(r['state']['freeze_reason'] for r in freezes)
    resume=Counter(r['state']['resume_reason'] for r in rows if r['state'].get('resume_reason'))
    freeze_violations=sum(r['state']['stage_frozen'] and
        (r['state']['state']!=r['state']['previous_state'] or r['state']['transition'] is not None) for r in rows)
    retire_dates=[x['closed_at'] for x in lc if x.get('closed_at')]
    reentry=[t for t in transitions if t['from_state']=='S4' and t['to_state']=='S1']
    rapid=sum(any(0<=calendar.index(t['trigger_date'])-calendar.index(d)<=5 for d in retire_dates) for t in reentry)
    first_c=known_first('confirmed_at')
    earliest_cand=known_first('candidate_at')
    transition_evidence=Counter(x['rule_id'] for r in event for x in r['rules'] if x['passed'] is False)
    confirm_failures=Counter(x['rule_id'] for r in event for x in r['rules'] if x['passed'] is False and x['rule_id'] in ['A','B','C','D','enhancers'])
    post_confirmation=[]
    for life in lc:
        confirmed=life.get('confirmed_at')
        if not confirmed:continue
        horizons={}
        for horizon in [5,10,20,60]:
            if confirmed not in days or days.index(confirmed)+horizon>=len(rows):
                horizons[str(horizon)]={'relative_return':None,'false_breakout':None,
                    'reason':'left_censored_confirmation' if confirmed<days[0] else 'right_censored_horizon'}
                continue
            i=days.index(confirmed);follow=rows[i+1:i+horizon+1]
            pairs=[(r['snapshot']['sector_return'],r['snapshot']['benchmark_return']) for r in follow]
            good=all(a is not None and b is not None for a,b in pairs)
            fb=any(r['state']['state'] in ['S3','S4'] for r in follow) and follow[-1]['state']['state']!='S2'
            horizons[str(horizon)]={'relative_return':math.prod(1+a for a,b in pairs)-math.prod(1+b for a,b in pairs) if good else None,
                'false_breakout':fb if horizon in [5,10] else None,'reason':None if good else 'price_or_benchmark_DATA_GAP'}
        post_confirmation.append({'lifecycle_id':life['lifecycle_id'],'confirmed_at':confirmed,'horizons':horizons})
    return {'case_id':case['case_id'],'case_name':case['case_name'],'case_type':case['case_type'],
        'market_style':case['market_style'],'market_regime':case['market_regime'],'mainline_type':case['mainline_type'],
        'episode_cluster':case['episode_cluster'],'days':len(rows),'event_days':len(event),
        'S1_detected':'S1' in states,'S2_detected':detected,'event_S1_detected':'S1' in evstates,'event_S2_detected':event_detected,
        'first_S1_date':first('S1'),'first_S2_date':first('S2'),'event_first_S1_date':first_event('S1'),'event_first_S2_date':first_event('S2'),
        'left_censored_S1':states[0]=='S1','left_censored_S2':states[0]=='S2',
        'S1_lag_observed':lag(first('S1')),'S2_lag_observed':lag(first('S2')),
        'first_confirmation_lag':lag(first_c),'first_candidate_lag':lag(earliest_cand),
        'peak_state':max(states),'confirmed_duration':states.count('S2'),'event_confirmed_days':s2count,
        'MISS':case['case_type']=='positive' and not detected,'miss_category':miss if case['case_type']=='positive' else None,
        'entered_S1':any(t['to_state']=='S1' for t in event_transitions),'entered_S2':confirmations>0,
        'false_S2_days':s2count if case['case_type']=='negative' else None,
        'false_confirmation_count':confirmations if case['case_type']=='negative' else None,
        'false_recovery_count':sum(t['from_state']=='S3' and t['to_state']=='S2' for t in event_transitions) if case['case_type']=='negative' else None,
        'max_false_state':max(evstates) if case['case_type']=='negative' else None,
        'false_positive_duration':s2count if case['case_type']=='negative' else None,
        'stable_false_S2':stable>=stable_min if case['case_type']=='negative' else None,
        'longest_event_S2_run':stable,'inherited_S2_at_event_start':inherited,
        'no_mainline_precision':fraction(len(event)-s2count,len(event)) if case['case_type']=='negative' else None,
        **churn(states,days,short_interval),
        'lifecycle_count':len(lc),'new_lifecycle_count':sum(case['pre_window_start']<=x['start_date']<=case['post_window_end'] for x in lc),
        'first_lifecycle_start':earliest_cand,'first_confirmation':first_c,'first_weaken':known_first('weakened_at'),
        'first_retire':min([x['closed_at'] for x in lc if x.get('closed_at') and x.get('close_reason')=='retire'] or [None]),
        'first_closed_lifecycle':known_first('closed_at'),'highest_state':max([x['highest_state'] for x in lc] or states),
        'reentry_count':len(reentry),'rapid_reentry_count':rapid,'duplicate_lifecycle_count':len(lcids)-len(set(lcids)),
        'right_censored_open_lifecycles':sum(x.get('closed_at') is None for x in lc),
        'retreat_delay':None,'retreat_delay_reason':'独立结构转弱参考日期未标注，不能编造早退/晚退标准答案。',
        'freeze_days':len(freezes),'event_freeze_days':sum(r['state']['stage_frozen'] for r in event),
        'freeze_reason':dict(frozen_reason),'freeze_before_transition_count':len(frozen_changes),
        'freeze_resume_mode':dict(resume),'freeze_transition_violations':freeze_violations,
        'coverage':coverage,'data_gap_days':len(missing_core),
        'baseline_equivalence':business['manifest'].get('baseline_equivalence_status','DATA_GAP_MISSING_84_WARMUP_DAYS'),
        'top_confirm_blockers':dict(confirm_failures.most_common()),
        'top_failed_rule_evidence':dict(transition_evidence.most_common(12)),
        'checksum':business['manifest']['checksum'],'post_confirmation_diagnostics':post_confirmation,
        'timeline':[{'date':r['snapshot']['as_of_date'],'state':r['state']['state'],
                    'frozen':r['state']['stage_frozen'],'reason':r['state']['reason'],
                    'transition':r['state']['transition'],'lifecycle_id':r['state']['lifecycle_id']} for r in rows]}

def aggregate(results):
    def group(rs):
        p=[r for r in rs if r['case_type']=='positive'];n=[r for r in rs if r['case_type']=='negative']
        lags=[r['S2_lag_observed'] for r in p if r['S2_lag_observed'] is not None]
        return {'cases':len(rs),'positive_cases':len(p),'negative_cases':len(n),
            'positive_full_window_S1':sum(r['S1_detected'] for r in p),
            'positive_full_window_S2':sum(r['S2_detected'] for r in p),
            'positive_event_window_S2':sum(r['event_S2_detected'] for r in p),
            'MISS':sum(r['MISS'] for r in p),'miss_categories':dict(Counter(r['miss_category'] for r in p if r['miss_category'])),
            'negative_any_event_S2_cases':sum(r['false_S2_days']>0 for r in n),
            'negative_stable_S2_cases':sum(r['stable_false_S2'] for r in n),
            'negative_new_confirmation_cases':sum(r['false_confirmation_count']>0 for r in n),
            'negative_false_S2_days':sum(r['false_S2_days'] for r in n),
            'negative_new_confirmations':sum(r['false_confirmation_count'] for r in n),
            'negative_no_mainline_precision':fraction(sum(r['event_days']-r['false_S2_days'] for r in n),sum(r['event_days'] for r in n)),
            'S2_lag_observed_median':median(lags) if lags else None,
            'transitions':sum(r['transition_count'] for r in rs),'reversals':sum(r['reversal_count'] for r in rs),
            'short_reversals':sum(r['short_interval_reversal_count'] for r in rs),
            'freeze_days':sum(r['freeze_days'] for r in rs),'case_days':sum(r['days'] for r in rs),
            'freeze_transition_violations':sum(r['freeze_transition_violations'] for r in rs),
            'duplicate_lifecycles':sum(r['duplicate_lifecycle_count'] for r in rs),
            'knowledge_time_unverified_ratio':1.0,'strict_pit_coverage':0.0,
            'qualification':'相关案例，不等于独立样本准确率；完整预热资格见每个case manifest。'}
    output={'overall':group(results),'strata':{}}
    for field in ['case_type','market_style','market_regime','mainline_type','episode_cluster']:
        groups=defaultdict(list)
        for r in results:groups[r[field]].append(r)
        output['strata'][field]={k:group(v) for k,v in groups.items()}
    output['checksum']=digest(output)
    return output
