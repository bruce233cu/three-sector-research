"""Frozen Baseline V1 replay of certified BOARD inputs, not inherited states."""
import gzip
import json
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from mainline.engine.replay import replay, digest
from mainline.production.daily import evolve

BASE_SHA = '4e38d4e16f84fb047380f8339135eefe536979ff'
RULE = 'mainline_v2.2.1_state_completion_v1'
PROFILE = 'industry_trend_v221_state_completion_v1'
PROFILE_PATH = 'config/parameter_profile_industry_trend_v221_state_completion_v1.json'
FROZEN_FILES = [PROFILE_PATH] + ['src/mainline/engine/'+f+'.py' for f in
    ['replay','metrics','completion','rules','state_machine']] + ['src/mainline/production/daily.py']

def utc():
    return datetime.now(timezone.utc).isoformat()

def read(path):
    path = Path(path)
    return json.loads(gzip.open(path,'rt').read() if path.suffix=='.gz' else path.read_text())

def write(path, payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        raise ValueError('immutable result already exists: '+str(path))
    data=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if path.suffix=='.gz':
        with path.open('wb') as f:
            with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:z.write(data)
    else:path.write_bytes(data+b'\n')

def validate_book(book, dates):
    checksum=digest({k:v for k,v in book.items() if k!='checksum'})
    if checksum!=book['checksum']:raise ValueError('casebook changed after freeze')
    if (book['code_sha'],book['rule_version'],book['parameter_profile'])!=(BASE_SHA,RULE,PROFILE):
        raise ValueError('unfrozen baseline')
    counts={t:sum(c['case_type']==t for c in book['cases']) for t in ['positive','negative','ambiguous']}
    if any(counts[t]<n for t,n in [('positive',8),('negative',8),('ambiguous',4)]):
        raise ValueError('insufficient case count')
    required='case_id case_name case_type sector object_id start_date end_date pre_window_start post_window_end selection_reason expected_behavior source_notes selection_frozen_at casebook_version'.split()
    ids=[]
    for c in book['cases']:
        if any(k not in c for k in required):raise ValueError('case schema incomplete')
        if c['case_type'] not in counts:raise ValueError('unknown case type')
        if c['casebook_version']!=book['casebook_version'] or c['selection_frozen_at']!=book['selection_frozen_at']:
            raise ValueError('inconsistent case freeze')
        ds=[c[k] for k in ['pre_window_start','start_date','end_date','post_window_end']]
        if ds!=sorted(ds) or any(d not in dates for d in ds):raise ValueError('invalid case dates')
        if not c['source_notes']:raise ValueError('independent selection source absent')
        ids.append(c['case_id'])
    if len(ids)!=len(set(ids)):raise ValueError('duplicate cases')
    return counts

def baseline_profile(root):
    # Bind engine bytes to starting SHA, even when the validation runner is new.
    hashes={}
    for name in FROZEN_FILES:
        frozen=subprocess.check_output(['git','show',BASE_SHA+':'+name],cwd=root)
        if frozen!=(root/name).read_bytes():raise ValueError('Baseline file modified: '+name)
        import hashlib
        hashes[name]=hashlib.sha256(frozen).hexdigest()
    p=read(root/PROFILE_PATH)
    if (p['rule_version'],p['profile_id'])!=(RULE,PROFILE):raise ValueError('profile mismatch')
    return p,hashes

def resolver_for(members):
    def resolve(day):
        m=deepcopy(members[day])
        if m['trade_date']!=day:raise ValueError('future/static membership')
        if m.get('complete') is not True:raise ValueError('incomplete membership')
        for oid,ids in m['members'].items():
            if not ids or len(ids)!=len(set(ids)):raise ValueError('invalid members')
            actual=digest({'trade_date':day,'taxonomy_version':m['taxonomy_version'],
                          'object_id':oid,'members':sorted(ids)})
            if actual!=m['checksums'][oid]:raise ValueError('membership proof mismatch')
        return m
    return resolve

def load_inputs(directory, profile):
    panel=read(directory/'data/certified_board_inputs.json.gz')
    members=read(directory/'data/daily_memberships.json.gz')
    prov=read(directory/'data_provenance.json')
    if digest(panel)!=prov['panel_checksum'] or digest(members)!=prov['membership_checksum']:
        raise ValueError('data snapshot changed')
    allowed=set(prov['board_input_fields'])
    for r in panel:
        if set(r)!=allowed:raise ValueError('state/label/derived feature in engine input')
        r.update(rule_version=profile['rule_version'],metric_availability_version=profile['metric_availability_version'],
                 run_id='historical_blind_test:'+prov['data_snapshot_version'])
    dates=sorted({r['as_of_date'] for r in panel})
    if dates!=sorted(members):raise ValueError('membership calendar gap')
    return panel, members, dates, prov

def context_replay(panel, dates, profile, members, end):
    # No prior states, case labels or post-cutoff facts enter this function.
    chosen=[deepcopy(r) for r in panel if r['as_of_date']<=end]
    calendar=[d for d in dates if d<=end]
    return replay(chosen,calendar,profile,resolver_for(members))

def case_replay(case, context, panel, dates, profile, members):
    start,end=case['pre_window_start'],case['post_window_end']
    prior=[r for r in context['rows'] if r['snapshot']['as_of_date']<start]
    actual=[deepcopy(r) for r in panel if start<=r['as_of_date']<=end]
    calendar=[d for d in dates if d<=end]
    if prior:
        seed_day=max(r['snapshot']['as_of_date'] for r in prior)
        seed={'date':seed_day,'checkpoints':{r['snapshot']['object_id']:r['state']['checkpoint']
              for r in prior if r['snapshot']['as_of_date']==seed_day}}
        result=evolve(actual,calendar,profile,resolver_for(members),[r['snapshot'] for r in prior],seed)
        seed_kind='isolated_causal_prefix_checkpoint'
    else:
        seed_day=None;seed={'checkpoints':{}}
        result=replay(actual,calendar,profile,resolver_for(members))
        seed_kind='explicit_S0_archive_anchor'
    rows=[r for r in result['rows'] if r['snapshot']['object_id']==case['object_id']]
    # Resume must equal the independent uninterrupted prefix; no planted states.
    expected=[r for r in context['rows'] if r['snapshot']['object_id']==case['object_id']
              and start<=r['snapshot']['as_of_date']<=end]
    if digest(rows)!=digest(expected):raise ValueError('checkpoint continuation changed trajectory')
    lifecycles={}
    for r in rows:
        lc=r['state']['checkpoint'].get('lifecycle')
        if lc:lifecycles[lc['lifecycle_id']]=lc
    business={'rows':rows,'lifecycles':sorted(lifecycles.values(),key=lambda x:(x['start_date'],x['lifecycle_id']))}
    component={
        'state_path':digest([r['state']['state'] for r in rows]),
        'rule_evidence':digest([r['rules'] for r in rows]),
        'checkpoints':digest([r['state']['checkpoint'] for r in rows]),
        'lifecycles':digest(business['lifecycles']),
        'full_business':digest(business)}
    ancestry={'checkpoint_date':seed_day,'checkpoint_source':seed_kind,
              'checkpoint_checksum':digest(seed),'warm_history_rows':len(prior),
              'warm_history_max_date':seed_day,'full_cross_section_industries':31,
              'continuation_matches_uninterrupted':True}
    return business,component,ancestry

def run(root, directory, output, run_id, repeat_ids=('P03','P06','N04','N05','A02')):
    started=utc();profile,hashes=baseline_profile(root)
    panel,members,dates,prov=load_inputs(directory,profile)
    book=read(directory/'casebook.json');validate_book(book,dates)
    if book['selection_frozen_at']>=started:raise ValueError('selection was not frozen before execution')
    if output.exists():raise ValueError('result version already exists')
    output.mkdir(parents=True)
    cutoff=max(c['post_window_end'] for c in book['cases'])
    context=context_replay(panel,dates,profile,members,cutoff)
    write(output/'causal_context.json.gz',context)
    manifests=[];checks=[]
    runner_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    for c in book['cases']:
        case_started=utc();business,components,ancestry=case_replay(c,context,panel,dates,profile,members)
        manifest={'backtest_run_id':run_id+':'+c['case_id'],'parent_backtest_run_id':run_id,
            'run_type':'historical_blind_test','baseline':'Baseline V1','case_id':c['case_id'],
            'casebook_version':book['casebook_version'],'casebook_checksum':book['checksum'],
            'rule_version':RULE,'parameter_profile':PROFILE,'code_sha':BASE_SHA,'runner_code_sha':runner_sha,
            'frozen_code_file_hashes':hashes,'data_snapshot_version':prov['data_snapshot_version'],
            'pit_level':prov['pit_level'],'knowledge_time_unverified':True,
            'membership_source':prov['original_provenance']['membership_source_version'],
            'source_snapshot_ids':prov['original_provenance']['source_ids'],
            'available_at':{'universe':prov['available_at'],'membership':None,'stock_price':None},
            'start_date':c['pre_window_start'],'end_date':c['post_window_end'],
            'archive_anchor':dates[0],'archived_warmup_available':False,
            'initialization_qualification':'cold-start reconstitution, not certified full-warmup equivalence',
            'checkpoint':ancestry,'checksum':components['full_business'],'component_checksums':components,
            'started_at':case_started,'finished_at':utc(),'execution_status':'succeeded',
            'baseline_equivalence_status':'DATA_GAP_MISSING_84_WARMUP_DAYS','production_writes':0}
        write(output/(c['case_id']+'.json.gz'),{**business,'manifest':manifest});manifests.append(manifest)
        if c['case_id'] in repeat_ids:
            # Complete cold anchor -> post-window rerun; not just rereading cached case files.
            repeated_context=context_replay(panel,dates,profile,members,c['post_window_end'])
            _,again,_=case_replay(c,repeated_context,panel,dates,profile,members)
            checks.append({'case_id':c['case_id'],'full_anchor_replayed':True,'components_equal':components==again,
                           'original':components,'rerun':again})
            if components!=again:raise ValueError('nondeterministic replay')
        print(c['case_id'],len(business['rows']),'saved',flush=True)
    write(output/'run_manifests.json',manifests)
    write(output/'deterministic_rerun.json',checks)
    write(output/'run_index.json',{'backtest_run_id':run_id,'started_at':started,'finished_at':utc(),
        'casebook_checksum':book['checksum'],'data_snapshot_version':prov['data_snapshot_version'],
        'manifests_checksum':digest(manifests),'context_checksum':digest(context),'case_count':len(manifests),
        'production_writes':0,'execution_status':'succeeded',
        'baseline_equivalence_status':'DATA_GAP_MISSING_84_WARMUP_DAYS'})
    return manifests
