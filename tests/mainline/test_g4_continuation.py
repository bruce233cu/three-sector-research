"""One real continuation session; no providers and no production writes."""
import json,os,copy
from pathlib import Path
import pytest
from mainline.production.checkpoints import select_seed
from mainline.production.daily import evolve,business_payload,day_checksum
ROOT=Path(__file__).resolve().parents[2]
profile=json.loads((ROOT/'config/parameter_profile_industry_trend_v221_state_completion_v1.json').read_text())

def inputs():
 path=os.environ.get('MAINLINE_G4_DB_CONTEXT')
 if not path:pytest.skip('requires actual DB context exported by G4 acceptance')
 return json.loads(Path(path).read_text())

def test_database_real_continuation_and_rerun():
 context=inputs();target='2026-09-30';seed=select_seed(context,profile,target)
 assert seed['bootstrap_source']=='database_checkpoint' and seed['date']=='2026-09-29'
 source=json.loads(Path(os.environ['MAINLINE_G4_REAL_STATES']).read_text())
 expected=[r for r in source if r['snapshot']['as_of_date']==target]
 assert len(expected)==31
 group=[r['snapshot'] for r in expected]
 members={'trade_date':target,'taxonomy_version':'SW2021','complete':True,'members':{r['object_id']:[] for r in group},'checksums':{r['object_id']:r['membership_checksum'] for r in group}}
 resolver=lambda d: members
 before=copy.deepcopy(seed)
 a=evolve(group,context['calendar'],profile,resolver,context['warm_history'],seed)
 b=evolve(group,context['calendar'],profile,resolver,context['warm_history'],seed)
 assert seed==before
 assert day_checksum(a['rows'])==day_checksum(b['rows'])
 for got,original in zip(sorted(a['rows'],key=lambda x:x['snapshot']['object_id']), sorted(expected,key=lambda x:x['snapshot']['object_id'])):
  assert business_payload(got)==business_payload(original),got['snapshot']['object_id']

@pytest.mark.parametrize('field,value',[('metric_availability_version','wrong'),('rule_version','wrong'),('parameter_profile','wrong'),('state_days',-1),('consecutive',{'confirm':-1})])
def test_incompatible_checkpoint_rejected(field,value):
 c=inputs();c['checkpoints'][0]['checkpoint'][field]=value
 with pytest.raises(ValueError,match='checkpoint_incompatible'):select_seed(c,profile,'2026-09-30')

def test_incomplete_checkpoint_rejected():
 c=inputs();c['checkpoints'].pop()
 with pytest.raises(ValueError,match='incomplete'):select_seed(c,profile,'2026-09-30')

def test_future_history_rejected():
 c=inputs();c['warm_history'][0]['as_of_date']='2026-09-30'
 with pytest.raises(ValueError,match='warm history'):select_seed(c,profile,'2026-09-30')

def test_bootstrap_only_explicit():
 c=inputs();c['checkpoints']=[]
 with pytest.raises(ValueError,match='explicit bootstrap'):select_seed(c,profile,'2026-09-30')
 assert select_seed(c,profile,'2026-09-30',bootstrap={'date':'2025-06-30','checkpoints':{}})['bootstrap_source']=='g3_certification'
