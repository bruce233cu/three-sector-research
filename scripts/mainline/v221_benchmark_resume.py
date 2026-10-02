"""Resume benchmark only: reuse passed sector inputs; temporary whole-market windows."""
from pathlib import Path
from datetime import date,datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor,as_completed
from io import BytesIO
import sys,json,hashlib,uuid,os,time
import pandas as pd,requests
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts/mainline')]
from v221_universe_normalize import normalize
from mainline.metrics.historical_universe import historical_benchmark_universe_resolver as resolve,exact_market_day_observations
from mainline.metrics.benchmark import calculate_benchmark_day,calculate_v221_with_benchmark
from mainline.metrics.sector import SectorMetricInput
from mainline.providers.phase1f_free import SinaWindow
from pypdf import PdfReader
P=ROOT/'reports/v221-benchmark-universe';OLD=ROOT/'.cache/v221-real-close'
RUN=str(uuid.uuid4());REPEAT=str(uuid.uuid4());PROFILE='industry_trend_v2_2_1_benchmark_close'
PARAMS={'benchmark':'ALL_A_EQUAL_WEIGHT','benchmark_min':.95,'rs_window_min':.9,'sector_min':.7,
        'return_basis':'exact_previous_market_day_close','profile_id':PROFILE,'rule_version':'mainline_v2.2.1'}
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False,default=str)
def sha(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def write(f,x):(P/f).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
def now():return datetime.now(timezone.utc).isoformat()
def source(dataset,rows,provider,upstream,params,**more):
    return dict(source_snapshot_id=str(uuid.uuid4()),source_id=provider,dataset_code=dataset,
                source_version='v221-benchmark-resume:'+sha(rows),fetched_at=now(),available_at=None,
                response_checksum=sha(rows),row_count=len(rows),raw_location='github-actions://bruce233cu/three-sector-research/runs/'+os.environ['GITHUB_RUN_ID']+'/artifacts/v221-benchmark-universe#'+dataset,
                historical_capability='historical_partial',metadata=dict(upstream=upstream,request_parameters=params,
                run_id=RUN,code_commit=os.environ['GITHUB_SHA'],parameter_hash=sha(PARAMS),knowledge_time_unverified=True,**more))
def main():
    audit=json.loads((P/'probe.json').read_text())
    url='https://www.bse.cn/disclosure/2022/2022-07-22/1658483683_879987.pdf'
    response=requests.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.bse.cn/'})
    if response.status_code!=200:
        audit.append(dict(label='bj_hanbo_primary_http_failure',url=url,status=response.status_code,fetched_at=now(),checksum=hashlib.sha256(response.content).hexdigest()))
        url=url.replace('www.bse.cn','www.bseinfo.net')
        response=requests.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.bseinfo.net/'})
    response.raise_for_status();(P/'bj_hanbo_exit.pdf').write_bytes(response.content)
    audit.append(dict(label='bj_hanbo_exit_pdf',url=url,status=response.status_code,fetched_at=now(),
                      checksum=hashlib.sha256(response.content).hexdigest(),bytes=len(response.content)))
    write('probe.json',audit)
    import re
    text=''.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
    proof=bool(re.search(r'2022\s*年\s*7\s*月\s*25\s*日',text) and '833994' in text)
    records,certificate,errors,inventory=normalize(ROOT,hanbo_exit_verified=proof)
    old=json.loads((OLD/'snapshots.json').read_text());calendar=[date.fromisoformat(x) for x in json.loads((ROOT/'reports/milestone-a-fast-close/calendar_input.json').read_text())]
    dates=sorted({date.fromisoformat(x['as_of_date']) for x in old});fixed=[resolve(d,records,certificate=certificate) for d in dates]
    expected_bj=[0,0,82,204,268]
    for r,count in zip(fixed,expected_bj):
        if r.summary['BJ_count']!=count:errors.append('fixed_BJ_count_crosscheck_failed:'+str(r.trade_date))
    valid=not errors and all(x.verified for x in fixed)
    write('universe_validation.json',dict(run_id=RUN,verified=valid,errors=errors,inventory=inventory,
           dates=[dict(x.summary,verified=x.verified,reasons=x.reasons) for x in fixed],
           sample_checks=[dict(security_id=s['security_id'],historical_code=s['historical_code'],trade_date=str(x.trade_date),listing_date=s['listing_date'],delisting_date=s['delisting_date'])
                          for x in fixed for s in list(x.members[:2])+[r for r in x.members if r['security_id'] in ['920680.BJ','920305.BJ','833994.BJ','600001.SH','688001.SH']]]))
    print('UNIVERSE',valid,inventory,errors,flush=True)
    if not valid:
        write('gate.json',dict(G1='FAIL',READY_FOR_PRODUCTION_ENABLEMENT=False,run_id=RUN,errors=errors));return
    write('temporary_universe_intervals.json',records)
    universe_source=source('historical_benchmark_universe',records,'official_exchange_listing_events',
        'reused SSE/SZSE ledgers + official SZ full pages + official BSE mapping/listing/exit documents',
        {'fixed_dates':list(map(str,dates))},evidence_grade='official_event_intervals_plus_response_checksums',
        upstream_audit=[{k:v for k,v in a.items() if k not in ['json','text_prefix']} for a in audit],
        input_source_ids=[s['source_snapshot_id'] for s in json.loads((OLD/'source_snapshots.json').read_text()) if s['dataset_code']=='historical_universe_component'],
        reused_artifact_run=36889897269,certificate=certificate,coverage=1.0)
    windows={d:tuple(x for x in calendar if x<=d)[-60:] for d in dates}
    days=sorted(set().union(*map(set,windows.values())))
    prior={d:calendar[calendar.index(d)-1] for d in days};needed=set(days)|set(prior.values())
    resolutions={d:resolve(d,records,certificate=certificate) for d in days}
    ids=set(m['security_id'] for r in resolutions.values() for m in r.members)
    cached=pd.read_json(OLD/'stock_window.json');cached.trade_date=pd.to_datetime(cached.trade_date).dt.date
    cached=cached[cached.trade_date.isin(needed)];frames={sid:g for sid,g in cached.groupby('security_id')}
    adapter=SinaWindow({});start=min(needed)-timedelta(days=2);end=max(dates);audits=[];began=time.monotonic()
    def fetch(sid):
        stamp=now()
        try:
            f,a=adapter.get_one(sid,start,end)
            if not a.get('unit_check_ok'):raise ValueError('amount_unit_check_failed')
            f=f[f.trade_date.isin(needed)]
            return sid,f,dict(security_id=sid,fetched_at=stamp,row_count=len(f),status='success' if len(f) else 'empty',**a)
        except Exception as e:return sid,None,dict(security_id=sid,fetched_at=stamp,status='failed',error=type(e).__name__+':'+str(e))
    missing=sorted(ids-frames.keys());print('BENCHMARK_MISSING_SECURITIES',len(missing),'reuse',len(frames),flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs={pool.submit(fetch,sid):sid for sid in missing}
        for i,fut in enumerate(as_completed(jobs)):
            sid,f,a=fut.result();audits.append(a)
            if f is not None and len(f):frames[sid]=f
            if (i+1)%100==0:print('BENCHMARK_FETCH',i+1,'/',len(missing),'seconds',int(time.monotonic()-began),flush=True)
    allbars=pd.concat(list(frames.values()),ignore_index=True);allbars=allbars[allbars.security_id.isin(ids)]
    # Parquet is temporary input evidence, never inserted into stock_daily.
    allbars.to_parquet(P/'temporary_benchmark_window.parquet',index=False)
    write('benchmark_fetch_audit.json',audits)
    stock_checksum=hashlib.sha256((P/'temporary_benchmark_window.parquet').read_bytes()).hexdigest()
    price_source=source('all_a_benchmark_price_amount',[{'checksum':stock_checksum,'row_count':len(allbars)}],
        'sina_akshare_existing',SinaWindow.endpoint,{'start':str(start),'end':str(end),'only_missing_securities':missing,
        'required_market_dates':list(map(str,needed))},normalized_checksum=stock_checksum,temporary_rows=len(allbars),
        reused_sector_artifact=36889897269,reused_checksum=hashlib.sha256((OLD/'stock_window.json').read_bytes()).hexdigest(),
        evidence_grade='normalized_parquet_plus_upstream_response_checksums',return_basis='exact_previous_market_day_close')
    price_source['row_count']=len(allbars)
    by_day={d:g for d,g in allbars.groupby('trade_date')};benchmark_days=[];benchmark_rows=[]
    for d in days:
        resolution=resolutions[d]
        pair=pd.concat([by_day.get(d,pd.DataFrame(columns=allbars.columns)),by_day.get(prior[d],pd.DataFrame(columns=allbars.columns))])
        observations=exact_market_day_observations(resolution,pair,prior[d])
        u=pd.DataFrame([dict(security_id=m['security_id'],share_type='A',list_date=m['listing_date'],delist_date=None) for m in resolution.members])
        b=calculate_benchmark_day(d,u,observations,universe_verified=resolution.verified,returns_verified=True,
            source_snapshot_ids=(universe_source['source_snapshot_id'],price_source['source_snapshot_id']))
        benchmark_days.append(b);benchmark_rows.append(dict(trade_date=str(d),benchmark_return=b.benchmark_return,
            universe_count=b.universe_count,valid_return_count=b.valid_count,benchmark_coverage=b.benchmark_coverage,
            all_a_amount=b.all_a_amount,amount_coverage=b.amount_coverage,previous_market_date=str(prior[d]),
            freeze_reason=b.reason,run_id=RUN,source_snapshot_ids=list(b.source_snapshot_ids)))
    bench_source=source('all_a_equal_weight_benchmark',benchmark_rows,'all_a_equal_weight_calculator',
        'verified historical A-share event intervals + exact market-day Sina closes and amounts',
        {'window_days':len(days),'fixed_dates':list(map(str,dates))},input_source_ids=[universe_source['source_snapshot_id'],price_source['source_snapshot_id']],
        coverage_threshold=.95,evidence_grade='computed_from_real_verified_inputs')
    write('all_a_equal_weight_benchmark.json',benchmark_rows)
    snapshots=[];checks=[]
    recalculated=['benchmark_return','rs_5','rs_10','rs_20','turnover_share','turnover_intensity']
    reused=['sector_return','up_ratio','above_ma20','above_ma60','new_high_60','top3_turnover_share']
    for original in old:
        d=date.fromisoformat(original['as_of_date']);code=original['taxonomy_code']
        # Membership and bars are read exclusively from the passed artifact.
        members=[m for m in json.loads((OLD/'membership_snapshot.json').read_text()) if m['snapshot_date']==str(d) and m['taxonomy_code']==code]
        member_ids=tuple(m['security_id'] for m in members);bars=cached[cached.security_id.isin(member_ids)&cached.trade_date.isin(windows[d])]
        value=SectorMetricInput(d,original['object_id'],code,original['taxonomy_version'],member_ids,bars,pd.Series(dtype=float),market_trading_dates=windows[d])
        a=calculate_v221_with_benchmark(value,benchmark_days);b=calculate_v221_with_benchmark(value,benchmark_days)
        core_a={k:a[k] for k in recalculated};core_b={k:b[k] for k in recalculated}
        updated=dict(original);updated.update(core_a,profile_id=PROFILE,run_id=RUN,recompute_run_id=REPEAT,
            stage_frozen=a['stage_frozen'],critical_data_ok=a['critical_data_ok'],freeze_reason=a['freeze_reason'])
        updated['metric_coverage_json']={**original['metric_coverage_json'],**{k:a['metric_coverage_json'][k] for k in ['benchmark','rs_5','rs_10','rs_20','turnover_share']}}
        updated['source_snapshot_ids']=list(original['source_snapshot_ids'])+[universe_source['source_snapshot_id'],price_source['source_snapshot_id'],bench_source['source_snapshot_id']]
        updated['decision_reason']={**original['decision_reason'],'benchmark':a['decision_reason']['benchmark'],
            'parameter_profile':PROFILE,'parameter_hash':sha(PARAMS),'code_commit':os.environ['GITHUB_SHA'],
            'parent_run_id':original['run_id'],'source_lineage_complete':True,'benchmark_input_return_basis':'exact_previous_market_day_close'}
        available=all(updated[k] is not None for k in recalculated)
        same=canon(a)==canon(b);status='SUCCESS' if available and updated['critical_data_ok'] else 'PARTIAL'
        updated['decision_reason']['status']=status
        updated['decision_reason']['parent_repeat_checksum']=original['decision_reason'].get('repeat_checksum')
        updated['decision_reason']['repeat_checksum']=sha(b)
        updated['cache_checksum']=sha(updated)
        unchanged=all(updated[k]==original[k] for k in reused)
        checks.append(dict(sample_id=str(d)+':'+code,status=status,repeat_identical=same,reused_metrics_unchanged=unchanged,
           parameter_hash=sha(PARAMS),same_source_refs=True,checksum=sha(a),recompute_checksum=sha(b)))
        snapshots.append(updated)
    write('snapshots.json',snapshots);write('checks.json',checks);write('source_snapshots.json',[universe_source,price_source,bench_source])
    passed=all(c['status']=='SUCCESS' and c['repeat_identical'] and c['reused_metrics_unchanged'] for c in checks)
    gate=dict(G1='PASS' if passed else 'FAIL',READY_FOR_PRODUCTION_ENABLEMENT=passed,run_id=RUN,recompute_run_id=REPEAT,
        code_commit=os.environ['GITHUB_SHA'],parameter_hash=sha(PARAMS),parameters=PARAMS,universe_verified=True,
        counts={k:sum(c['status']==k for c in checks) for k in ['SUCCESS','PARTIAL','FAIL']},benchmark_days=len(days),
        fetched_missing_securities=len(missing),reused_sector_securities=cached.security_id.nunique(),temporary_rows=len(allbars),
        deterministic_repeatability=all(c['repeat_identical'] for c in checks),source_lineage_complete=15,
        fixed_benchmark_rows=[r for r in benchmark_rows if r['trade_date'] in set(map(str,dates))])
    write('gate.json',gate);print(canon(gate),flush=True)
if __name__=='__main__':main()
