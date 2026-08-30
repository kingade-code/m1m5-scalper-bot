# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Full-history backtest of the CURRENT (live) strategy using the user's
downloaded XAUUSD M1 CSV (2023-01-02 -> 2026-08-26, ~3.65y) instead of the
MT5 server window (which caps M1 at ~3.3 months of depth).

get_ohlc is swapped for a CSV-backed loader. M1 requests return the full M1
frame; M5 requests are resampled from the same M1 series (aligned 5-min OHLC).
Time semantics match the MT5 epoch the engine already consumes.
Saves full_history_comparison.json so the PDF can render a section.
"""
import json
import os
import sys
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
sys.path.insert(0, BASE)
import backtest_m1_trend as bt  # noqa: E402
import config as cfg  # noqa: E402

CSV = os.path.join(BASE, "data", "xauusd_m1.csv")
OUT = os.path.join(BASE, "full_history_comparison.json")

_FULL_M1 = None


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


def csv_get_ohlc(symbol, timeframe, count):
    m1 = _load()
    if timeframe == mt5.TIMEFRAME_M1:
        return m1
    # 5-min resample aligned to :00/:05/... from the same M1 series.
    tmp = m1.set_index(m1["time"])
    g = tmp["open"].resample("5min").first()
    tmp2 = m1.set_index(m1["time"])
    m5 = pd.DataFrame({
        "open": tmp2["open"].resample("5min").first(),
        "high": tmp2["high"].resample("5min").max(),
        "low": tmp2["low"].resample("5min").min(),
        "close": tmp2["close"].resample("5min").last(),
        "tick_volume": tmp2["tick_volume"].resample("5min").sum(),
        "real_volume": tmp2["real_volume"].resample("5min").sum(),
    }).dropna()
    m5 = m5.reset_index()
    m5 = m5.rename(columns={"index": "time"})
    m5["time"] = m5["time"].dt.tz_localize(None)
    m5["spread"] = 0
    return m5.reset_index(drop=True)


def _metrics(r):
    return {
        "trades": r["total_trades"], "wins": r["wins"], "losses": r["losses"],
        "win_rate": round(r["win_rate"], 1), "pf": round(r["profit_factor"], 2),
        "net": round(r["total_pnl"], 2),
        "net_pct": round(r["total_pnl_pct"], 1),
        "expectancy": round(r["expectancy"], 2),
        "avg_rr": round(r["avg_rr"], 2), "max_dd": round(r["max_dd_pct"], 2),
        "sharpe": round(r["sharpe"], 2), "calmar": round(r["calmar"], 2),
    }


def main():
    bt.BACKTEST_TIMEFRAMES = [mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M1]
    bt.BACKTEST_MONTHS = 99          # irrelevant under CSV feed (full history)
    bt.TREND_TF_MODE = "m1"          # live semantics: single M1 EMA set
    bt.MAX_BARS = cfg.MAX_BARS_IN_TRADE
    bt.WICK_GUARD = cfg.get_symbol_param("XAUUSD", "WICK_GUARD", 0.0)
    bt.ATR_GATE = cfg.get_symbol_param("XAUUSD", "ATR_GATE", 0.0)
    bt.RANGE_EDGE_ATR = cfg.get_symbol_param("XAUUSD", "RANGE_EDGE_ATR", 0.0)
    bt.SPREAD_PRICE = 0.30
    bt.SLIP_PRICE = 0.10
    bt.USE_TRAILING = True
    bt.TRAIL_START_ATR = 0.3
    bt.TRAIL_STEP_ATR = 0.1
    bt.PIP_BUFFER = cfg.get_symbol_param("XAUUSD", "SL_PIP_BUFFER", 0.5)
    bt.RR_RATIO = cfg.get_symbol_param("XAUUSD", "RR_RATIO", 4.0)
    bt.USE_BE_PROTECT = False
    bt.get_ohlc = csv_get_ohlc
    bt._print_results = lambda r: None
    bt.mt5_init()
    bt.mt5_init = lambda: None

    m1 = _load()
    print(f"CSV feed: {len(m1)} M1 bars | "
          f"{m1['time'].iloc[0].strftime('%Y-%m-%d')} -> "
          f"{m1['time'].iloc[-1].strftime('%Y-%m-%d')}", flush=True)

    r = bt.run_backtest()
    if not r or not r.get("trades"):
        print("no trades")
        sys.exit(1)

    out = {"meta": {
        "source": "xauusd_m1.csv (Dukascopy-style epoch)",
        "window": f"{m1['time'].iloc[0].strftime('%Y-%m-%d')} -> "
                  f"{m1['time'].iloc[-1].strftime('%Y-%m-%d')}",
        "bars_m1": int(len(m1)), "config": "live (0.3/0.1 trail, 1:4, 0.30/0.10)"}}
    _tf_map = {mt5.TIMEFRAME_M1: "M1", mt5.TIMEFRAME_M5: "M5"}
    for tf_name in ("M5", "M1"):
        sel = [t for t in r["trades"] if _tf_map.get(t.timeframe) == tf_name]
        if not sel:
            continue
        wins = [t for t in sel if t.result == "win"]
        losses = [t for t in sel if t.result == "loss"]
        gross_w = sum(t.profit for t in wins)
        gross_l = abs(sum(t.profit for t in losses))
        net = sum(t.profit for t in sel)
        rr = gross_w / gross_l if gross_l > 0 else float("inf")
        avg_rr = []
        for t in sel:
            risk = abs(t.entry_price - t.sl)
            if risk > 0:
                avg_rr.append(abs(t.exit_price - t.entry_price) / risk)
        out[tf_name] = {
            "trades": len(sel), "wins": len(wins), "losses": len(losses),
            "win_rate": round(100.0 * len(wins) / len(sel), 1),
            "pf": round(rr, 2),
            "net": round(net, 2),
            "net_pct": round(100.0 * net / bt.INITIAL_BALANCE, 1),
            "avg_rr": round(float(np.mean(avg_rr)), 2) if avg_rr else 0.0,
        }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    for tf_name in ("M5", "M1"):
        if tf_name in out:
            m = out[tf_name]
            print(f"{tf_name}: {m['trades']} T  WR {m['win_rate']}%  "
                  f"PF {m['pf']}  net {m['net']}%", flush=True)
    mt5.shutdown()


if __name__ == "__main__":
    main()