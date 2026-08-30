# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Single SL-buffer x R:R backtest worker. Trailing ON at live 0.3/0.1."""
import json
import os
import sys
import MetaTrader5 as mt5

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
sys.path.insert(0, BASE)
import backtest_m1_trend as bt  # noqa: E402
import config as cfg  # noqa: E402
from pattern_sweep import cached_get_ohlc  # noqa: E402

tf = getattr(mt5, sys.argv[1])
months = int(sys.argv[2])
mode = sys.argv[3]
label = sys.argv[4]
buf = float(sys.argv[5])    # SL buffer in price units (was 0.5)
ratio = float(sys.argv[6])  # R:R target (was 4.0)

bt.BACKTEST_TIMEFRAMES = [tf]
bt.BACKTEST_MONTHS = months
bt.TREND_TF_MODE = mode
bt.MAX_BARS = cfg.MAX_BARS_IN_TRADE
bt.WICK_GUARD = cfg.get_symbol_param("XAUUSD", "WICK_GUARD", 0.0)
bt.ATR_GATE = cfg.get_symbol_param("XAUUSD", "ATR_GATE", 0.0)
bt.RANGE_EDGE_ATR = cfg.get_symbol_param("XAUUSD", "RANGE_EDGE_ATR", 0.0)
bt.SPREAD_PRICE = 0.30
bt.SLIP_PRICE = 0.10
bt.USE_TRAILING = True
bt.TRAIL_START_ATR = 0.3
bt.TRAIL_STEP_ATR = 0.1
bt.USE_OPEN_RR = False  # SL x R:R sweep tests fixed-TP ladder
bt.PIP_BUFFER = buf
bt.RR_RATIO = ratio
bt.get_ohlc = cached_get_ohlc
bt._print_results = lambda r: None
bt.mt5_init()
bt.mt5_init = lambda: None

r = bt.run_backtest()
if not r:
    print("no results")
    sys.exit(1)

metrics = {
    "trades": r["total_trades"], "wins": r["wins"], "losses": r["losses"],
    "win_rate": round(r["win_rate"], 1), "pf": round(r["profit_factor"], 2),
    "net": round(r["total_pnl"], 2),
    "net_pct": round(r["total_pnl_pct"], 1),
    "expectancy": round(r["expectancy"], 2),
    "avg_rr": round(r["avg_rr"], 2), "max_dd": round(r["max_dd_pct"], 2),
    "sharpe": round(r["sharpe"], 2), "calmar": round(r["calmar"], 2),
}
name = f"_res_slrr_{label}_{str(buf).replace('.', 'p')}_{int(ratio):d}.json"
with open(os.path.join(BASE, name), "w") as f:
    json.dump(metrics, f)
print(f"{label}/b{buf}/1:{int(ratio):d}: {metrics['net_pct']}%  "
      f"WR {metrics['win_rate']}%  PF {metrics['pf']}  "
      f"avgRR {metrics['avg_rr']}  ({metrics['trades']} T)")
mt5.shutdown()