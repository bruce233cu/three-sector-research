"""V2.2 §6: exact market windows, SQL percent_rank, nullable metrics."""
from __future__ import annotations
import math
from copy import deepcopy
import pandas as pd
from mainline.metrics.availability import DEFERRED_METRICS, AVAILABILITY_VERSION


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) else None


def sql_percent_rank(values, *, descending=False, minimum=1):
    """(SQL rank - 1)/(n - 1), ties share minimum rank; invalids stay NULL.

    RS ranks descending because frozen rules use <=20% for strongest objects.
    Own-history turnover ranks ascending, so high turnover has high percentile.
    """
    values = {k: number(v) for k, v in values.items()}
    valid = pd.Series({k: v for k, v in values.items() if v is not None}, dtype=float)
    if len(valid) < minimum:
        return {k: None for k in values}
    ranks = ((valid.rank(method='min', ascending=not descending)-1)/(len(valid)-1)
             if len(valid)>1 else pd.Series(0., index=valid.index))
    return {k: float(ranks[k]) if k in ranks else None for k in values}


def finalize_metrics(snapshot, history, market_dates):
    """Adds frozen non-circ_mv features without overwriting G1 core facts.

    history is a date-keyed, certified BOARD-level panel. No provider is invoked.
    Missing market days are explicit gaps, not stretched observation windows.
    """
    result = deepcopy(snapshot)
    day = str(snapshot['as_of_date'])
    dates = sorted(str(d) for d in market_dates if str(d)<=day)
    if len(dates)!=len(set(dates)) or not dates or dates[-1]!=day:
        raise ValueError('invalid market calendar')
    rows = {}
    for row in history:
        d = str(row['as_of_date'])
        if row['object_id'] != snapshot['object_id']:
            raise ValueError('mixed history objects')
        if d in rows:
            raise ValueError('duplicate board date')
        if row.get('taxonomy_version') != snapshot.get('taxonomy_version'):
            raise ValueError('mixed taxonomy versions')
        rows[d] = row
    rows[day] = snapshot
    coverage = dict(result.get('metric_coverage_json', {}))
    for window, minimum in [(5,4),(10,8)]:
        pairs = [(number(rows.get(d,{}).get('sector_return')),
                  number(rows.get(d,{}).get('benchmark_return'))) for d in dates[-window:]]
        pairs = [(a,b) for a,b in pairs if a is not None and b is not None]
        result['win_'+str(window)] = (sum(a>b for a,b in pairs)/len(pairs)
                                     if len(pairs)>=minimum else None)
        coverage['win_'+str(window)] = len(pairs)/window
    for window, minimum in [(60,40),(250,160)]:
        vals = {d: rows.get(d,{}).get('turnover_share') for d in dates[-window:]}
        valid = {d: number(v) for d,v in vals.items() if number(v) is not None}
        result['turnover_pct_'+str(window)] = sql_percent_rank(valid, minimum=minimum).get(day)
        coverage['turnover_pct_'+str(window)] = len(valid)/window
    for window in [3]:
        pairs = [(number(rows.get(d,{}).get('sector_return')),
                  number(rows.get(d,{}).get('benchmark_return'))) for d in dates[-window:]]
        pairs = [(a,b) for a,b in pairs if a is not None and b is not None]
        result['rs_'+str(window)] = (math.prod(1+a for a,b in pairs)-math.prod(1+b for a,b in pairs)
                                     if len(pairs)/window>=.90 else None)
        coverage['rs_'+str(window)] = len(pairs)/window
    shares = [number(rows.get(d,{}).get('turnover_share')) for d in dates[-20:]]
    result['turnover_share_mean20'] = sum(shares)/20 if len(shares)==20 and all(v is not None for v in shares) else None
    for field in ['above_ma20','above_ma60','new_high_60','top3_turnover_share']:
        result[field+'_lag3'] = (rows.get(dates[-4],{}).get(field) if len(dates)>=4 else None)
    # Frozen confirmation C explicitly says last THREE valid trading days.
    last_shares = [number(rows.get(d,{}).get('turnover_share')) for d in dates]
    last_shares = [v for v in last_shares if v is not None][-3:]
    result['turnover_not_three_valid_days_down'] = (not (last_shares[0]>last_shares[1]>last_shares[2])
                                                 if len(last_shares)==3 else None)
    for field in DEFERRED_METRICS:
        result[field] = None
    result['metric_availability_version'] = AVAILABILITY_VERSION
    result['metric_coverage_json'] = coverage
    return result


def add_cross_section(rows):
    """Group strictly by same date, taxonomy version AND object type."""
    result = deepcopy(rows)
    groups = {}
    for i,row in enumerate(result):
        key=(row['as_of_date'],row['taxonomy_version'],row['object_type'])
        groups.setdefault(key,[]).append(i)
    for indices in groups.values():
        ids=[result[i]['object_id'] for i in indices]
        if len(ids)!=len(set(ids)):
            raise ValueError('duplicate cross-section object')
        for w in [5,10,20]:
            vals={result[i]['object_id']: result[i].get('rs_'+str(w))
                  if result[i].get('critical_data_ok') and not result[i].get('stage_frozen') else None for i in indices}
            ranks=sql_percent_rank(vals,descending=True,minimum=10)
            count=sum(number(v) is not None for v in vals.values())
            for i in indices:
                result[i]['rs_'+str(w)+'_pct']=ranks[result[i]['object_id']]
                result[i].setdefault('metric_diagnostics',{})['rs_'+str(w)+'_pct']={
                    'valid_objects':count,'minimum_objects':10,'reason':None if count>=10 else 'cross_section_valid_objects_below_10'}
    return result


def metric_availability(snapshot, fields):
    frozen=not snapshot.get('critical_data_ok',False) or snapshot.get('stage_frozen',False)
    result={}
    for field in fields:
        value=snapshot.get(field)
        status=('deferred' if field in DEFERRED_METRICS else 'frozen' if frozen else
                'available' if value is not None and (isinstance(value,bool) or number(value) is not None) else 'unavailable')
        result[field]={'status':status,'value':None if status=='deferred' else value if isinstance(value,bool) else number(value),
                       'reason':'deferred_due_to_unproven_historical_circ_mv' if status=='deferred' else
                                snapshot.get('freeze_reason') if status=='frozen' else
                                'metric_missing_or_nonfinite' if status=='unavailable' else None}
    return result
