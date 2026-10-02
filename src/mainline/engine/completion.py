"""User-approved V2.2.1 state completion; pure, market-date/PIT safe features."""
from copy import deepcopy
from statistics import median
from .metrics import number, sql_percent_rank

BREADTH = ('up_ratio', 'above_ma20', 'above_ma60', 'new_high_60')
CLARIFICATION = 'V2.2.1-mainline-state-completion-2026-10-02'


def ols_slope(values, minimum=4):
    # Preserve the original market-day positions when observations are missing.
    points = [(x, number(y)) for x, y in enumerate(values)]
    points = [(x, y) for x, y in points if y is not None]
    if len(values) != 5 or len(points) < minimum:
        return None
    xm = sum(x for x, y in points) / len(points)
    ym = sum(y for x, y in points) / len(points)
    return sum((x-xm)*(y-ym) for x, y in points) / sum((x-xm)**2 for x, y in points)


def completion_features(snapshot, history, market_dates):
    result = deepcopy(snapshot)
    day = str(snapshot['as_of_date'])
    dates = [str(d) for d in market_dates]
    if dates != sorted(set(dates)) or day not in dates:
        raise ValueError('invalid market calendar')
    dates = dates[:dates.index(day)+1]
    rows = {}
    for r in history:
        if (r['object_id'], r['taxonomy_version']) != (snapshot['object_id'], snapshot['taxonomy_version']):
            raise ValueError('mixed history object/taxonomy')
        d = str(r['as_of_date'])
        if d in rows:
            raise ValueError('duplicate history date')
        rows[d] = r
    rows[day] = snapshot
    def window(field, n):
        return [number(rows.get(d, {}).get(field)) for d in dates[-n:]]
    rs5 = window('rs_5', 5)
    result['rs5_slope'] = ols_slope(rs5)
    p = window('rs_10_pct', 3)
    # Exact adjacent sessions. NULL does not skip a market day.
    result['rs10_percentile_deteriorating'] = (p[2] > p[1] > p[0]
        if len(p) == 3 and all(v is not None for v in p) else None)
    medians = {}
    for f in BREADTH:
        result[f+'_lag3'] = number(rows.get(dates[-4], {}).get(f)) if len(dates) >= 4 else None
        # Last 20 valid observations among past/current market dates, never future.
        vals = [number(rows.get(d, {}).get(f)) for d in dates]
        vals = [v for v in vals if v is not None][-20:]
        result[f+'_median20'] = median(vals) if len(vals) == 20 else None
        medians[f] = len(vals)
    vals = {d: rows.get(d, {}).get('top3_turnover_share') for d in dates[-250:]}
    result['top3_turnover_pct_250'] = sql_percent_rank(vals, minimum=160).get(day)
    result['e4_high_percentile'] = (result['top3_turnover_pct_250'] >= .90
                                  if result['top3_turnover_pct_250'] is not None else None)
    result['clarification_version'] = CLARIFICATION
    result.setdefault('metric_diagnostics', {}).update({
        'rs5_slope': {'window':5, 'minimum_valid':4, 'valid':sum(v is not None for v in rs5)},
        'breadth_median20': {'valid_observations':medians},
        'top3_turnover_pct_250': {'window':250, 'minimum_valid':160,
            'valid':sum(number(v) is not None for v in vals.values())}})
    return result
