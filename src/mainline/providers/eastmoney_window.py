from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import pandas as pd
import requests


class EastmoneyWindowProvider:
    source_id = "eastmoney_kline"
    source_version = "eastmoney-push2his-kline-v1"

    def __init__(self, *, workers: int = 6, retries: int = 4) -> None:
        self.workers = workers
        self.retries = retries

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
        if not frames:
            return pd.DataFrame(columns=["security_id", "trade_date", "open", "high", "low", "close", "volume", "amount", "pct_chg"]), errors
        return pd.concat(frames, ignore_index=True), errors

    def get_one(self, security_id: str, start_date: date, end_date: date) -> pd.DataFrame:
        code = security_id.split(".", 1)[0]
        market = 1 if security_id.endswith(".SH") else 0
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": "101", "fqt": "0", "secid": f"{market}.{code}",
            "beg": start_date.strftime("%Y%m%d"), "end": end_date.strftime("%Y%m%d"),
        }
        payload = self._json("https://push2his.eastmoney.com/api/qt/stock/kline/get", params)
        klines = ((payload.get("data") or {}).get("klines") or [])
        rows = [item.split(",") for item in klines]
        frame = pd.DataFrame(rows, columns=["trade_date", "open", "close", "high", "low", "volume", "amount", "amplitude", "pct_chg", "change", "turnover_rate"])
        if frame.empty:
            return frame
        frame["security_id"] = security_id
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
        for column in ["open", "close", "high", "low", "volume", "amount", "pct_chg", "turnover_rate"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame[["security_id", "trade_date", "open", "high", "low", "close", "volume", "amount", "pct_chg", "turnover_rate"]]

    def get_sw_index(self, code: str) -> pd.DataFrame:
        payload = self._json(
            "https://www.swsresearch.com/institute-sw/api/index_publish/trend/",
            {"swindexcode": code, "period": "DAY"}, verify=False,
        )
        frame = pd.DataFrame(payload.get("data") or [])
        if frame.empty:
            return frame
        frame = frame.rename(columns={"bargaindate": "trade_date", "closeindex": "close", "bargainsum": "amount"})
        frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
        frame["pct_chg"] = frame["close"].pct_change() * 100
        return frame[["trade_date", "close", "amount", "pct_chg"]].sort_values("trade_date")

    def _json(self, url: str, params: dict, *, verify: bool = True) -> dict:
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = requests.get(url, params=params, timeout=45, verify=verify, headers={"User-Agent": "Mozilla/5.0 phase1d-poc/1.0"})
                response.raise_for_status()
                return response.json()
            except Exception as error:
                last = error
                if attempt + 1 < self.retries:
                    time.sleep(2 ** attempt)
        fingerprint = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
        raise RuntimeError(f"fetch failed {fingerprint}: {type(last).__name__}: {last}")
