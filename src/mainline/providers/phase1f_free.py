"""Minimal, sequential POC adapters. No DB, no alternative endpoint chain."""
from __future__ import annotations

import importlib.metadata
import json
import time
from datetime import date

import pandas as pd

FIELDS = ["security_id", "trade_date", "open", "high", "low", "close",
          "volume", "amount", "pct_chg", "circ_mv"]


def version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def normalize(raw, sid, start, end, volume_scale=1):
    """Preserve missing cells; derive adjacent-observed unadjusted return only."""
    f = pd.DataFrame(raw).copy()
    if f.empty:
        return pd.DataFrame(columns=FIELDS), {"raw_rows": 0, "unit_check_ok": False}
    f = f.rename(columns={"date": "trade_date", "datetime": "trade_date", "vol": "volume"})
    if not set(["trade_date", "open", "high", "low", "close", "volume", "amount"]).issubset(f):
        raise ValueError("provider schema missing OHLCV/amount/date")
    f["trade_date"] = pd.to_datetime(f["trade_date"], errors="raise").dt.date
    raw_ordered = f.trade_date.is_monotonic_increasing or f.trade_date.is_monotonic_decreasing
    f = f.sort_values("trade_date")
    if f.trade_date.duplicated().any():
        raise ValueError("duplicate provider dates; no silent deduplication")
    for c in ["open", "high", "low", "close", "volume", "amount"]:
        f[c] = pd.to_numeric(f[c], errors="coerce")
    f["volume"] *= volume_scale
    # Zero-volume bars may be suspension placeholders. Keep audit counts but
    # never forward-fill them into a price history or label suspension confirmed.
    no_trade = f.volume.le(0) | f.amount.le(0)
    f = f[~no_trade & (f.trade_date <= end)].copy()
    f["pct_chg"] = (f.close / f.close.shift(1) - 1) * 100
    f["security_id"] = sid
    f["circ_mv"] = float("nan")
    f = f[(f.trade_date >= start) & (f.trade_date <= end)].copy()
    complete = f.dropna(subset=["open", "high", "low", "close", "volume", "amount"])
    vwap = complete.amount / complete.volume
    unit_ok = bool(len(complete) and ((vwap >= complete.low * .9) &
                                     (vwap <= complete.high * 1.1)).mean() >= .9)
    invalid = (complete[["open","high","low","close"]] <= 0).any(axis=1) | (complete.low > complete.high) | (complete.open < complete.low) | (
        complete.open > complete.high) | (complete.close < complete.low) | (complete.close > complete.high)
    if invalid.any():
        raise ValueError("OHLC relationship invalid")
    return f[FIELDS], {"raw_rows": len(raw), "raw_order_valid": bool(raw_ordered),
        "no_trade_rows": int(no_trade.sum()), "unit_check_ok": unit_ok,
        "volume_unit": "shares", "amount_unit": "CNY", "adjust": "unadjusted",
        "return_basis": "adjacent_observed_close; corporate_action_not_adjusted",
        "suspension_confirmed": False}


class TdxWindow:
    name = "TDX"
    library = "pytdx"

    def __init__(self, config, servers=None):
        from pytdx.hq import TdxHq_API
        from pytdx.config.hosts import hq_hosts
        if version("pytdx") != "1.72":
            raise RuntimeError("DEPENDENCY: pytdx==1.72 required")
        self.config = config
        self.factory = TdxHq_API
        hosts = servers if servers else [{"name": h[0], "host": h[1], "port": h[2]} for h in hq_hosts]
        self.server_audit = []
        candidates = []
        # Node list comes from pinned package/runtime override, not permanent IPs.
        for h in hosts[:config["max_server_probes"]]:
            started = time.monotonic()
            api = self.factory(raise_exception=True, auto_retry=False)
            try:
                connected = api.connect(h["host"], int(h["port"]), time_out=3)
                count = api.get_security_count(0) if connected else None
                if not count:
                    raise RuntimeError("connection/count unavailable")
                elapsed = time.monotonic() - started
                candidates.append((elapsed, h))
                self.server_audit.append({**h, "ok": True, "elapsed_time": elapsed})
            except Exception as e:
                self.server_audit.append({**h, "ok": False, "reason": str(e), "elapsed_time": time.monotonic()-started})
            finally:
                api.disconnect()
        if not candidates:
            raise RuntimeError("TDX_SERVERS_UNREACHABLE:" + json.dumps(self.server_audit))
        self.endpoint = min(candidates, key=lambda x: x[0])[1]
        self.candidates = [h for _, h in sorted(candidates, key=lambda x: x[0])]
        self.api = None

    def connect(self):
        if self.api is not None:
            return
        errors = []
        for attempt in range(self.config["connection_attempts"]):
            self.endpoint = self.candidates[attempt % len(self.candidates)]
            api = self.factory(raise_exception=True, auto_retry=False)
            try:
                if not api.connect(self.endpoint["host"], int(self.endpoint["port"]), time_out=3):
                    raise RuntimeError("connect returned false")
                self.api = api
                return
            except Exception as e:
                errors.append(str(e))
                api.disconnect()
        raise RuntimeError("TDX_CONNECT:" + ";".join(errors))

    def get_one(self, sid, start, end):
        if sid.endswith(".BJ"):
            raise ValueError("unsupported historic BJ market mapping; no guessed mapping")
        self.connect()
        rows = []
        oldest = None
        pages = 0
        for offset in range(0, self.config["max_tdx_pages"] * 800, 800):
            page = self.api.get_security_bars(9, int(sid.endswith(".SH")), sid.split(".")[0], offset, 800)
            pages += 1
            if not page:
                break
            # Pages newer than the requested window are discarded immediately.
            p = pd.DataFrame(page)
            dates = pd.to_datetime(p["datetime"]).dt.date
            new_oldest = min(dates)
            if oldest is not None and new_oldest >= oldest:
                raise RuntimeError("pagination not progressing")
            oldest = new_oldest
            rows.extend(p.loc[(dates <= end) & (dates >= start), :].to_dict("records"))
            before = p.loc[dates < start]
            if not before.empty:
                rows.extend(before.tail(1).to_dict("records"))
                break
        f, audit = normalize(rows, sid, start, end, volume_scale=100)
        audit.update({"page_requests": pages, "history_limit_reached": pages == self.config["max_tdx_pages"],
                      "endpoint": self.endpoint})
        return f, audit


class SinaWindow:
    name = "Sina"
    library = "akshare"
    endpoint = "https://finance.sina.com.cn/realstock/company/{symbol}/hisdata_klc2/klc_kl.js"
    server_audit = []

    def __init__(self, config, servers=None):
        if version("akshare") != "1.18.97":
            raise RuntimeError("DEPENDENCY: optional akshare==1.18.97 required")
        self.config = config

    def get_one(self, sid, start, end):
        import requests
        import py_mini_racer
        from akshare.stock.cons import hk_js_decode, zh_sina_a_stock_hist_url
        if sid.endswith(".BJ"):
            raise ValueError("unsupported Sina historic BJ symbol")
        # Do NOT call stock_zh_a_daily: its share-history merge ffill may create
        # synthetic OHLC rows. Reuse the SAME raw upstream URL and JS decoder.
        if "finance.sina.com.cn/realstock/company/" not in zh_sina_a_stock_hist_url:
            raise RuntimeError("unexpected upstream URL in pinned AKShare")
        symbol = sid.split(".")[1].lower() + sid.split(".")[0]
        response = requests.get(zh_sina_a_stock_hist_url.format(symbol), timeout=10,
            headers={"User-Agent": "Mozilla/5.0 mainline-phase1f-c"})
        response.raise_for_status()
        js = py_mini_racer.MiniRacer()
        try:
            js.eval(hk_js_decode)
            raw = js.call("d", response.text.split("=", 1)[1].split(";", 1)[0].strip().strip('"'))
        finally:
            if hasattr(js, "close"):
                js.close()
        f, audit = normalize(raw, sid, start, end)
        audit.update({"page_requests": 1, "upstream": zh_sina_a_stock_hist_url,
            "function": "AKShare stock_zh_a_daily raw decode only; no share merge/ffill",
            "raw_payload_checksum": __import__("hashlib").sha256(response.content).hexdigest()})
        return f, audit


def worker(pipe, name, config, servers):
    """Persistent isolated connection; parent kills blocked calls on all OSes."""
    try:
        provider = {"TDX": TdxWindow, "Sina": SinaWindow}[name](config, servers)
        pipe.send({"ok": True, "endpoint": provider.endpoint, "server_audit": provider.server_audit,
                   "library_version": version(provider.library)})
    except Exception as e:
        pipe.send({"ok": False, "error": f"{type(e).__name__}:{e}"})
        return
    try:
        while True:
            command = pipe.recv()
            if command is None:
                return
            sid, start, end = command
            t = time.monotonic()
            try:
                f, audit = provider.get_one(sid, start, end)
                pipe.send({"ok": True, "frame": f, "audit": audit, "elapsed_time": time.monotonic()-t})
            except Exception as e:
                if name == "TDX" and provider.api:
                    provider.api.disconnect()
                    provider.api = None
                pipe.send({"ok": False, "error": f"{type(e).__name__}:{e}", "elapsed_time": time.monotonic()-t})
    except (EOFError, BrokenPipeError):
        pass
