"""Bounded missing-field acquisition from existing official exchange upstreams."""
from pathlib import Path
from datetime import datetime,timezone
import requests,json,hashlib
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
fetch('sz_full_xlsx','https://fund.szse.cn/api/report/ShowReport',{'SHOWTYPE':'xlsx','CATALOGID':'1110','TABKEY':'tab1'})
fetch('bj_2021_count','https://www.bse.cn/important_news/200011669.html')
fetch('bj_guandian_exit','https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php',{'id':'8062882'})
fetch('bj_taixiang_exit','https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php',{'id':'8365150','stockid':'301192'})
fetch('bj_guangdao_exit','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php',{'id':'11894718','stockid':'920680'})
fetch('bj_hanbo_report','https://vip.stock.finance.sina.com.cn/corp/view/vISSUE_MarketBulletinDetail.php',{'id':'8426680','stockid':'301321'})
fetch('bj_pilot_names','https://www.bse.cn/important_news/200025487.html')
fetch('bj_full_switch','https://www.bse.cn/important_news/200026735.html')
(P/'probe.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
