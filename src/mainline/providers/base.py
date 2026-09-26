from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

import pandas as pd


class Dataset(StrEnum):
    TRADING_CALENDAR = "trading_calendar"
    SECURITY_MASTER = "security_master"
    DAILY_BARS = "daily_bars"
    DAILY_VALUATION = "daily_valuation"
    TAXONOMIES = "taxonomies"
    MEMBERSHIP_HISTORY = "membership_history"
    INDEX_DAILY = "index_daily"


REQUIRED_COLUMNS: dict[Dataset, tuple[str, ...]] = {
    Dataset.TRADING_CALENDAR: ("exchange", "cal_date", "is_open", "pretrade_date"),
    Dataset.SECURITY_MASTER: ("security_id", "ts_code", "name", "exchange", "list_date", "delist_date"),
    Dataset.DAILY_BARS: ("security_id", "trade_date", "open", "high", "low", "close", "volume", "amount", "pct_chg"),
    Dataset.DAILY_VALUATION: ("security_id", "trade_date", "circ_mv", "total_mv", "turnover_rate"),
    Dataset.TAXONOMIES: ("taxonomy_type", "taxonomy_code", "taxonomy_name", "taxonomy_version", "effective_from"),
    Dataset.MEMBERSHIP_HISTORY: ("security_id", "taxonomy_code", "effective_from", "effective_to"),
    Dataset.INDEX_DAILY: ("index_id", "trade_date", "open", "high", "low", "close", "volume", "amount"),
}


class ProviderError(RuntimeError):
    code = "PROVIDER_ERROR"


class ProviderTimeout(ProviderError):
    code = "PROVIDER_TIMEOUT"


class ProviderSchemaError(ProviderError):
    code = "PROVIDER_SCHEMA_ERROR"


class EmptyDatasetError(ProviderError):
    code = "EMPTY_DATASET"


class CapabilityUnavailable(ProviderError):
    code = "CAPABILITY_UNAVAILABLE"


@dataclass(frozen=True)
class ProviderBatch:
    dataset: Dataset
    frame: pd.DataFrame
    source_id: str
    source_version: str
    fetched_at: datetime
    available_at: datetime | None
    run_id: UUID
    request_fingerprint: str
    historical_capability: str

    def validate(self, *, require_rows: bool = True) -> "ProviderBatch":
        missing = [name for name in REQUIRED_COLUMNS[self.dataset] if name not in self.frame.columns]
        if missing:
            raise ProviderSchemaError(f"{self.dataset}: missing columns {','.join(missing)}")
        if require_rows and self.frame.empty:
            raise EmptyDatasetError(f"{self.dataset}: provider returned no rows")
        if not self.source_version:
            raise ProviderSchemaError(f"{self.dataset}: source_version is required")
        if self.fetched_at.tzinfo is None:
            raise ProviderSchemaError(f"{self.dataset}: fetched_at must be timezone aware")
        return self


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_batch(
    dataset: Dataset,
    frame: pd.DataFrame,
    *,
    source_id: str,
    source_version: str,
    request_fingerprint: str,
    historical_capability: str,
    available_at: datetime | None = None,
    run_id: UUID | None = None,
) -> ProviderBatch:
    return ProviderBatch(
        dataset=dataset,
        frame=frame,
        source_id=source_id,
        source_version=source_version,
        fetched_at=utc_now(),
        available_at=available_at,
        run_id=run_id or uuid4(),
        request_fingerprint=request_fingerprint,
        historical_capability=historical_capability,
    ).validate()


class MarketDataProvider(Protocol):
    name: str
    source_id: str

    def get_trading_calendar(self, start_date: str, end_date: str) -> ProviderBatch: ...
    def get_security_master(self, as_of_date: str | None = None) -> ProviderBatch: ...
    def get_daily_bars(self, trade_date: str, security_ids: list[str] | None = None) -> ProviderBatch: ...
    def get_daily_valuation(self, trade_date: str, security_ids: list[str] | None = None) -> ProviderBatch: ...
    def get_taxonomies(self, taxonomy_type: str, as_of_date: str | None = None) -> ProviderBatch: ...
    def get_membership_history(self, taxonomy_type: str, start_date: str, end_date: str) -> ProviderBatch: ...
    def get_index_daily(self, index_id: str, start_date: str, end_date: str) -> ProviderBatch: ...
