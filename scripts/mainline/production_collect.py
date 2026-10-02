"""On-demand full-SW1 historical BOARD panel. Individual inputs are temporary.

Reuses approved SWS, Sina, Universe intervals and SSE calendar. No DB writes,
no parameter tuning, no new provider, no lifetime individual-price asset.
"""
import os,sys,json,hashlib,uuid,time,math,io
from pathlib import Path
from datetime import date
from concurrent.futures import ThreadPoolExecutor,as_completed
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from mainline.providers.sws_history import SwsEffectivePitProvider,_download,SWS_STOCK_HISTORY_URL,SWS_CODE_URL
from mainline.providers.phase1f_free import SinaWindow
from mainline.metrics.historical_universe import historical_benchmark_universe_resolver
from mainline.engine.metrics import sql_percent_rank
from mainline.engine.replay import replay,digest

OUT=ROOT/'reports/mainline-production';OUT.mkdir(parents=True,exist_ok=True)
def write(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
RUN=os.environ.get('MAINLINE_RUN_ID',str(uuid.uuid4()))
def main():
    profile=json.loads((ROOT/'config/parameter_profile_industry_trend_v221_state_completion_v1.json').read_text())
    cached=ROOT/'temporary_g3_input'
    records=json.loads((cached/'temporary_universe_intervals.json').read_text())
    prior_sources=json.loads((cached/'source_snapshots.json').read_text())
    usource=next(s for s in prior_sources if s['dataset_code']=='historical_benchmark_universe')
    certificate=usource['metadata']['certificate']
    calendar=json.loads((ROOT/'reports/milestone-a-fast-close/calendar_input.json').read_text())
    target=os.environ['MAINLINE_TARGET_DATE']
    seed=json.loads((cached/'trusted_seed.json').read_text())
    seed_date=seed['date']
    prior_dates=[d for d in calendar if d<=seed_date]
    begin=prior_dates[max(0,len(prior_dates)-330)]
    dates=[d for d in calendar if begin<=d<=target]
    actual_dates=[d for d in dates if d>seed_date]
    start=date.fromisoformat(dates[0]);end=date.fromisoformat(dates[-1])
    stock_raw=_download(SWS_STOCK_HISTORY_URL,retries=3,timeout_seconds=60);code_raw=_download(SWS_CODE_URL,retries=3,timeout_seconds=60)
    provider=SwsEffectivePitProvider(stock_bytes=stock_raw,code_bytes=code_raw)
    codes=pd.read_excel(io.BytesIO(code_raw),dtype=str)
    names=sorted(provider.history.level1_name.unique())
    # Use actual official classification code rows, never invent index mappings.
    namecol='一级行业名称';codecol='行业代码'
    mapping={}
    for name in names:
        candidates=codes[codes[namecol]==name]
        if '一级行业代码' in candidates.columns:
            explicit=[str(c).replace('.0','') for c in candidates['一级行业代码'].dropna()]
            if len(set(explicit))==1:
                mapping[name]=explicit[0];continue
        cs=[str(c).replace('.0','') for c in candidates[codecol].dropna()]
        roots=[c for c in cs if c.endswith('0000')]
        if len(set(roots))!=1:
            raise ValueError('official level1 code mapping unavailable:'+name+':'+str(cs[:5]))
        mapping[name]=roots[0]
    universe={}
    for d in dates:
        u=historical_benchmark_universe_resolver(d,records,certificate=certificate)
        if not u.verified:raise ValueError('unverified reused universe:'+d+str(u.reasons))
        universe[d]=u
    # Includes one exact prior market date for first output input, no price borrowing.
    first_prior=calendar[calendar.index(dates[0])-1]
    stock_start=date.fromisoformat(first_prior)
    ids=sorted({m['security_id'] for u in universe.values() for m in u.members})
    adapter=SinaWindow({});audit=[];frames=[];began=time.monotonic()
    def fetch(sid):
        fetched=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
        try:
            cache=ROOT/'.cache/mainline-production'/target
            cache.mkdir(parents=True,exist_ok=True)
            fp=cache/(sid+'.parquet');ap=cache/(sid+'.json')
            if fp.exists() and ap.exists():
                a=json.loads(ap.read_text());f=pd.read_parquet(fp)
                if a.get('cache_scope')!=[str(stock_start),str(end)]:raise ValueError('temporary_cache_scope_mismatch')
            else:
                f,a=adapter.get_one(sid,stock_start,end)
                if a.get('unit_check_ok'):
                    a['cache_scope']=[str(stock_start),str(end)];f.to_parquet(fp,index=False);ap.write_text(json.dumps(a))
            if not a.get('unit_check_ok'):raise ValueError('amount_unit_check_failed')
            f=f.drop(columns=['circ_mv'],errors='ignore')
            return f,{'security_id':sid,'fetched_at':fetched,'row_count':len(f),'status':'success',**a}
        except Exception as e:return None,{'security_id':sid,'fetched_at':fetched,'status':'failed','error':str(e)[:250]}
    with ThreadPoolExecutor(max_workers=12) as pool:
        jobs=[pool.submit(fetch,sid) for sid in ids]
        for i,j in enumerate(as_completed(jobs)):
            f,a=j.result();audit.append(a)
            if f is not None and len(f):frames.append(f)
            if (i+1)%250==0:print('G3 TEMP FETCH',i+1,len(ids),'seconds',int(time.monotonic()-began),flush=True)
    if not frames:raise ValueError('no actual Sina observations')
    bars=pd.concat(frames,ignore_index=True);bars['trade_date']=pd.to_datetime(bars.trade_date).dt.strftime('%Y-%m-%d')
    if bars.duplicated(['security_id','trade_date']).any():raise ValueError('duplicate actual bars')
    tmp=ROOT/'.cache/mainline-production';tmp.mkdir(parents=True,exist_ok=True)
    bars.to_parquet(tmp/'temporary_window.parquet',index=False)
    price_sha=hashlib.sha256((tmp/'temporary_window.parquet').read_bytes()).hexdigest()
    source_ids={k:str(uuid.uuid5(uuid.NAMESPACE_URL,RUN+':'+k)) for k in ['membership','price','benchmark','board']}
    close=bars.pivot(index='trade_date',columns='security_id',values='close').reindex([first_prior]+dates)
    amount=bars.pivot(index='trade_date',columns='security_id',values='amount').reindex([first_prior]+dates)
    returns=close.div(close.shift(1))-1
    valid=(close>0)&(close.shift(1)>0)&(amount>0)
    returns=returns.where(valid)
    ma20=close.rolling(20,min_periods=20).mean();ma60=close.rolling(60,min_periods=60).mean()
    hi60=close.rolling(60,min_periods=60).max()
    panel=[];memberships={};benchmark=[];allhist={}
    for d in dates:
        u=universe[d];uids=[m['security_id'] for m in u.members]
        # Existing Universe qualification, including listing date for exact previous close.
        prior=calendar[calendar.index(d)-1]
        eligible=[m['security_id'] for m in u.members if m['listing_date']<=prior]
        ur=returns.loc[d].reindex(eligible).dropna();bcov=len(ur)/len(uids)
        br=float(ur.mean()) if bcov>=.95 else None
        ua=amount.loc[d].reindex(uids);ua=ua.where(ua>0).dropna()
        allamount=float(ua.sum()) if len(ua) else None
        allup=float(ur.gt(0).mean()) if bcov>=.70 else None
        allma20=ma20.loc[d].reindex(uids).dropna()
        allabove=float(close.loc[d].reindex(allma20.index).gt(allma20).mean()) if len(allma20)/len(uids)>=.70 else None
        benchmark.append({'trade_date':d,'benchmark_return':br,'benchmark_coverage':bcov,'universe_count':len(uids),
                          'valid_member_count':len(ur),'all_a_amount':allamount,'amount_coverage':len(ua)/len(uids)})
        daily_members={};rows=[]
        for name in names:
            code=mapping[name];oid='sw1_classification_'+code
            resolved=provider.snapshot(date.fromisoformat(d),code,name)
            if resolved.taxonomy_version!='SW2021':raise ValueError('unexpected historical taxonomy')
            mid=sorted(set(resolved.frame.security_id)&set(uids))
            if not mid:raise ValueError('empty effective membership:'+d+':'+name)
            daily_members[oid]=mid
            rr=returns.loc[d].reindex(mid).dropna();aa=amount.loc[d].reindex(mid).where(lambda x:x>0).dropna()
            cov=len(rr)/len(mid);share=float(aa.sum())/allamount if allamount and len(aa)/len(mid)>=.7 else None
            row={'as_of_date':d,'object_id':oid,'object_type':'industry','taxonomy_code':code,'taxonomy_version':'SW2021',
                 'industry_name':name,'member_count':len(mid),'valid_member_count':len(rr),
                 'sector_return':float(rr.mean()) if cov>=.70 else None,'benchmark_return':br,
                 'turnover_share':share,'up_ratio':float(rr.gt(0).mean()) if cov>=.70 else None,
                 'all_a_up_ratio':allup,'all_a_above_ma20':allabove,
                 'top3_turnover_share':float(aa.nlargest(3).sum()/aa.sum()) if len(aa)>=3 else None,
                 'turnover_cap_deviation':None,'top3_return_contribution':None,
                 'rule_version':profile['rule_version'],'metric_availability_version':profile['metric_availability_version'],
                 'source_snapshot_ids':[source_ids['membership'],source_ids['price'],source_ids['benchmark'],usource['source_snapshot_id']],
                 'run_id':RUN,'evidence_kind':'real_historical_board',
                 'metric_coverage_json':{'sector_return':cov,'amount':len(aa)/len(mid),'benchmark':bcov}}
            for field,indicator in [('above_ma20',ma20),('above_ma60',ma60),('new_high_60',hi60)]:
                av=indicator.loc[d].reindex(mid).dropna();cc=close.loc[d].reindex(av.index)
                coverage=len(av)/len(mid);row['metric_coverage_json'][field]=coverage
                row[field]=float((cc.ge(av) if field=='new_high_60' else cc.gt(av)).mean()) if coverage>=.70 else None
            h=allhist.setdefault(oid,[]);h.append(row)
            for n in [5,10,20]:
                recent=h[-n:];pairs=[(x['sector_return'],x['benchmark_return']) for x in recent if x['sector_return'] is not None and x['benchmark_return'] is not None]
                row['rs_'+str(n)]=math.prod(1+a for a,b in pairs)-math.prod(1+b for a,b in pairs) if len(pairs)/n>=.9 else None
                row['metric_coverage_json']['rs_'+str(n)]=len(pairs)/n
            sh=[x['turnover_share'] for x in h[-60:] if x['turnover_share'] is not None]
            med=float(np.median(sh)) if len(sh)>=40 else None
            row['turnover_intensity']=share/med if share is not None and med is not None and med>0 else None
            row['critical_data_ok']=all(row[f] is not None for f in ['sector_return','benchmark_return','rs_20','turnover_share','up_ratio','above_ma20','above_ma60','new_high_60'])
            row['stage_frozen']=not row['critical_data_ok'];row['freeze_reason']=None if row['critical_data_ok'] else 'required_metric_coverage_unavailable'
            row['membership_checksum']=digest({'trade_date':d,'taxonomy_version':'SW2021','object_id':oid,'members':mid})
            rows.append(row)
        memberships[d]={'trade_date':d,'taxonomy_version':'SW2021','complete':True,'members':daily_members,
            'checksums':{r['object_id']:r['membership_checksum'] for r in rows},'source_snapshot_ids':[source_ids['membership']]}
        panel.extend(rows)
    # Precompute warmup features and ranks using actual daily board history.
    from mainline.engine.metrics import finalize_metrics,add_cross_section
    prepared=[];history={}
    for d in dates:
        rows=[r for r in panel if r['as_of_date']==d]
        rows=add_cross_section([finalize_metrics(r,history.get(r['object_id'],[]),dates) for r in rows])
        for r in rows:history.setdefault(r['object_id'],[]).append(r)
        prepared.extend(rows)
    # Replay includes warmup to preserve feature history, but state S0 is seeded
    # at first fully-ready date for >=10 industries. Earlier metrics are warmup.
    first=next(d for d in dates if d>seed_date)
    # Seed at first actual window day; warmup input explicitly supplied to replay.
    live=[r for r in prepared if r['as_of_date']>=first]
    warm=[r for r in prepared if r['as_of_date']<first]
    calls=[]
    def resolver(d):
        # Parse again for the actual target date, not a static extension.
        calls.append(d)
        expected=memberships[d]
        for name in names:
            oid='sw1_classification_'+mapping[name]
            actual=sorted(set(provider.snapshot(date.fromisoformat(d),mapping[name],name).frame.security_id)&
                          {m['security_id'] for m in universe[d].members})
            if actual!=expected['members'][oid]:raise ValueError('daily resolver repeat changed')
        return expected
    from mainline.production.daily import evolve
    a=evolve(live,dates,profile,resolver,warm,seed);first_calls=list(calls);calls.clear()
    b=evolve(live,dates,profile,resolver,warm,seed)
    events=a['events'];kinds={k:sum(e['from_state']+'->'+e['to_state']==k for e in events) for k in ['S0->S1','S1->S2','S2->S3','S3->S2','S3->S4','S4->S1']}
    result={'run_id':RUN,'code_commit':os.environ['CODE_COMMIT'],'rule_version':profile['rule_version'],
            'parameter_profile':profile['profile_id'],'clarification_version':profile['clarification_version'],
            'metric_availability_version':profile['metric_availability_version'],'parameter_hash':profile['calculation_parameter_hash'],
            'window_start':first,'window_end':dates[-1],'warmup_days':len({r['as_of_date'] for r in warm}),
            'days':len(first_calls),'industry_count':len(names),'daily_membership_calls':len(first_calls),
            'minimum_valid_cross_section':min(r['valid_ranked_objects'] for r in a['cross_sections']),
            'seed':'trusted_checkpoint:'+seed_date,'real_transition_counts':kinds,'rows':len(a['rows']),'deterministic':digest(a)==digest(b),
            'repeat_checksum':digest(b),'input_price_checksum':price_sha,'temporary_stock_rows':len(bars),
            'source_snapshot_ids':source_ids,'provider_failures':sum(x['status']=='failed' for x in audit),
            'provider_requests':len(audit),'membership_source_version':provider.source_version,
            'tls_verified':False,'knowledge_time_unverified':True,'pit_level':'effective_pit'}
    write('real_window_gate.json',result);write('real_events.json',events);write('real_board_states.json',a['rows'])
    write('real_cross_sections.json',a['cross_sections']);write('real_benchmark.json',benchmark)
    write('real_fetch_manifest.json',audit)
    write('real_memberships.json',memberships)
    write('real_input_provenance.json',{'universe_source':usource,'membership_source_version':provider.source_version,
        'stock_workbook_sha256':hashlib.sha256(stock_raw).hexdigest(),'taxonomy_workbook_sha256':hashlib.sha256(code_raw).hexdigest(),
        'source_ids':source_ids,'membership_resolution_count':len(dates)*len(names),'temporary_price_checksum':price_sha,
        'source_evidence_grade':'normalized_temporary_parquet_and_real_response_checksums','no_individual_longterm_database':True})
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as e:
        write('real_window_error.json',{'code_commit':os.environ.get('CODE_COMMIT'),'type':type(e).__name__,'error':str(e),'run_id':RUN})
        raise
