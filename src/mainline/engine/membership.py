"""Temporary daily historical SW1 resolver; no permanent stock database.

Completeness must be certified by the source adapter. A fixed-date snapshot is
never expanded into an interval ledger by this resolver.
"""
from .replay import digest


class HistoricalMembershipResolver:
    def __init__(self, ledger, taxonomy, certificate):
        self.ledger=ledger
        self.taxonomy=taxonomy
        self.certificate=certificate
        self.calls=[]

    def __call__(self, trade_date):
        self.calls.append(trade_date)
        cert=self.certificate
        if (cert.get('scope') != 'complete_effective_interval_ledger' or
            not cert.get('source_snapshot_ids') or
            not (cert.get('valid_from','9999')<=trade_date<=cert.get('valid_to','0000'))):
            raise ValueError('complete daily membership certificate unavailable')
        definitions=[t for t in self.taxonomy if t['effective_from']<=trade_date and
                     (t.get('effective_to') is None or trade_date<=t['effective_to'])]
        versions={t['taxonomy_version'] for t in definitions}
        if len(versions)!=1 or len({t['object_id'] for t in definitions})!=len(definitions):
            raise ValueError('invalid daily historical taxonomy')
        version=next(iter(versions));members={t['object_id']:[] for t in definitions}
        active=set()
        for m in self.ledger:
            if m['effective_from']<=trade_date and (m.get('effective_to') is None or trade_date<=m['effective_to']):
                if m['taxonomy_version']!=version:
                    continue
                key=m['security_id']
                if key in active:
                    raise ValueError('overlapping member intervals')
                active.add(key)
                if m['object_id'] not in members:
                    raise ValueError('member taxonomy not effective')
                members[m['object_id']].append(key)
        if any(not ids for ids in members.values()):
            raise ValueError('empty industry membership')
        members={oid:sorted(ids) for oid,ids in members.items()}
        return {'trade_date':trade_date,'taxonomy_version':version,'complete':True,
                'members':members,'checksums':{oid:digest({'trade_date':trade_date,'taxonomy_version':version,
                    'object_id':oid,'members':ids}) for oid,ids in members.items()},
                'source_snapshot_ids':cert['source_snapshot_ids']}
