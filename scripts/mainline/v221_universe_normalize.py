"""Normalize reused exchange ledgers into temporary listing/code intervals."""
from pathlib import Path
from datetime import date
from io import StringIO
import json,re,pandas as pd
from lxml import html

def normalize(root, *, hanbo_exit_verified=False):
    p=root/'reports/v221-benchmark-universe';old=root/'.cache/v221-real-close'
    if not old.exists():old=root/'reports/milestone-a-final-close'
    previous=json.loads((old/'historical_universe_component.json').read_text())
    upstream=json.loads((old/'universe_acquisition.json').read_text())
    audit=json.loads((p/'probe.json').read_text());records=[];errors=[]
    def add(sid,ex,listed,removed=None,historical=None,code_from=None,code_to=None,evidence=None):
        records.append(dict(security_id=sid,exchange=ex,security_type='A',listing_date=listed,
                            delisting_date=removed,historical_code=historical or sid.split('.')[0],
                            code_valid_from=code_from or listed,code_valid_to=code_to,evidence=evidence))
    for r in previous:
        if r['dataset']=='bj_active':continue
        add(r['security_id'],r['security_id'].split('.')[1],r['list_date'],r['delist_date'],evidence=r['dataset'])
    pages=sorted([r for r in audit if r['label'].startswith('sz_page_')],key=lambda r:int(r['label'].rsplit('_',1)[1]))
    rows=[];expected=next(r for r in audit if r['label']=='sz_fund_backend')['json'][0]['metadata']['recordcount']
    for page in pages:
        payload=(page.get('json') or [{}])[0]
        if not payload.get('data') or payload['metadata']['pageno']!=int(page['label'].rsplit('_',1)[1]):errors.append('sz_page_missing_or_wrong')
        rows.extend(payload.get('data',[]))
    if len(rows)!=expected or len({r['agdm'] for r in rows})!=expected:errors.append('sz_active_count_incomplete')
    for r in rows:
        if not re.fullmatch(r'(00|30)\d{4}',r['agdm']) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',r['agssrq']):errors.append('sz_code_or_listing_invalid');continue
        add(r['agdm']+'.SZ','SZ',r['agssrq'],evidence='official_sz_paginated_A_only')
    table=pd.read_html(StringIO((p/'bj_mapping.raw').read_text()))[0].iloc[1:-1].copy()
    table.columns=['sequence','name','listed','old','new'];mapping={r['new']:r for r in table.to_dict('records')}
    if len(mapping)!=248:errors.append('bj_mapping_incomplete')
    bj=next(r for r in upstream if r['dataset']=='bj_active')['rows']
    canonical={r['证券代码']:str(r['上市日期'])[:10] for r in bj}
    for code in ['920680','920305']:canonical[code]=str(pd.Timestamp(mapping[code]['listed']).date())
    pilots={'颖泰生物','艾融软件','龙竹科技','佳先股份','同享科技','球冠电缆'}
    pilot_text=html.fromstring((p/'bj_pilot_names.raw').read_text()).text_content()
    if not all(name in pilot_text for name in pilots):errors.append('bj_pilot_names_unverified')
    exits={'920680':'2026-01-05','920305':'2026-07-30'}
    for code,rawfn,pattern in [('920680','bj_guangdao_exit',r'2026\s*年\s*1\s*月\s*5\s*日'),('920305','bj_yunchuang_exit',r'2026\s*年\s*7\s*月\s*30\s*日')]:
        text=html.fromstring((p/(rawfn+'.raw')).read_bytes().decode('gb18030',errors='replace')).text_content()
        if not re.search(pattern,text):errors.append(code+'_exit_unverified')
    for code,listed in canonical.items():
        listed=max(listed,'2021-11-15');removed=exits.get(code);sid=code+'.BJ'
        if code in mapping:
            m=mapping[code];change='2025-05-06' if m['name'] in pilots else '2025-10-09'
            add(sid,'BJ',listed,removed,m['old'],listed,change,'official_bse_old_new_mapping')
            add(sid,'BJ',listed,removed,code,change,None,'official_bse_switch_notice')
        elif listed<'2024-04-22':errors.append(code+'_missing_historical_mapping')
        else:add(sid,'BJ',listed,removed,evidence='official_bse_new_920_listing')
    # Three terminated transfer securities remain eligible before their exit.
    for code,removed,fn in [('832317','2022-04-26','bj_guandian_exit'),('833874','2022-07-18','bj_taixiang_exit')]:
        text=html.fromstring((p/(fn+'.raw')).read_bytes().decode('gb18030',errors='replace')).text_content()
        yy,mm,dd=map(int,removed.split('-'))
        if not re.search(fr'{yy}\s*年\s*{mm}\s*月\s*{dd}\s*日',text):errors.append(code+'_transfer_exit_unverified')
        add(code+'.BJ','BJ','2021-11-15',removed,evidence=fn)
    add('833994.BJ','BJ','2021-11-15','2022-07-25',evidence='official_bse_hanbo_transfer_pdf')
    if not hanbo_exit_verified:errors.append('hanbo_transfer_exit_unverified')
    # Non-BSE listings cannot have contradictory duplicate event records.
    plain=[r for r in records if r['exchange']!='BJ'];ids=[r['security_id'] for r in plain]
    if len(ids)!=len(set(ids)):errors.append('sh_sz_listing_records_duplicate')
    cert={ex:{'complete_historical_ledger':not errors,'method':'official_active_plus_exits_and_code_intervals'} for ex in ['SH','SZ','BJ']}
    return records,cert,sorted(set(errors)),{'sz_active_rows':len(rows),'sz_active_expected':expected,'bj_mapping_rows':len(mapping),'bj_active_rows':len(bj)}
