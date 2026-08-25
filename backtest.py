# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
import config
import swing_detector
import fibonacci
import filters

# ─── Backtest Config ──────────────────────────────────────────────
INITIAL_BALANCE = 1000.0
RISK_PER_TRADE = config.RISK_PERCENT
BACKTEST_SYMBOLS = ["XAUUSD", "GBPUSD", "AUDUSD"]
BACKTEST_TIMEFRAMES = [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M15]
BACKTEST_MONTHS = 6  # 6 months
MAX_CONCURRENT_TRADES = 10
MT5_CHUNK_SIZE = 60000  # MT5 limit per request


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
    print(f"MT5 connected | Account: {info.login} | Balance: {info.balance}")


def get_ohlc(symbol, timeframe, count):
    """Fetch OHLC data in chunks to bypass MT5's ~65K bar limit."""
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
    df = pd.DataFrame(np.array(all_rates, dtype=[('time','<i8'),('open','<f8'),('high','<f8'),('low','<f8'),('close','<f8'),('tick_volume','<u8'),('spread','<i4'),('real_volume','<u8')]))
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def get_symbol_tick_value(symbol):
    info = mt5.symbol_info(symbol)
    if info is None:
        return None, None, None
    return info.trade_tick_value, info.trade_tick_size, info.point


def _tf_name(timeframe):
    tf_map = {
        1: "M1", 5: "M5", 15: "M15", 30: "M30",
        16385: "H1", 16388: "H4", 32769: "D1",
    }
    return tf_map.get(timeframe, f"TF{timeframe}")


def _update_trailing_stop(trade, bar, current_atr):
    """Update trailing stop for a profitable trade."""
    if not config.USE_TRAILING_STOP:
        return

    trail_start = current_atr * config.TRAILING_START_ATR
    trail_step = current_atr * config.TRAILING_STEP_ATR

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
    """Return the higher (for buy) or lower (for sell) of original SL and trailing SL."""
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

    # Determine exit price and whether it's a win or loss
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

    # Classify based on actual P/L, not which level was hit
    if trade.direction == "buy":
        trade.result = "win" if trade.exit_price >= trade.entry_price else "loss"
    else:
        trade.result = "win" if trade.exit_price <= trade.entry_price else "loss"

    trade.exit_time = bar["time"]

    # P/L via tick value
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

    bars_needed = 96 * 22 * BACKTEST_MONTHS + 200

    # Pre-fetch H1 data for trend filter
    h1_data = {}
    if config.USE_TREND_FILTER:
        for symbol in BACKTEST_SYMBOLS:
            h1_bars = 96 * 22 * BACKTEST_MONTHS + 200
            h1_df = get_ohlc(symbol, 16385, h1_bars)
            if h1_df is not None and len(h1_df) > config.TREND_EMA_PERIOD + 10:
                h1_ema = filters.calc_ema(h1_df["close"], config.TREND_EMA_PERIOD)
                h1_data[symbol] = {"df": h1_df, "ema": h1_ema}

    # Pre-fetch ATR data per symbol+tf
    atr_cache = {}

    all_trades = []
    balance = INITIAL_BALANCE
    peak_balance = INITIAL_BALANCE
    equity_points = [{"time": None, "equity": INITIAL_BALANCE}]

    total_combos = len(BACKTEST_SYMBOLS) * len(BACKTEST_TIMEFRAMES)
    combo_idx = 0

    for symbol in BACKTEST_SYMBOLS:
        for tf in BACKTEST_TIMEFRAMES:
            combo_idx += 1
            tf_name = _tf_name(tf)
            print(f"\r[{combo_idx}/{total_combos}] {symbol} {tf_name}...", end="", flush=True)

            df = get_ohlc(symbol, tf, bars_needed)
            if df is None or len(df) < config.SWING_LOOKBACK + 30:
                print(f" skipped (insufficient data)")
                continue

            tick_value, tick_size, point = get_symbol_tick_value(symbol)
            if tick_value is None or tick_value == 0:
                print(f" skipped (no tick data)")
                continue

            # Pre-calculate ATR for this symbol+tf
            atr_series = filters.calc_atr(df["high"], df["low"], df["close"], config.ATR_PERIOD)

            print(f" {len(df)} bars | {df.iloc[0]['time'].strftime('%Y-%m-%d')} -> {df.iloc[-1]['time'].strftime('%Y-%m-%d')}")

            start_bar = config.SWING_LOOKBACK + 20
            open_trades = []
            signals_found = 0

            for i in range(start_bar, len(df)):
                current_bar = df.iloc[i]
                current_time = current_bar["time"]
                current_atr = atr_series.iloc[i]

                # ─── Check exits for open trades ─────────────────────
                for trade in open_trades:
                    if trade.result != "open":
                        continue
                    trade.bars_held += 1

                    # Update trailing stop
                    _update_trailing_stop(trade, current_bar, current_atr)

                    # Force close on max bars
                    if trade.bars_held >= config.MAX_BARS_IN_TRADE:
                        _close_trade(trade, current_bar, tick_value, tick_size)
                        balance += trade.profit
                        continue

                    if _check_exit(trade, current_bar):
                        _close_trade(trade, current_bar, tick_value, tick_size)
                        balance += trade.profit

                open_trades = [t for t in open_trades if t.result == "open"]

                # ─── Cap concurrent trades ───────────────────────────
                total_open = sum(1 for t in all_trades if t.result == "open")
                if total_open >= MAX_CONCURRENT_TRADES:
                    continue

                if open_trades:
                    continue

                # ─── Swing detection ─────────────────────────────────
                window = df.iloc[max(0, i - config.SWING_LOOKBACK - 20):i + 1]

                move = swing_detector.detect_current_move(window)
                if move is None:
                    continue

                direction = move["direction"]
                sh_price = move["swing_high"][1]
                sl_price = move["swing_low"][1]

                levels = fibonacci.calculate_retracement_levels(sh_price, sl_price, direction)
                if levels is None:
                    continue

                entry_zone = fibonacci.get_entry_zone(levels, direction)
                if entry_zone is None:
                    continue

                prev_bar = df.iloc[i - 1]
                prev_close = prev_bar["close"]

                if not fibonacci.is_price_in_entry_zone(prev_close, entry_zone):
                    continue

                # ─── Confirmation ────────────────────────────────────
                if config.REQUIRE_CONFIRMATION:
                    if direction == "bullish" and prev_close < entry_zone["entry_zone_low"]:
                        continue
                    if direction == "bearish" and prev_close > entry_zone["entry_zone_high"]:
                        continue

                # ─── Trend filter ────────────────────────────────────
                if config.USE_TREND_FILTER and symbol in h1_data:
                    h1_info = h1_data[symbol]
                    h1_df = h1_info["df"]
                    h1_ema = h1_info["ema"]
                    h1_idx = h1_df["time"].searchsorted(current_time, side="right") - 1
                    if h1_idx > 0 and h1_idx < len(h1_df):
                        h1_price = h1_df.iloc[h1_idx]["close"]
                        h1_ema_val = h1_ema.iloc[h1_idx]
                        h1_ema_prev = h1_ema.iloc[h1_idx - 1]
                        ema_rising = h1_ema_val > h1_ema_prev
                        ema_falling = h1_ema_val < h1_ema_prev
                        if direction == "bullish" and not (h1_price > h1_ema_val or ema_rising):
                            continue
                        if direction == "bearish" and not (h1_price < h1_ema_val or ema_falling):
                            continue

                # ─── Momentum filter ─────────────────────────────────
                if config.USE_MOMENTUM_FILTER:
                    rsi = filters.calc_rsi(window["close"], config.RSI_PERIOD)
                    current_rsi = rsi.iloc[-2]
                    if direction == "bullish" and current_rsi > config.RSI_OVERSOLD:
                        continue
                    if direction == "bearish" and current_rsi < config.RSI_OVERBOUGHT:
                        continue
                    body = abs(prev_bar["close"] - prev_bar["open"])
                    total_range = prev_bar["high"] - prev_bar["low"]
                    if total_range > 0 and (body / total_range) < config.MIN_BODY_RATIO:
                        continue

                # ─── ATR-based SL + TP ──────────────────────────────
                if config.USE_ATR_SL:
                    atr_sl_dist = current_atr * config.ATR_SL_MULTIPLIER
                    if direction == "bullish":
                        atr_sl = prev_close - atr_sl_dist
                    else:
                        atr_sl = prev_close + atr_sl_dist
                else:
                    atr_sl = entry_zone["sl"]

                # Scalper TP: use ATR-based TP (tighter than fib extension)
                atr_tp_dist = current_atr * config.ATR_TP_MULTIPLIER
                if direction == "bullish":
                    atr_tp = prev_close + atr_tp_dist
                else:
                    atr_tp = prev_close - atr_tp_dist

                # Lot sizing
                sl_dist = abs(prev_close - atr_sl)
                if sl_dist == 0 or tick_size == 0 or tick_value == 0:
                    continue

                risk_amount = min(balance * RISK_PER_TRADE / 100.0, INITIAL_BALANCE * RISK_PER_TRADE / 100.0)
                sl_ticks = sl_dist / tick_size
                lot_size = risk_amount / (sl_ticks * tick_value)
                lot_size = max(0.01, round(lot_size, 2))
                lot_size = min(1.0, lot_size)  # Cap at 1.0 lot for realism

                trade = Trade(
                    symbol=symbol,
                    timeframe=tf,
                    direction=entry_zone["direction"],
                    entry_price=prev_close,
                    sl=atr_sl,
                    tp1=atr_tp,
                    entry_time=current_time,
                    lot_size=lot_size,
                )
                open_trades.append(trade)
                all_trades.append(trade)
                signals_found += 1

                # Track equity
                unrealized = 0
                for t in open_trades:
                    if t.direction == "buy":
                        unrealized += (current_bar["close"] - t.entry_price) * t.lot_size * 100000
                    else:
                        unrealized += (t.entry_price - current_bar["close"]) * t.lot_size * 100000

                equity_points.append({
                    "time": current_time,
                    "equity": balance + unrealized,
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

    # Avg R:R
    rr = []
    for t in closed:
        risk = abs(t.entry_price - t.sl)
        if risk > 0:
            reward = abs(t.exit_price - t.entry_price)
            rr.append(reward / risk)
    avg_rr = np.mean(rr) if rr else 0

    # Drawdown
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

    # Sharpe
    if len(closed) > 1:
        rets = [t.profit / INITIAL_BALANCE for t in closed]
        sharpe = (np.mean(rets) / np.std(rets)) * np.sqrt(252) if np.std(rets) > 0 else 0
    else:
        sharpe = 0

    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss) if closed else 0
    recovery = total_pnl / max_dd if max_dd > 0 else 0
    calmar = total_pnl_pct / max_dd_pct if max_dd_pct > 0 else 0

    # Avg bars held
    avg_bars = np.mean([t.bars_held for t in closed]) if closed else 0

    # Breakdowns
    sym_stats = {}
    tf_stats = {}
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

        tf_n = _tf_name(t.timeframe)
        if tf_n not in tf_stats:
            tf_stats[tf_n] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        tf_stats[tf_n]["trades"] += 1
        if t.result == "win":
            tf_stats[tf_n]["wins"] += 1
        else:
            tf_stats[tf_n]["losses"] += 1
        tf_stats[tf_n]["pnl"] += t.profit

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
        "tf_stats": tf_stats,
        "monthly": monthly,
    }


def _print_results(r):
    w = 64
    print(f"\n\n{'='*w}")
    print(f"{'KINGADE SCALPER BOT - BACKTEST RESULTS':^{w}}")
    print(f"{'='*w}")

    print(f"\n  {'ACCOUNT SUMMARY':^{w-4}}")
    print(f"  {'-'*(w-4)}")
    print(f"  Initial Balance:      ${r['initial_balance']:>14,.2f}")
    print(f"  Final Balance:        ${r['final_balance']:>14,.2f}")
    print(f"  Net P/L:              ${r['total_pnl']:>14,.2f}  ({r['total_pnl_pct']:+.2f}%)")
    print(f"  Risk Per Trade:       {RISK_PER_TRADE}%")

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

    print(f"\n  {'BY TIMEFRAME':^{w-4}}")
    print(f"  {'-'*(w-4)}")
    for tf_n, s in sorted(r["tf_stats"].items()):
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] else 0
        print(f"  {tf_n:<6} | Trades: {s['trades']:>3} | WR: {wr:5.1f}% | P/L: ${s['pnl']:>10,.2f}")

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
        bar_len = min(int(abs(pnl) / max(abs(x) for x in r["monthly"].values()) * 20) if r["monthly"] else 0, 20)
        bar = ("+" * bar_len if pnl > 0 else "-" * bar_len) if bar_len > 0 else ""
        print(f"  {m}  | ${pnl:>10,.2f} | Cum: ${cum:>12,.2f} | {marker} {bar}")

    # Equity curve
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
