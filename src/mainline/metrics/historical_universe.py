"""Temporary event-interval resolver; no stock database or provider dependency."""
from dataclasses import dataclass
from datetime import date
import math
import pandas as pd

@dataclass(frozen=True)
class UniverseResolution:
    trade_date: date
    members: tuple[dict, ...]
    verified: bool
    summary: dict
    reasons: tuple[str, ...]

def historical_benchmark_universe_resolver(trade_date, records, *, certificate):
    """Records represent documented listing/code intervals, not current survivors.

    delisting_date is the first unlisted day. Code interval end is exclusive.
    certificate must explicitly certify active AND historical exit ledgers.
    A later fetch time is permitted for effective PIT; knowledge PIT is separate.
    """
    day=pd.Timestamp(trade_date).date()
    needed=['SH','SZ']+(['BJ'] if day>=date(2021,11,15) else [])
    reasons=[ex+'_historical_ledger_unverified' for ex in needed
             if not certificate.get(ex,{}).get('complete_historical_ledger',False)]
    excluded={k:set() for k in ['future_listing_excluded','already_delisted_excluded',
              'non_a_excluded','inactive_code_excluded','later_delisted_included']}
    members=[];seen=set()
    for r in records:
        ex=r.get('exchange');typ=r.get('security_type')
        if ex not in ['SH','SZ','BJ'] or typ!='A':excluded['non_a_excluded'].add(r['security_id']);continue
        try:
            listed=date.fromisoformat(r['listing_date'])
            removed=date.fromisoformat(r['delisting_date']) if r.get('delisting_date') else None
        except (ValueError,TypeError,KeyError):reasons.append('listing_interval_missing_or_invalid');continue
        if removed is not None and removed<=listed:reasons.append('listing_interval_conflict');continue
        if listed>day:excluded['future_listing_excluded'].add(r['security_id']);continue
        if removed is not None and removed<=day:excluded['already_delisted_excluded'].add(r['security_id']);continue
        if ex=='BJ' and listed<date(2021,11,15):reasons.append('bse_listing_date_is_pre_exchange');continue
        code=r.get('historical_code')
        if not code or not r.get('code_valid_from'):
            reasons.append('historical_code_interval_unverified');continue
        try:
            start=date.fromisoformat(r['code_valid_from'])
            end=date.fromisoformat(r['code_valid_to']) if r.get('code_valid_to') else None
        except ValueError:reasons.append('historical_code_interval_invalid');continue
        if start>day or (end is not None and day>=end):excluded['inactive_code_excluded'].add(r['security_id']);continue
        identity=r['security_id']
        if identity in seen:reasons.append('overlapping_security_code_intervals');continue
        seen.add(identity);members.append(dict(r,trade_date=str(day)))
        if removed is not None:excluded['later_delisted_included'].add(r['security_id'])
    counts={ex+'_count':sum(r['exchange']==ex for r in members) for ex in ['SH','SZ','BJ']}
    summary={'trade_date':str(day),'universe_count':len(members),**counts,**{k:len(v) for k,v in excluded.items()}}
    return UniverseResolution(day,tuple(sorted(members,key=lambda r:r['security_id'])),
                              not reasons and bool(members),summary,tuple(sorted(set(reasons))))

def exact_market_day_observations(resolution, bars, previous_market_date):
    """Two exact market-day closes; no forward fill or borrowed prior price."""
    prior=pd.Timestamp(previous_market_date).date();day=resolution.trade_date
    if prior>=day:raise ValueError('previous market date must precede target')
    b=bars.copy();b['trade_date']=pd.to_datetime(b.trade_date).dt.date
    if b.duplicated(['security_id','trade_date']).any():raise ValueError('duplicate security date')
    by={(r.security_id,r.trade_date):r for r in b.itertuples(index=False)}
    rows=[]
    for m in resolution.members:
        sid=m['security_id'];current=by.get((sid,day));old=by.get((sid,prior))
        amount=getattr(current,'amount',None);close=getattr(current,'close',None);pc=getattr(old,'close',None)
        finite=lambda v:v is not None and pd.notna(v) and math.isfinite(float(v)) and float(v)>0
        valid=prior>=date.fromisoformat(m['listing_date']) and finite(close) and finite(pc) and finite(amount)
        rows.append({'security_id':sid,'daily_return':float(close)/float(pc)-1 if valid else None,
                     'amount':float(amount) if finite(amount) else None})
    return pd.DataFrame(rows,columns=['security_id','daily_return','amount'])
