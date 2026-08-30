# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""BTCUSD first-look backtest of the current Kingade live ruleset.

Mirrors the XAUUSD trail-sweep configuration (pattern entry, EMA10/100
trend filter, wick+/-buffer SL, TP 1:4, ATR-scaled 0.3/0.1 trailing,
max-bars 45, 600s cooldown, 4% risk capped at $20) but with BTCUSD-
calibrated price-unit buffers and friction from config.SYMBOL_OVERRIDES.
Runs both legs and checkpoints to btc_comparison.json.
"""
import json
import os
import sys
import MetaTrader5 as mt5

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
OUT = os.path.join(BASE, "btc_comparison_notrail_rr3.json")
SYMBOL = "BTCUSD"

sys.path.insert(0, BASE)
import backtest_m1_trend as bt  # noqa: E402
import config as cfg  # noqa: E402
from pattern_sweep import cached_get_ohlc  # noqa: E402


def set_sym_params():
    bt.BACKTEST_SYMBOLS = [SYMBOL]
    bt.MAX_BARS = cfg.MAX_BARS_IN_TRADE
    bt.RR_RATIO = cfg.get_symbol_param(SYMBOL, "RR_RATIO", 4.0)
    bt.PIP_BUFFER = cfg.get_symbol_param(SYMBOL, "SL_PIP_BUFFER", 10.0)
    bt.WICK_GUARD = cfg.get_symbol_param(SYMBOL, "WICK_GUARD", 6.0)
    bt.ATR_GATE = 0.0
    bt.RANGE_EDGE_ATR = cfg.get_symbol_param(SYMBOL, "RANGE_EDGE_ATR", 0.0)
    bt.TRAIL_START_ATR = cfg.get_symbol_param(SYMBOL, "TRAILING_START_ATR", 0.3)
    bt.TRAIL_STEP_ATR = cfg.get_symbol_param(SYMBOL, "TRAILING_STEP_ATR", 0.1)
    bt.USE_TRAILING = cfg.get_symbol_param(SYMBOL, "TRAILING_ENABLED", True)
    bt.USE_REVERSE_CLOSE = cfg.USE_REVERSE_CLOSE
    bt.SPREAD_PRICE = cfg.get_symbol_param(SYMBOL, "SPREAD", 1.0)
    bt.SLIP_PRICE = 0.5  # placeholder stop-slippage until a BTC fill audit
    bt.get_ohlc = cached_get_ohlc
    bt._print_results = lambda r: None


def run_leg(tf_name, months, mode, label):
    data = {}
    set_sym_params()
    bt.PIP_BUFFER = (
        cfg.get_symbol_param(SYMBOL, f"SL_PIP_BUFFER_{label}", None)
        or cfg.get_symbol_param(SYMBOL, "SL_PIP_BUFFER", 10.0))
    bt.BACKTEST_TIMEFRAMES = [getattr(mt5, tf_name)]
    bt.BACKTEST_MONTHS = months
    bt.TREND_TF_MODE = mode
    bt.mt5_init()
    bt.mt5_init = lambda: None
    r = bt.run_backtest()
    if not r:
        print(f"{label}: no results")
        return
    m = {
        "trades": r["total_trades"], "wins": r["wins"], "losses": r["losses"],
        "win_rate": round(r["win_rate"], 1), "pf": round(r["profit_factor"], 2),
        "net": round(r["total_pnl"], 2), "net_pct": round(r["total_pnl_pct"], 1),
        "expectancy": round(r["expectancy"], 2), "avg_rr": round(r["avg_rr"], 2),
        "max_dd": round(r["max_dd_pct"], 2), "sharpe": round(r["sharpe"], 2),
        "calmar": round(r["calmar"], 2),
        "start": str(r.get("start_date", "")), "end": str(r.get("end_date", "")),
    }
    data[label] = m
    print(f"{label}: {m['net_pct']}%  WR {m['win_rate']}%  PF {m['pf']}  "
          f"avgRR {m['avg_rr']}  maxDD {m['max_dd']}%  ({m['trades']} T)")
    return data[label]


def main():
    if os.path.exists(OUT):
        data = json.load(open(OUT))
    else:
        data = {}
    for tf_name, months, mode, label in [
        ("TIMEFRAME_M5", 16, "own", "M5"),
        ("TIMEFRAME_M1", 50, "m1", "M1"),
    ]:
        if label in data:
            print(f"[skip] {label} already done")
            continue
        m = run_leg(tf_name, months, mode, label)
        if m:
            data[label] = m
            json.dump(data, open(OUT, "w"), indent=2)
    print("done")


if __name__ == "__main__":
    main()