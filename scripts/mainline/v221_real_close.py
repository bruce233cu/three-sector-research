"""Final close through the existing Sina adapter; temporary inputs only.

No synthetic input, old SUCCESS inheritance, new provider route or production
write. Outputs are ingested by the mainline-only audited persistence step.
"""
from pathlib import Path
from datetime import date, timedelta, datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys, json, hashlib, os, time, subprocess, uuid
import pandas as pd

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from mainline.providers.phase1f_free import SinaWindow
from mainline.metrics.sector import SectorMetricInput
from mainline.metrics.benchmark import calculate_benchmark_day, calculate_v221_with_benchmark
OUT=ROOT/'reports/milestone-a-final-close';OUT.mkdir(parents=True,exist_ok=True)
PROFILE='industry_trend_v2_2_1_final_close';RUN=str(uuid.uuid4());REPEAT=str(uuid.uuid4())
PARAMS={'benchmark':'ALL_A_EQUAL_WEIGHT','benchmark_min':.95,'rs_min':.9,'sector_min':.7,
        'profile_id':PROFILE,'rule_version':'mainline_v2.2.1','metric_availability_version':'mainline_metric_availability_v2.2.1_deferred_circ_mv'}
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False,default=str)
def sha(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def write(name,x): (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
def now():return datetime.now(timezone.utc).isoformat()
def source(dataset,rows,provider,upstream,requests,**meta):
    if not rows:return None # Never register a placeholder/failed fetch as data.
    sid=str(uuid.uuid4()); fetched=now()
    return {'source_snapshot_id':sid,'source_id':provider,'dataset_code':dataset,
            'source_version':'v221-real-close:'+sha(rows),'fetched_at':fetched,'available_at':None,
            'response_checksum':sha(rows),'row_count':len(rows),'raw_location':
            'github-actions://bruce233cu/three-sector-research/runs/'+os.getenv('GITHUB_RUN_ID','local')+'/artifacts/mainline-v221-real-close#'+('stock_window' if dataset=='all_a_stock_window' else dataset)+'.json',
            'historical_capability':'historical_partial','metadata':{
            'evidence_grade':'normalized_rows_plus_upstream_response_checksums','upstream':upstream,
            'request_parameters':requests,'run_id':RUN,'code_commit':os.getenv('GITHUB_SHA'),
            'parameter_hash':sha(PARAMS),'knowledge_time_unverified':True,**meta}}

def official_master():
    # The existing AKShare official-exchange master route, bounded once per
    # dataset. A current-only list can never certify a historical universe.
    specs=[('sh_main','stock_info_sh_name_code','主板A股','SH','证券代码','上市日期',None),
           ('sh_star','stock_info_sh_name_code','科创板','SH','证券代码','上市日期',None),
           ('sh_delist','stock_info_sh_delist','全部','SH','公司代码','上市日期','暂停上市日期'),
           ('sz_active','stock_info_sz_name_code','A股列表','SZ','A股代码','A股上市日期',None),
           ('sz_delist','stock_info_sz_delist','终止上市公司','SZ','证券代码','上市日期','终止上市日期'),
           ('bj_active','stock_info_bj_name_code',None,'BJ','证券代码','上市日期',None)]
    groups={}; acquisition=[];normalized=[];snapshots=[]
    for key,fn,arg,ex,cc,lc,dc in specs:
        program='''import requests,json,akshare as ak
from datetime import datetime,timezone
audit=[];old=requests.sessions.Session.request
def request(self,method,url,**kw):
 kw['timeout']=10
 r=old(self,method,url,**kw)
 import hashlib
 audit.append({'url':r.url,'method':method,'request_params':kw.get('params',kw.get('data')),'fetched_at':datetime.now(timezone.utc).isoformat(),'response_checksum':hashlib.sha256(r.content).hexdigest(),'bytes':len(r.content)})
 return r
requests.sessions.Session.request=request
try:
 f=getattr(ak,sys_fn)(*sys_args)
 print('MASTER_JSON='+json.dumps({'rows':json.loads(f.to_json(orient='records',date_format='iso',force_ascii=False)),'audit':audit},ensure_ascii=False))
except Exception as e: print('MASTER_JSON='+json.dumps({'rows':[],'audit':audit,'error':type(e).__name__+':'+str(e)}))
'''
        program="sys_fn="+repr(fn)+";sys_args="+repr([] if arg is None else [arg])+"\n"+program
        try:
            r=subprocess.run([sys.executable,'-c',program],capture_output=True,text=True,timeout=28)
            payload=json.loads(r.stdout.split('MASTER_JSON=')[-1]) if 'MASTER_JSON=' in r.stdout else {'rows':[],'error':r.stderr[-600:]}
        except subprocess.TimeoutExpired:payload={'rows':[],'error':'bounded_timeout_28_seconds'}
        acquisition.append({'dataset':key,'function':fn,'argument':arg,**payload})
        rows=[]
        for row in payload['rows']:
            code=str(row.get(cc,'')).split('.')[0].zfill(6)
            if ex=='SH' and not code.startswith(('60','68')):continue
            if ex=='SZ' and not code.startswith(('00','30')):continue
            ld=pd.to_datetime(row.get(lc),errors='coerce');dd=pd.to_datetime(row.get(dc),errors='coerce') if dc else pd.NaT
            if pd.isna(ld) or (dc and pd.isna(dd)):continue
            rows.append({'security_id':code+'.'+ex,'share_type':'A','list_date':str(ld.date()),
                         'delist_date':None if pd.isna(dd) else str(dd.date()),'dataset':key})
        groups[key]=bool(rows) and len(rows)==sum(1 for row in payload['rows'] if
                     ex=='BJ' or str(row.get(cc,'')).zfill(6).startswith(('60','68') if ex=='SH' else ('00','30')))
        normalized.extend(rows)
        s=source('historical_universe_component',rows,'akshare_official_exchange_master',
                 'SSE/SZSE/BSE official listing and termination datasets',{'function':fn,'symbol':arg},
                 upstream_audit=payload.get('audit',[]),component_key=key,coverage=None)
        if s:snapshots.append(s)
        print('MASTER',key,len(rows),payload.get('error',''),flush=True)
    # Certification is deliberately separate from nonempty fetch success.
    # Official SH/SZ active+terminated ledgers may replay pre-BSE universes.
    # BSE current list alone lacks the complete historical code/delist ledger.
    before_bse=all(groups.get(k,False) for k in ['sh_main','sh_star','sh_delist','sz_active','sz_delist'])
    unique={};conflicts=[]
    for r in normalized:
        sid=r['security_id']
        if sid in unique and any(unique[sid][c]!=r[c] for c in ['list_date','delist_date']):conflicts.append(sid)
        unique[sid]=r
    write('universe_acquisition.json',acquisition);write('historical_universe_component.json',normalized)
    return pd.DataFrame(list(unique.values()),columns=['security_id','share_type','list_date','delist_date','dataset']), snapshots, before_bse and not conflicts,conflicts

def memberships(samples):
    chosen={};evidence=[]
    paths=['reports/phase1d/runtime/membership_evidence.json','scripts/mainline/phase1f_c/membership.json',
           'reports/phase1d/fallback/sws_official_cached_membership.json']
    for path in paths:
        try:
            p=json.loads((ROOT/path).read_text());rows=p if isinstance(p,list) else p['rows']
            evidence.append({'path':path,'rows':len(rows),'checksum':hashlib.sha256((ROOT/path).read_bytes()).hexdigest()})
            for r in rows:chosen.setdefault((r['snapshot_date'],r['taxonomy_code'],r['security_id']),dict(r,artifact_path=path))
        except Exception as e:evidence.append({'path':path,'error':str(e)})
    # Salvage only individually valid JSON objects BEFORE the known corrupted
    # byte, retaining byte-range provenance. Never ignore malformed fields.
    path='reports/phase1d/final-v2/membership_evidence.json';raw=(ROOT/path).read_bytes()
    try:text=raw.decode('utf-8')
    except UnicodeDecodeError as e:text=raw[:e.start].decode('utf-8');evidence.append({'path':path,'error':'invalid_utf8','valid_prefix_bytes':e.start,'checksum':hashlib.sha256(raw).hexdigest()})
    decoder=json.JSONDecoder();pos=text.find('[')+1;recovered=0
    while pos<len(text):
        while pos<len(text) and text[pos] in ' \n\r\t,':pos+=1
        try:r,end=decoder.raw_decode(text,pos)
        except ValueError:break
        if not isinstance(r,dict):break
        key=(r['snapshot_date'],r['taxonomy_code'],r['security_id'])
        if key not in chosen:chosen[key]=dict(r,artifact_path=path,artifact_character_range=[pos,end]);recovered+=1
        pos=end
    evidence.append({'path':path,'validated_additional_objects':recovered})
    write('membership_artifact_reads.json',evidence)
    result={}
    for s in samples:
        d=s['trade_date'];c=s['taxonomy_code']
        rows=sorted([r for (day,code,_),r in chosen.items() if day==d and code==c],key=lambda r:r['security_id'])
        result[(d,c)]=rows
    return result

def main():
    samples=json.loads((ROOT/'reports/milestone-a-final-close/input_samples.json').read_text())
    calendar=[date.fromisoformat(d) for d in json.loads((ROOT/'reports/milestone-a-fast-close/calendar_input.json').read_text())]
    member=memberships(samples);master, sources,master_verified,conflicts=official_master()
    dates=sorted({date.fromisoformat(s['trade_date']) for s in samples})
    windows={d:tuple(day for day in calendar if day<=d)[-60:] for d in dates}
    needed_days=set().union(*map(set,windows.values()))
    ids=set(r['security_id'] for rows in member.values() for r in rows)
    # Fetch ALL-A inputs only when the historical ledger is certified, otherwise
    # limit acquisition to actual sector members; an unknown universe cannot be
    # repaired by a large price fetch.
    if master_verified:ids.update(master.loc[pd.to_datetime(master.list_date).dt.date<=dates[-1],'security_id'])
    start=min(needed_days)-timedelta(days=7);end=max(dates)
    adapter=SinaWindow({});cache={};audits=[];began=time.monotonic()
    def fetch(sid):
        at=now()
        try:
            f,a=adapter.get_one(sid,start,end)
            if not a.get('unit_check_ok'):raise ValueError('amount_unit_check_failed')
            f=f[f.trade_date.isin(needed_days)]
            return sid,f,{'security_id':sid,'fetched_at':at,'status':'success' if not f.empty else 'empty',
                          'request_start':str(start),'request_end':str(end),'row_count':len(f),**a}
        except Exception as e:return sid,None,{'security_id':sid,'fetched_at':at,'status':'failed','request_start':str(start),'request_end':str(end),'error':type(e).__name__+':'+str(e)}
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs={pool.submit(fetch,sid):sid for sid in sorted(ids)}
        for i,fut in enumerate(as_completed(jobs)):
            sid,f,a=fut.result();audits.append(a)
            if f is not None and not f.empty:cache[sid]=f
            if (i+1)%100==0:print('SINA',i+1,'/',len(ids),'usable',len(cache),'seconds',int(time.monotonic()-began),flush=True)
    write('sina_fetch_audit.json',sorted(audits,key=lambda a:a['security_id']))
    empty=pd.DataFrame(columns=['security_id','trade_date','open','high','low','close','volume','amount','pct_chg','circ_mv'])
    allbars=pd.concat(list(cache.values()),ignore_index=True) if cache else empty
    all_records=json.loads(allbars.to_json(orient='records',date_format='iso'))
    write('stock_window.json',all_records)
    # A benchmark source is genuine only if we actually have the certified
    # historical universe AND stock observations. Failed attempts stay in logs.
    benchmark_days=[];benchmark_rows=[]
    universe_ids=[s['source_snapshot_id'] for s in sources]
    all_stock_source=source('all_a_stock_window',all_records,'sina_akshare_existing',SinaWindow.endpoint,
                            {'start':str(start),'end':str(end),'security_ids':sorted(ids)},
                            response_audit_file='sina_fetch_audit.json',universe_certified=master_verified,
                            return_basis='unadjusted_adjacent_observed_close',data_quality_warning='corporate_action_not_adjusted') if master_verified else None
    if all_stock_source:sources.append(all_stock_source)
    for d in sorted(needed_days):
        latest=allbars[allbars.trade_date==d][['security_id','pct_chg','amount']].rename(columns={'pct_chg':'daily_return'}).copy()
        latest.daily_return=pd.to_numeric(latest.daily_return,errors='coerce')/100
        verified=master_verified and d<date(2021,11,15)
        day=calculate_benchmark_day(d,master,latest,universe_verified=verified,returns_verified=True,
                                   source_snapshot_ids=tuple(universe_ids+([all_stock_source['source_snapshot_id']] if all_stock_source else [])))
        benchmark_days.append(day)
        benchmark_rows.append({'trade_date':str(d),'benchmark_return':day.benchmark_return,'member_count':day.universe_count if verified else None,
                               'valid_member_count':day.valid_count if verified else len(latest),'coverage':day.benchmark_coverage,
                               'reason':day.reason,'run_id':RUN,'source_snapshot_ids':list(day.source_snapshot_ids)})
    write('all_a_equal_weight_benchmark.json',benchmark_rows)
    bench_source=source('all_a_equal_weight_benchmark',[r for r in benchmark_rows if r['member_count'] is not None],
                        'all_a_equal_weight_calculator','historical official universe + existing Sina normalized bars',
                        {'trading_dates':sorted(map(str,needed_days))},coverage_threshold=.95,input_source_ids=universe_ids)
    if bench_source:sources.append(bench_source)
    snapshots=[];checks=[];member_payload=[]
    for sample in samples:
        target=sample['trade_date'];code=sample['taxonomy_code'];d=date.fromisoformat(target);members=member[(target,code)]
        member_payload.extend(members);expected=sample['member_count']
        pit=bool(members) and len(members)==expected and all(r['effective_from']<=target and (not r['effective_to'] or r['effective_to']>=target) for r in members)
        msource=source('membership_snapshot',members,'sws_official_cached_membership_evidence','pinned official SWS membership artifacts',
                        {'trade_date':target,'taxonomy_code':code},coverage=len(members)/expected if expected else None,pit_level='effective_pit',effective_pit_valid=pit)
        frames=[cache[r['security_id']] for r in members if r['security_id'] in cache]
        bars=pd.concat(frames,ignore_index=True) if frames else empty
        bars=bars[bars.trade_date.isin(windows[d])]
        if not pit:bars=empty.copy() # Do not propagate malformed membership.
        records=json.loads(bars.to_json(orient='records',date_format='iso'))
        latest=bars[bars.trade_date==d];valid=latest.dropna(subset=['open','high','low','close','volume','amount'])
        ohlcv=len(valid)/expected;amount=int(latest.amount.gt(0).sum())/expected
        psource=source('stock_window',records,'sina_akshare_existing',SinaWindow.endpoint,
                       {'trade_date':target,'window_start':str(windows[d][0]),'security_ids':[r['security_id'] for r in members]},
                       coverage={'ohlcv':ohlcv,'amount':amount},response_audit_file='sina_fetch_audit.json',
                       return_basis='unadjusted_adjacent_observed_close',data_quality_warning='corporate_action_not_adjusted')
        refs=[s['source_snapshot_id'] for s in [msource,psource,bench_source] if s]+['243f49a9-32cb-4b72-8205-d91b03498625']
        for s in [msource,psource]:
            if s:sources.append(s)
        v=SectorMetricInput(d,'sw1_'+code,code,'SW2021' if d>=date(2021,12,13) else 'SW2014',
                            tuple(r['security_id'] for r in members),bars,pd.Series(dtype=float),market_trading_dates=windows[d])
        first=calculate_v221_with_benchmark(v,benchmark_days);second=calculate_v221_with_benchmark(v,benchmark_days)
        for x in [first,second]:
            x['metric_coverage_json'].update(OHLCV=ohlcv,amount=amount,membership=len(members)/expected,
                                              MA20=x['metric_coverage_json']['above_ma20'],MA60=x['metric_coverage_json']['above_ma60'],
                                              NEW_HIGH60=x['metric_coverage_json']['new_high_60'])
            reasons=[r for r in (x['freeze_reason'] or '').split(';') if r]
            if not pit:reasons.append('membership_invalid_or_incomplete')
            if ohlcv<.95:reasons.append('daily_OHLCV_coverage_below_original_95_percent')
            x.update(stage_frozen=bool(reasons),critical_data_ok=not reasons,freeze_reason=';'.join(reasons) or None,
                     profile_id=PROFILE,parameter_profile=PROFILE,source_snapshot_ids=refs)
        same=canonical(first)==canonical(second)
        complete=bool(pit and psource and bench_source and first['benchmark_return'] is not None)
        status='SUCCESS' if first['critical_data_ok'] and complete else 'PARTIAL' if psource and pit else 'FAIL'
        checks.append({'sample_id':target+':'+code,'status':status,'repeat_identical':same,'checksum':sha(first),
                       'recompute_checksum':sha(second),'parameter_hash':sha(PARAMS),'same_source_refs':True,
                       'effective_pit':pit,'source_chain_complete':complete,'OHLCV_coverage':ohlcv,'amount_coverage':amount})
        first['decision_reason'].update(status=status,parameter_hash=sha(PARAMS),code_commit=os.getenv('GITHUB_SHA'),
                                       source_lineage_complete=complete,effective_membership_pit=pit,
                                       membership_expected_count=expected,data_quality_warning='corporate_action_not_adjusted',
                                       metric_availability_version=PARAMS['metric_availability_version'],parameter_profile=PROFILE,
                                       repeat_checksum=sha(second),return_basis='unadjusted_adjacent_observed_close')
        first.update(run_id=RUN,recompute_run_id=REPEAT,source_snapshot_id=msource['source_snapshot_id'] if msource else None,
                     cache_checksum=sha(first),pit_level='effective_pit',knowledge_time_unverified=True)
        for key in ['parameter_profile','metric_availability_version','circ_mv_status']:first.pop(key,None)
        snapshots.append(first)
    write('membership_snapshot.json',member_payload);write('source_snapshots.json',sources)
    write('snapshots.json',snapshots);write('checks.json',checks)
    passed=len(snapshots)==15 and all(s['critical_data_ok'] for s in snapshots) and all(c['repeat_identical'] and c['source_chain_complete'] and c['effective_pit'] for c in checks)
    summary={'G1':'PASS' if passed else 'FAIL','READY_FOR_PRODUCTION_ENABLEMENT':passed,'run_id':RUN,'recompute_run_id':REPEAT,
             'code_commit':os.getenv('GITHUB_SHA'),'parameter_hash':sha(PARAMS),'parameters':PARAMS,
             'counts':{k:sum(c['status']==k for c in checks) for k in ['SUCCESS','PARTIAL','FAIL']},
             'master_verified_before_bse':master_verified,'master_conflicts':conflicts,'certified_full_period_universe':False,
             'successful_sina_securities':len(cache),'requested_sina_securities':len(ids),'stock_window_rows':len(allbars),
             'source_chains_complete':sum(c['source_chain_complete'] for c in checks),
             'deterministic_repeatability':all(c['repeat_identical'] for c in checks),'effective_membership_pit':sum(c['effective_pit'] for c in checks)}
    write('gate.json',summary);print(canonical(summary),flush=True)
if __name__=='__main__':main()
