from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pandas as pd

from .base import CapabilityUnavailable, Dataset, ProviderBatch, ProviderError, build_batch


class AkshareProvider:
    name = "AKShare"
    source_id = "akshare"

    def __init__(self) -> None:
        try:
            import akshare as ak
        except ImportError as error:
            raise CapabilityUnavailable("akshare package is not installed") from error
        self.ak = ak
        self.version = getattr(ak, "__version__", "unknown")

    def _batch(self, dataset: Dataset, frame: pd.DataFrame, method: str, params: dict, capability: str = "historical_full") -> ProviderBatch:
        fingerprint = hashlib.sha256(json.dumps({"method": method, "params": params}, sort_keys=True).encode()).hexdigest()
        return build_batch(dataset, frame, source_id=self.source_id, source_version=f"akshare:{self.version}:{method}", request_fingerprint=fingerprint, historical_capability=capability)

    def get_trading_calendar(self, start_date: str, end_date: str) -> ProviderBatch:
        try:
            f = self.ak.tool_trade_date_hist_sina().rename(columns={"trade_date": "cal_date"})
        except Exception as error:
            raise ProviderError(f"tool_trade_date_hist_sina: {type(error).__name__}") from error
        f["cal_date"] = pd.to_datetime(f["cal_date"]).dt.date.astype(str)
        f = f[(f["cal_date"] >= start_date) & (f["cal_date"] <= end_date)].copy()
        f["exchange"] = "SSE"
        f["is_open"] = True
        f["pretrade_date"] = f["cal_date"].shift(1)
        return self._batch(Dataset.TRADING_CALENDAR, f, "tool_trade_date_hist_sina", {"start": start_date, "end": end_date})

    def get_security_master(self, as_of_date: str | None = None) -> ProviderBatch:
        raise CapabilityUnavailable("AKShare current code-name list cannot prove list/delist dates and is not a qualified security_master backup")

    def get_daily_bars(self, trade_date: str, security_ids: list[str] | None = None) -> ProviderBatch:
        raise CapabilityUnavailable("AKShare per-symbol endpoint is implemented as an operational extension, not bulk Phase 1 backup")

    def get_daily_valuation(self, trade_date: str, security_ids: list[str] | None = None) -> ProviderBatch:
        raise CapabilityUnavailable("AKShare does not provide a qualified historical daily valuation backup")

    def get_taxonomies(self, taxonomy_type: str, as_of_date: str | None = None) -> ProviderBatch:
        raise CapabilityUnavailable("AKShare taxonomy snapshot lacks a verified taxonomy version/effective interval")

    def get_membership_history(self, taxonomy_type: str, start_date: str, end_date: str) -> ProviderBatch:
        raise CapabilityUnavailable("AKShare industry constituents are current snapshots, not strict PIT history")

    def get_index_daily(self, index_id: str, start_date: str, end_date: str) -> ProviderBatch:
        symbol = index_id.lower().replace(".", "")
        try:
            f = self.ak.stock_zh_index_daily_em(symbol=symbol)
        except Exception as error:
            raise ProviderError(f"stock_zh_index_daily_em: {type(error).__name__}") from error
        f = f.rename(columns={"date": "trade_date", "vol": "volume"})
        f["index_id"] = index_id
        f = f[(f["trade_date"].astype(str) >= start_date) & (f["trade_date"].astype(str) <= end_date)]
        return self._batch(Dataset.INDEX_DAILY, f, "stock_zh_index_daily_em", {"symbol": symbol, "start": start_date, "end": end_date})
