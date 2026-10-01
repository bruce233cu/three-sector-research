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


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--special-only',action='store_true');args=parser.parse_args()
    config,snaps,integrity=c.preflight(ROOT,ROOT/'scripts/mainline/phase1f_c')
    out=ROOT/'artifacts/phase1f_d11_special';out.mkdir(parents=True,exist_ok=True)
    c.write(out/'environment.json',{'OS':platform.platform(),'Python':sys.version,'git_sha':os.getenv('GITHUB_SHA'),
             'git_branch':os.getenv('GITHUB_REF_NAME'),'timezone':'UTC','execution_time':datetime.now(timezone.utc),
             'dependencies':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()}})
    try:special(out,config,snaps)
    except Exception as e:
        c.write(out/'summary.json',{'phase':'1F-D1.1','status':'BLOCKED','reason':f'{type(e).__name__}:{e}','production_writes':False})
        raise
    finally:
        c.write(out/'checksums.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.json') if p.name!='checksums.json'})


if __name__=='__main__':main()
