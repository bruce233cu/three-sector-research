from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import date

import pandas as pd
import requests


SWS_TREND_URL = "https://www.swsresearch.com/institute-sw/api/index_publish/trend/"
SW2021_LEVEL1 = {
    "801010": "农林牧渔", "801030": "基础化工", "801040": "钢铁", "801050": "有色金属",
    "801080": "电子", "801110": "家用电器", "801120": "食品饮料", "801130": "纺织服饰",
    "801140": "轻工制造", "801150": "医药生物", "801160": "公用事业", "801170": "交通运输",
    "801180": "房地产", "801200": "商贸零售", "801210": "社会服务", "801230": "综合",
    "801710": "建筑材料", "801720": "建筑装饰", "801730": "电力设备", "801740": "国防军工",
    "801750": "计算机", "801760": "传媒", "801770": "通信", "801780": "银行",
    "801790": "非银金融", "801880": "汽车", "801890": "机械设备", "801950": "煤炭",
    "801960": "石油石化", "801970": "环保", "801980": "美容护理",
}


@dataclass(frozen=True)
class SwsIndexSeries:
    code: str
    name: str
    frame: pd.DataFrame
    source_id: str
    source_version: str


class SwsIndexProvider:
    source_id = "sws_official_index_trend"

    def __init__(self, *, timeout_seconds: int = 30, retries: int = 2, session: requests.Session | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.session = session or requests.Session()

    def fetch(self, code: str, name: str, start: date, end: date) -> SwsIndexSeries:
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = self.session.get(
                    SWS_TREND_URL,
                    params={"swindexcode": code, "period": "DAY"},
                    headers={"User-Agent": "Mozilla/5.0 mainline-phase2a/1.0"},
                    timeout=self.timeout_seconds,
                    # The official SWS host currently serves an incomplete CA
                    # chain.  Keep the hostname fixed and fingerprint every
                    # response; this mirrors the audited Phase 1D adapter.
                    verify=False,
                )
                response.raise_for_status()
                payload = response.json()
                rows = payload.get("data") or payload.get("result") or []
                if isinstance(rows, dict):
                    rows = rows.get("data") or rows.get("list") or rows.get("rows") or []
                frame = pd.DataFrame(rows)
                aliases = {
                    "bargaindate": "trade_date", "trade_date": "trade_date", "date": "trade_date",
                    "swindexname": "index_name", "closeindex": "close", "close": "close",
                    "bargainamount": "amount", "amount": "amount", "volume": "volume",
                    "pctchange": "pct_chg", "pct_chg": "pct_chg", "changepercent": "pct_chg",
                }
                frame = frame.rename(columns={key: value for key, value in aliases.items() if key in frame.columns})
                if not {"trade_date", "close"}.issubset(frame.columns):
                    raise ValueError(f"SWS index schema changed: {sorted(frame.columns)}")
                frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
                for column in ("close", "amount", "volume", "pct_chg"):
                    if column in frame.columns:
                        frame[column] = pd.to_numeric(frame[column], errors="coerce")
                frame = frame.sort_values("trade_date")
                if "pct_chg" not in frame.columns:
                    frame["pct_chg"] = frame["close"].pct_change() * 100
                frame = frame[(frame.trade_date >= start) & (frame.trade_date <= end)].reset_index(drop=True)
                if frame.empty:
                    raise ValueError(f"SWS returned no rows for {code} {start}..{end}")
                digest = hashlib.sha256(response.content).hexdigest()
                return SwsIndexSeries(code, name, frame, self.source_id, f"sws-trend:{digest}")
            except Exception as error:
                last = error
                if attempt + 1 < self.retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"SWS fetch failed {code}: {type(last).__name__}: {last}")
