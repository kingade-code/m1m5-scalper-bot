# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import MetaTrader5 as mt5
import backtest as bt
import config

SYMBOLS = ["XAUUSD", "GBPUSD", "AUDUSD"]

def run(label, low, high):
    config.FIB_ENTRY_LOW = low
    config.FIB_ENTRY_HIGH = high
    bt.BACKTEST_SYMBOLS = SYMBOLS
    bt.BACKTEST_TIMEFRAMES = [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5]
    bt.BACKTEST_MONTHS = 6
    r = bt.run_backtest()
    config.FIB_ENTRY_LOW = 0.5
    config.FIB_ENTRY_HIGH = 0.786
    return r

tests = [
    ("Current: 0.500-0.786 (full zone)", 0.5, 0.786),
    ("Only 0.500 level (0.495-0.505)", 0.495, 0.505),
    ("Only 0.500 level (0.490-0.510)", 0.49, 0.51),
    ("Only 0.500 level (0.485-0.515)", 0.485, 0.515),
    ("Only 0.618 level (0.610-0.625)", 0.61, 0.625),
    ("Only 0.500 level (0.490-0.510) + EMA20", 0.49, 0.51),
]

results = []
for label, low, high in tests:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    r = run(label, low, high)
    wr = r["win_rate"]
    results.append((label, r))
    print(f"  Trades={r['total_trades']} WR={wr:.1f}% PF={r['profit_factor']:.2f} Sharpe={r['sharpe']:.2f} P/L=${r['total_pnl']:,.0f} MaxDD={r['max_dd_pct']:.1f}% AvgWin=${r['avg_win']:.2f} Expect=${r['expectancy']:.2f}")

print(f"\n\n{'='*80}")
print("  COMPARISON")
print(f"{'='*80}")
print(f"{'Test':<40} {'Trades':>7} {'WR%':>7} {'PF':>6} {'Sharpe':>7} {'P/L':>12}")
print("-" * 80)
for label, r in results:
    print(f"{label:<40} {r['total_trades']:>7} {r['win_rate']:>6.1f}% {r['profit_factor']:>5.2f} {r['sharpe']:>6.2f} ${r['total_pnl']:>10,.0f}")
