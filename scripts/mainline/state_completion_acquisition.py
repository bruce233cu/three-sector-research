"""Bounded reuse of existing official SWS source; no new provider research.

Full workbooks stay temporary. Only acquisition metadata goes into the report.
The source read does not itself certify a real state transition.
"""
import json,hashlib,urllib.request,time,os
from pathlib import Path
from datetime import date
from mainline.providers.sws_history import SwsEffectivePitProvider,SWS_STOCK_HISTORY_URL,SWS_CODE_URL,_download

out=Path('reports/g3-state-completion');out.mkdir(parents=True,exist_ok=True)
result={'code_commit':os.environ.get('CODE_COMMIT'),'source':'existing_official_SWS',
        'fetched_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'reads':[],
        'certified_real_transitions':0,'temporary_individual_payload_persisted':False}
payload=[]
for url in [SWS_STOCK_HISTORY_URL,SWS_CODE_URL]:
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(request,timeout=20) as r:
            b=r.read();status=r.status
        if len(b)<1024:raise ValueError('short or empty response')
        result['reads'].append({'url':url,'http_status':status,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
        payload.append(b)
    except Exception as e:
        initial={'url':url,'error_type':type(e).__name__,'error':str(e)[:400]}
        result['reads'].append(initial)
        # Reuse the already-approved adapter's existing transport compatibility.
        # Its verify=False is explicit in source; flag it, never claim verified TLS.
        try:
            b=_download(url,retries=1,timeout_seconds=20)
            result['reads'].append({'url':url,'transport':'existing_adapter','tls_verified':False,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
            payload.append(b)
        except Exception as fallback:
            result['reads'].append({'url':url,'transport':'existing_adapter','tls_verified':False,'error_type':type(fallback).__name__,'error':str(fallback)[:400]})
if len(payload)==2:
    try:
        p=SwsEffectivePitProvider(stock_bytes=payload[0],code_bytes=payload[1])
        result['ledger']={'rows':len(p.history),'level1_names':sorted(p.history.level1_name.unique().tolist()),
                          'effective_from_min':str(p.history.effective_from.min()),'source_version':p.source_version}
        # Resolve each actual session from existing calendar; no target-day extension.
        days=json.loads(Path('reports/milestone-a-fast-close/calendar_input.json').read_text())
        days=[d for d in days if '2025-01-01'<=d<='2025-06-30']
        result['daily_member_counts']=[{'trade_date':d,'industry':name,'members':len(p.snapshot(date.fromisoformat(d),'audit-name-only',name).frame)}
            for d in days for name in result['ledger']['level1_names']]
    except Exception as e:
        result['parse_error']={'type':type(e).__name__,'error':str(e)[:400]}
cache=Path('temporary_g3_input')
result['temporary_cache_inventory']=[{'path':str(p.relative_to(cache)),'bytes':p.stat().st_size} for p in cache.rglob('*') if p.is_file()] if cache.exists() else []
result['complete_board_panel_available']=False
(out/'source_acquisition.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='daily_member_counts'},ensure_ascii=False))
