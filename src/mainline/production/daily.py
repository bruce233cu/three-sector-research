"""Daily orchestration around the already-certified pure functions.

Persisted checkpoints are immutable per date. Backfill chooses a checkpoint
strictly before the target, never the latest checkpoint irrespective of date.
"""
from copy import deepcopy
from collections import defaultdict
from dataclasses import asdict
from mainline.engine.metrics import finalize_metrics,add_cross_section
from mainline.engine.completion import completion_features
from mainline.engine.rules import evaluate_rules
from mainline.engine.state_machine import Checkpoint,advance
from mainline.engine.replay import digest


def evolve(panel,dates,profile,resolver,warm,seed):
    history=defaultdict(list);daily=defaultdict(list)
    for row in warm:history[(row['object_id'],row['taxonomy_version'])].append(deepcopy(row))
    checkpoints={k:Checkpoint(**deepcopy(v)) for k,v in seed['checkpoints'].items()}
    for row in panel:daily[row['as_of_date']].append(deepcopy(row))
    rows=[];cross=[]
    for day in sorted(daily):
        member=resolver(day);group=daily[day]
        if member['trade_date']!=day or member.get('complete') is not True:
            raise ValueError('daily membership unavailable')
        if set(member['members'])!={r['object_id'] for r in group}:
            raise ValueError('incomplete daily taxonomy')
        for r in group:
            if r['membership_checksum']!=member['checksums'][r['object_id']]:
                raise ValueError('membership checksum mismatch')
        prepared=add_cross_section([finalize_metrics(r,history[(r['object_id'],r['taxonomy_version'])],dates) for r in group])
        n=sum(r['rs_10_pct'] is not None for r in prepared)
        cross.append({'trade_date':day,'taxonomy_version':member['taxonomy_version'],'valid_ranked_objects':n})
        for r in prepared:
            # Insufficient cross-section freezes production rather than inventing ranks.
            if n<10:r.update(critical_data_ok=False,stage_frozen=True,freeze_reason='cross_section_valid_objects_below_10')
            key=(r['object_id'],r['taxonomy_version'])
            cp=checkpoints.get(r['object_id'])
            if cp is None:raise ValueError('trusted previous checkpoint missing:'+r['object_id'])
            r=completion_features(r,history[key],dates);evaluation=evaluate_rules(r,profile)
            state,cp=advance(cp,r,evaluation,profile,dates)
            checkpoints[r['object_id']]=cp
            rows.append({'snapshot':r,'rules':evaluation['rules'],'state':state})
            history[key].append(r)
    return {'rows':rows,'cross_sections':cross,'seed':'trusted_checkpoint:'+seed['date'],
            'events':[r['state']['transition'] for r in rows if r['state']['transition']]}


def business_payload(row):
    """Run IDs and pointer IDs vary per attempt; business facts do not."""
    def clean(v):
        if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k not in {'run_id','source_snapshot_ids'}}
        if isinstance(v,list):return [clean(x) for x in v]
        return v
    return clean(row)


def day_checksum(rows):
    return digest([business_payload(r) for r in sorted(rows,key=lambda r:r['snapshot']['object_id'])])


class AtomicMemoryStore:
    """Fault-injection contract double; not a source of historical observations."""
    def __init__(self):self.days={};self.attempts=[]
    def commit(self,day,rows,*,fail_at=None):
        checksum=day_checksum(rows);before=deepcopy(self.days)
        self.attempts.append({'date':day,'checksum':checksum})
        if day in self.days:
            if self.days[day]['checksum']!=checksum:raise ValueError('conflicting same-day business input')
            return 'idempotent'
        if fail_at in {'provider','metrics','state','db'}:
            assert self.days==before
            raise RuntimeError('injected_'+fail_at)
        self.days[day]={'checksum':checksum,'rows':deepcopy(rows)}
        return 'committed'
