"""Bounded missing-field acquisition from existing official exchange upstreams."""
from pathlib import Path
from datetime import datetime,timezone
import requests,json,hashlib
P=Path('reports/v221-benchmark-universe');P.mkdir(parents=True,exist_ok=True)
audit=[]
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
params={'SHOWTYPE':'JSON','CATALOGID':'1110','TABKEY':'tab1','PAGENO':'1','PAGESIZE':'10000'}
for label,url in [('sz_json','https://www.szse.cn/api/report/ShowReport/data'),('sz_json_query','https://query.szse.cn/api/report/ShowReport/data')]:
    r=fetch(label,url,params)
    if r is not None and r.status_code==200 and audit[-1].get('json'):break
fetch('bj_mapping','https://www.bse.cn/service/code_mapping.html')
fetch('bj_mapping_info','https://www.bseinfo.net/service/code_mapping.html')
fetch('bj_listing_page','https://www.bse.cn/nq/listedcompany.html')
fetch('bj_pilot','https://www.bse.cn/important_news/200025603.html')
fetch('sz_http','http://www.szse.cn/api/report/ShowReport/data',params)
fetch('sz_fund_backend','https://fund.szse.cn/api/report/ShowReport/data',params)
fetch('bj_listing_js','https://www.bse.cn/template/6/bluewise/_files/js/products/companies_name.min.js')
(P/'probe.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
