# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Accumulation-Manipulation-Distribution (AMD) backtest engine for XAUUSD.

ICT/SMC mechanics implemented deterministically (closed bars only, no look-ahead):

  * ACCUMULATION: a consolidation window in the last ACC_LOOKBACK closed bars.
    Compact range (range <= ACC_RANGE_MULT x ATR) with price sitting near the
    middle (|close - mid| <= ACC_POS_FRAC x range width) - a coil, not a trend.
  * MANIPULATION: a signal candle sweeps beyond one edge of that range by more
    than SWEEP_MIN and closes back inside it (single-bar rejection), i.e. the
    stop-hunt / liquidity grab. Optional --two-bar variant: one candle closes
    beyond, the next closes back inside.
  * DISTRIBUTION: trade the reversal - short after an up-sweep targeting the
    range's low, long after a down-sweep targeting its high. This is the phase
    the smart-money move actually wants.

Money management and costs are identical to backtest_m1_trend.py (the current
strategy): 4% risk, $20 cap, 0.10 max lot, spread + stop-slippage charges, so
the comparison is apples-to-apples. One entry per accumulation (cooldown of
ACC_LOOKBACK bars after each entry).
"""
import sys
import argparse
import MetaTrader5 as mt5
import numpy as np
import backtest_m1_trend as bt
import filters
import config as cfg

# ─── AMD parameters ─────────────────────────────────────────────
SHORT_LB = 45          # closed bars of the accumulation coil (inner zone)
CONTEXT_LB = 180       # closed bars of the larger structure it nests in
COIL_FRAC = 0.40       # inner range must be <= this fraction of the context range
POS_FRAC = 0.35        # |last close - context mid| <= this x context range
SWEEP_MIN = 0.10       # price units the manipulation must pierce the edge by
MIN_RR = 1.0           # skip a distribution paying less than 1:1
PIP_BUFFER = bt.PIP_BUFFER  # 0.5, same buffer as the live wick-SL
TWO_BAR_SWEEP = False

ACTF = mt5.TIMEFRAME_M1


def _lot_size(risk_amount, sl_ticks, tick_value):
    if sl_ticks <= 0 or tick_value <= 0:
        return 0.01
    lot = risk_amount / (sl_ticks * tick_value)
    lot = max(0.01, round(lot, 2))
    return lot


def _draw_window(df, i, lookback):
    return df.iloc[max(0, i - 1 - lookback): i - 1]


def _evaluate_entry(df, i, tick_size, tick_value, balance):
    """Accumulation nested in context + manipulation sweep on the closed
    signal candle (i-1). No look-ahead: every window ends at i-2."""
    global SHORT_LB
    wS = _draw_window(df, i, SHORT_LB)
    wC = _draw_window(df, i, CONTEXT_LB)
    if len(wS) < SHORT_LB or len(wC) < CONTEXT_LB:
        return None

    shHi = float(wS["high"].max()); shLo = float(wS["low"].min())
    cHi = float(wC["high"].max());  cLo = float(wC["low"].min())
    cMid = float(wC["close"].mean())
    cRw = cHi - cLo
    shRw = shHi - shLo
    if cRw <= 0 or shRw <= 0:
        return None
    if shRw > COIL_FRAC * cRw:      # inner zone not compact -> not accumulation
        return None

    sig = df.iloc[i - 1]
    if abs(float(sig["close"]) - cMid) > POS_FRAC * cRw:
        return None                 # price already at a context extreme

    def build(direction, entry, sl, tp):
        risk = abs(entry - sl)
        rew = abs(tp - entry)
        if risk <= 0 or rew / risk < MIN_RR:
            return None
        risk_amount = balance * bt.RISK_PER_TRADE / 100.0
        sl_ticks = risk / tick_size
        lot = _lot_size(risk_amount, sl_ticks, tick_value)
        return bt.Trade(symbol="XAUUSD", timeframe=ACTF, direction=direction,
                        entry_price=entry, sl=sl, tp1=tp,
                        entry_time=sig["time"], lot_size=lot)

    if TWO_BAR_SWEEP:
        prev = df.iloc[i - 2] if i >= 2 else None
        if (prev is not None
                and float(prev["high"]) > shHi + SWEEP_MIN
                and float(prev["close"]) > shHi
                and float(sig["close"]) <= shHi):
            # distribution target = opposite edge of the context zone
            return build("sell", float(sig["close"]),
                         max(shHi + PIP_BUFFER, float(prev["high"]) + PIP_BUFFER), cLo)
        if (prev is not None
                and float(prev["low"]) < shLo - SWEEP_MIN
                and float(prev["close"]) < shLo
                and float(sig["close"]) >= shLo):
            return build("buy", float(sig["close"]),
                         min(shLo - PIP_BUFFER, float(prev["low"]) - PIP_BUFFER), cHi)
        return None

    if float(sig["high"]) > shHi + SWEEP_MIN and float(sig["close"]) <= shHi:
        return build("sell", float(sig["close"]),
                     float(sig["high"]) + PIP_BUFFER, cLo)
    if float(sig["low"]) < shLo - SWEEP_MIN and float(sig["close"]) >= shLo:
        return build("buy", float(sig["close"]),
                     float(sig["low"]) - PIP_BUFFER, cHi)
    return None


def run_amd_backtest(symbol="XAUUSD", tf=mt5.TIMEFRAME_M5, months=16,
                     spread=0.30, slip=0.10):
    global ACTF
    ACTF = tf
    bt.mt5_init()

    bars_needed = 96 * 22 * months + 500
    df = bt.get_ohlc(symbol, tf, bars_needed)
    if df is None or len(df) < 500:
        print(f"insufficient data: {0 if df is None else len(df)}")
        bt.mt5.shutdown()
        return None

    tick_value, tick_size, point = bt.get_symbol_tick_value(symbol)
    if tick_value is None or tick_value == 0:
        print("no tick data")
        bt.mt5.shutdown()
        return None

    bt.SPREAD_PRICE = spread
    bt.SLIP_PRICE = slip

    print(f"AMD | {len(df)} bars | {df.iloc[0]['time'].strftime('%Y-%m-%d')} -> "
          f"{df.iloc[-1]['time'].strftime('%Y-%m-%d')} | "
          f"acc {SHORT_LB} bars in {CONTEXT_LB}-bar zone, sweep-reject "
          f"{'two-bar' if TWO_BAR_SWEEP else 'single-bar'}, "
          f"costs {spread:.2f}+{slip:.2f}")

    all_trades = []
    balance = bt.INITIAL_BALANCE
    equity_points = [{"time": None, "equity": bt.INITIAL_BALANCE}]
    open_trades = []
    cooldown = 0

    for i in range(200, len(df)):
        bar = df.iloc[i]
        for t in open_trades:
            if t.result == "open":
                t.bars_held += 1
                if bt._check_exit(t, bar):
                    bt._close_trade(t, bar, tick_value, tick_size)
                    balance += t.profit
                    equity_points.append({"time": t.exit_time, "equity": balance})
        open_trades = [t for t in open_trades if t.result == "open"]
        if open_trades:
            continue

        if cooldown > 0:
            cooldown -= 1
            continue

        trade = _evaluate_entry(df, i, tick_value, tick_size, balance)
        if trade is not None:
            open_trades.append(trade)
            all_trades.append(trade)
            cooldown = SHORT_LB

    for t in open_trades:
        if t.result == "open":
            bt._close_trade(t, df.iloc[-1], tick_value, tick_size)
            balance += t.profit

    bt.mt5.shutdown()
    r = bt._compile_results(all_trades, equity_points, balance)
    return r


def _print_amd(r):
    w = 64
    print(f"\n{'='*w}")
    print(f"{'AMD (ACCUMULATION-MANIPULATION-DISTRIBUTION) - RESULTS':^{w}}")
    print(f"{('Range coil -> liquidity sweep -> distribution, ' + ('two-bar' if TWO_BAR_SWEEP else 'single-bar') + ' reject'):^{w}}")
    print(f"{'='*w}")
    print(f"  Initial Balance:   ${r['initial_balance']:>12,.2f}")
    print(f"  Final Balance:     ${r['final_balance']:>12,.2f}")
    print(f"  Net P/L:           ${r['total_pnl']:>12,.2f} ({r['total_pnl_pct']:+.2f}%)")
    print(f"  Total Trades:      {r['total_trades']:>10}")
    print(f"  Win Rate:          {r['win_rate']:>9.1f}%")
    print(f"  Profit Factor:     {r['profit_factor']:>10.2f}")
    print(f"  Avg R:R:           {r['avg_rr']:>10.2f}")
    print(f"  Expectancy/Trade:  ${r['expectancy']:>10,.2f}")
    print(f"  Max Drawdown %:    {r['max_dd_pct']:>8.2f}%  (${r['max_dd']:,.2f})")
    cum = 0
    for m, data in sorted(r["monthly"].items()):
        cum += data["pnl"]
        wr = data["wins"] / data["trades"] * 100 if data["trades"] else 0
        print(f"  {m} | {data['trades']:>3} trades | WR {wr:5.1f}% | "
              f"${data['pnl']:>11,.2f} | Cum ${cum:>12,.2f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="AMD backtest")
    p.add_argument("--tf", choices=["M1", "M5"], default="M5")
    p.add_argument("--months", type=int, default=16)
    p.add_argument("--spread", type=float, default=0.30)
    p.add_argument("--slip", type=float, default=0.10)
    p.add_argument("--lookback", type=int, default=45,
                   help="accumulation coil window in closed bars")
    p.add_argument("--ctx", type=int, default=180,
                   help="context zone window in closed bars")
    p.add_argument("--coil-frac", type=float, default=0.40,
                   help="coil range <= this x context range")
    p.add_argument("--pos-frac", type=float, default=0.35,
                   help="max |close - context mid| as a fraction of context range")
    p.add_argument("--sw-min", type=float, default=0.10)
    p.add_argument("--min-rr", type=float, default=1.0)
    p.add_argument("--two-bar", action="store_true")
    args = p.parse_args()

    SHORT_LB = args.lookback
    CONTEXT_LB = args.ctx
    COIL_FRAC = args.coil_frac
    POS_FRAC = args.pos_frac
    SWEEP_MIN = args.sw_min
    MIN_RR = args.min_rr
    TWO_BAR_SWEEP = args.two_bar
    tf_map = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5}

    r = run_amd_backtest(tf=tf_map[args.tf], months=args.months,
                         spread=args.spread, slip=args.slip)
    if r:
        _print_amd(r)