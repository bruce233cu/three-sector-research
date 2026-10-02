"""Certified daily BOARD inputs only. No synthetic data accepted as history."""
import hashlib
import json
from collections import defaultdict
from .metrics import finalize_metrics, add_cross_section
from .completion import completion_features
from .rules import evaluate_rules
from .state_machine import Checkpoint, advance


def verified_freeze_gap(proof, gap, cp):
    if not gap or len(proof) != len(gap):
        return False
    if [p.get('trade_date') for p in proof] != gap:
        return False
    required={'S0':['candidate'],'S1':['candidate','confirm'],'S2':['weaken'],
              'S3':['retire','recover'],'S4':['candidate']}.get(cp.state,[])
    for p in proof:
        if (p.get('object_id'),p.get('rule_version'),p.get('parameter_profile')) != (
                cp.object_id,cp.rule_version,cp.parameter_profile):
            return False
        if p.get('critical_data_ok') is not True or p.get('stage_frozen') is not False:
            return False
        if not p.get('source_snapshot_ids') or p.get('checksum') != digest({k:v for k,v in p.items() if k!='checksum'}):
            return False
        e=p.get('evidence',{})
        if any(type(e.get(k)) is not bool for k in required):
            return False
        # Continuity must really be verifiable, not just a repaired numeric row.
        for k,n in cp.consecutive.items():
            if n>0 and e.get(k) is not True:
                return False
    return True


def replay(panel, market_dates, profile, membership_resolver):
    """Resolver is called for every day, including frozen days; fail closed.

    It returns a certified daily mapping object_id -> member IDs with versions
    and source IDs. No target-date/static-membership fallback is permitted.
    Seed S0 only at each object's first appearance in this replay window.
    """
    dates=[str(d) for d in market_dates]
    if dates != sorted(set(dates)):
        raise ValueError('invalid market calendar')
    daily=defaultdict(list)
    for r in panel:
        if r.get('evidence_kind') != 'real_historical_board':
            raise ValueError('uncertified/synthetic panel')
        daily[str(r['as_of_date'])].append(dict(r))
    if not daily or any(d not in dates for d in daily):
        raise ValueError('invalid board dates')
    first,last=min(daily),max(daily)
    history=defaultdict(list);checkpoints={};outputs=[];counts=[]
    for day in dates[dates.index(first):dates.index(last)+1]:
        member=membership_resolver(day)
        if member.get('trade_date') != day or member.get('complete') is not True:
            raise ValueError('daily membership incomplete: '+day)
        rows=daily.get(day,[])
        if {r['object_id'] for r in rows} != set(member['members']):
            raise ValueError('board panel does not cover resolved daily taxonomy: '+day)
        for r in rows:
            oid=r['object_id']
            if not member.get('source_snapshot_ids') or not member['members'][oid]:
                raise ValueError('membership source/member missing')
            if r['taxonomy_version'] != member['taxonomy_version']:
                raise ValueError('membership taxonomy mismatch')
            if r.get('membership_checksum') != member['checksums'][oid]:
                raise ValueError('board metric/membership checksum mismatch')
            r.update(rule_version=profile['rule_version'],
                     metric_availability_version=profile['metric_availability_version'])
        rows=[finalize_metrics(r,history[(r['object_id'],r['taxonomy_version'])],dates) for r in rows]
        ranked=add_cross_section(rows)
        groups=defaultdict(list)
        for r in ranked: groups[(r['taxonomy_version'],r['object_type'])].append(r)
        for key, group in groups.items():
            n=sum(r.get('rs_10_pct') is not None for r in group)
            counts.append({'trade_date':day,'taxonomy_version':key[0],'valid_ranked_objects':n})
            if n<10:
                raise ValueError('cross_section_valid_objects_below_10: '+day)
        for r in ranked:
            key=(r['object_id'],r['taxonomy_version'])
            r=completion_features(r,history[key],dates)
            evaluation=evaluate_rules(r,profile)
            if key not in checkpoints:
                checkpoints[key]=Checkpoint(r['object_id'],profile['rule_version'],profile['profile_id'],
                                            profile['metric_availability_version'],state='S0')
            output,checkpoints[key]=advance(checkpoints[key],r,evaluation,profile,dates)
            outputs.append({'snapshot':r,'rules':evaluation['rules'],'state':output})
            history[key].append(r)
    return {'rows':outputs,'cross_sections':counts,'seed':'S0',
            'events':[o['state']['transition'] for o in outputs if o['state']['transition']]}


def digest(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
