# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Single walk-forward backtest worker.

Args: leg_label tmframe monthsmode? No - windowed CSV feed:
    window  start|end ISO dates, actually two args: start_iso, end_iso
    leg     'M5' | 'M1'
    trail   'None' or 'start/step' e.g. '0.3/0.1'
    rr      target ratio (int)
    out     result filename (without dir)
Everything else is the live config (wick SL 0.5, cooldown, max-bars,
reverse-close, 0.30 spread + 0.10 slip). Writes full per-trade roll-up JSON.
"""
import json
import os
import sys
import numpy as np
import MetaTrader5 as mt5

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
sys.path.insert(0, BASE)
import backtest_m1_trend as bt  # noqa: E402
import config as cfg  # noqa: E402
from csvfeed import csv_get_ohlc, set_window  # noqa: E402

start_iso, end_iso, leg, trail, rr_s = sys.argv[1], sys.argv[2], sys.argv[3], \
    sys.argv[4], sys.argv[5]
rr = float(rr_s)
out = sys.argv[6]

tf = mt5.TIMEFRAME_M5 if leg == "M5" else mt5.TIMEFRAME_M1
set_window(start_iso, end_iso)

bt.BACKTEST_TIMEFRAMES = [tf]
bt.BACKTEST_MONTHS = 99          # feed decides the window, not 'months'
bt.TREND_TF_MODE = "m1"          # live semantics: single M1 EMA set
bt.MAX_BARS = cfg.MAX_BARS_IN_TRADE
bt.WICK_GUARD = cfg.get_symbol_param("XAUUSD", "WICK_GUARD", 0.0)
bt.ATR_GATE = cfg.get_symbol_param("XAUUSD", "ATR_GATE", 0.0)
bt.RANGE_EDGE_ATR = cfg.get_symbol_param("XAUUSD", "RANGE_EDGE_ATR", 0.0)
bt.SPREAD_PRICE = 0.30
bt.SLIP_PRICE = 0.10
bt.PIP_BUFFER = cfg.get_symbol_param("XAUUSD", "SL_PIP_BUFFER", 0.5)
bt.RR_RATIO = rr
bt.USE_BE_PROTECT = False
if trail.upper() == "NONE" or "/" not in trail:
    bt.USE_TRAILING = False
else:
    bt.USE_TRAILING = True
    bt.TRAIL_START_ATR, bt.TRAIL_STEP_ATR = \
        (float(x) for x in trail.split("/"))
bt.USE_OPEN_RR = False  # walk-forward sweep keeps classic fixed-TP exits
bt.get_ohlc = csv_get_ohlc
bt._print_results = lambda r: None
bt.mt5_init()
bt.mt5_init = lambda: None

r = bt.run_backtest()
if not r:
    print("no results")
    sys.exit(1)

closed = [t for t in r["trades"] if t.result != "open"]
wins = [t for t in closed if t.result == "win"]
losses = [t for t in closed if t.result == "loss"]
gross_w = sum(t.profit for t in wins)
gross_l = abs(sum(t.profit for t in losses))
net = sum(t.profit for t in closed)
rr_list = []
for t in closed:
    risk = abs(t.entry_price - t.sl)
    if risk > 0:
        rr_list.append(abs(t.exit_price - t.entry_price) / risk)
metrics = {
    "trades": len(closed), "wins": len(wins), "losses": len(losses),
    "win_rate": round(100.0 * len(wins) / len(closed), 1) if closed else 0,
    "pf": round(gross_w / gross_l, 2) if gross_l > 0 else float("inf"),
    "net": round(net, 2),
    "net_pct": round(100.0 * net / bt.INITIAL_BALANCE, 1),
    "avg_rr": round(float(np.mean(rr_list)), 2) if rr_list else 0.0,
    "max_dd": round(r["max_dd_pct"], 2),
    "expectancy": round(r["expectancy"], 2),
}
with open(os.path.join(BASE, out), "w") as f:
    json.dump(metrics, f)
print(f'{leg}/{trail}/1:{int(rr)}: {metrics["net_pct"]}%  '
      f'WR {metrics["win_rate"]}%  PF {metrics["pf"]}  '
      f'net {metrics["net"]}  ({metrics["trades"]} T)', flush=True)
mt5.shutdown()