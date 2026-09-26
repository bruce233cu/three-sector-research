from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from .base import SqlExecutor


class SecurityRepository:
    def __init__(self, executor: SqlExecutor) -> None:
        self.executor = executor

    def universe_as_of(self, trade_date: date) -> Sequence[dict[str, Any]]:
        return self.executor.fetch_all(
            """
select security_id, ts_code, name, exchange, list_date, delist_date, is_st
from mainline.security_master
where list_date <= %(trade_date)s
  and (delist_date is null or delist_date >= %(trade_date)s)
order by security_id
""".strip(),
            {"trade_date": trade_date},
        )
