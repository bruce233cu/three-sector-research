"""Trust only complete compatible DB checkpoints; never silently reset state."""
from dataclasses import fields
from mainline.engine.state_machine import Checkpoint

def select_seed(context, profile, target, *, bootstrap=None):
    items=context.get('checkpoints') or []
    if not items:
        if bootstrap is None:raise ValueError('checkpoint_incompatible: explicit bootstrap required')
        return {**bootstrap,'bootstrap_source':'g3_certification'}
    day=context.get('seed_date')
    expected=('SW2021',profile['rule_version'],profile['profile_id'],profile['metric_availability_version'])
    cps={}
    for row in items:
        cp=row['checkpoint']
        if (row['taxonomy_version'],row['rule_version'],row['profile_id'],cp.get('metric_availability_version'))!=expected:
            raise ValueError('checkpoint_incompatible: version identity')
        if cp.get('object_id')!=row['object_id'] or cp.get('last_date')!=day or row['trade_date']!=day or day>=target:
            raise ValueError('checkpoint_incompatible: object/date')
        if cp.get('rule_version')!=expected[1] or cp.get('parameter_profile')!=expected[2] or cp.get('state') not in {'S0','S1','S2','S3','S4'}:
            raise ValueError('checkpoint_incompatible: state/version')
        if not isinstance(cp.get('state_days'),int) or cp['state_days']<0 or not isinstance(cp.get('consecutive'),dict):
            raise ValueError('checkpoint_incompatible: damaged counters')
        if any(not isinstance(v,int) or v<0 for v in cp['consecutive'].values()):raise ValueError('checkpoint_incompatible: damaged consecutive')
        Checkpoint(**cp)
        if row['object_id'] in cps:raise ValueError('checkpoint_incompatible: duplicate object')
        cps[row['object_id']]=cp
    if len(cps)!=31:raise ValueError('checkpoint_incompatible: incomplete SW1')
    if day not in context['calendar'] or target not in context['calendar']:raise ValueError('unverified market date')
    warm=context.get('warm_history') or []
    if len({r['as_of_date'] for r in warm})<250:raise ValueError('checkpoint_history_insufficient: 250 board sessions required')
    if any(r['as_of_date']>day or r['taxonomy_version']!='SW2021' or r['rule_version']!=expected[1] or r['metric_availability_version']!=expected[3] for r in warm):
        raise ValueError('checkpoint_incompatible: warm history')
    return {'date':day,'checkpoints':cps,'bootstrap_source':'database_checkpoint'}
