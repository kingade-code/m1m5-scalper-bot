import MetaTrader5 as mt5
import backtest as bt
import config

SYMBOLS = ["XAUUSD", "GBPUSD", "AUDUSD"]
orig = {k: getattr(config, k) for k in [
    "TREND_EMA_PERIOD", "TRAILING_START_ATR", "TRAILING_STEP_ATR",
    "RSI_OVERSOLD", "RSI_OVERBOUGHT", "MIN_BODY_RATIO",
    "MAX_BARS_IN_TRADE", "ATR_SL_MULTIPLIER", "ATR_PERIOD",
    "SWING_LOOKBACK", "SWING_STRENGTH", "RSI_PERIOD"
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

# Test ATR period variations
tests = [
    # Baseline
    ("BASELINE (EMA20, Trail0.15)", {}),

    # ATR period
    ("ATR Period 7", {"ATR_PERIOD": 7}),
    ("ATR Period 10", {"ATR_PERIOD": 10}),
    ("ATR Period 21", {"ATR_PERIOD": 21}),

    # SL multiplier
    ("SL 0.75 ATR", {"ATR_SL_MULTIPLIER": 0.75}),
    ("SL 1.25 ATR", {"ATR_SL_MULTIPLIER": 1.25}),
    ("SL 1.5 ATR", {"ATR_SL_MULTIPLIER": 1.5}),

    # Trailing start
    ("Trail Start 0.5", {"TRAILING_START_ATR": 0.5}),
    ("Trail Start 0.6", {"TRAILING_START_ATR": 0.6}),
    ("Trail Start 0.8", {"TRAILING_START_ATR": 0.8}),

    # RSI period
    ("RSI Period 7", {"RSI_PERIOD": 7}),
    ("RSI Period 10", {"RSI_PERIOD": 10}),
    ("RSI Period 21", {"RSI_PERIOD": 21}),

    # Swing settings
    ("Swing LB 60", {"SWING_LOOKBACK": 60}),
    ("Swing LB 100", {"SWING_LOOKBACK": 100}),
    ("Swing Str 3", {"SWING_STRENGTH": 3}),

    # Body ratio
    ("Body 12%", {"MIN_BODY_RATIO": 0.12}),
    ("Body 18%", {"MIN_BODY_RATIO": 0.18}),

    # Max bars
    ("Max Bars 8", {"MAX_BARS_IN_TRADE": 8}),
    ("Max Bars 12", {"MAX_BARS_IN_TRADE": 12}),
]

results = []
for label, params in tests:
    print(f"\n  {label}")
    r = run(label, **params)
    wr = r["win_rate"]
    results.append((label, r))
    print(f"  Trades={r['total_trades']} WR={wr:.1f}% PF={r['profit_factor']:.2f} Sharpe={r['sharpe']:.2f} P/L=${r['total_pnl']:,.0f} MaxDD={r['max_dd_pct']:.1f}% Expect=${r['expectancy']:.2f}")

# Find best improvements
baseline = results[0][1]
improvements = []
for label, r in results[1:]:
    wr_diff = r["win_rate"] - baseline["win_rate"]
    pf_diff = r["profit_factor"] - baseline["profit_factor"]
    if wr_diff > 0 or pf_diff > 0.1:
        improvements.append((label, r, wr_diff, pf_diff))

if improvements:
    improvements.sort(key=lambda x: (-x[2], -x[3]))
    print(f"\n\n{'='*80}")
    print("  IMPROVEMENTS OVER BASELINE")
    print(f"{'='*80}")
    for label, r, wr_d, pf_d in improvements[:5]:
        print(f"  {label:<30} WR={r['win_rate']:.1f}% (+{wr_d:.1f}%) PF={r['profit_factor']:.2f} (+{pf_d:.2f}) P/L=${r['total_pnl']:,.0f}")
