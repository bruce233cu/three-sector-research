"""V2.2 §9 independent rules. Unknown evidence is neither false nor zero."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import operator
from .metrics import metric_availability


def tri_all(items):
    items=list(items)
    return False if False in items else None if None in items else True


def tri_any(items):
    items=list(items)
    return True if True in items else None if None in items else False


def at_least(items, minimum, valid_min=0):
    items=list(items)
    valid=sum(v is not None for v in items)
    if valid<valid_min:
        return None
    passed=sum(v is True for v in items)
    if passed>=minimum:
        return True
    return False if passed+sum(v is None for v in items)<minimum else None


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    rule_version: str
    object_id: str
    trade_date: str
    metric: str
    actual_value: object
    threshold: object
    operator: str
    passed: bool | None
    reason: str | None
    parameter_profile: str
    metric_availability_version: str


def evaluate_rules(snapshot, profile):
    rules=[]
    def emit(rid, metric, actual, threshold, op, passed, reason=None):
        result=RuleResult(rid,snapshot['rule_version'],snapshot['object_id'],snapshot['as_of_date'],
            metric,actual,threshold,op,passed,reason if reason else ('passed' if passed is True else
            'threshold_not_met' if passed is False else 'insufficient_evidence'),profile['profile_id'],
            snapshot['metric_availability_version'])
        rules.append(asdict(result))
        return passed
    def compare(rid, metric, threshold, op, threshold_metric=None):
        fields=[metric]+([threshold_metric] if threshold_metric else [])
        av=metric_availability(snapshot,fields)
        left=av[metric]['value']
        right=av[threshold_metric]['value'] if threshold_metric else threshold
        if any(av[x]['status']!='available' for x in fields) or right is None:
            return emit(rid,metric,left,right,op,None,';'.join(av[x]['reason'] or '' for x in fields))
        fn={'>':operator.gt,'>=':operator.ge,'<':operator.lt,'<=':operator.le,'==':operator.eq}[op]
        return emit(rid,metric,left,right,op,fn(left,right))
    def group(rid, ids, result, threshold, op):
        return emit(rid,','.join(ids),[next(r['passed'] for r in rules if r['rule_id']==i) for i in ids],threshold,op,result)
    c=profile['candidate'];q=profile['confirm']
    c1=compare('C1','rs_5_pct',c['rs5_cross_section_pct_max'],'<=')
    c2=compare('C2','rs_10',c['rs10_min'],'>')
    c3=compare('C3','win_5',c['win5_min'],'>=')
    c4a=compare('C4.mean20','turnover_share',None,'>','turnover_share_mean20')
    c4b=compare('C4.intensity','turnover_intensity',c['turnover_intensity_min'],'>')
    c4=group('C4',['C4.mean20','C4.intensity'],tri_any([c4a,c4b]),1,'OR')
    c5a=compare('C5.up','up_ratio',None,'>','all_a_up_ratio')
    c5b=compare('C5.ma20','above_ma20',None,'>','all_a_above_ma20')
    c5=group('C5',['C5.up','C5.ma20'],tri_any([c5a,c5b]),1,'OR')
    candidate=group('candidate',['C1','C2','C3','C4','C5'],at_least([c1,c2,c3,c4,c5],c['candidate_min_pass_count'],4),
                    {'valid_min':4,'pass_min':c['candidate_min_pass_count']},'COUNT')
    ar=compare('A.return','rs_10',q['rs10_min'],'>')
    ap=compare('A.rank','rs_10_pct',q['rs10_cross_section_pct_max'],'<=')
    a=group('A',['A.return','A.rank'],tri_all([ar,ap]),2,'AND')
    b5=compare('B.win5','win_5',q['win5_min'],'>=')
    b10=compare('B.win10','win_10',q['win10_min'],'>=')
    b=group('B',['B.win5','B.win10'],tri_any([b5,b10]),1,'OR')
    cp=compare('C.percentile','turnover_pct_60',q['turnover_pct60_min'],'>=')
    cn=compare('C.trend','turnover_not_three_valid_days_down',True,'==')
    cg=group('C',['C.percentile','C.trend'],tri_all([cp,cn]),2,'AND')
    d1=compare('D.up','up_ratio',None,'>','all_a_up_ratio')
    d2=compare('D.ma20','above_ma20',q['above_ma20_min'],'>=')
    d3=compare('D.newhigh','new_high_60',None,'>','new_high_60_lag3')
    d=group('D',['D.up','D.ma20','D.newhigh'],at_least([d1,d2,d3],q['breadth_min_pass_count']),q['breadth_min_pass_count'],'COUNT')
    e1=compare('E1','rs_20',0,'>')
    e2=compare('E2','above_ma60',None,'>','above_ma60_lag3')
    e3=compare('E3','new_high_60',None,'>','new_high_60_lag3')
    completed=profile.get('clarification_version') == 'V2.2.1-mainline-state-completion-2026-10-02'
    if completed:
        e4low=compare('E4.not_high','top3_turnover_pct_250',.90,'<')
        # High concentration requires reliable synchronous-breadth enhancement.
        # That optional structural evidence stays deferred; do not fill false.
        e4=emit('E4','top3_turnover_pct_250',snapshot.get('top3_turnover_pct_250'),.90,'NOT_HIGH_OR_ENHANCEMENT',
                True if e4low is True else None,'passed' if e4low is True else 'enhancement_evidence_deferred' if e4low is False else 'insufficient_evidence')
    else:
        e4=emit('E4','top3_turnover_share',snapshot.get('top3_turnover_share'),.90,'historical_percentile_OR_breadth_improvement',None,
            'BUSINESS_RULE_CONFLICT:E4_history_window_and_synchronous_breadth_definition_missing')
    e5=emit('E5','active_subtheme_count',snapshot.get('active_subtheme_count'),None,'increase',None,
            'enhancement_evidence_deferred' if completed else 'family_evidence_unavailable_not_counted')
    enhancer=group('enhancers',['E1','E2','E3','E4','E5'],at_least([e1,e2,e3,e4] if completed else [e1,e2,e3,e4,e5],q['enhancer_min_pass_count']),q['enhancer_min_pass_count'],'COUNT')
    confirm=group('confirm',['A','B','C','D','enhancers'],tri_all([a,b,cg,d,enhancer]),5,'AND')
    if completed:
        wa=compare('weaken.slope','rs5_slope',0,'<')
        wb=compare('weaken.rank','rs10_percentile_deteriorating',True,'==')
        decline=[]
        weak_zone=[]
        fields=['up_ratio','above_ma20','above_ma60','new_high_60']
        for field in fields:
            decline.append(compare('weaken.breadth.'+field,field,None,'<',field+'_lag3'))
            weak_zone.append(compare('retire.breadth.'+field,field,None,'<',field+'_median20'))
        wc=group('weaken.breadth',['weaken.breadth.'+f for f in fields],at_least(decline,3),3,'COUNT')
        weaken=group('weaken',['weaken.slope','weaken.rank','weaken.breadth'],at_least([wa,wb,wc],2),2,'COUNT')
        ra1=compare('retire.rs10','rs_10',0,'<')
        ra2=compare('retire.rs20','rs_20',0,'<')
        ra=group('retire.returns',['retire.rs10','retire.rs20'],tri_all([ra1,ra2]),2,'AND')
        rb=compare('retire.rank','rs_10_pct',.50,'>')
        rc=group('retire.breadth',['retire.breadth.'+f for f in fields],at_least(weak_zone,3),3,'COUNT')
        retire=group('retire',['retire.returns','retire.rank','retire.breadth'],at_least([ra,rb,rc],2),2,'COUNT')
        recover=group('recover',['confirm'],confirm,2,'CONFIRM_CONSECUTIVE_KERNEL')
        for name in ['core','midcap','family']:
            emit('enhancement.'+name,name,None,None,'DEFERRED',None,'enhancement_evidence_deferred')
    else:
        # V2.2 names these groups but does not quantify their estimator/window or
        # structural/core/family deterioration. Do not substitute developer guesses.
        deterioration=[]
        for name in ['RS','turnover','breadth','structure']:
            deterioration.append(emit('weaken.'+name,name,None,None,'frozen_contract_group',None,
                'BUSINESS_RULE_CONFLICT:deterioration_group_executable_definition_incomplete'))
        weaken=group('weaken',['weaken.RS','weaken.turnover','weaken.breadth','weaken.structure'],
                     at_least(deterioration,profile['weaken']['deterioration_group_min']),profile['weaken']['deterioration_group_min'],'COUNT')
        exit_rank=compare('retire.rank','rs_10_pct',profile['retire']['rs10_cross_section_pct_exit'],'>')
        retire=emit('retire','core_deterioration_groups',None,profile['retire']['core_deterioration_group_min'],'COUNT_AND_ENHANCER',None,
                    'BUSINESS_RULE_CONFLICT:core_group_definition_and_structure_or_family_exit_missing')
        recover=emit('recover','confirm_recovery',confirm,None,'recover_to_confirmed',None,
                     'BUSINESS_RULE_CONFLICT:recovery_consecutive_and_debounce_policy_missing')
    return {'rules':rules,'evidence':{'candidate':candidate,'confirm':confirm,'weaken':weaken,'retire':retire,'recover':recover},
            'trigger_rules':[r['rule_id'] for r in rules if r['passed'] is True],
            'failed_rules':[r['rule_id'] for r in rules if r['passed'] is False],
            'unavailable_rules':[r['rule_id'] for r in rules if r['passed'] is None]}

