"""Isolated mainline gap POC; stock inputs are ephemeral, no DB credentials."""
import argparse
import hashlib
import importlib.metadata
import inspect
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import sys
import time
from datetime import date, timedelta, datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from mainline.poc import phase1f_c as c


def probe_worker(pipe,source,sid,end):
    try:
        import requests
        import akshare as ak
        # AKShare's CNinfo method has no timeout. Bound it in this isolated process.
        post=requests.post
        def bounded_post(*a,**kw):
            kw.setdefault('timeout',10)
            return post(*a,**kw)
        requests.post=bounded_post
        symbol=sid[-2:].lower()+sid[:6]
        if source=='Sina_float':
            from akshare.stock.cons import zh_sina_a_stock_amount_url
            from akshare.utils import demjson
            url=zh_sina_a_stock_amount_url.format(symbol,symbol)
            r=requests.get(url,timeout=10);r.raise_for_status()
            rows=demjson.decode(r.text[r.text.find('['):r.text.rfind(']')+1])
            result={'ok':bool(rows),'rows':rows,'endpoint':url,'raw_checksum':hashlib.sha256(r.content).hexdigest(),
                    'date_semantics':'Sina date field; effective-date semantics unverified',
                    'unit':'upstream 10,000 shares per pinned AKShare scaling',
                    'source_code_checksum':hashlib.sha256(inspect.getsource(ak.stock_zh_a_daily).encode()).hexdigest()}
        elif source=='CNinfo_float':
            f=ak.stock_share_change_cninfo(symbol=sid[:6],start_date='19900101',end_date=end.strftime('%Y%m%d'))
            wanted=['证券代码','证券简称','公告日期','变动日期','变动原因','总股本','已流通股份','人民币普通股','境内上市外资股-B股','境外上市外资股-H股','高管股']
            result={'ok':not f.empty,'rows':c.clean(f[[x for x in wanted if x in f]].to_dict('records')),
                    'columns':list(f.columns),'endpoint':'https://webapi.cninfo.com.cn/api/stock/p_stock2215',
                    'date_semantics':'VARYDATE effective-date; DECLAREDATE separate; knowledge time unverified',
                    'unit':'10,000 shares; F022N circulating RMB ordinary shares',
                    'source_code_checksum':hashlib.sha256(inspect.getsource(ak.stock_share_change_cninfo).encode()).hexdigest()}
        elif source=='Sina_structure':
            import pandas as pd
            import io
            url=f'https://money.finance.sina.com.cn/corp/go.php/vCI_StockStructureHistory/stockid/{sid[:6]}/stocktype/TotalStock.phtml'
            r=requests.get(url,timeout=10);r.raise_for_status();r.encoding=r.apparent_encoding
            tables=pd.read_html(io.StringIO(r.text))
            selected=[f.astype(str).to_dict('split') for f in tables if any('流通A股' in str(x) for x in f.values.flatten())]
            result={'ok':bool(selected),'tables':selected,'endpoint':url,'raw_checksum':hashlib.sha256(r.content).hexdigest()}
        elif source=='BSE_mapping':
            import pandas as pd
            import io
            url='https://www.bse.cn/service/code_mapping.html'
            r=requests.get(url,timeout=10);r.raise_for_status();r.encoding=r.apparent_encoding
            tables=pd.read_html(io.StringIO(r.text));rows=[]
            for f in tables:
                if '旧代码' in str(f.columns) and '新代码' in str(f.columns):rows.extend(f.astype(str).to_dict('records'))
            result={'ok':bool(rows),'rows':rows,'endpoint':url,'raw_checksum':hashlib.sha256(r.content).hexdigest()}
        else:raise ValueError('unknown probe source')
        pipe.send(result)
    except Exception as e:pipe.send({'ok':False,'error':f'{type(e).__name__}:{e}'})


def probe(source,sid,end):
    started=time.monotonic();ctx=mp.get_context('spawn');parent,child=ctx.Pipe()
    process=ctx.Process(target=probe_worker,args=(child,source,sid,end));process.start();child.close()
    try:
        r=parent.recv() if parent.poll(25) else {'ok':False,'error':'timeout:isolated source probe'}
    except EOFError:r={'ok':False,'error':'dependency/worker exited'}
    finally:
        if process.is_alive():process.terminate()
        process.join(2);parent.close()
    return {'source':source,'security_id':sid,'as_of_date':end.isoformat(),'elapsed_time':time.monotonic()-started,**r}


def special(out,config,snaps):
    members={sid for s in snaps for sid in s.frame.security_id}
    planned=[('600183.SH','2019-06-28'),('000045.SZ','2019-06-28'),('000049.SZ','2019-06-28'),
             ('002475.SZ','2025-06-30'),('688041.SH','2025-06-30'),('920174.BJ','2021-12-31'),
             ('920001.BJ','2025-06-30'),('920060.BJ','2025-06-30')]
    assert all(s in members for s,_ in planned)
    results=[]
    for source in ('Sina_float','CNinfo_float'):
        consecutive=0
        for sid,d in planned:
            pair=[probe(source,sid,date.fromisoformat(d)) for _ in (1,2)]
            results.extend(pair);consecutive=0 if any(r['ok'] for r in pair) else consecutive+1
            print(source,sid,[r['ok'] for r in pair],flush=True)
            if consecutive>=3:break
    for sid,d in planned[:3]:results.append(probe('Sina_structure',sid,date.fromisoformat(d)))
    results.append(probe('BSE_mapping','scope',date(2025,6,30)))
    c.write(out/'circ_mv_source_probes.json',results)
    client=c.IsolatedClient('Sina',config);health=[]
    try:
        health.append(c.health_check(client,config,snaps))
        for sid,d in [('920174.BJ','2021-12-31'),('920001.BJ','2025-06-30'),('920060.BJ','2025-06-30'),
                      ('833994.BJ','2025-06-30'),('920245.BJ','2021-12-31'),
                      ('600806.SH','2021-12-31'),('601299.SH','2021-12-31'),('600898.SH','2025-06-30')]:
            pair=[]
            for _ in (1,2):
                end=date.fromisoformat(d);r=c.fetch_checked(client,sid,end-timedelta(days=120),end)
                if r['ok']:
                    f=r.pop('frame');r['row_count']=len(f);r['checksum']=c.digest(c.frame_records(f));
                    r['observed_dates']=list(f.trade_date);r['non_null_prices']=f.close.notna().sum()
                pair.append(r)
            health.append({'security_id':sid,'trade_date':d,'calls':pair})
    finally:client.close()
    c.write(out/'special_health.json',health)
    c.write(out/'summary.json',{'phase':'1F-D1.1','status':'SPECIAL_CHECK_COMPLETE','production_writes':False,'gate':'UNCHANGED'})


def classify(sid,reason):
    known={'833994.BJ':'delisted_or_changed:transfer_to_301321_no_alias_substitution',
           '920245.BJ':'security_no_history_pre_listing:2022-01-06',
           '600806.SH':'delisted_or_changed:delisted_2018-07-13',
           '601299.SH':'delisted_or_changed:absorbed_2015',
           '600898.SH':'delisted_or_changed:delisted_2025-02-10'}
    if reason=='empty':return known.get(sid,'provider_empty_unclassified')
    if 'UNSUPPORTED' in reason:return 'adapter_unsupported'
    if 'timeout' in reason.lower():return 'timeout'
    return 'request_error:'+reason


def full(out,config,snaps,integrity,env):
    import pandas as pd
    from collections import Counter
    import uuid
    benchmark,evidence=c.get_benchmark(ROOT/'scripts/mainline/phase1f_d11/benchmark.json')
    evidence['source_snapshot_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,evidence['checksum']))
    health=[];metrics=[];errors=[];sources=[evidence];batches=[]
    client=c.IsolatedClient('Sina',config)
    summary={'phase':'1F-D1.1','status':'PARTIAL','gate':'UNCHANGED','mainline_job':'pending_provider',
             'production_write_allowed':False,'recommend_phase1f_d2':False,
             'circ_mv_policy':'unaccepted historical share candidates remain NULL; no asof filling',
             'circ_mv_rejection':'daily effective-date completeness unverified; 600183 source disagreement; all-A denominator missing'}
    try:
        h=c.health_check(client,config,snaps);health.append(h)
        if not h['health_pass']:raise RuntimeError('Sina health did not pass; no sector requests')
        deadline=time.monotonic()+config['provider_budget_seconds']
        for rep in (1,2):
            batch=[]
            for sample,membership in zip(config['samples'],snaps):
                result,err,source=c.run_sample(client,config,sample,membership,benchmark,out,deadline,rep)
                for e in err:e['category']=classify(e['security_id'],e['reason'])
                result['error_categories']=dict(Counter(e['category'] for e in err))
                result['membership_listing_universe_warning']=sample['sample_id']=='2021-12-31:801890'
                member_source=str(uuid.uuid5(uuid.NAMESPACE_URL,c.digest(c.clean(membership.frame.sort_values('security_id').to_dict('records')))))
                benchmark_source=str(uuid.uuid5(uuid.NAMESPACE_URL,evidence['checksum']))
                result['source_snapshot_ids'] += [member_source,benchmark_source]
                result['run_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,'phase1fd11:'+result['run_id']))
                batch.append(result);metrics.append(result);sources.append(source)
                errors.extend({'sample_id':sample['sample_id'],**e} for e in err)
            batches.append(batch)
        repeats=[{'sample_id':a['sample_id'],**c.compare(a,b)} for a,b in zip(*batches)]
        summary.update(market_window_pass=all(m['market_window_pass'] for m in metrics),
                       repeatability_pass=all(x['identical'] for x in repeats),
                       reason='Historical shares and all-A circulating capitalization not accepted; full PASS blocked')
        c.write(out/'repeatability_report.json',{'executed':True,'samples':repeats})
        # Audit real missing-session cases; missing records alone cannot prove suspension.
        cases=[]
        for sample,source in zip(config['samples'],[x for x in sources if x.get('repetition')==1]):
            wanted=list(benchmark.loc[benchmark.trade_date<=date.fromisoformat(sample['trade_date']),'trade_date'].tail(60))
            for row in source['securities']:
                file=out/'cache/Sina/1'/sample['sample_id'].replace(':','_')/(row['security_id']+'.json')
                bars=json.loads(file.read_text());available={x['trade_date'] for x in bars if x['close'] is not None}
                gaps=[str(d) for d in wanted if str(d) not in available]
                if gaps and len(available)>=60 and row['security_id'] not in {x['security_id'] for x in cases}:
                    cases.append({'sample_id':sample['sample_id'],'security_id':row['security_id'],
                        'market_window':list(map(str,wanted)),'missing_dates':gaps,
                        'zero_trade_dates':row['audit'].get('no_trade_dates',[]),
                        'classification':'missing_or_no_trade; suspension announcement unverified',
                        'MA20_valid':not any(str(d) not in available for d in wanted[-20:]),
                        'MA60_valid':False,'older_observations_available':len(available),
                        'older_records_borrowed':False})
                if len(cases)>=5:break
            if len(cases)>=5:break
        c.write(out/'suspension_report.json',{'cases':cases,'confirmed_suspension_count':0,
            'status':'window semantics verified; suspension cause requires announcements'})
    finally:
        client.close()
        for sample,snap in zip(config['samples'],snaps):
            sources.append({'source_id':'sws_official_cached_membership_evidence',
                'source_snapshot_id':str(uuid.uuid5(uuid.NAMESPACE_URL,c.digest(c.clean(snap.frame.sort_values('security_id').to_dict('records'))))),
                'sample_id':sample['sample_id'],'row_count':len(snap.frame),
                'response_checksum':c.digest(c.clean(snap.frame.sort_values('security_id').to_dict('records'))),
                'pit_level':snap.pit_level,'knowledge_time_unverified':True})
        c.write(out/'circ_mv_health.json',json.loads((ROOT/'scripts/mainline/phase1f_d11/circ_mv_probe_evidence.json').read_text()))
        c.write(out/'calendar_manifest.json',{'source':'existing SWS official 801003 index dates',
            'checksum':evidence['checksum'],'parent_checksum':evidence.get('parent_evidence_checksum'),
            'pit':'effective_pit; knowledge_time_unverified','tls_authenticity':'legacy verify=False unverified',
            'production_calendar_written':False})
        c.finalize(out,summary,metrics,health,errors,sources,env,integrity)
        manifest=json.loads((out/'run_manifest.json').read_text());manifest['job_name']='phase1fd11_gap_poc'
        manifest['window_semantics']='last N market sessions inclusive target; no valid-record substitution'
        c.write(out/'run_manifest.json',manifest)
        c.write(out/'checksums.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.suffix in ('.json','.csv') and p.name!='checksums.json'})
        print(json.dumps(summary),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--special-only',action='store_true');args=parser.parse_args()
    config,snaps,integrity=c.preflight(ROOT,ROOT/'scripts/mainline/phase1f_c')
    out=ROOT/'artifacts'/('phase1f_d11_special' if args.special_only else 'phase1f_d11')
    out.mkdir(parents=True,exist_ok=True)
    env={'OS':platform.platform(),'Python':sys.version,'git_sha':os.getenv('GITHUB_SHA'),
        'git_branch':os.getenv('GITHUB_REF_NAME'),'timezone':'UTC','business_timezone':'Asia/Shanghai',
        'execution_time':datetime.now(timezone.utc),'runner':os.getenv('RUNNER_ENVIRONMENT'),
        'dependencies':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()}}
    c.write(out/'environment.json',env)
    if args.special_only:
        special(out,config,snaps)
        c.write(out/'checksums.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.json') if p.name!='checksums.json'})
    else:full(out,config,snaps,integrity,env)


if __name__=='__main__':main()
