"""Offline acceptance safeguards over the real D1.2 evidence; no network."""
import hashlib,json,sys
from pathlib import Path

def verify(root):
 root=Path(root)
 read=lambda name:json.loads((root/name).read_text())
 checks=read('checksums.json')
 assert all(hashlib.sha256((root/n).read_bytes()).hexdigest()==h for n,h in checks.items()),'checksum mismatch'
 rows=read('validation.json');plan=read('sample_plan.json');sources=read('source_manifest.json')
 assert len(plan)==12 and len(rows)==36 and len(sources)==72
 assert len({(x['security_id'],x['target_date']) for x in rows})==36
 assert all(x['float_shares'] is None and x['circ_mv'] is None and x['effective_date'] is None for x in rows)
 assert all(x['source_date']<=x['target_date'] and x['cninfo_source_date']<=x['target_date'] for x in rows)
 assert all(x['pit_level']=='unproven' and x['knowledge_time_unverified'] for x in rows)
 for x in rows:
  assert abs(x['candidate_sina_circ_mv']-x['candidate_sina_shares']*x['close'])<1e-5
  assert abs(x['candidate_cninfo_circ_mv']-x['candidate_cninfo_shares']*x['close'])<1e-5
 assert all(x['both_ok'] and x['identical'] for x in read('repeatability.json'))
 conflict=next(x for x in rows if x['security_id']=='600183.SH' and x['target_date']=='2019-06-28')
 assert abs(conflict['difference_pct']-2.649218010312914)<1e-8
 assert conflict['validation_status']=='UNACCEPTED_EVENT_SEQUENCE' and not conflict['resolved']
 s=read('summary.json')
 assert s['accepted_count']==0 and s['sector_retest']=='NOT_RUN_SPECIALIST_GATE_NOT_PASSED'
 assert not s['production_writes'] and not s['mainline_job_enabled']
 return {'status':'OFFLINE_EVIDENCE_CHECK_PASS','checks':['file_checksums','12x3_samples','72_source_fetches',
  'candidate_date_boundary','unit_multiplication','no_unaccepted_asof_output','two_rounds',
  '600183_conflict_retained','sector_gate_not_bypassed','no_production_flags']}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1])))
