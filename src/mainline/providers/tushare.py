from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

from .base import (
    CapabilityUnavailable,
    Dataset,
    EmptyDatasetError,
    ProviderBatch,
    ProviderError,
    ProviderSchemaError,
    ProviderTimeout,
    build_batch,
)


class TushareProvider:
    name = "Tushare Pro"
    source_id = "tushare"
    endpoint = "https://api.tushare.pro"

    def __init__(self, token: str | None = None, timeout_seconds: float | None = None) -> None:
        self.token = token or os.getenv("TUSHARE_TOKEN")
        self.timeout_seconds = timeout_seconds or float(os.getenv("MAINLINE_PROVIDER_TIMEOUT_SECONDS", "30"))

    def _call(self, api_name: str, params: dict, fields: list[str]) -> pd.DataFrame:
        if not self.token:
            raise CapabilityUnavailable("TUSHARE_TOKEN is not configured")
        body = json.dumps({"api_name": api_name, "token": self.token, "params": params, "fields": ",".join(fields)}).encode()
        request = Request(self.endpoint, data=body, headers={"content-type": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except TimeoutError as error:
            raise ProviderTimeout(f"{api_name}: timeout") from error
        except (HTTPError, URLError, json.JSONDecodeError) as error:
            raise ProviderError(f"{api_name}: {type(error).__name__}") from error
        if payload.get("code") not in (0, None):
            raise ProviderError(f"{api_name}: {payload.get('msg') or 'provider error'}")
        data = payload.get("data") or {}
        provider_fields = data.get("fields") or []
        items = data.get("items") or []
        if not provider_fields:
            raise ProviderSchemaError(f"{api_name}: fields missing")
        frame = pd.DataFrame(items, columns=provider_fields)
        if frame.empty:
            raise EmptyDatasetError(f"{api_name}: empty")
        return frame

    @staticmethod
    def _date(value: str | None) -> pd.Series | None:
        return pd.to_datetime(value, format="%Y%m%d", errors="coerce") if value is not None else None

    def _batch(self, dataset: Dataset, frame: pd.DataFrame, api: str, params: dict, capability: str = "historical_full") -> ProviderBatch:
        fingerprint = hashlib.sha256(json.dumps({"api": api, "params": params}, sort_keys=True).encode()).hexdigest()
        version = f"tushare:{api}:{datetime.now(timezone.utc).date().isoformat()}"
        return build_batch(dataset, frame, source_id=self.source_id, source_version=version, request_fingerprint=fingerprint, historical_capability=capability)

    def get_trading_calendar(self, start_date: str, end_date: str) -> ProviderBatch:
        params = {"exchange": "SSE", "start_date": start_date.replace("-", ""), "end_date": end_date.replace("-", "")}
        f = self._call("trade_cal", params, ["exchange", "cal_date", "is_open", "pretrade_date"])
        f["is_open"] = f["is_open"].astype(bool)
        return self._batch(Dataset.TRADING_CALENDAR, f, "trade_cal", params)

    def get_security_master(self, as_of_date: str | None = None) -> ProviderBatch:
        parts = []
        for status in ("L", "D", "P"):
            parts.append(self._call("stock_basic", {"exchange": "", "list_status": status}, ["ts_code", "symbol", "name", "area", "industry", "market", "exchange", "list_status", "list_date", "delist_date", "is_hs"] ))
        f = pd.concat(parts, ignore_index=True).drop_duplicates("ts_code", keep="last")
        f.insert(0, "security_id", f["ts_code"])
        return self._batch(Dataset.SECURITY_MASTER, f, "stock_basic", {"list_status": "L,D,P"})

    def get_daily_bars(self, trade_date: str, security_ids: list[str] | None = None) -> ProviderBatch:
        params = {"trade_date": trade_date.replace("-", "")}
        f = self._call("daily", params, ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"])
        f = f.rename(columns={"ts_code": "security_id", "vol": "volume"})
        if security_ids:
            f = f[f["security_id"].isin(security_ids)]
        return self._batch(Dataset.DAILY_BARS, f, "daily", params)

    def get_daily_valuation(self, trade_date: str, security_ids: list[str] | None = None) -> ProviderBatch:
        params = {"trade_date": trade_date.replace("-", "")}
        f = self._call("daily_basic", params, ["ts_code", "trade_date", "turnover_rate", "volume_ratio", "pe", "pb", "total_share", "float_share", "free_share", "total_mv", "circ_mv"])
        f = f.rename(columns={"ts_code": "security_id"})
        if security_ids:
            f = f[f["security_id"].isin(security_ids)]
        return self._batch(Dataset.DAILY_VALUATION, f, "daily_basic", params)

    def get_taxonomies(self, taxonomy_type: str, as_of_date: str | None = None) -> ProviderBatch:
        if taxonomy_type != "sw1":
            raise CapabilityUnavailable(f"taxonomy {taxonomy_type} is not implemented in Phase 1")
        params = {"index_code": "", "level": "L1", "src": "SW2021"}
        f = self._call("index_classify", params, ["index_code", "industry_name", "level", "industry_code", "is_pub", "parent_code", "src"])
        f = f.rename(columns={"index_code": "taxonomy_code", "industry_name": "taxonomy_name"})
        f["taxonomy_type"] = "sw1"
        f["taxonomy_version"] = f["src"].fillna("SW2021")
        f["effective_from"] = "2021-12-13"
        return self._batch(Dataset.TAXONOMIES, f, "index_classify", params, "historical_partial")

    def get_membership_history(self, taxonomy_type: str, start_date: str, end_date: str) -> ProviderBatch:
        if taxonomy_type != "sw1":
            raise CapabilityUnavailable(f"taxonomy {taxonomy_type} is not implemented in Phase 1")
        params = {"is_new": "N"}
        f = self._call("index_member_all", params, ["l1_code", "l1_name", "l2_code", "l2_name", "l3_code", "l3_name", "ts_code", "name", "in_date", "out_date", "is_new"])
        f = f.rename(columns={"ts_code": "security_id", "l1_code": "taxonomy_code", "in_date": "effective_from", "out_date": "effective_to"})
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        f = f[(f["effective_from"].fillna("") <= end) & ((f["effective_to"].isna()) | (f["effective_to"] == "") | (f["effective_to"] >= start))]
        return self._batch(Dataset.MEMBERSHIP_HISTORY, f, "index_member_all", params, "historical_partial")

    def get_index_daily(self, index_id: str, start_date: str, end_date: str) -> ProviderBatch:
        params = {"ts_code": index_id, "start_date": start_date.replace("-", ""), "end_date": end_date.replace("-", "")}
        f = self._call("index_daily", params, ["ts_code", "trade_date", "close", "open", "high", "low", "pre_close", "change", "pct_chg", "vol", "amount"])
        f = f.rename(columns={"ts_code": "index_id", "vol": "volume"})
        return self._batch(Dataset.INDEX_DAILY, f, "index_daily", params)
