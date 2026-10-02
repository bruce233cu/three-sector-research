"""Independent arithmetic checks against original archives; never evaluates rules."""
import csv,gzip,hashlib,json,statistics
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
D=ROOT/'reports/milestone-d-rule-diagnostic'
R=ROOT/'reports/milestone-d-baseline-v1/runs/historical-blind-v1-20261002-diagnostic-v2'
def load(p):
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def verify():
    book=load(ROOT/'reports/milestone-d-baseline-v1/casebook.json'); summary=load(D/'diagnostic_summary.json')
    assert book['checksum']==summary['casebook_checksum']
    assert book['rule_version']==summary['rule_version'] and book['parameter_profile']==summary['parameter_profile']
    rows={c['case_id']:load(R/(c['case_id']+'.json.gz'))['rows'] for c in book['cases']}
    cases={c['case_id']:c for c in book['cases']}
    rule=lambda r,rid:next(x for x in r['rules'] if x['rule_id']==rid)
    events={cid:[r for r in rr if cases[cid]['start_date']<=r['snapshot']['as_of_date']<=cases[cid]['end_date']] for cid,rr in rows.items()}
    groups=['A','B','C','D','enhancers']; counts=Counter(); sole=Counter(); solecases=defaultdict(set); rates=defaultdict(list)
    previous_vote_distribution=Counter(); exitvotes=Counter(); newnegative=[]; independent_same=0
    for cid,rr in rows.items():
        kind=cases[cid]['case_type']; ev=events[cid]
        for rid in ['B','D','C4','D.newhigh','E3']:
            rates[(kind,rid)].append(sum(rule(r,rid)['passed'] is True for r in ev)/len(ev))
        counts[kind+'_event_days']+=len(ev)
        if kind=='positive':
            counts['positive_full_window_S1']+=any(r['state']['state']=='S1' for r in rr)
            counts['positive_full_window_S2']+=any(r['state']['state']=='S2' for r in rr)
            counts['positive_event_window_S2']+=any(r['state']['state']=='S2' for r in ev)
        if kind=='negative':
            counts['negative_any_event_S2_cases']+=any(r['state']['state']=='S2' for r in ev)
            counts['negative_false_S2_days']+=sum(r['state']['state']=='S2' for r in ev)
            for r in ev:
                t=r['state']['transition']
                if t and t['from_state']=='S1' and t['to_state']=='S2':newnegative.append(cid)
        counts['case_days']+=len(rr);counts['transitions']+=sum(bool(r['state']['transition']) for r in rr);counts['freeze_days']+=sum(r['state']['stage_frozen'] for r in rr)
        for i,r in enumerate(rr):
            t=r['state']['transition']
            if t and t['trigger_rule']=='candidate_failed':
                exitvotes[sum(rule(r,g)['passed'] is True for g in ['C1','C2','C3','C4','C5'])]+=1
                if i:previous_vote_distribution[sum(rule(rr[i-1],g)['passed'] is True for g in ['C1','C2','C3','C4','C5'])]+=1
        for r in ev:
            a=rule(r,'D.newhigh'); b=rule(r,'E3')
            assert all(a[k]==b[k] for k in ['actual_value','threshold','operator','passed'])
            independent_same+=1
            if kind!='positive' or r['state']['state']=='S2':continue
            values={g:rule(r,g)['passed'] for g in groups}
            if sum(v is True for v in values.values())==4:
                g=next(g for g,v in values.items() if v is not True)
                sole[g]+=1;solecases[g].add(cid)
                if r['state']['previous_state']=='S1' and not r['state']['stage_frozen'] and r['state']['reason']!='freeze_recovery_first_session_no_transition':sole[g+'_eligible']+=1
    expected={'positive_full_window_S1':10,'positive_full_window_S2':6,'positive_event_window_S2':5,'negative_any_event_S2_cases':4,'negative_false_S2_days':11,'transitions':341,'freeze_days':63,'case_days':1631}
    for k,v in expected.items():assert counts[k]==v==summary['aggregate']['overall'][k],(k,counts[k],v)
    assert newnegative==['N10'];assert sole['B']==25 and len(solecases['B'])==7 and sole['B_eligible']==8
    assert sole['C']==7 and sole['C_eligible']==2 and sole['A_eligible']==1
    assert independent_same==450 and sum(exitvotes.values())==138 and exitvotes[2]==80
    matrix={r['rule_id']:r for r in csv.DictReader((D/'rule_discrimination_matrix.csv').open())}
    computed={}
    for (kind,rid),v in rates.items():
        rate=statistics.mean(v);assert abs(rate-float(matrix[rid][kind+'_case_equal_pass_rate_all_days']))<1e-12
        computed[kind+'_'+rid]=rate
    for check in summary['frozen_code_checks']:
        assert hashlib.sha256((ROOT/check['path']).read_bytes()).hexdigest()==check['expected']
    assert hashlib.sha256((R/'causal_context.json.gz').read_bytes()).hexdigest()==summary['context_source_sha256']
    for cid,c in summary['source_case_checksums'].items():
        # Source manifest uses SHA256 of the original compressed bytes.
        if isinstance(c,str):assert hashlib.sha256((R/(cid+'.json.gz')).read_bytes()).hexdigest()==c
    candidates=load(D/'calibration_candidates.json');assert len(candidates)==5
    result={'status':'PASS','scope':'independent arithmetic on original frozen case archives; no rule or production replay','casebook':book['casebook_version'],'headline_recomputed':dict(counts),'new_negative_confirmations':newnegative,'sole_blocker_days':dict(sole),'B_sole_cases':sorted(solecases['B']),'case_equal_rates':computed,'D_newhigh_E3_identical_event_rows':independent_same,'candidate_failure_votes':dict(exitvotes),'previous_candidate_votes':dict(previous_vote_distribution),'frozen_files_verified':len(summary['frozen_code_checks']),'production_writes':0,'calibration_executed':False}
    return result
if __name__=='__main__':
    result=verify();(D/'validation_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'case_days':result['headline_recomputed']['case_days'],'checks':'headlines, frequency denominators, legal eligibility, duplication, frozen source hashes'},ensure_ascii=False))
