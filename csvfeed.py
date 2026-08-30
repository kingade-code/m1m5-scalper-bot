# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Shared CSV feed for XAUUSD M1 history (2023-01-02 -> 2026-08-26).

Mirrors MT5's get_ohlc return shape (time/open/high/low/close/tick_volume/
spread/real_volume with a datetime 'time' column). A module-level WINDOW
(start, end) ISO-date tuple slices the feed before use, so the same engine can
be walk-forwarded over disjoint train/test windows without touching backend
code. M5 is resampled from the same M1 series (global fences).
"""
import os
import pandas as pd
import MetaTrader5 as mt5

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
CSV = os.path.join(BASE, "data", "xauusd_m1.csv")

_FULL_M1 = None
WINDOW = None  # (datetime, datetime) inclusive, or None for full history


def _load():
    global _FULL_M1
    if _FULL_M1 is None:
        df = pd.read_csv(CSV)
        df["time"] = pd.to_datetime(df["timestamp"], unit="s")
        df["tick_volume"] = df["volume"].astype("int64")
        df["spread"] = 0
        df["real_volume"] = df["volume"].astype("int64")
        df = df[["time", "open", "high", "low", "close",
                 "tick_volume", "spread", "real_volume"]]
        _FULL_M1 = df.reset_index(drop=True)
    return _FULL_M1


def set_window(start_iso, end_iso):
    """Constrain the feed to [start, end] inclusive (ISO 'YYYY-MM-DD')."""
    global WINDOW
    WINDOW = (pd.Timestamp(start_iso), pd.Timestamp(end_iso))


def clear_window():
    global WINDOW
    WINDOW = None


def csv_get_ohlc(symbol, timeframe, count):
    df = _load()
    if WINDOW is not None:
        s, e = WINDOW
        df = df[(df["time"] >= s) & (df["time"] <= e)].reset_index(drop=True)
    if timeframe == mt5.TIMEFRAME_M1:
        return df
    tmp2 = df.set_index(df["time"])
    m5 = pd.DataFrame({
        "open": tmp2["open"].resample("5min").first(),
        "high": tmp2["high"].resample("5min").max(),
        "low": tmp2["low"].resample("5min").min(),
        "close": tmp2["close"].resample("5min").last(),
        "tick_volume": tmp2["tick_volume"].resample("5min").sum(),
        "real_volume": tmp2["real_volume"].resample("5min").sum(),
    }).dropna()
    m5 = m5.reset_index().rename(columns={"index": "time"})
    m5["time"] = m5["time"].dt.tz_localize(None)
    m5["spread"] = 0
    return m5.reset_index(drop=True)