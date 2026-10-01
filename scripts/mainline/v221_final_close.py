"""Isolated final gate. No production/Daily Pipeline writes or schema changes.

Never promote legacy aggregate metrics into a new rule version. If normalized
certified stock/universe inputs are absent, persist explicit frozen results.
"""
from pathlib import Path
import sys, json, hashlib, os, subprocess
from datetime import date, datetime, timezone
from uuid import uuid4
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from mainline.metrics.sector import SectorMetricInput
from mainline.metrics.benchmark import calculate_benchmark_day, calculate_v221_with_benchmark

OUT = ROOT / "reports/milestone-a-fast-close/v221-final"
OUT.mkdir(parents=True, exist_ok=True)
DATES = ['2019-06-28','2020-06-30','2021-12-31','2023-06-30','2025-06-30']
SAMPLES = [(DATES[0],c) for c in ['801080','801120','801790']] + [(DATES[1],c) for c in ['801050','801120','801790']] + [(DATES[2],c) for c in ['801080','801780','801890']] + [(DATES[3],c) for c in ['801050','801120','801890']] + [(DATES[4],c) for c in ['801080','801780','801890']]

def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
def write(name,x): (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def acquire_existing_historical_universe():
    """One bounded acquisition through the existing Baostock backup; no tests.

    Its output is acquisition evidence, NOT certified complete all-A data. In
    particular SH/SZ-only histories cannot certify all-A after BSE inception.
    No listing/delisting/code-history facts are invented from present-day lists.
    """
    program = '''import baostock as bs,json
r=bs.login()
output={'login_code':r.error_code,'provider':'baostock','days':[]}
if r.error_code=='0':
 for day in ['2019-06-28','2020-06-30','2021-12-31','2023-06-30','2025-06-30']:
  q=bs.query_all_stock(day=day); rows=[]
  while q.error_code=='0' and q.next(): rows.append(q.get_row_data())
  output['days'].append({'date':day,'fields':q.fields,'rows':rows,'error_code':q.error_code,'error_msg':q.error_msg})
 bs.logout()
print('FINAL_UNIVERSE_JSON='+json.dumps(output,ensure_ascii=False))'''
    started=datetime.now(timezone.utc).isoformat()
    try:
        r=subprocess.run([sys.executable,'-c',program],capture_output=True,text=True,timeout=50)
        marker='FINAL_UNIVERSE_JSON='
        payload=json.loads(r.stdout.split(marker)[-1]) if marker in r.stdout else None
        evidence={'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
                  'exit_code':r.returncode,'payload':payload,'stdout':r.stdout[-2000:],
                  'stderr':r.stderr[-2000:],'complete_all_a_certified':False,
                  'certification_reason':'missing historical listing/delisting/security-type and complete exchange evidence'}
    except subprocess.TimeoutExpired as e:
        evidence={'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
                  'status':'timeout_50_seconds','complete_all_a_certified':False,
                  'stdout':str(e.stdout or '')[-1000:],'stderr':str(e.stderr or '')[-1000:]}
    write('universe_acquisition.json',evidence)
    return evidence

def main():
    acquisition=acquire_existing_historical_universe()
    membership_path=ROOT/'reports/phase1d/final-v2/membership_evidence.json'
    membership=json.loads(membership_path.read_text())
    calendar=[date.fromisoformat(d) for d in json.loads((ROOT/'reports/milestone-a-fast-close/calendar_input.json').read_text())]
    empty_universe=pd.DataFrame(columns=['security_id','share_type','list_date','delist_date'])
    empty_obs=pd.DataFrame(columns=['security_id','daily_return','amount'])
    empty_bars=pd.DataFrame(columns=['security_id','trade_date','close','amount','pct_chg'])
    run_id=str(uuid4()); recompute_id=str(uuid4())
    params={'benchmark':'ALL_A_EQUAL_WEIGHT','benchmark_daily_coverage':.95,
            'rs_window_coverage':.9,'sector_internal_coverage':.7,
            'circ_mv':'deferred','calendar':'existing_supabase_SSE','stock_input':'absent'}
    snapshots=[]; repeated=[]; sources=[]; checks=[]
    for target,code in SAMPLES:
        d=date.fromisoformat(target)
        members=[r for r in membership if r['snapshot_date']==target and r['taxonomy_code']==code]
        members=sorted(members,key=lambda r:r['security_id'])
        pit=all(r['effective_from']<=target and (not r['effective_to'] or r['effective_to']>=target) for r in members)
        sid=str(uuid4())
        sources.append({'source_snapshot_id':sid,'source_id':'sws_official_cached_membership_evidence',
                        'dataset_code':'membership_snapshot','source_version':'pinned-github-52da934:normalized-membership',
                        'fetched_at':datetime.now(timezone.utc).isoformat(),'available_at':None,
                        'response_checksum':digest(members),'row_count':len(members),
                        'raw_location':'github://bruce233cu/three-sector-research/52da9346398e4513d4fe0b85ec19030b2c76421e/reports/phase1d/final-v2/membership_evidence.json',
                        'historical_capability':'historical_partial',
                        'metadata':{'sample_id':target+':'+code,'evidence_grade':'normalized_immutable_artifact',
                                    'pit_level':'effective_pit','knowledge_time_unverified':True,
                                    'upstream_http_payload_reverified':False,'run_id':run_id,
                                    'code_commit':os.getenv('GITHUB_SHA'),'parameter_hash':digest(params)}})
        days=[calculate_benchmark_day(day,empty_universe,empty_obs,universe_verified=False,
                                      returns_verified=False) for day in calendar if day<=d]
        value=SectorMetricInput(d,'sw1_'+code,code,'SW2021' if d>=date(2021,12,13) else 'SW2014',
                                 tuple(r['security_id'] for r in members),empty_bars,pd.Series(dtype=float),
                                 market_trading_dates=tuple(day for day in calendar if day<=d))
        result=calculate_v221_with_benchmark(value,days)
        again=calculate_v221_with_benchmark(value,days)
        checks.append({'date':target,'code':code,'membership_rows':len(members),'effective_membership_pit':pit,
                       'repeat_identical':canonical(result)==canonical(again),
                       'input_complete':False,'benchmark_source_complete':False,'stock_rows':0,
                       'coverage':result['metric_coverage_json'],'freeze_reason':result['freeze_reason'],
                       'output_checksum':digest(result),'recompute_checksum':digest(again)})
        result['decision_reason'].update({'input_status':'blocked_missing_historical_all_a_universe_and_stock_window',
                                          'source_lineage_complete':False,'membership_effective_pit':pit,
                                          'code_commit':os.getenv('GITHUB_SHA'),'parameter_hash':digest(params),
                                          'recompute_run_id':recompute_id,'repeat_checksum':digest(again),
                                          'benchmark_coverage':None,'snapshot_status':'FORMAL_FROZEN_DATA_UNAVAILABLE'})
        result.update(source_snapshot_ids=[sid,'243f49a9-32cb-4b72-8205-d91b03498625'],
                      source_snapshot_id=sid,run_id=run_id,recompute_run_id=recompute_id,
                      pit_level='effective_pit',knowledge_time_unverified=True,cache_checksum=digest(result))
        # Optional metadata keys are nested; core schema remains unchanged.
        for key in ['parameter_profile','metric_availability_version','circ_mv_status']: result.pop(key,None)
        snapshots.append(result)
    result={'G1':'FAIL','READY_FOR_PRODUCTION_ENABLEMENT':False,'sample_count':len(snapshots),
            'formal_frozen_count':sum(s['stage_frozen'] for s in snapshots),
            'repeatability_check_passed':all(c['repeat_identical'] for c in checks),
            'real_data_repeatability_accepted':False,'membership_effective_pit_checks':sum(c['effective_membership_pit'] for c in checks),
            'benchmark_coverage_certified_samples':0,'complete_new_source_chains':0,
            'blocking_issues':['Historical ALL_A universe and valid individual return/amount windows are absent or uncertified.',
                               'No complete stock+ALL_A source chain exists for the 15 new formal snapshots.'],
            'run_id':run_id,'recompute_run_id':recompute_id,'code_commit':os.getenv('GITHUB_SHA'),
            'parameter_hash':digest(params),'parameters':params}
    write('snapshots.json',snapshots);write('source_snapshots.json',sources)
    write('checks.json',checks);write('gate.json',result)
    print(canonical(result))

if __name__=='__main__': main()
