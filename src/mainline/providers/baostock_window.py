from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date

import pandas as pd


def _fetch_chunk(security_ids: list[str], start_date: date, end_date: date) -> tuple[pd.DataFrame, dict[str, str]]:
    """Run one independent BaoStock session in a worker process."""
    provider = BaostockWindowProvider(workers=1)
    return provider._get_many_serial(security_ids, start_date, end_date)


class BaostockWindowProvider:
    """Token-free historical-bar backup, used only after Primary failures."""

    source_id = "baostock_history_k"
    source_version = "baostock:0.8.9:query_history_k_data_plus"

    def __init__(self, *, workers: int = 4) -> None:
        import baostock as bs
        self.bs = bs
        self.workers = max(1, workers)

    def get_many(self, security_ids: list[str], start_date: date, end_date: date) -> tuple[pd.DataFrame, dict[str, str]]:
        if not security_ids:
            return pd.DataFrame(), {}
        if self.workers == 1 or len(security_ids) < 8:
            return self._get_many_serial(security_ids, start_date, end_date)
        chunks = [security_ids[index:: self.workers] for index in range(self.workers)]
        frames: list[pd.DataFrame] = []
        errors: dict[str, str] = {}
        with ProcessPoolExecutor(max_workers=self.workers) as pool:
            futures = [pool.submit(_fetch_chunk, chunk, start_date, end_date) for chunk in chunks if chunk]
            for future in as_completed(futures):
                frame, chunk_errors = future.result()
                if not frame.empty:
                    frames.append(frame)
                errors.update(chunk_errors)
        return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()), errors

    def _get_many_serial(self, security_ids: list[str], start_date: date, end_date: date) -> tuple[pd.DataFrame, dict[str, str]]:
        login = self.bs.login()
        if login.error_code != "0":
            return pd.DataFrame(), {sid: f"login:{login.error_code}:{login.error_msg}" for sid in security_ids}
        frames: list[pd.DataFrame] = []
        errors: dict[str, str] = {}
        try:
            for security_id in security_ids:
                try:
                    frame = self.get_one(security_id, start_date, end_date)
                    if frame.empty:
                        errors[security_id] = "empty"
                    else:
                        frames.append(frame)
                except Exception as error:
                    errors[security_id] = f"{type(error).__name__}:{error}"
        finally:
            self.bs.logout()
        return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()), errors

    def get_one(self, security_id: str, start_date: date, end_date: date) -> pd.DataFrame:
        exchange = security_id.split(".", 1)[1].lower()
        if exchange not in {"sh", "sz"}:
            return pd.DataFrame()
        symbol = f"{exchange}.{security_id.split('.', 1)[0]}"
        fields = "date,code,open,high,low,close,volume,amount,pctChg,turn,tradestatus"
        result = self.bs.query_history_k_data_plus(
            symbol, fields, start_date=start_date.isoformat(), end_date=end_date.isoformat(),
            frequency="d", adjustflag="3",
        )
        if result.error_code != "0":
            raise RuntimeError(f"{result.error_code}:{result.error_msg}")
        rows: list[list[str]] = []
        while result.next():
            rows.append(result.get_row_data())
        frame = pd.DataFrame(rows, columns=fields.split(","))
        if frame.empty:
            return frame
        frame = frame.rename(columns={"date": "trade_date", "turn": "turnover_rate"})
        frame["security_id"] = security_id
        frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
        for column in ("open", "high", "low", "close", "volume", "amount", "pctChg", "turnover_rate", "tradestatus"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.rename(columns={"pctChg": "pct_chg"})
        frame.loc[frame["tradestatus"].ne(1), ["amount", "pct_chg"]] = None
        # BaoStock volume is shares (not 100-share lots).  Preserve NULL when
        # turnover is unavailable, zero, or the security did not trade.
        valid_turnover = (
            frame["tradestatus"].eq(1)
            & frame["turnover_rate"].gt(0)
            & frame["volume"].ge(0)
            & frame["close"].gt(0)
        )
        frame["circ_mv"] = pd.NA
        frame.loc[valid_turnover, "circ_mv"] = (
            frame.loc[valid_turnover, "close"]
            * frame.loc[valid_turnover, "volume"]
            / (frame.loc[valid_turnover, "turnover_rate"] / 100.0)
        )
        frame["circ_mv_derivation"] = "close*volume_shares/(turnover_rate/100)"
        frame["source_id"] = self.source_id
        frame["source_version"] = self.source_version
        return frame[["security_id", "trade_date", "open", "high", "low", "close", "volume", "amount", "pct_chg", "turnover_rate", "circ_mv", "circ_mv_derivation", "source_id", "source_version"]]
