# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import MetaTrader5 as mt5
import backtest as bt
import config

SYMBOLS = ["XAUUSD", "GBPUSD", "AUDUSD"]
orig = {k: getattr(config, k) for k in [
    "TRAILING_START_ATR", "TRAILING_STEP_ATR",
    "MIN_BODY_RATIO", "MAX_BARS_IN_TRADE", "ATR_SL_MULTIPLIER"
]}

def reset():
    for k, v in orig.items():
        setattr(config, k, v)

def run(label, **kwargs):
    reset()
    for k, v in kwargs.items():
        setattr(config, k, v)
    bt.BACKTEST_SYMBOLS = SYMBOLS
    bt.BACKTEST_TIMEFRAMES = [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5]
    bt.BACKTEST_MONTHS = 6
    r = bt.run_backtest()
    reset()
    return r

tests = [
    ("Trail Start 0.6", {"TRAILING_START_ATR": 0.6}),
    ("Trail Start 0.8", {"TRAILING_START_ATR": 0.8}),
    ("SL 0.75 ATR", {"ATR_SL_MULTIPLIER": 0.75}),
    ("SL 1.5 ATR", {"ATR_SL_MULTIPLIER": 1.5}),
    ("Body 12%", {"MIN_BODY_RATIO": 0.12}),
    ("Body 18%", {"MIN_BODY_RATIO": 0.18}),
    ("Max Bars 8", {"MAX_BARS_IN_TRADE": 8}),
    ("Max Bars 12", {"MAX_BARS_IN_TRADE": 12}),
    ("EMA20 + Trail0.15 + SL1.25", {"ATR_SL_MULTIPLIER": 1.25}),
    ("EMA20 + Trail0.15 + TrailStart0.6", {"TRAILING_START_ATR": 0.6, "TRAILING_STEP_ATR": 0.15}),
]

for label, params in tests:
    print(f"\n  {label}")
    r = run(label, **params)
    print(f"  Trades={r['total_trades']} WR={r['win_rate']:.1f}% PF={r['profit_factor']:.2f} Sharpe={r['sharpe']:.2f} P/L=${r['total_pnl']:,.0f} MaxDD={r['max_dd_pct']:.1f}% Expect=${r['expectancy']:.2f}")
