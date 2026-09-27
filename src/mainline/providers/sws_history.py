from __future__ import annotations

import hashlib
import io
import time
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import requests


SWS_BASE = "https://www.swsresearch.com/swindex/pdf/SwClass2021"
SWS_STOCK_HISTORY_URL = f"{SWS_BASE}/StockClassifyUse_stock.xls"
SWS_CODE_URL = f"{SWS_BASE}/SwClassCode_2021.xls"


@dataclass(frozen=True)
class MembershipSnapshot:
    trade_date: date
    taxonomy_code: str
    taxonomy_name: str
    taxonomy_version: str
    frame: pd.DataFrame
    source_version: str
    pit_level: str
    knowledge_time_unverified: bool


def _download(url: str, retries: int = 4) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0 phase1d-audit/1.0"}
    last: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=90, verify=False)
            response.raise_for_status()
            if len(response.content) < 1024:
                raise RuntimeError(f"short response: {len(response.content)} bytes")
            return response.content
        except Exception as error:
            last = error
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"download failed: {url}: {type(last).__name__}: {last}")


class SwsEffectivePitProvider:
    """Official SWS classification history, effective-PIT only.

    The official file exposes membership effective dates but not a complete
    publication timestamp history.  Therefore this provider must never label
    its output strict_knowledge_pit.
    """

    source_id = "sws_official_stock_classification"

    def __init__(self, stock_bytes: bytes | None = None, code_bytes: bytes | None = None) -> None:
        self.stock_bytes = stock_bytes or _download(SWS_STOCK_HISTORY_URL)
        self.code_bytes = code_bytes or _download(SWS_CODE_URL)
        digest = hashlib.sha256(self.stock_bytes + self.code_bytes).hexdigest()
        self.source_version = f"sws-official:{digest}"
        self.history = self._parse()

    def _parse(self) -> pd.DataFrame:
        stocks = pd.read_excel(io.BytesIO(self.stock_bytes), dtype={"股票代码": str, "行业代码": str})
        codes = pd.read_excel(io.BytesIO(self.code_bytes), dtype={"行业代码": str})
        stocks = stocks.rename(columns={"股票代码": "security_code", "计入日期": "effective_from", "行业代码": "industry_code", "更新日期": "source_update_date"})
        required = {"security_code", "effective_from", "industry_code"}
        if not required.issubset(stocks.columns):
            raise ValueError(f"SWS membership schema changed: {sorted(stocks.columns)}")
        if "一级行业名称" not in codes.columns or "行业代码" not in codes.columns:
            raise ValueError(f"SWS taxonomy schema changed: {sorted(codes.columns)}")
        codes = codes.rename(columns={"行业代码": "industry_code", "一级行业名称": "level1_name"})
        stocks["security_code"] = stocks["security_code"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        stocks["industry_code"] = stocks["industry_code"].astype(str).str.replace(r"\.0$", "", regex=True)
        stocks["effective_from"] = pd.to_datetime(stocks["effective_from"], errors="coerce").dt.date
        merged = stocks.merge(codes[["industry_code", "level1_name"]].drop_duplicates(), on="industry_code", how="left")
        # Some official revisions include the level-1 name directly in the
        # membership workbook.  Prefer it when an older code is absent from the
        # current taxonomy dictionary; never infer an unknown historical code.
        direct_name = next((c for c in ("一级行业名称", "一级行业") if c in stocks.columns), None)
        if direct_name:
            direct = stocks[["security_code", "effective_from", "industry_code", direct_name]].rename(columns={direct_name: "direct_level1_name"})
            merged = merged.merge(direct, on=["security_code", "effective_from", "industry_code"], how="left")
            merged["level1_name"] = merged["level1_name"].fillna(merged["direct_level1_name"])
        merged = merged.dropna(subset=["security_code", "effective_from", "level1_name"]).sort_values(["security_code", "effective_from"])
        merged["next_from"] = merged.groupby("security_code")["effective_from"].shift(-1)
        merged["effective_to"] = merged["next_from"].map(lambda v: v - timedelta(days=1) if pd.notna(v) else None)
        merged["security_id"] = merged["security_code"].map(_security_id)
        return merged

    def snapshot(self, trade_date: date, taxonomy_code: str, taxonomy_name: str) -> MembershipSnapshot:
        frame = self.history[
            (self.history["level1_name"] == taxonomy_name)
            & (self.history["effective_from"] <= trade_date)
            & (self.history["effective_to"].isna() | (self.history["effective_to"] >= trade_date))
        ].copy()
        frame = frame[["security_id", "security_code", "effective_from", "effective_to", "industry_code"]].drop_duplicates("security_id")
        taxonomy_version = "SW2021" if trade_date >= date(2021, 12, 13) else "SW2014"
        return MembershipSnapshot(
            trade_date, taxonomy_code, taxonomy_name, taxonomy_version, frame,
            self.source_version, "effective_pit", True,
        )


def _security_id(code: str) -> str:
    suffix = "SH" if code.startswith("6") else "BJ" if code.startswith(("4", "8", "9")) else "SZ"
    return f"{code}.{suffix}"
