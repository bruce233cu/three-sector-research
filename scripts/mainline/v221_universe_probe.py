"""Bounded missing-field acquisition from existing official exchange upstreams."""
from pathlib import Path
from datetime import datetime,timezone
import requests,json,hashlib
from concurrent.futures import ThreadPoolExecutor
P=Path('reports/v221-benchmark-universe');P.mkdir(parents=True,exist_ok=True)
audit=json.loads((P/'probe.json').read_text()) if (P/'probe.json').exists() else []
def fetch(label,url,params=None):
    try:
        r=requests.get(url,params=params,timeout=18,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.szse.cn/'})
        data=r.content;(P/(label+'.raw')).write_bytes(data)
        try:payload=r.json()
        except ValueError:payload=None
        audit.append({'label':label,'url':r.url,'status':r.status_code,'fetched_at':datetime.now(timezone.utc).isoformat(),'checksum':hashlib.sha256(data).hexdigest(),'bytes':len(data),'json':payload,'text_prefix':r.text[:250]})
        print(label,r.status_code,len(data),flush=True)
        return r
    except Exception as e:
        audit.append({'label':label,'url':url,'error':type(e).__name__+':'+str(e)})
        print(label,type(e).__name__,flush=True)
fetch('sz_http_full_xlsx','http://www.szse.cn/api/report/ShowReport',{'SHOWTYPE':'xlsx','CATALOGID':'1110','TABKEY':'tab1'})
if not (P/'sz_http_full_xlsx.raw').exists() or (P/'sz_http_full_xlsx.raw').read_bytes()[:2]!=b'PK':
    template=next(x for x in audit if x['label']=='sz_fund_backend')['json'][0]
    def page(n):
        return fetch('sz_page_'+str(n),'https://fund.szse.cn/api/report/ShowReport/data',{'SHOWTYPE':'JSON','CATALOGID':'1110','TABKEY':'tab1','PAGENO':str(n)})
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(page,range(1,template['metadata']['pagecount']+1)))
fetch('bj_yunchuang_exit','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php',{'id':'12467916','stockid':'920305'})
(P/'probe.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
