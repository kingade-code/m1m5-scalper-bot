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

# EMA 20 was best WR so far. Now test combos with it
tests = [
    ("EMA20 + Trail0.15", {"TREND_EMA_PERIOD": 20, "TRAILING_STEP_ATR": 0.15}),
    ("EMA20 + Body15%", {"TREND_EMA_PERIOD": 20, "MIN_BODY_RATIO": 0.15}),
    ("EMA20 + Body20%", {"TREND_EMA_PERIOD": 20, "MIN_BODY_RATIO": 0.20}),
    ("EMA20 + SL1.2", {"TREND_EMA_PERIOD": 20, "ATR_SL_MULTIPLIER": 1.2}),
    ("EMA20 + RSI60/40", {"TREND_EMA_PERIOD": 20, "RSI_OVERSOLD": 60, "RSI_OVERBOUGHT": 40}),
    ("EMA20 + MaxBars20", {"TREND_EMA_PERIOD": 20, "MAX_BARS_IN_TRADE": 20}),
    ("EMA20 + Trail0.15 + Body15%", {"TREND_EMA_PERIOD": 20, "TRAILING_STEP_ATR": 0.15, "MIN_BODY_RATIO": 0.15}),
    ("EMA20 + Trail0.15 + Body20%", {"TREND_EMA_PERIOD": 20, "TRAILING_STEP_ATR": 0.15, "MIN_BODY_RATIO": 0.20}),
    ("EMA20 + Trail0.15 + SL1.2", {"TREND_EMA_PERIOD": 20, "TRAILING_STEP_ATR": 0.15, "ATR_SL_MULTIPLIER": 1.2}),
    ("EMA20 + Trail0.1 + Body15%", {"TREND_EMA_PERIOD": 20, "TRAILING_STEP_ATR": 0.1, "MIN_BODY_RATIO": 0.15}),
    ("EMA25 + Trail0.15 + Body15%", {"TREND_EMA_PERIOD": 25, "TRAILING_STEP_ATR": 0.15, "MIN_BODY_RATIO": 0.15}),
    ("EMA25 + Trail0.1 + Body20%", {"TREND_EMA_PERIOD": 25, "TRAILING_STEP_ATR": 0.1, "MIN_BODY_RATIO": 0.20}),
]

for label, params in tests:
    print(f"\n  {label}")
    r = run(label, **params)
    wr = r["win_rate"]
    print(f"  Trades={r['total_trades']} WR={wr:.1f}% PF={r['profit_factor']:.2f} Sharpe={r['sharpe']:.2f} P/L=${r['total_pnl']:,.0f} MaxDD={r['max_dd_pct']:.1f}% AvgWin=${r['avg_win']:.2f} Expect=${r['expectancy']:.2f}")
