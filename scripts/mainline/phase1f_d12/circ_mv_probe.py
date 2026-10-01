"""Read-only circ_mv candidate diagnostics. Never authorizes as-of or production writes."""
import argparse, concurrent.futures, datetime as dt, hashlib, inspect, json, platform
from pathlib import Path
import akshare as ak
import pandas as pd
import requests
from akshare.stock.cons import zh_sina_a_stock_amount_url, zh_sina_a_stock_hist_url, hk_js_decode
from akshare.utils import demjson
from py_mini_racer import py_mini_racer

SAMPLES=[('600183.SH','2019-06-28'),('000045.SZ','2019-06-28'),('000049.SZ','2019-06-28'),
 ('002475.SZ','2025-06-30'),('688041.SH','2025-06-30'),('920174.BJ','2021-12-31'),
 ('920001.BJ','2025-06-30'),('920060.BJ','2025-06-30'),('000008.SZ','2021-12-31'),
 ('000039.SZ','2021-12-31'),('600031.SH','2021-12-31'),('300124.SZ','2021-12-31')]
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(dt.date,dt.datetime)):return x.isoformat()
 if pd.isna(x):return None
 if hasattr(x,'item'):return x.item()
 return x
def encoded(x):return json.dumps(clean(x),ensure_ascii=False,sort_keys=True,allow_nan=False).encode()
def digest(x):return hashlib.sha256(encoded(x)).hexdigest()
def write(p,x):p.write_bytes(encoded(x))
POST=requests.post
def bounded_post(*a,**kw):kw.setdefault('timeout',15);return POST(*a,**kw)
requests.post=bounded_post
def fetch(sid,source,rep,out):
 existing=out/f'{sid}_{source}_{rep}.json'
 if existing.exists():
  return json.loads(existing.read_text())
 symbol=sid[-2:].lower()+sid[:6];started=dt.datetime.now(dt.timezone.utc).isoformat()
 result={'security_id':sid,'source':source,'repetition':rep,'fetched_at':started,'ok':False}
 try:
  if source=='CNinfo':
   result['endpoint']='https://webapi.cninfo.com.cn/api/stock/p_stock2215'
   rows=ak.stock_share_change_cninfo(symbol=sid[:6],start_date='19900101',end_date='20261001').to_dict('records')
  else:
   url=zh_sina_a_stock_amount_url.format(symbol,symbol) if source=='Sina_shares' else zh_sina_a_stock_hist_url.format(symbol)
   result['endpoint']=url;r=requests.get(url,timeout=15);r.raise_for_status()
   result['raw_checksum']=hashlib.sha256(r.content).hexdigest()
   (out/f'{sid}_{source}_{rep}.raw').write_bytes(r.content)
   if source=='Sina_shares':rows=demjson.decode(r.text[r.text.find('['):r.text.rfind(']')+1])
   else:
    js=py_mini_racer.MiniRacer();js.eval(hk_js_decode)
    raw=js.call('d',r.text.split('=')[1].split(';')[0].replace('"',''))
    rows=[{'date':str(v['date'])[:10],'close':v.get('close')} for v in raw]
  result.update(ok=bool(rows),rows=clean(rows),normalized_checksum=digest(rows),row_count=len(rows))
 except Exception as e:result['error']=type(e).__name__+':'+str(e)[:250]
 write(out/f'{sid}_{source}_{rep}.json',result)
 return result
def latest_candidate(rows,target,source):
 # Diagnostic candidate only: NOT accepted effective-date selection.
 key='date' if source=='Sina_shares' else '变动日期'
 valid=[x for x in rows if x.get(key) and str(x[key])[:10]<=target]
 if not valid:return None
 return sorted(valid,key=lambda x:str(x[key]))[-1]
def run(out):
 out.mkdir(parents=True,exist_ok=True);raw=out/'raw';raw.mkdir(exist_ok=True)
 fetches=[]
 for rep in (1,2):
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
   tasks=[pool.submit(fetch,sid,source,rep,raw) for sid,_ in SAMPLES for source in ('Sina_shares','CNinfo','Sina_close')]
   for task in concurrent.futures.as_completed(tasks):
    r=task.result();fetches.append(r);print(rep,r['security_id'],r['source'],r['ok'],r.get('row_count',0),flush=True)
 index={(x['security_id'],x['source'],x['repetition']):x for x in fetches}
 repeats=[];validation=[];sample_plan=[]
 for sid,target in SAMPLES:
  for source in ('Sina_shares','CNinfo','Sina_close'):
   a=index[sid,source,1];b=index[sid,source,2]
   repeats.append({'security_id':sid,'source':source,'both_ok':a['ok'] and b['ok'],
    'identical':a['ok'] and b['ok'] and a['normalized_checksum']==b['normalized_checksum']})
  a=index[sid,'Sina_shares',1];b=index[sid,'CNinfo',1];c=index[sid,'Sina_close',1]
  prices={x['date']:x['close'] for x in c.get('rows',[]) if x.get('close') is not None and x['date']<=target}
  changes=[];prior=None
  for x in sorted(a.get('rows',[]),key=lambda x:x['date']):
   if x['date']<=target and x.get('amount')!=prior:changes.append(x['date'])
   prior=x.get('amount')
  event=changes[-1] if changes else target
  if sid=='600183.SH':dates=['2018-05-25','2018-05-29',target]
  else:
   pre=[d for d in prices if d<event];post=[d for d in prices if d>=event]
   dates=[max(pre) if pre else target,min(post) if post else target,target]
   # Ensure three distinct historical trading dates; these are probes, not proven event dates.
   dates=list(dict.fromkeys(dates))
   for d in sorted(prices,reverse=True):
    if len(dates)>=3:break
    if d not in dates:dates.append(d)
   if len(dates)<3:
    dates=list(dict.fromkeys(dates+['2021-12-30','2025-06-27']))[:3]
  sample_plan.append({'security_id':sid,'poc_date':target,'dates':dates,'candidate_event_date':event,
   'event_date_verified':False})
  for d in dates:
   sr=latest_candidate(a.get('rows',[]),d,'Sina_shares');cr=latest_candidate(b.get('rows',[]),d,'CNinfo')
   ss=float(sr['amount'])*10000 if sr and sr.get('amount') is not None else None
   cs=float(cr['人民币普通股'])*10000 if cr and cr.get('人民币普通股') is not None else None
   pct=(ss-cs)/cs*100 if ss is not None and cs else None
   close=prices.get(d)
   validation.append({'provider/source':'Sina_shares vs CNinfo F022N','security_id':sid,'target_date':d,
    'float_shares':None,'close':close,'circ_mv':None,'effective_date':None,
    'source_date':sr.get('date') if sr else None,'cninfo_source_date':cr.get('变动日期') if cr else None,
    'cninfo_announcement_date':cr.get('公告日期') if cr else None,
    'candidate_sina_shares':ss,'candidate_cninfo_shares':cs,
    'candidate_sina_circ_mv':ss*close if ss is not None and close is not None else None,
    'candidate_cninfo_circ_mv':cs*close if cs is not None and close is not None else None,
    'pit_level':'unproven','knowledge_time_unverified':True,'difference_pct':pct,
    'difference_reason':'event completeness and effective dates unproven; source field semantics not fully locked',
    'resolved':False,'validation_status':'UNACCEPTED_EVENT_SEQUENCE',
    'raw_float_share_unit':'10,000 shares; candidate conversion only','close_unit':'CNY/share','circ_mv_unit':'CNY'})
 write(out/'source_manifest.json',fetches);write(out/'repeatability.json',repeats)
 write(out/'sample_plan.json',sample_plan);write(out/'validation.json',validation)
 summary={'phase':'1F-D1.2','status':'PARTIAL' if any(x['ok'] for x in fetches) else 'BLOCKED',
  'free_source_status':'FREE_CIRC_MV_NOT_PROVEN','accepted_count':0,'sample_count':len(SAMPLES),
  'date_count':len(validation),'retrieval_successes':sum(x['ok'] for x in fetches),'retrieval_attempts':len(fetches),
  'accepted_coverage':0,'sector_retest':'NOT_RUN_SPECIALIST_GATE_NOT_PASSED','production_writes':False,
  'mainline_job_enabled':False,'recommend_d13':False}
 write(out/'summary.json',summary)
 write(out/'run_manifest.json',{'phase':'1F-D1.2','base_commit':'7b9d968df49335db9cc36d06f231705803fd7f3a',
  'started_at':fetches[0]['fetched_at'],'finished_at':dt.datetime.now(dt.timezone.utc).isoformat(),
  'python':platform.python_version(),'akshare':ak.__version__,'requests':requests.__version__,
  'script_checksum':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  'cninfo_decoder_checksum':hashlib.sha256(inspect.getsource(ak.stock_share_change_cninfo).encode()).hexdigest(),
  'production_writes':False,'candidate_asof_authorizes_use':False,'summary':summary})
 write(out/'checksums.json',{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
  for p in out.rglob('*') if p.is_file() and p.name!='checksums.json'})
 print(json.dumps(summary),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();run(Path(a.out))
