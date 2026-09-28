from __future__ import annotations

import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import pandas as pd
import requests


class NeteaseWindowProvider:
    """Token-free NetEase historical CSV backup with amount and turnover."""

    source_id = "netease_chddata"
    source_version = "netease-money-163-chddata-v1"

    def __init__(self, *, workers: int = 12, retries: int = 1, timeout_seconds: int = 15) -> None:
        self.workers = workers
        self.retries = retries
        self.timeout_seconds = timeout_seconds

    def get_many(self, security_ids: list[str], start_date: date, end_date: date) -> tuple[pd.DataFrame, dict[str, str]]:
        frames: list[pd.DataFrame] = []
        errors: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self.get_one, sid, start_date, end_date): sid for sid in security_ids}
            for future in as_completed(futures):
                sid = futures[future]
                try:
                    frame = future.result()
                    if frame.empty:
                        errors[sid] = "empty"
                    else:
                        frames.append(frame)
                except Exception as error:
                    errors[sid] = f"{type(error).__name__}:{error}"
        columns = ["security_id", "trade_date", "open", "high", "low", "close", "volume", "amount", "pct_chg", "turnover_rate", "circ_mv", "circ_mv_derivation", "source_id", "source_version"]
        return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)), errors

    def get_one(self, security_id: str, start_date: date, end_date: date) -> pd.DataFrame:
        code, exchange = security_id.split(".", 1)
        if exchange == "SH":
            provider_code = f"0{code}"
        elif exchange == "SZ":
            provider_code = f"1{code}"
        else:
            return pd.DataFrame()
        params = {
            "code": provider_code,
            "start": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
            "fields": "TCLOSE;HIGH;LOW;TOPEN;LCLOSE;CHG;PCHG;VOTURNOVER;VATURNOVER;TURNOVER",
        }
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = requests.get(
                    "https://quotes.money.163.com/service/chddata.html",
                    params=params,
                    timeout=self.timeout_seconds,
                    headers={"User-Agent": "Mozilla/5.0 phase1d-poc/1.0"},
                )
                response.raise_for_status()
                frame = pd.read_csv(io.BytesIO(response.content), encoding="gbk")
                return self._normalize(frame, security_id)
            except Exception as error:
                last = error
                if attempt + 1 < self.retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"fetch failed: {type(last).__name__}:{last}")

    def _normalize(self, frame: pd.DataFrame, security_id: str) -> pd.DataFrame:
        mapping = {
            "日期": "trade_date",
            "开盘价": "open",
            "最高价": "high",
            "最低价": "low",
            "收盘价": "close",
            "成交量": "volume",
            "成交金额": "amount",
            "涨跌幅": "pct_chg",
            "换手率": "turnover_rate",
        }
        frame = frame.rename(columns=mapping)
        required = set(mapping.values())
        if frame.empty or not required.issubset(frame.columns):
            return pd.DataFrame()
        frame["security_id"] = security_id
        frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
        for column in ("open", "high", "low", "close", "volume", "amount", "pct_chg", "turnover_rate"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        valid = frame["turnover_rate"].gt(0) & frame["volume"].ge(0) & frame["close"].gt(0)
        frame["circ_mv"] = pd.NA
        frame.loc[valid, "circ_mv"] = (
            frame.loc[valid, "close"]
            * frame.loc[valid, "volume"]
            / (frame.loc[valid, "turnover_rate"] / 100.0)
        )
        frame["circ_mv_derivation"] = "close*volume_shares/(turnover_rate/100)"
        frame["source_id"] = self.source_id
        frame["source_version"] = self.source_version
        columns = ["security_id", "trade_date", "open", "high", "low", "close", "volume", "amount", "pct_chg", "turnover_rate", "circ_mv", "circ_mv_derivation", "source_id", "source_version"]
        return frame[columns].dropna(subset=["trade_date"]).sort_values("trade_date")
