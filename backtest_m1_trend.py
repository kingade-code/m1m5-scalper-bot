# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Backtest matching live bot config: M1 pattern + M1 EMA10/100 trend + wick SL + reverse close + trailing + 1:4.0 RR"""
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
import swing_detector

# ─── Backtest Config ──────────────────────────────────────────────
INITIAL_BALANCE = 500.0
RISK_PER_TRADE = config.RISK_PERCENT  # 4%
MAX_LOT = config.MAX_LOT  # 0.10
MAX_RISK_DOLLARS = config.MAX_RISK_PER_TRADE  # $20
BACKTEST_SYMBOLS = ["XAUUSD"]
BACKTEST_TIMEFRAMES = [mt5.TIMEFRAME_M1]
BACKTEST_MONTHS = 3  # ~3 weeks
MT5_CHUNK_SIZE = 60000

# Trend filter TF. "m1" = M1 EMAs (matches live check_trend_filter),
# matching live exactly but limited to the M1 data depth. "own" = EMA on
# the signal timeframe's own bars -- self-consistent for long windows.
TREND_TF = mt5.TIMEFRAME_M1
TREND_TF_MODE = "m1"  # "m1" | "own"

# Live cooldown is 600 SECONDS (10 min) regardless of timeframe.
TRADE_COOLDOWN_SECONDS = config.TRADE_COOLDOWN_SECONDS  # live parity

# Trailing config (read live per-symbol override so backtest == live behavior)
TRAIL_START_ATR = config.get_symbol_param("XAUUSD", "TRAILING_START_ATR", config.TRAILING_START_ATR)  # live: 0.3
TRAIL_STEP_ATR = config.get_symbol_param("XAUUSD", "TRAILING_STEP_ATR", config.TRAILING_STEP_ATR)     # live: 0.1
USE_TRAILING = config.USE_TRAILING_STOP

# Open RR + RR-step trailing (live == config). When ON, there is no fixed
# TP (1:infinity) and the ATR trail is bypassed; the stop ratchets to
# (milestone - RR_TRAIL_LOCK_R)*R at every RR_TRAIL_STEP_R milestone
# starting at RR_TRAIL_START_R.
USE_OPEN_RR = config.USE_OPEN_RR
RR_TRAIL_START_R = config.RR_TRAIL_START_R
RR_TRAIL_STEP_R = config.RR_TRAIL_STEP_R
RR_TRAIL_LOCK_R = config.RR_TRAIL_LOCK_R

# ─── A/B flags (overridden via CLI, see __main__) ─────────────────-
WICK_GUARD = 0.0  # 0 = disabled; skip entry if forming bar pierced signal wick +/- this many price units
ATR_GATE = 0.0    # 0 = disabled; skip entry if ATR(14) > this value
SEND_REPORT = True  # set False with --no-report to skip PDF + Telegram
RUN_LABEL = "baseline"
MAX_BARS = config.MAX_BARS_IN_TRADE  # 15
RR_RATIO = 4.0
# Breakeven-protect floor (default OFF): when a trade reaches
# BE_PROTECT_AT_RR*SL distance of profit, the stop ratchets to
# entry +/- BE_FLOOR (price units; 1 XAUUSD "pip" ~ 0.10), guaranteeing a
# tiny winner while the rest runs toward the R:R target.
USE_BE_PROTECT = 0  # 0 = disabled
BE_PROTECT_AT_RR = 2.0
BE_FLOOR = 0.20  # ~2 pips on XAUUSD
PIP_BUFFER = config.get_symbol_param("XAUUSD", "SL_PIP_BUFFER", 0.5)  # 5 pips
USE_REVERSE_CLOSE = config.USE_REVERSE_CLOSE
REVERSE_CLOSE_DISTANCE = config.get_symbol_param("XAUUSD", "REVERSE_CLOSE_DISTANCE", 0.2)

# A/B: Range-edge (mean-reversion mode) gate ────────────────────
# RELAX_TREND=True  -> skip the EMA10/100 trend filter entirely.
# RANGE_EDGE_ATR>0  -> require entry price within N*ATR of the current
#                      move's swing LOW (buys) / swing HIGH (sells).
# Together they turn the bot from trend-continuation into pure
# fade-the-range-edge mean reversion.
RELAX_TREND = False
RANGE_EDGE_ATR = 0.0  # 0 = disabled
RANGE_EDGE_LOOKBACK = None  # None => per-symbol SWING_LOOKBACK

# Real-world cost per round trip, in price units (XAUUSD ~0.25-0.50).
# Charged as a full-spread penalty on the trade's exit price.
SPREAD_PRICE = 0.0  # 0 = idealized fills (backwards compatible)
# Additional slippage on stop-loss exits (price skips through the level).
# Combined realistic friction = SPREAD_PRICE + SLIP_PRICE on SL losers.
SLIP_PRICE = 0.0


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
    signal_wick: Optional[float] = None


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
    if USE_OPEN_RR:
        return  # RR-step trail replaces ATR trailing
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


def _update_be_protect(trade, bar):
    """Breakeven-protect floor: once profit >= BE_PROTECT_AT_RR * SL distance,
    ratchet the stop to entry +/- BE_FLOOR (lock a small win)."""
    if not USE_BE_PROTECT:
        return
    sl_distance = abs(trade.entry_price - trade.sl)
    if sl_distance <= 0:
        return
    if trade.direction == "buy":
        unrealized = bar["high"] - trade.entry_price
        if unrealized >= BE_PROTECT_AT_RR * sl_distance:
            floor = trade.entry_price + BE_FLOOR
            if trade.trailing_sl is None or floor > trade.trailing_sl:
                trade.trailing_sl = floor
    else:
        unrealized = trade.entry_price - bar["low"]
        if unrealized >= BE_PROTECT_AT_RR * sl_distance:
            floor = trade.entry_price - BE_FLOOR
            if trade.trailing_sl is None or floor < trade.trailing_sl:
                trade.trailing_sl = floor


def _update_rr_trail(trade, bar):
    """Open-RR ratchet: once unrealized profit reaches RR_TRAIL_START_R*SL,
    the stop locks (milestone - RR_TRAIL_LOCK_R)*R every RR_TRAIL_STEP_R R."""
    if not USE_OPEN_RR:
        return
    sl_distance = abs(trade.entry_price - trade.sl)
    if sl_distance <= 0:
        return
    if trade.direction == "buy":
        unrealized = bar["high"] - trade.entry_price
    else:
        unrealized = trade.entry_price - bar["low"]
    if unrealized <= 0:
        return
    rr = unrealized / sl_distance
    if rr < RR_TRAIL_START_R:
        return
    milestone = RR_TRAIL_START_R + (
        (rr - RR_TRAIL_START_R) // RR_TRAIL_STEP_R
    ) * RR_TRAIL_STEP_R
    lock_r = milestone - RR_TRAIL_LOCK_R
    if lock_r <= 0:
        return
    if trade.direction == "buy":
        lock_price = trade.entry_price + lock_r * sl_distance
        if trade.trailing_sl is None or lock_price > trade.trailing_sl:
            trade.trailing_sl = lock_price
    else:
        lock_price = trade.entry_price - lock_r * sl_distance
        if trade.trailing_sl is None or lock_price < trade.trailing_sl:
            trade.trailing_sl = lock_price


def _get_effective_sl(trade):
    if trade.trailing_sl is None:
        return trade.sl
    if trade.direction == "buy":
        return max(trade.sl, trade.trailing_sl)
    else:
        return min(trade.sl, trade.trailing_sl)


def _range_edge_ok(win, direction, price, atr):
    """True when price sits within RANGE_EDGE_ATR*ATR of the current move's
    swing extreme (the edge of the recent range). Closed bars only -- the
    forming bar is excluded by the caller, so there is no look-ahead."""
    if win is None or len(win) < 12:
        return False
    lookback = RANGE_EDGE_LOOKBACK or config.get_symbol_param(
        "XAUUSD", "SWING_LOOKBACK", config.SWING_LOOKBACK
    )
    move = swing_detector.detect_current_move(win, lookback=lookback)
    if move is None:
        return False
    edge = move["swing_low"][1] if direction == "bullish" else move["swing_high"][1]
    return abs(price - edge) <= RANGE_EDGE_ATR * atr


def _reverse_close_triggered(trade, bar):
    """True if price reversed toward SL and reached the signal wick."""
    if not USE_REVERSE_CLOSE or trade.signal_wick is None:
        return False
    if trade.direction == "buy":
        return (
            bar["close"] < trade.entry_price
            and bar["low"] <= trade.signal_wick + REVERSE_CLOSE_DISTANCE
        )
    else:
        return (
            bar["close"] > trade.entry_price
            and bar["high"] >= trade.signal_wick - REVERSE_CLOSE_DISTANCE
        )


def _check_exit(trade, bar):
    eff_sl = _get_effective_sl(trade)
    if _reverse_close_triggered(trade, bar):
        return True
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
    exit_reason = "close"
    if _reverse_close_triggered(trade, bar):
        trade.exit_price = bar["close"]
        exit_reason = "reverse"
    elif trade.direction == "buy":
        if bar["low"] <= eff_sl:
            trade.exit_price = eff_sl
            exit_reason = "sl"
        elif bar["high"] >= trade.tp1:
            trade.exit_price = trade.tp1
            exit_reason = "tp"
        else:
            trade.exit_price = bar["close"]
    else:
        if bar["high"] >= eff_sl:
            trade.exit_price = eff_sl
            exit_reason = "sl"
        elif bar["low"] <= trade.tp1:
            trade.exit_price = trade.tp1
            exit_reason = "tp"
        else:
            trade.exit_price = bar["close"]

    if SPREAD_PRICE > 0:
        # Charge the full spread against the exit. Buy exits on the bid
        # (exit - spread/2) having entered on the ask (+ spread/2); sell
        # the mirror. Net: exit_price pushed a full spread against us.
        if trade.direction == "buy":
            trade.exit_price -= SPREAD_PRICE
        else:
            trade.exit_price += SPREAD_PRICE

    if SLIP_PRICE > 0 and exit_reason == "sl":
        # Stops get filled worse than the quoted level in live markets.
        if trade.direction == "buy":
            trade.exit_price -= SLIP_PRICE
        else:
            trade.exit_price += SLIP_PRICE

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

    # Pre-fetch trend data. "m1" mode: a single M1 EMA set used for every
    # timeframe (== live). "own" mode: EMA computed on each signal TF's own
    # bars inside the per-TF loop, so long windows don't lose the filter.
    trend_data = {}  # {(symbol, tf): {"df": df, "fast": ..., "slow": ...}}
    if config.USE_TREND_FILTER and not RELAX_TREND and TREND_TF_MODE == "m1":
        for symbol in BACKTEST_SYMBOLS:
            trend_bars = bars_needed
            trend_df = get_ohlc(symbol, TREND_TF, trend_bars)
            if trend_df is not None and len(trend_df) > 160:
                fast_ema = filters.calc_ema(trend_df["close"], 10)
                slow_ema = filters.calc_ema(trend_df["close"], 100)
                for tf in BACKTEST_TIMEFRAMES:
                    trend_data[(symbol, tf)] = {
                        "df": trend_df, "fast": fast_ema, "slow": slow_ema
                    }

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
                    _update_rr_trail(trade, current_bar)
                    _update_be_protect(trade, current_bar)

                    if trade.bars_held >= MAX_BARS:
                        _close_trade(trade, current_bar, tick_value, tick_size)
                        balance += trade.profit
                        continue

                    if _check_exit(trade, current_bar):
                        _close_trade(trade, current_bar, tick_value, tick_size)
                        balance += trade.profit

                open_trades = [t for t in open_trades if t.result == "open"]

                # Cooldown: live skips a symbol for TRADE_COOLDOWN_SECONDS
                # (600s = 10 min) after its last entry, on any timeframe.
                if symbol in last_trade_time:
                    elapsed = (current_time - last_trade_time[symbol]).total_seconds()
                    if elapsed < TRADE_COOLDOWN_SECONDS:
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

                # ─── Trend filter (EMA10/EMA100) ────────────────────────
                if config.USE_TREND_FILTER and not RELAX_TREND:
                    if TREND_TF_MODE == "own":
                        trend_data[(symbol, tf)] = {
                            "df": df, "fast": filters.calc_ema(df["close"], 10),
                            "slow": filters.calc_ema(df["close"], 100),
                        }
                    t_info = trend_data.get((symbol, tf))
                    if t_info is not None:
                        t_df = t_info["df"]
                        t_fast = t_info["fast"]
                        t_slow = t_info["slow"]
                        t_idx = t_df["time"].searchsorted(current_time, side="right") - 1
                        if t_idx > 0 and t_idx < len(t_df):
                            t_price = t_df.iloc[t_idx]["close"]
                            f_val = t_fast.iloc[t_idx]
                            s_val = t_slow.iloc[t_idx]
                            uptrend = f_val > s_val
                            downtrend = f_val < s_val
                            if direction == "bullish" and not (uptrend and t_price > f_val):
                                continue
                            if direction == "bearish" and not (downtrend and t_price < f_val):
                                continue

                # ─── Wick SL (prev bar low/high) - 5 pip buffer ───────
                signal_wick = prev_bar["low"] if direction == "bullish" else prev_bar["high"]
                if direction == "bullish":
                    swing_sl = signal_wick - PIP_BUFFER
                else:
                    swing_sl = signal_wick + PIP_BUFFER

                # ─── A/B: Wick-pierce guard ────────────────────────────
                # Skip if the forming (current) bar already moved against
                # the signal toward the wick/SL before entry.
                if WICK_GUARD > 0:
                    if direction == "bullish" and current_bar["low"] <= signal_wick + WICK_GUARD:
                        continue
                    if direction == "bearish" and current_bar["high"] >= signal_wick - WICK_GUARD:
                        continue

                # ─── A/B: ATR volatility gate ──────────────────────────
                # Skip entries taken into high-volatility states that tend
                # to run straight to the stop.
                if ATR_GATE > 0 and current_atr > ATR_GATE:
                    continue

                # ─── A/B: Range-edge gate (mean-reversion mode, M1 only) ─────────
                # Live applies this gate on M1 exclusively (signal_engine
                # `_analyze_pattern`), so the backtest does too.
                if RANGE_EDGE_ATR > 0 and tf == mt5.TIMEFRAME_M1:
                    swing_window = df.iloc[max(0, i - 150):i]
                    if not _range_edge_ok(swing_window, direction, prev_close, current_atr):
                        continue

                sl_dist = abs(prev_close - swing_sl)
                if sl_dist < config.MIN_STOP_DISTANCE:
                    continue

                # ─── TP: 1:4.0 RR ───────────────────────────────────
                if USE_OPEN_RR:
                    atr_tp = float("inf") if signal_direction == "buy" else float("-inf")
                else:
                    tp_dist = sl_dist * RR_RATIO
                    if direction == "bullish":
                        atr_tp = prev_close + tp_dist
                    else:
                        atr_tp = prev_close - tp_dist

                # ─── Lot sizing (4% risk, max $20, max 0.10 lot) ──────
                risk_amount = balance * RISK_PER_TRADE / 100.0
                risk_amount = min(risk_amount, MAX_RISK_DOLLARS)
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
                    signal_wick=signal_wick,
                )
                open_trades.append(trade)
                all_trades.append(trade)
                signals_found += 1
                last_trade_time[symbol] = current_time

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
    weekly = {}
    daily = {}
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
        monthly[mk] = monthly.get(mk, {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        monthly[mk]["trades"] += 1
        if t.result == "win":
            monthly[mk]["wins"] += 1
        else:
            monthly[mk]["losses"] += 1
        monthly[mk]["pnl"] += t.profit

        wk = t.entry_time.strftime("%Y-W%W")
        weekly[wk] = weekly.get(wk, {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        weekly[wk]["trades"] += 1
        if t.result == "win":
            weekly[wk]["wins"] += 1
        else:
            weekly[wk]["losses"] += 1
        weekly[wk]["pnl"] += t.profit

        dk = t.entry_time.strftime("%Y-%m-%d")
        daily[dk] = daily.get(dk, {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        daily[dk]["trades"] += 1
        if t.result == "win":
            daily[dk]["wins"] += 1
        else:
            daily[dk]["losses"] += 1
        daily[dk]["pnl"] += t.profit

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
        "weekly": weekly,
        "daily": daily,
    }


def _print_results(r):
    w = 64
    print(f"\n\n{'='*w}")
    print(f"{'KINGADE M1-M5 SCALPER - BACKTEST RESULTS':^{w}}")
    print(f"{'Config: M1 Pattern + M1 Trend + Wick SL + Reverse Close + Trail + 1:4.0 RR':^{w}}")
    print(f"{'='*w}")

    print(f"\n  {'ACCOUNT SUMMARY':^{w-4}}")
    print(f"  {'-'*(w-4)}")
    print(f"  Initial Balance:      ${r['initial_balance']:>14,.2f}")
    print(f"  Final Balance:        ${r['final_balance']:>14,.2f}")
    print(f"  Net P/L:              ${r['total_pnl']:>14,.2f}  ({r['total_pnl_pct']:+.2f}%)")
    print(f"  Risk Per Trade:       {RISK_PER_TRADE}% | Max Lot: {MAX_LOT} | Max Risk: ${MAX_RISK_DOLLARS}")

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
    for m, data in sorted(r["monthly"].items()):
        pnl = data["pnl"]
        cum += pnl
        marker = "+++" if pnl > 0 else "---" if pnl < 0 else "==="
        print(f"  {m}  | {data['trades']} trades | WR {data['wins']/data['trades']*100:.0f}% | ${pnl:>10,.2f} | Cum: ${cum:>12,.2f}")

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
    import argparse

    p = argparse.ArgumentParser(description="Kingade backtest (A/B variant runner)")
    p.add_argument("--trail-start", type=float, default=None, help="override TRAIL_START_ATR")
    p.add_argument("--trail-step", type=float, default=None, help="override TRAIL_STEP_ATR")
    p.add_argument("--wick-guard", type=float, default=None, help="None=config; skip if forming bar pierced signal wick")
    p.add_argument("--atr-gate", type=float, default=None, help="None=config; skip if ATR(14) > value")
    p.add_argument("--range-edge", type=float, default=None, help="None=config; require entry within N*ATR of a range extreme")
    p.add_argument("--relax-trend", action="store_true", help="skip the EMA10/100 trend filter (mean-reversion mode)")
    def _tf_arg(s):
        vals = [x for x in s.split(",") if x]
        for v in vals:
            if v not in ("M1", "M5"):
                raise argparse.ArgumentTypeError(f"unknown timeframe {v!r}")
        return vals

    p.add_argument("--tf", type=_tf_arg, default=["M1", "M5"], help="timeframes to backtest (comma list, default both as live)")
    p.add_argument("--symbol", default="XAUUSD", help="comma-separated symbols (default XAUUSD)")
    p.add_argument("--months", type=int, default=3, help="backtest lookback in months (7 = ~3.5 months of M1 depth)")
    p.add_argument("--force-pattern", action="store_true", help="use pattern entry mode for all symbols (needed for non-gold)")
    p.add_argument("--max-bars", type=int, default=None, help="None=config; force-close after N M1 bars in trade")
    p.add_argument("--trend-tf", choices=["m1", "own"], default="m1",
                   help="trend filter data: 'm1' (matches live) or 'own' (EMA on signal TF's bars)")
    p.add_argument("--spread", type=float, default=None,
                   help="None=config; round-trip spread cost in price units (0 = idealized)")
    p.add_argument("--slip", type=float, default=None,
                   help="None=config; extra slippage on stop-loss fills in price units")
    p.add_argument("--label", default="", help="variant label for report")
    p.add_argument("--no-report", action="store_true", help="skip PDF + Telegram send")
    args = p.parse_args()

    tf_map = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5}
    BACKTEST_TIMEFRAMES = [tf_map[x] for x in args.tf]
    BACKTEST_SYMBOLS = [s.strip() for s in args.symbol.split(",") if s.strip()]
    BACKTEST_MONTHS = args.months
    if args.force_pattern:
        config.ENTRY_MODE = "pattern"  # process-local; live config untouched
    if args.max_bars is not None:
        MAX_BARS = args.max_bars
    TREND_TF_MODE = args.trend_tf
    if args.spread is not None:
        SPREAD_PRICE = args.spread
    if args.slip is not None:
        SLIP_PRICE = args.slip

    if args.trail_start is not None:
        TRAIL_START_ATR = args.trail_start
    if args.trail_step is not None:
        TRAIL_STEP_ATR = args.trail_step
    WICK_GUARD = args.wick_guard if args.wick_guard is not None else config.get_symbol_param("XAUUSD", "WICK_GUARD", 0.0)
    ATR_GATE = args.atr_gate if args.atr_gate is not None else config.get_symbol_param("XAUUSD", "ATR_GATE", 0.0)
    RELAX_TREND = args.relax_trend
    RANGE_EDGE_ATR = args.range_edge if args.range_edge is not None else config.get_symbol_param("XAUUSD", "RANGE_EDGE_ATR", 0.0)
    RUN_LABEL = args.label
    SEND_REPORT = not args.no_report

    print(f"A/B variant: {RUN_LABEL or 'baseline'}"
          f" | trail {TRAIL_START_ATR}/{TRAIL_STEP_ATR}"
          f" | wick-guard {WICK_GUARD} | atr-gate {ATR_GATE}"
          f" | range-edge {RANGE_EDGE_ATR} | relax-trend {RELAX_TREND}")

    result = run_backtest()
    mt5.shutdown()

    # Generate PDF report
    if result and SEND_REPORT:
        from fpdf import FPDF
        import telegram_notifier as tg
        from datetime import datetime

        r = result

        class PDF(FPDF):
            def header(self):
                self.set_font("Helvetica", "B", 20)
                self.set_text_color(255, 140, 0)
                self.cell(0, 12, "KINGADE SCALPER BOT", new_x="LMARGIN", new_y="NEXT", align="C")
                self.set_font("Helvetica", "", 10)
                self.set_text_color(100, 100, 100)
                self.cell(0, 6, "Backtest Performance Report", new_x="LMARGIN", new_y="NEXT", align="C")
                self.cell(0, 5, "EMA(10)/EMA(100) Trend | M1 Pattern | Wick SL | Reverse Close | 1:4.0 RR", new_x="LMARGIN", new_y="NEXT", align="C")
                self.cell(0, 5, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT", align="C")
                self.ln(2)
                self.set_draw_color(255, 140, 0)
                self.set_line_width(0.8)
                self.line(10, self.get_y(), 200, self.get_y())
                self.ln(4)

            def footer(self):
                self.set_y(-15)
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(150, 150, 150)
                self.cell(0, 10, f"Kingade Forex | {self.page_no()}", align="C")

            def section_title(self, title):
                self.set_font("Helvetica", "B", 13)
                self.set_text_color(255, 140, 0)
                self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
                self.set_draw_color(255, 140, 0)
                self.set_line_width(0.3)
                self.line(10, self.get_y(), 80, self.get_y())
                self.ln(3)

            def stat_row(self, label, value, bold=False):
                self.set_font("Helvetica", "B" if bold else "", 10)
                self.set_text_color(50, 50, 50)
                self.cell(80, 6, label)
                self.set_font("Helvetica", "B" if bold else "", 10)
                self.set_text_color(0, 0, 0)
                self.cell(0, 6, str(value), new_x="LMARGIN", new_y="NEXT")

        pdf = PDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        # A/B variant label
        if RUN_LABEL not in ("", "baseline"):
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 8, f"Variant: {RUN_LABEL}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        # Account Summary
        pdf.section_title("ACCOUNT SUMMARY")
        pdf.stat_row("Initial Balance", f"${r['initial_balance']:,.2f}")
        pdf.stat_row("Final Balance", f"${r['final_balance']:,.2f}")
        pdf.stat_row("Net P/L", f"${r['total_pnl']:+,.2f} ({r['total_pnl_pct']:+.1f}%)", bold=True)
        pdf.stat_row("Risk Per Trade", f"{RISK_PER_TRADE}% | Max Lot: {MAX_LOT} | Max Risk: ${MAX_RISK_DOLLARS}")
        pdf.ln(4)

        # Trade Statistics
        pdf.section_title("TRADE STATISTICS")
        pdf.stat_row("Total Trades", str(r['total_trades']))
        pdf.stat_row("Winning / Losing", f"{r['wins']} / {r['losses']}")
        pdf.stat_row("Win Rate", f"{r['win_rate']:.1f}%", bold=True)
        pdf.stat_row("Profit Factor", f"{r['profit_factor']:.2f}", bold=True)
        pdf.stat_row("Avg R:R", f"{r['avg_rr']:.2f}")
        pdf.stat_row("Expectancy/Trade", f"${r['expectancy']:+,.2f}")
        pdf.stat_row("Avg Bars Held", f"{r['avg_bars_held']:.1f}")
        pdf.ln(4)

        # Risk Metrics
        pdf.section_title("RISK METRICS")
        pdf.stat_row("Max Drawdown", f"${r['max_dd']:,.2f} ({r['max_dd_pct']:.1f}%)")
        pdf.stat_row("Sharpe Ratio", f"{r['sharpe']:.2f}")
        pdf.stat_row("Recovery Factor", f"{r['recovery']:.2f}")
        pdf.stat_row("Calmar Ratio", f"{r['calmar']:.2f}")
        pdf.ln(4)

        # Win/Loss
        pdf.section_title("WIN / LOSS")
        pdf.stat_row("Avg Win", f"${r['avg_win']:+,.2f}")
        pdf.stat_row("Avg Loss", f"${r['avg_loss']:+,.2f}")
        pdf.stat_row("Largest Win", f"${r['largest_win']:+,.2f}")
        pdf.stat_row("Largest Loss", f"${r['largest_loss']:+,.2f}")
        pdf.ln(4)

        # By Symbol
        pdf.section_title("BY SYMBOL")
        for sym, s in sorted(r["sym_stats"].items(), key=lambda x: x[1]["pnl"], reverse=True):
            wr = (s["wins"] / s["trades"] * 100) if s["trades"] else 0
            pdf.stat_row(sym, f"{s['trades']} trades | WR {wr:.1f}% | P/L ${s['pnl']:+,.2f}")
        pdf.ln(4)

        # Daily Breakdown
        pdf.add_page()
        pdf.section_title("DAILY BREAKDOWN")
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(30, 6, "Date", border=1, fill=True)
        pdf.cell(20, 6, "Trades", border=1, fill=True, align="C")
        pdf.cell(20, 6, "Wins", border=1, fill=True, align="C")
        pdf.cell(20, 6, "Losses", border=1, fill=True, align="C")
        pdf.cell(25, 6, "WR%", border=1, fill=True, align="C")
        pdf.cell(35, 6, "P/L", border=1, fill=True, align="C")
        pdf.cell(0, 6, "Cum P/L", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        cum = 0
        for dk in sorted(r["daily"].keys()):
            d = r["daily"][dk]
            cum += d["pnl"]
            wr = (d["wins"] / d["trades"] * 100) if d["trades"] else 0
            pdf.cell(30, 5, dk, border=1)
            pdf.cell(20, 5, str(d["trades"]), border=1, align="C")
            pdf.cell(20, 5, str(d["wins"]), border=1, align="C")
            pdf.cell(20, 5, str(d["losses"]), border=1, align="C")
            pdf.cell(25, 5, f"{wr:.0f}%", border=1, align="C")
            pnl_color = (0, 150, 0) if d["pnl"] >= 0 else (200, 0, 0)
            pdf.set_text_color(*pnl_color)
            pdf.cell(35, 5, f"${d['pnl']:+,.2f}", border=1, align="C")
            pdf.cell(0, 5, f"${cum:+,.2f}", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

        # Weekly Breakdown
        pdf.section_title("WEEKLY BREAKDOWN")
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(30, 6, "Week", border=1, fill=True)
        pdf.cell(20, 6, "Trades", border=1, fill=True, align="C")
        pdf.cell(20, 6, "Wins", border=1, fill=True, align="C")
        pdf.cell(20, 6, "Losses", border=1, fill=True, align="C")
        pdf.cell(25, 6, "WR%", border=1, fill=True, align="C")
        pdf.cell(35, 6, "P/L", border=1, fill=True, align="C")
        pdf.cell(0, 6, "Cum P/L", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        cum = 0
        for wk in sorted(r["weekly"].keys()):
            w = r["weekly"][wk]
            cum += w["pnl"]
            wr = (w["wins"] / w["trades"] * 100) if w["trades"] else 0
            pdf.cell(30, 5, wk, border=1)
            pdf.cell(20, 5, str(w["trades"]), border=1, align="C")
            pdf.cell(20, 5, str(w["wins"]), border=1, align="C")
            pdf.cell(20, 5, str(w["losses"]), border=1, align="C")
            pdf.cell(25, 5, f"{wr:.0f}%", border=1, align="C")
            pnl_color = (0, 150, 0) if w["pnl"] >= 0 else (200, 0, 0)
            pdf.set_text_color(*pnl_color)
            pdf.cell(35, 5, f"${w['pnl']:+,.2f}", border=1, align="C")
            pdf.cell(0, 5, f"${cum:+,.2f}", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

        # Monthly Breakdown
        pdf.section_title("MONTHLY BREAKDOWN")
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(30, 6, "Month", border=1, fill=True)
        pdf.cell(20, 6, "Trades", border=1, fill=True, align="C")
        pdf.cell(20, 6, "Wins", border=1, fill=True, align="C")
        pdf.cell(20, 6, "Losses", border=1, fill=True, align="C")
        pdf.cell(25, 6, "WR%", border=1, fill=True, align="C")
        pdf.cell(35, 6, "P/L", border=1, fill=True, align="C")
        pdf.cell(0, 6, "Cum P/L", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        cum = 0
        for mk in sorted(r["monthly"].keys()):
            m = r["monthly"][mk]
            cum += m["pnl"]
            wr = (m["wins"] / m["trades"] * 100) if m["trades"] else 0
            pdf.cell(30, 5, mk, border=1)
            pdf.cell(20, 5, str(m["trades"]), border=1, align="C")
            pdf.cell(20, 5, str(m["wins"]), border=1, align="C")
            pdf.cell(20, 5, str(m["losses"]), border=1, align="C")
            pdf.cell(25, 5, f"{wr:.0f}%", border=1, align="C")
            pnl_color = (0, 150, 0) if m["pnl"] >= 0 else (200, 0, 0)
            pdf.set_text_color(*pnl_color)
            pdf.cell(35, 5, f"${m['pnl']:+,.2f}", border=1, align="C")
            pdf.cell(0, 5, f"${cum:+,.2f}", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)

        # Save PDF
        pdf_path = r"C:\Users\kinga\Documents\My Site\backtest_report.pdf"
        pdf.output(pdf_path)

        # Send to Telegram
        tg.send_document(pdf_path, caption="Kingade Scalper Bot - 3 Week Backtest Report (EMA10/EMA100 | RR 1:4)")
        print(f"PDF sent to Telegram: {pdf_path}")
