# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Backtest matching live bot config: M1 pattern + M1 EMA50 trend + wick SL + trailing + 1:2.5 RR"""
import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
import config
import pattern_detector
import filters

# ─── Backtest Config ──────────────────────────────────────────────
INITIAL_BALANCE = 500.0
RISK_PER_TRADE = config.RISK_PERCENT  # 4%
MAX_LOT = config.MAX_LOT  # 0.05
BACKTEST_SYMBOLS = ["XAUUSD", "GBPUSD", "AUDUSD"]
BACKTEST_TIMEFRAMES = [mt5.TIMEFRAME_M1]
BACKTEST_MONTHS = 2  # ~60 days
MT5_CHUNK_SIZE = 60000

# Trend filter TF
TREND_TF = mt5.TIMEFRAME_M1  # M1 trend for live

# Trailing config
TRAIL_START_ATR = config.TRAILING_START_ATR  # 0.3
TRAIL_STEP_ATR = config.TRAILING_STEP_ATR    # 0.1
USE_TRAILING = config.USE_TRAILING_STOP
MAX_BARS = config.MAX_BARS_IN_TRADE  # 15
RR_RATIO = 2.5
SPREAD = config.get_symbol_param("XAUUSD", "SPREAD", 0)  # 0.3


@dataclass
class Trade:
    symbol: str
    timeframe: int
    direction: str
    entry_price: float
    sl: float
    tp1: float
    entry_time: datetime
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    lot_size: float = 0.01
    profit: float = 0.0
    result: str = "open"
    bars_held: int = 0
    trailing_sl: Optional[float] = None


def mt5_init():
    if not mt5.initialize():
        print(f"MT5 init failed: {mt5.last_error()}")
        sys.exit(1)
    info = mt5.account_info()
    print(f"MT5 connected | Account: {info.login} | Balance: ${info.balance:.2f}")


def get_ohlc(symbol, timeframe, count):
    all_rates = []
    fetched = 0
    while fetched < count:
        batch = min(MT5_CHUNK_SIZE, count - fetched)
        rates = mt5.copy_rates_from_pos(symbol, timeframe, fetched, batch)
        if rates is None or len(rates) == 0:
            break
        all_rates = list(rates) + all_rates
        fetched += len(rates)
        if len(rates) < batch:
            break
    if not all_rates:
        return None
    df = pd.DataFrame(np.array(all_rates, dtype=[
        ('time','<i8'),('open','<f8'),('high','<f8'),('low','<f8'),
        ('close','<f8'),('tick_volume','<u8'),('spread','<i4'),('real_volume','<u8')
    ]))
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def get_symbol_tick_value(symbol):
    info = mt5.symbol_info(symbol)
    if info is None:
        return None, None, None
    return info.trade_tick_value, info.trade_tick_size, info.point


def _update_trailing_stop(trade, bar, current_atr):
    if not USE_TRAILING:
        return
    trail_start = current_atr * TRAIL_START_ATR
    trail_step = current_atr * TRAIL_STEP_ATR
    if trade.direction == "buy":
        unrealized = bar["high"] - trade.entry_price
        if unrealized >= trail_start:
            new_sl = bar["high"] - trail_step
            if trade.trailing_sl is None or new_sl > trade.trailing_sl:
                trade.trailing_sl = new_sl
    else:
        unrealized = trade.entry_price - bar["low"]
        if unrealized >= trail_start:
            new_sl = bar["low"] + trail_step
            if trade.trailing_sl is None or new_sl < trade.trailing_sl:
                trade.trailing_sl = new_sl


def _get_effective_sl(trade):
    if trade.trailing_sl is None:
        return trade.sl
    if trade.direction == "buy":
        return max(trade.sl, trade.trailing_sl)
    else:
        return min(trade.sl, trade.trailing_sl)


def _check_exit(trade, bar):
    eff_sl = _get_effective_sl(trade)
    if trade.direction == "buy":
        if bar["low"] <= eff_sl:
            return True
        if bar["high"] >= trade.tp1:
            return True
    else:
        if bar["high"] >= eff_sl:
            return True
        if bar["low"] <= trade.tp1:
            return True
    return False


def _close_trade(trade, bar, tick_value, tick_size):
    eff_sl = _get_effective_sl(trade)
    if trade.direction == "buy":
        if bar["low"] <= eff_sl:
            trade.exit_price = eff_sl
        elif bar["high"] >= trade.tp1:
            trade.exit_price = trade.tp1
        else:
            trade.exit_price = bar["close"]
    else:
        if bar["high"] >= eff_sl:
            trade.exit_price = eff_sl
        elif bar["low"] <= trade.tp1:
            trade.exit_price = trade.tp1
        else:
            trade.exit_price = bar["close"]

    if trade.direction == "buy":
        trade.result = "win" if trade.exit_price >= trade.entry_price else "loss"
    else:
        trade.result = "win" if trade.exit_price <= trade.entry_price else "loss"

    trade.exit_time = bar["time"]

    sl_dist = abs(trade.entry_price - trade.sl)
    if sl_dist > 0 and tick_size > 0 and tick_value > 0:
        if trade.direction == "buy":
            price_diff = trade.exit_price - trade.entry_price
        else:
            price_diff = trade.entry_price - trade.exit_price
        sl_ticks = sl_dist / tick_size
        price_ticks = price_diff / tick_size
        trade.profit = trade.lot_size * price_ticks * tick_value
    else:
        if trade.direction == "buy":
            trade.profit = (trade.exit_price - trade.entry_price) * trade.lot_size * 100000
        else:
            trade.profit = (trade.entry_price - trade.exit_price) * trade.lot_size * 100000


def run_backtest():
    mt5_init()

    bars_needed = 96 * 22 * BACKTEST_MONTHS + 500  # More bars for M1

    # Pre-fetch M1 data for trend filter
    trend_data = {}
    if config.USE_TREND_FILTER:
        for symbol in BACKTEST_SYMBOLS:
            trend_bars = 96 * 22 * BACKTEST_MONTHS + 500
            trend_df = get_ohlc(symbol, TREND_TF, trend_bars)
            if trend_df is not None and len(trend_df) > config.TREND_EMA_PERIOD + 10:
                trend_ema = filters.calc_ema(trend_df["close"], config.TREND_EMA_PERIOD)
                trend_data[symbol] = {"df": trend_df, "ema": trend_ema}

    all_trades = []
    balance = INITIAL_BALANCE
    peak_balance = INITIAL_BALANCE
    equity_points = [{"time": None, "equity": INITIAL_BALANCE}]

    total_combos = len(BACKTEST_SYMBOLS) * len(BACKTEST_TIMEFRAMES)
    combo_idx = 0

    for symbol in BACKTEST_SYMBOLS:
        for tf in BACKTEST_TIMEFRAMES:
            combo_idx += 1
            print(f"\r[{combo_idx}/{total_combos}] {symbol} M1...", end="", flush=True)

            df = get_ohlc(symbol, tf, bars_needed)
            if df is None or len(df) < 200:
                print(f" skipped (insufficient data: {len(df) if df is not None else 0})")
                continue

            tick_value, tick_size, point = get_symbol_tick_value(symbol)
            if tick_value is None or tick_value == 0:
                print(f" skipped (no tick data)")
                continue

            atr_series = filters.calc_atr(df["high"], df["low"], df["close"], config.ATR_PERIOD)

            print(f" {len(df)} bars | {df.iloc[0]['time'].strftime('%Y-%m-%d')} -> {df.iloc[-1]['time'].strftime('%Y-%m-%d')}")

            start_bar = 200
            open_trades = []
            signals_found = 0
            last_trade_time = {}

            for i in range(start_bar, len(df)):
                current_bar = df.iloc[i]
                current_time = current_bar["time"]
                current_atr = atr_series.iloc[i]

                # ─── Check exits for open trades ─────────────────────
                for trade in open_trades:
                    if trade.result != "open":
                        continue
                    trade.bars_held += 1

                    _update_trailing_stop(trade, current_bar, current_atr)

                    if trade.bars_held >= MAX_BARS:
                        _close_trade(trade, current_bar, tick_value, tick_size)
                        balance += trade.profit
                        continue

                    if _check_exit(trade, current_bar):
                        _close_trade(trade, current_bar, tick_value, tick_size)
                        balance += trade.profit

                open_trades = [t for t in open_trades if t.result == "open"]

                # Cooldown: 10 min = 10 bars on M1
                if symbol in last_trade_time:
                    bars_since = i - last_trade_time[symbol]
                    if bars_since < 600:  # 600 seconds / 60s per bar
                        continue

                if open_trades:
                    continue

                # ─── Pattern detection ───────────────────────────────
                window = df.iloc[max(0, i - 100):i + 1]
                raw_direction = pattern_detector.detect_pattern(window, symbol=symbol)
                if raw_direction == 0:
                    continue

                direction = "bullish" if raw_direction == 1 else "bearish"
                signal_direction = "buy" if raw_direction == 1 else "sell"

                prev_bar = df.iloc[i - 1]
                prev_close = prev_bar["close"]

                # ─── Trend filter (M1 EMA50) ─────────────────────────
                if config.USE_TREND_FILTER and symbol in trend_data:
                    t_info = trend_data[symbol]
                    t_df = t_info["df"]
                    t_ema = t_info["ema"]
                    t_idx = t_df["time"].searchsorted(current_time, side="right") - 1
                    if t_idx > 0 and t_idx < len(t_df):
                        t_price = t_df.iloc[t_idx]["close"]
                        t_ema_val = t_ema.iloc[t_idx]
                        if direction == "bullish" and t_price < t_ema_val:
                            continue
                        if direction == "bearish" and t_price > t_ema_val:
                            continue

                # ─── Wick SL (prev bar low/high) + spread ────────────
                spread_price = SPREAD * 0.10  # 0.3 pip -> price
                if direction == "bullish":
                    swing_sl = prev_bar["low"] + spread_price
                else:
                    swing_sl = prev_bar["high"] - spread_price

                sl_dist = abs(prev_close - swing_sl)
                if sl_dist < config.MIN_STOP_DISTANCE:
                    continue

                # ─── TP: 1:2.5 RR ───────────────────────────────────
                tp_dist = sl_dist * RR_RATIO
                if direction == "bullish":
                    atr_tp = prev_close + tp_dist
                else:
                    atr_tp = prev_close - tp_dist

                # ─── Lot sizing (4% risk, max 0.05) ─────────────────
                risk_amount = balance * RISK_PER_TRADE / 100.0
                sl_ticks = sl_dist / tick_size
                lot_size = risk_amount / (sl_ticks * tick_value)
                lot_size = max(0.01, round(lot_size, 2))
                lot_size = min(MAX_LOT, lot_size)

                trade = Trade(
                    symbol=symbol,
                    timeframe=tf,
                    direction=signal_direction,
                    entry_price=prev_close,
                    sl=swing_sl,
                    tp1=atr_tp,
                    entry_time=current_time,
                    lot_size=lot_size,
                )
                open_trades.append(trade)
                all_trades.append(trade)
                signals_found += 1
                last_trade_time[symbol] = i

                equity_points.append({
                    "time": current_time,
                    "equity": balance,
                })

                if balance > peak_balance:
                    peak_balance = balance

            # Force-close remaining
            for trade in open_trades:
                if trade.result == "open":
                    last_bar = df.iloc[-1]
                    _close_trade(trade, last_bar, tick_value, tick_size)
                    balance += trade.profit

            print(f"    Signals: {signals_found}")

    # Force-close all still-open
    for trade in all_trades:
        if trade.result == "open":
            trade.exit_price = trade.entry_price
            trade.result = "loss"
            trade.profit = 0
            trade.exit_time = datetime.now()

    result = _compile_results(all_trades, equity_points, balance)
    _print_results(result)
    return result


def _compile_results(all_trades, equity_points, final_balance):
    closed = [t for t in all_trades if t.result != "open"]
    wins = [t for t in closed if t.result == "win"]
    losses = [t for t in closed if t.result == "loss"]

    total_pnl = sum(t.profit for t in closed)
    total_pnl_pct = (total_pnl / INITIAL_BALANCE) * 100

    win_rate = (len(wins) / len(closed) * 100) if closed else 0
    avg_win = np.mean([t.profit for t in wins]) if wins else 0
    avg_loss = np.mean([t.profit for t in losses]) if losses else 0
    largest_win = max([t.profit for t in wins]) if wins else 0
    largest_loss = min([t.profit for t in losses]) if losses else 0

    gross_profit = sum(t.profit for t in wins)
    gross_loss = abs(sum(t.profit for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    rr = []
    for t in closed:
        risk = abs(t.entry_price - t.sl)
        if risk > 0:
            reward = abs(t.exit_price - t.entry_price)
            rr.append(reward / risk)
    avg_rr = np.mean(rr) if rr else 0

    peak = INITIAL_BALANCE
    max_dd = 0
    max_dd_pct = 0
    bal = INITIAL_BALANCE
    for t in closed:
        bal += t.profit
        if bal > peak:
            peak = bal
        dd = peak - bal
        dd_pct = (dd / peak) * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)
        max_dd_pct = max(max_dd_pct, dd_pct)

    if len(closed) > 1:
        rets = [t.profit / INITIAL_BALANCE for t in closed]
        sharpe = (np.mean(rets) / np.std(rets)) * np.sqrt(252) if np.std(rets) > 0 else 0
    else:
        sharpe = 0

    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss) if closed else 0
    recovery = total_pnl / max_dd if max_dd > 0 else 0
    calmar = total_pnl_pct / max_dd_pct if max_dd_pct > 0 else 0
    avg_bars = np.mean([t.bars_held for t in closed]) if closed else 0

    sym_stats = {}
    monthly = {}
    for t in closed:
        if t.symbol not in sym_stats:
            sym_stats[t.symbol] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        sym_stats[t.symbol]["trades"] += 1
        if t.result == "win":
            sym_stats[t.symbol]["wins"] += 1
        else:
            sym_stats[t.symbol]["losses"] += 1
        sym_stats[t.symbol]["pnl"] += t.profit

        mk = t.entry_time.strftime("%Y-%m")
        monthly[mk] = monthly.get(mk, 0.0) + t.profit

    return {
        "trades": closed,
        "equity_curve": equity_points,
        "initial_balance": INITIAL_BALANCE,
        "final_balance": final_balance,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "total_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "profit_factor": pf,
        "max_dd": max_dd,
        "max_dd_pct": max_dd_pct,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
        "avg_rr": avg_rr,
        "sharpe": sharpe,
        "expectancy": expectancy,
        "recovery": recovery,
        "calmar": calmar,
        "avg_bars_held": avg_bars,
        "sym_stats": sym_stats,
        "monthly": monthly,
    }


def _print_results(r):
    w = 64
    print(f"\n\n{'='*w}")
    print(f"{'KINGADE M1-M5 SCALPER - BACKTEST RESULTS':^{w}}")
    print(f"{'Config: M1 Pattern + M1 Trend + Wick SL + Trail + 1:2.5 RR':^{w}}")
    print(f"{'='*w}")

    print(f"\n  {'ACCOUNT SUMMARY':^{w-4}}")
    print(f"  {'-'*(w-4)}")
    print(f"  Initial Balance:      ${r['initial_balance']:>14,.2f}")
    print(f"  Final Balance:        ${r['final_balance']:>14,.2f}")
    print(f"  Net P/L:              ${r['total_pnl']:>14,.2f}  ({r['total_pnl_pct']:+.2f}%)")
    print(f"  Risk Per Trade:       {RISK_PER_TRADE}% | Max Lot: {MAX_LOT}")

    print(f"\n  {'TRADE STATISTICS':^{w-4}}")
    print(f"  {'-'*(w-4)}")
    print(f"  Total Trades:         {r['total_trades']:>10}")
    print(f"  Winning Trades:       {r['wins']:>10}")
    print(f"  Losing Trades:        {r['losses']:>10}")
    print(f"  Win Rate:             {r['win_rate']:>9.1f}%")
    print(f"  Profit Factor:        {r['profit_factor']:>10.2f}")
    print(f"  Avg R:R:              {r['avg_rr']:>10.2f}")
    print(f"  Expectancy/Trade:     ${r['expectancy']:>13,.2f}")
    print(f"  Avg Bars Held:        {r['avg_bars_held']:>10.1f}")

    print(f"\n  {'RISK METRICS':^{w-4}}")
    print(f"  {'-'*(w-4)}")
    print(f"  Max Drawdown:         ${r['max_dd']:>14,.2f}")
    print(f"  Max Drawdown %:       {r['max_dd_pct']:>13.2f}%")
    print(f"  Sharpe Ratio:         {r['sharpe']:>10.2f}")
    print(f"  Recovery Factor:      {r['recovery']:>10.2f}")
    print(f"  Calmar Ratio:         {r['calmar']:>10.2f}")

    print(f"\n  {'WIN/LOSS':^{w-4}}")
    print(f"  {'-'*(w-4)}")
    print(f"  Avg Win:              ${r['avg_win']:>14,.2f}")
    print(f"  Avg Loss:             ${r['avg_loss']:>14,.2f}")
    print(f"  Largest Win:          ${r['largest_win']:>14,.2f}")
    print(f"  Largest Loss:         ${r['largest_loss']:>14,.2f}")

    print(f"\n  {'BY SYMBOL':^{w-4}}")
    print(f"  {'-'*(w-4)}")
    for sym, s in sorted(r["sym_stats"].items(), key=lambda x: x[1]["pnl"], reverse=True):
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] else 0
        print(f"  {sym:<8} | Trades: {s['trades']:>3} | WR: {wr:5.1f}% | P/L: ${s['pnl']:>10,.2f}")

    print(f"\n  {'MONTHLY P/L':^{w-4}}")
    print(f"  {'-'*(w-4)}")
    cum = 0
    for m, pnl in sorted(r["monthly"].items()):
        cum += pnl
        marker = "+++" if pnl > 0 else "---" if pnl < 0 else "==="
        mx = max(abs(x) for x in r["monthly"].values()) if r["monthly"] else 1
        bar_len = min(int(abs(pnl) / mx * 20), 20) if mx > 0 else 0
        bar = ("+" * bar_len if pnl > 0 else "-" * bar_len) if bar_len > 0 else ""
        print(f"  {m}  | ${pnl:>10,.2f} | Cum: ${cum:>12,.2f} | {marker} {bar}")

    ec = r["equity_curve"]
    if len(ec) > 2:
        print(f"\n  {'EQUITY CURVE':^{w-4}}")
        print(f"  {'-'*(w-4)}")
        vals = [p["equity"] for p in ec if p["equity"] is not None]
        if vals:
            step = max(1, len(vals) // 40)
            sampled = vals[::step]
            mn, mx = min(sampled), max(sampled)
            h = 12
            if mx > mn:
                for row in range(h, -1, -1):
                    thresh = mn + (mx - mn) * row / h
                    line = ""
                    for v in sampled:
                        line += "#" if v >= thresh else " "
                    if row == h:
                        lbl = f"  ${mx:>10,.0f} |"
                    elif row == 0:
                        lbl = f"  ${mn:>10,.0f} |"
                    elif row == h // 2:
                        lbl = f"  ${(mx+mn)/2:>10,.0f} |"
                    else:
                        lbl = " " * 14 + "|"
                    print(f"  {lbl}{line}")
                print(f"  {'':>14} +{'-' * len(sampled)}")

    print(f"\n{'='*w}")


if __name__ == "__main__":
    result = run_backtest()
    mt5.shutdown()
