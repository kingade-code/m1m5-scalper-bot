import MetaTrader5 as mt5
import backtest as bt
import config

SYMBOLS = ["XAUUSD", "GBPUSD", "AUDUSD"]
orig = {k: getattr(config, k) for k in [
    "TREND_EMA_PERIOD", "TRAILING_START_ATR", "TRAILING_STEP_ATR",
    "RSI_OVERSOLD", "RSI_OVERBOUGHT", "MIN_BODY_RATIO",
    "MAX_BARS_IN_TRADE", "ATR_SL_MULTIPLIER"
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
    # Baseline
    ("BASELINE (EMA30, Trail0.2)", {}),

    # EMA variations for M1-M5
    ("EMA 20", {"TREND_EMA_PERIOD": 20}),
    ("EMA 25", {"TREND_EMA_PERIOD": 25}),
    ("EMA 35", {"TREND_EMA_PERIOD": 35}),
    ("EMA 40", {"TREND_EMA_PERIOD": 40}),

    # Trail step variations
    ("Trail Step 0.15", {"TRAILING_STEP_ATR": 0.15}),
    ("Trail Step 0.25", {"TRAILING_STEP_ATR": 0.25}),
    ("Trail Step 0.1", {"TRAILING_STEP_ATR": 0.1}),

    # Trail start variations
    ("Trail Start 0.5", {"TRAILING_START_ATR": 0.5}),
    ("Trail Start 0.65", {"TRAILING_START_ATR": 0.65}),

    # RSI variations
    ("RSI 60/40", {"RSI_OVERSOLD": 60, "RSI_OVERBOUGHT": 40}),
    ("RSI 50/50", {"RSI_OVERSOLD": 50, "RSI_OVERBOUGHT": 50}),

    # Body ratio
    ("Body 15%", {"MIN_BODY_RATIO": 0.15}),
    ("Body 20%", {"MIN_BODY_RATIO": 0.20}),

    # SL multiplier
    ("SL 1.2 ATR", {"ATR_SL_MULTIPLIER": 1.2}),
    ("SL 0.8 ATR", {"ATR_SL_MULTIPLIER": 0.8}),

    # Max bars
    ("Max Bars 20", {"MAX_BARS_IN_TRADE": 20}),
    ("Max Bars 10", {"MAX_BARS_IN_TRADE": 10}),
]

results = []
for label, params in tests:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    r = run(label, **params)
    wr = r["win_rate"]
    results.append((label, r))
    print(f"  Trades={r['total_trades']} WR={wr:.1f}% PF={r['profit_factor']:.2f} Sharpe={r['sharpe']:.2f} P/L=${r['total_pnl']:,.0f} MaxDD={r['max_dd_pct']:.1f}% AvgWin=${r['avg_win']:.2f} Expect=${r['expectancy']:.2f}")

# Find best WR with 70%+ PF > 2.0
qual = [(l, r) for l, r in results if r["win_rate"] >= 68 and r["profit_factor"] >= 2.0]
if qual:
    qual.sort(key=lambda x: -x[1]["win_rate"])
    print(f"\n\n{'='*80}")
    print("  BEST RESULTS (WR >= 68%, PF >= 2.0)")
    print(f"{'='*80}")
    for l, r in qual[:5]:
        print(f"  {l:<40} WR={r['win_rate']:.1f}% PF={r['profit_factor']:.2f} P/L=${r['total_pnl']:,.0f}")

# Best combo test
print(f"\n\n{'='*80}")
print("  TESTING BEST COMBOS")
print(f"{'='*80}")

combos = [
    ("EMA25 + Trail0.15 + Body15%", {"TREND_EMA_PERIOD": 25, "TRAILING_STEP_ATR": 0.15, "MIN_BODY_RATIO": 0.15}),
    ("EMA25 + Trail0.15 + RSI55/45", {"TREND_EMA_PERIOD": 25, "TRAILING_STEP_ATR": 0.15, "RSI_OVERSOLD": 55, "RSI_OVERBOUGHT": 45}),
    ("EMA25 + Trail0.15 + SL1.2", {"TREND_EMA_PERIOD": 25, "TRAILING_STEP_ATR": 0.15, "ATR_SL_MULTIPLIER": 1.2}),
    ("EMA30 + Trail0.15 + Body15%", {"TREND_EMA_PERIOD": 30, "TRAILING_STEP_ATR": 0.15, "MIN_BODY_RATIO": 0.15}),
    ("EMA25 + Trail0.1 + Body15% + SL1.2", {"TREND_EMA_PERIOD": 25, "TRAILING_STEP_ATR": 0.1, "MIN_BODY_RATIO": 0.15, "ATR_SL_MULTIPLIER": 1.2}),
    ("EMA25 + Trail0.15 + Body20% + RSI55/45", {"TREND_EMA_PERIOD": 25, "TRAILING_STEP_ATR": 0.15, "MIN_BODY_RATIO": 0.20, "RSI_OVERSOLD": 55, "RSI_OVERBOUGHT": 45}),
]

for label, params in combos:
    print(f"\n  {label}")
    r = run(label, **params)
    wr = r["win_rate"]
    print(f"  Trades={r['total_trades']} WR={wr:.1f}% PF={r['profit_factor']:.2f} Sharpe={r['sharpe']:.2f} P/L=${r['total_pnl']:,.0f} MaxDD={r['max_dd_pct']:.1f}% AvgWin=${r['avg_win']:.2f} Expect=${r['expectancy']:.2f}")
