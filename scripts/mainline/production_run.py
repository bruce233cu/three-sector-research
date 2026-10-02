"""One production chain for production, simulation and backfill.

No persistent stock-price asset; only normalized board output is uploaded.
GitHub OIDC binds writes to this exact repository/branch/workflow and SHA.
"""
import os,json,uuid,subprocess,sys,hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from mainline.production.daily import day_checksum,evolve,business_payload
from mainline.production.checkpoints import select_seed
OUT=ROOT/'reports/mainline-production';OUT.mkdir(parents=True,exist_ok=True)
def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def gateway(operation,**kwargs):
    url=os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']+'&audience=mainline-production'
    token=requests.get(url,headers={'Authorization':'Bearer '+os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']},timeout=30)
    token.raise_for_status()
    response=requests.post(os.environ['MAINLINE_GATEWAY'],headers={'Authorization':'Bearer '+token.json()['value']},json={'operation':operation,**kwargs},timeout=180)
    response.raise_for_status();body=response.json()
    if body.get('error'):raise RuntimeError(body['error'])
    return body
def locate(directory,name):
    hits=list((ROOT/directory).rglob(name))
    if len(hits)!=1:raise ValueError('expected one certified input '+name)
    return hits[0]
def main():
    typ=os.environ.get('MAINLINE_RUN_TYPE','production_simulation')
    today=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    target=os.environ.get('MAINLINE_TARGET_DATE') or today
    context=gateway('context',trade_date=target)
    if typ=='production_simulation' and target==today:
        target=max(d for d in context['calendar'] if d<today)
        context=gateway('context',trade_date=target)
    if target not in context['calendar']:
        write(OUT/'production_gate.json',{'status':'skipped_non_trading_day','date':target,'calendar':'mainline.trading_calendar'});return
    if typ=='production' and not context['enabled']:raise ValueError('production remains disabled until G4 PASS')
    write(ROOT/'reports/milestone-a-fast-close/calendar_input.json',context['calendar'])
    if typ!='production_validation':
        universe=locate('temporary_g3_input','temporary_universe_intervals.json')
        sources=locate('temporary_g3_input','source_snapshots.json')
        for path in (universe,sources):
            destination=ROOT/'temporary_g3_input'/path.name
            if path!=destination:destination.write_bytes(path.read_bytes())
    profile=read(ROOT/'config/parameter_profile_industry_trend_v221_state_completion_v1.json')
    g3=[]
    bootstrap=None
    if not context.get('checkpoints') and os.environ.get('MAINLINE_ALLOW_G3_BOOTSTRAP')=='true':
        g3=read(locate('temporary_seed','real_board_states.json'))
        day=max(r['snapshot']['as_of_date'] for r in g3)
        bootstrap={'date':day,'checkpoints':{r['snapshot']['object_id']:r['state']['checkpoint'] for r in g3 if r['snapshot']['as_of_date']==day}}
    seed=select_seed(context,profile,target,bootstrap=bootstrap)
    parent=os.environ.get('MAINLINE_PIPELINE_RUN_ID') or str(uuid.uuid4())
    attempt={'pipeline_run_id':parent,'trade_date':target,'run_type':typ,'code_sha':os.environ['CODE_COMMIT'],'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'run_id':str(uuid.uuid5(uuid.NAMESPACE_URL,parent+':'+target+':attempt')),'parameter_hash':profile['calculation_parameter_hash']}
    if typ in {'production','production_validation'}:gateway('attempt',payload={**attempt,'phase':'running'})
    # Reuse a production success only after a genuine production manifest exists.
    # Simulation checkpoints alone must never promote the date to LIVE.
    existing=context.get('existing_target') or []
    if typ!='production_validation' and len(existing)==31 and (typ!='production' or context.get('latest_success')==target):
        if typ in {'production','production_validation'}:gateway('attempt',payload={**attempt,'phase':'succeeded','result':'already_committed'})
        write(OUT/'production_gate.json',{'run_type':typ,'date':target,'result':'already_committed','bootstrap_source':seed['bootstrap_source'],'seed_date':seed['date'],'pipeline_run_id':parent})
        return
    checkpoint_evidence={'source':'database' if seed['bootstrap_source']=='database_checkpoint' else seed['bootstrap_source'],
      'checkpoint_trade_date':seed['date'],'checkpoint_run_id':sorted({r['run_id'] for r in context.get('checkpoints',[])}),
      'checkpoint_rule_version':profile['rule_version'],'checkpoint_parameter_profile':profile['profile_id'],
      'checkpoint_taxonomy_version':'SW2021','metric_availability_version':profile['metric_availability_version']}
    write(OUT/'checkpoint_evidence.json',checkpoint_evidence)
    if typ=='production_validation':
        actual=gateway('validation_input',trade_date=target)
        memberships=read(locate('temporary_validation_evidence','real_memberships.json'))
        member=memberships[target]
        from mainline.engine.replay import digest
        for oid,ids in member['members'].items():
            if not ids or digest({'trade_date':target,'taxonomy_version':'SW2021','object_id':oid,'members':sorted(ids)})!=member['checksums'][oid]:
                raise ValueError('real membership evidence checksum failed')
        certified=[r for r in read(locate('temporary_validation_evidence','real_board_states.json')) if r['snapshot']['as_of_date']==target]
        if len(certified)!=31 or [business_payload(r) for r in sorted(certified,key=lambda r:r['snapshot']['object_id'])]!=[business_payload(r) for r in sorted(actual['rows'],key=lambda r:r['snapshot']['object_id'])]:
            raise ValueError('database daily facts differ from certified evidence')
        panel=[r['snapshot'] for r in certified]
        result=evolve(panel,context['calendar'],profile,lambda day:memberships[day],context['warm_history'],seed)
        repeat=evolve(panel,context['calendar'],profile,lambda day:memberships[day],context['warm_history'],seed)
        rows=result['rows'];selected=[target];sources=actual['sources']
        expected=day_checksum(certified)
        if expected!=existing[0]['business_checksum']:raise ValueError('certified input checksum differs from database')
        if day_checksum(rows)!=expected or digest(result)!=digest(repeat):
            raise ValueError('validation continuation differs from certified daily checksum')
        gate={'parameter_profile':profile['profile_id'],'rule_version':profile['rule_version'],'parameter_hash':profile['calculation_parameter_hash']}
        write(OUT/'validation_continuation.json',{'date':target,'source':actual['source'],'checkpoint':checkpoint_evidence,
            'actual_membership_artifact_run_id':'36970118460','checksum':expected,'recomputed_checksum':day_checksum(rows),'deterministic':True,
            'industry_count':len(rows),'warm_history_dates':len({r['as_of_date'] for r in context['warm_history']}),
            'pipeline_run_id':parent,'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'code_sha':os.environ['CODE_COMMIT']})
        write(OUT/'real_board_states.json',rows)
    else:
        write(ROOT/'temporary_g3_input/trusted_seed.json',seed)
        write(ROOT/'temporary_g3_input/trusted_warm_history.json',context.get('warm_history') or [])
        env=dict(os.environ,MAINLINE_TARGET_DATE=target,MAINLINE_RUN_ID=str(uuid.uuid4()))
        subprocess.run([sys.executable,str(ROOT/'scripts/mainline/production_collect.py')],env=env,check=True,cwd=ROOT)
        rows=read(OUT/'real_board_states.json');gate=read(OUT/'real_window_gate.json');provenance=read(OUT/'real_input_provenance.json')
        if not gate['deterministic']:raise ValueError('non-deterministic certified engine')
        dates=sorted({r['snapshot']['as_of_date'] for r in rows})
        selected=dates[-5:] if typ=='production_simulation' else dates
        if typ!='production_simulation' and (not selected or selected[-1]!=target):raise ValueError('missing sequential continuation dates')
        if typ=='production_simulation' and len(selected)!=5:raise ValueError('five verified real sessions required')
        sources=[]
        for name,sid in gate['source_snapshot_ids'].items():
            checksum=provenance['stock_workbook_sha256'] if name=='membership' else gate['input_price_checksum'] if name=='price' else hashlib.sha256((OUT/('real_benchmark.json' if name=='benchmark' else 'real_board_states.json')).read_bytes()).hexdigest()
            sources.append({'source_snapshot_id':sid,'source_id':{'membership':'sws','price':'sina','benchmark':'approved_universe_equal_weight','board':'certified_engine'}[name],
              'dataset_code':'production_'+name,'source_version':str(gate['membership_source_version'])+':collection:'+gate['run_id'],
              'fetched_at':datetime.now(ZoneInfo('UTC')).isoformat(),'response_checksum':checksum,
              'row_count':gate['temporary_stock_rows'] if name=='price' else len(rows),'raw_location':'github-actions://'+os.environ.get('GITHUB_RUN_ID','local')+'/mainline-production-evidence',
              'metadata':{'temporary_inputs_only':True,'knowledge_time_unverified':True,'provenance':provenance if name=='membership' else {'normalized_checksum':checksum}}})
        sources.append(provenance['universe_source'])
    checks=[]
    for day in selected:
        group=[r for r in rows if r['snapshot']['as_of_date']==day]
        if len(group)!=31:raise ValueError('incomplete SW1 daily output')
        ancestry={}
        for r in g3+rows:
            if r['snapshot']['as_of_date']>day:continue
            lc=r['state']['checkpoint'].get('lifecycle')
            if lc:ancestry[lc['lifecycle_id']]=lc
        payload={'trade_date':day,'profile_id':gate['parameter_profile'],'rule_version':gate['rule_version'],
          'parameter_hash':gate['parameter_hash'],'run_type':typ,'code_sha':os.environ['CODE_COMMIT'],
          'checksum':day_checksum(group),'rows':group,'sources':sources,'parent_pipeline_run_id':parent,'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'business_date':target,'bootstrap_source':seed['bootstrap_source'],'seed_date':seed['date'],'checkpoint_evidence':checkpoint_evidence,
          'lifecycle_ancestry':sorted(ancestry.values(),key=lambda x:(x['candidate_at'],x['lifecycle_id']))}
        attempts=[]
        for _ in range(1 if typ=='production' else 2):
            payload['run_id']=str(uuid.uuid4());payload['pipeline_run_id']=str(uuid.uuid4())
            attempts.append(gateway('commit',payload=payload))
        if len(attempts)>1 and (attempts[0]['checksum']!=attempts[1]['checksum'] or attempts[1]['result']!='idempotent'):raise ValueError('database idempotency failure')
        checks.append({'date':day,'attempts':attempts,'member_count':31,'checksum':payload['checksum']})
        write(OUT/'production_gate.json',{'run_type':typ,'dates':selected,'daily_checks':checks,'five_days_complete':len(checks)==5,'deterministic':True,'production_enabled':False,'g4':'PENDING'})
    if typ in {'production','production_validation'}:gateway('attempt',payload={**attempt,'phase':'succeeded','result':'completed','seed_date':seed['date']})
    print(json.dumps({'dates':selected,'committed':len(checks),'run_type':typ}),flush=True)
if __name__=='__main__':
    try:main()
    except Exception as e:
        if os.environ.get('MAINLINE_RUN_TYPE') in {'production','production_validation'}:
            try:gateway('attempt',payload={'phase':'failed','run_id':str(uuid.uuid5(uuid.NAMESPACE_URL,os.environ.get('MAINLINE_PIPELINE_RUN_ID','')+':'+os.environ.get('MAINLINE_TARGET_DATE','')+':attempt')),'trade_date':os.environ.get('MAINLINE_TARGET_DATE'),'pipeline_run_id':os.environ.get('MAINLINE_PIPELINE_RUN_ID'),'code_sha':os.environ.get('CODE_COMMIT'),'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'run_type':os.environ.get('MAINLINE_RUN_TYPE'),'reason':str(e)[:1000]})
            except Exception as reporting_error:print('failure_reporting_error:'+str(reporting_error),file=sys.stderr)
        write(OUT/'production_error.json',{'error':str(e),'code_sha':os.environ.get('CODE_COMMIT'),'run_type':os.environ.get('MAINLINE_RUN_TYPE')});raise
