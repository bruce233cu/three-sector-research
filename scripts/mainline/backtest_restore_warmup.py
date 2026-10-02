"""Recover ONLY the missing 84 BOARD warmup days from the same certified bytes.

No G1-G4 gate, Universe reconstruction, provider change or production write.
Temporary individual bars are used locally and are not published as an asset.
Require each successful raw response to match its original certification hash.
"""
import argparse,sys,json,zipfile,hashlib,gzip,time,math,subprocess
from pathlib import Path
from datetime import date
from concurrent.futures import ThreadPoolExecutor,as_completed
import pandas as pd
from statistics import median
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from mainline.providers.phase1f_free import SinaWindow
from mainline.metrics.historical_universe import historical_benchmark_universe_resolver
from mainline.engine.replay import digest
from mainline.backtest.runner import read,write

def main(g3_zip,production_zip,universe_zip,output,cache):
    started=time.monotonic();cache.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(g3_zip) as z:
        original=json.loads(z.read('real_fetch_manifest.json'))
        provenance=json.loads(z.read('real_input_provenance.json'))
        benchmark=json.loads(z.read('real_benchmark.json'))
    with zipfile.ZipFile(production_zip) as z:members=json.loads(z.read('real_memberships.json'))
    with zipfile.ZipFile(universe_zip) as z:
        intervals=json.loads(z.read('temporary_universe_intervals.json'))
    usource=provenance['universe_source'];certificate=usource['metadata']['certificate']
    dates=[r['trade_date'] for r in benchmark if r['trade_date']<'2024-09-02']
    if len(dates)!=84 or dates[0]!='2024-05-06' or dates[-1]!='2024-08-30':raise ValueError('warmup scope changed')
    calendar=read(ROOT/'reports/milestone-a-fast-close/calendar_input.json')
    prior=calendar[calendar.index(dates[0])-1]
    universe={d:historical_benchmark_universe_resolver(d,intervals,certificate=certificate) for d in dates}
    if any(not u.verified for u in universe.values()):raise ValueError('uncertified prior universe')
    approved={r['security_id']:r for r in original if r['status']=='success'}
    requested=sorted({m['security_id'] for u in universe.values() for m in u.members})
    # Preserve original acquisition failures and original universe membership.
    requested=[sid for sid in requested if sid in approved]
    adapter=SinaWindow({});frames=[];audit=[]
    def fetch(sid):
        fp=cache/(sid+'.parquet');ap=cache/(sid+'.json')
        try:
            if fp.exists() and ap.exists():f=pd.read_parquet(fp);a=read(ap)
            else:
                f,a=adapter.get_one(sid,date.fromisoformat(prior),date.fromisoformat(dates[-1]))
                if a.get('unit_check_ok'):
                    f=f.drop(columns=['circ_mv'],errors='ignore');f.to_parquet(fp,index=False)
                    ap.write_text(json.dumps(a))
            if a['raw_payload_checksum']!=approved[sid]['raw_payload_checksum']:
                raise ValueError('raw response differs from original certification')
            if not a.get('unit_check_ok'):raise ValueError('amount unit not certified')
            return f,{'security_id':sid,'status':'success','raw_checksum_matches_original':True,**a}
        except Exception as e:return None,{'security_id':sid,'status':'failed','error':str(e)}
    with ThreadPoolExecutor(max_workers=12) as pool:
        jobs=[pool.submit(fetch,sid) for sid in requested]
        for i,j in enumerate(as_completed(jobs)):
            f,a=j.result();audit.append(a)
            if f is not None:frames.append(f)
            if (i+1)%250==0:print('WARMUP_RECOVERY',i+1,len(requested),'seconds',round(time.monotonic()-started),'failures',sum(a['status']=='failed' for a in audit),flush=True)
    cache_audit=cache/'recovery_audit.json';cache_audit.write_text(json.dumps(audit,ensure_ascii=False))
    if any(a['status']!='success' for a in audit):raise ValueError('exact certified warmup recovery incomplete; retry same temporary cache')
    bars=pd.concat(frames,ignore_index=True);bars['trade_date']=bars.trade_date.astype(str)
    if bars.duplicated(['security_id','trade_date']).any():raise ValueError('duplicate real bars')
    close=bars.pivot(index='trade_date',columns='security_id',values='close').reindex([prior]+dates)
    amount=bars.pivot(index='trade_date',columns='security_id',values='amount').reindex([prior]+dates)
    returns=(close.div(close.shift(1))-1).where((close>0)&(close.shift(1)>0)&(amount>0))
    ma20=close.rolling(20,min_periods=20).mean();ma60=close.rolling(60,min_periods=60).mean();hi60=close.rolling(60,min_periods=60).max()
    live=read(ROOT/'reports/milestone-d-baseline-v1/data/certified_board_inputs.json.gz')
    identity={r['object_id']:{k:r[k] for k in ['object_id','object_type','taxonomy_code','taxonomy_version','industry_name']} for r in live}
    history={};panel=[];checks=[]
    benchmark_by_date={r['trade_date']:r for r in benchmark}
    for d in dates:
        u=universe[d];uids=[m['security_id'] for m in u.members]
        previous=calendar[calendar.index(d)-1];eligible=[m['security_id'] for m in u.members if m['listing_date']<=previous]
        ur=returns.loc[d].reindex(eligible).dropna();bcov=len(ur)/len(uids);br=float(ur.mean()) if bcov>=.95 else None
        ua=amount.loc[d].reindex(uids).where(lambda v:v>0).dropna();allamount=float(ua.sum()) if len(ua) else None
        certified=benchmark_by_date[d]
        if br!=certified['benchmark_return'] and (br is None or certified['benchmark_return'] is None or abs(br-certified['benchmark_return'])>1e-12):
            raise ValueError('warm benchmark no longer matches certified observations:'+d)
        checks.append({'trade_date':d,'benchmark_return_matches':True,'universe_count':len(uids),'benchmark_coverage':bcov})
        allup=float(ur.gt(0).mean()) if bcov>=.70 else None
        av20=ma20.loc[d].reindex(uids).dropna()
        allabove=float(close.loc[d].reindex(av20.index).gt(av20).mean()) if len(av20)/len(uids)>=.70 else None
        m=members[d]
        if m['taxonomy_version']!='SW2021' or not m['complete']:raise ValueError('warm membership invalid')
        for oid in sorted(identity):
            mid=m['members'][oid]
            if not set(mid)<=set(uids):raise ValueError('future/outside-universe membership')
            checksum=digest({'trade_date':d,'taxonomy_version':'SW2021','object_id':oid,'members':sorted(mid)})
            if checksum!=m['checksums'][oid]:raise ValueError('warm membership checksum changed')
            rr=returns.loc[d].reindex(mid).dropna();aa=amount.loc[d].reindex(mid).where(lambda v:v>0).dropna();cov=len(rr)/len(mid)
            share=float(aa.sum())/allamount if allamount and len(aa)/len(mid)>=.70 else None
            row={**identity[oid],'as_of_date':d,'member_count':len(mid),'valid_member_count':len(rr),
                'sector_return':float(rr.mean()) if cov>=.70 else None,'benchmark_return':br,'turnover_share':share,
                'up_ratio':float(rr.gt(0).mean()) if cov>=.70 else None,'all_a_up_ratio':allup,'all_a_above_ma20':allabove,
                'top3_turnover_share':float(aa.nlargest(3).sum()/aa.sum()) if len(aa)>=3 else None,
                'source_snapshot_ids':[provenance['source_ids'][k] for k in ['membership','price','benchmark']]+[usource['source_snapshot_id']],
                'membership_checksum':checksum,'evidence_kind':'real_historical_board',
                'metric_coverage_json':{'sector_return':cov,'amount':len(aa)/len(mid),'benchmark':bcov}}
            for field,indicator in [('above_ma20',ma20),('above_ma60',ma60),('new_high_60',hi60)]:
                av=indicator.loc[d].reindex(mid).dropna();cc=close.loc[d].reindex(av.index);coverage=len(av)/len(mid)
                row['metric_coverage_json'][field]=coverage
                row[field]=float((cc.ge(av) if field=='new_high_60' else cc.gt(av)).mean()) if coverage>=.70 else None
            h=history.setdefault(oid,[]);h.append(row)
            for n in [5,10,20]:
                pairs=[(x['sector_return'],x['benchmark_return']) for x in h[-n:] if x['sector_return'] is not None and x['benchmark_return'] is not None]
                row['rs_'+str(n)]=math.prod(1+a for a,b in pairs)-math.prod(1+b for a,b in pairs) if len(pairs)/n>=.9 else None
                row['metric_coverage_json']['rs_'+str(n)]=len(pairs)/n
            sh=[x['turnover_share'] for x in h[-60:] if x['turnover_share'] is not None];med=median(sh) if len(sh)>=40 else None
            row['turnover_intensity']=share/med if share is not None and med is not None and med>0 else None
            row['critical_data_ok']=all(row[f] is not None for f in ['sector_return','benchmark_return','rs_20','turnover_share','up_ratio','above_ma20','above_ma60','new_high_60'])
            row['stage_frozen']=not row['critical_data_ok'];row['freeze_reason']=None if row['critical_data_ok'] else 'required_metric_coverage_unavailable'
            panel.append(row)
    if len(panel)!=84*31:raise ValueError('warm panel incomplete')
    output.mkdir(parents=True,exist_ok=True)
    write(output/'warmup_board_inputs.json.gz',panel)
    warm_members={d:members[d] for d in dates}
    for d in dates:warm_members[d]['source_snapshot_ids']=[provenance['source_ids']['membership']]
    write(output/'warmup_memberships.json.gz',warm_members)
    write(output/'warmup_acquisition_audit.json.gz',audit)
    write(output/'warmup_provenance.json',{'scope':'missing 84-day warmup only',
        'code_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'acquisition_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'warmup_checksum':digest(panel),'membership_checksum':digest(warm_members),
        'warmup_days':84,'warmup_rows':len(panel),'warmup_start':dates[0],'warmup_end':dates[-1],
        'original_raw_response_checksum_matching':True,'requested_successful_original_sources':len(requested),
        'original_failed_sources_kept_missing':[a['security_id'] for a in original if a['status']=='failed'],
        'warm_benchmark_checks':checks,'data_snapshot_version':'board-archive-warm-restored-'+digest(panel)[:16],
        'source_snapshot_ids':provenance['source_ids'],'universe_source':usource['source_snapshot_id'],
        'universe_zip_sha256':hashlib.sha256(Path(universe_zip).read_bytes()).hexdigest(),
        'universe_interval_payload_sha256':hashlib.sha256(json.dumps(intervals,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'source_artifact_run_ids':[36961627493,36970118460,36942748135],
        'membership_source_version':provenance['membership_source_version'],
        'pit_level':'effective_pit','knowledge_time_unverified':True,'available_at':None,
        'individual_longterm_asset_created':False,'provider_changed':False,'universe_rebuilt':False,
        'rules_changed':False,'production_writes':0,'elapsed_seconds':round(time.monotonic()-started)})
    print('WARMUP_RESTORED',len(panel),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--g3-zip',type=Path,required=True);p.add_argument('--production-zip',type=Path,required=True)
    p.add_argument('--universe-zip',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--cache',type=Path,required=True)
    a=p.parse_args();main(a.g3_zip,a.production_zip,a.universe_zip,a.output,a.cache)
