from __future__ import annotations

from datetime import date, datetime
from typing import Any, Sequence

from .base import SqlExecutor


def pit_membership_sql() -> str:
    return """
select mh.security_id, td.taxonomy_code, mh.effective_from, mh.effective_to,
       mh.available_at, mh.source_version, mh.source_snapshot_id
from mainline.membership_history mh
join mainline.taxonomy_definitions td on td.taxonomy_id = mh.taxonomy_id
where td.taxonomy_code = %(taxonomy_code)s
  and mh.effective_from <= %(trade_date)s
  and (mh.effective_to is null or mh.effective_to >= %(trade_date)s)
  and mh.available_at <= %(calculation_cutoff)s
order by mh.security_id
""".strip()


class MembershipRepository:
    def __init__(self, executor: SqlExecutor) -> None:
        self.executor = executor

    def members_as_of(
        self,
        taxonomy_code: str,
        trade_date: date,
        calculation_cutoff: datetime,
    ) -> Sequence[dict[str, Any]]:
        return self.executor.fetch_all(pit_membership_sql(), {
            "taxonomy_code": taxonomy_code,
            "trade_date": trade_date,
            "calculation_cutoff": calculation_cutoff,
        })
