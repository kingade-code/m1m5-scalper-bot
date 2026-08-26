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
import pattern_detector
import requests

TELEGRAM_TOKEN = "8803542513:AAF4TtMmcWIHAj88xNxsjHH8NYxqHMUfwag"
CHAT_ID = "6412335897"

INITIAL_BALANCE = 1000.0
RISK_PER_TRADE = config.RISK_PERCENT
MAX_CONCURRENT_TRADES = 10
MT5_CHUNK_SIZE = 60000

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
    rr: float = 0.0


def mt5_init():
    if not mt5.initialize():
        print(f"MT5 init failed: {mt5.last_error()}")
        sys.exit(1)
    info = mt5.account_info()
    print(f"MT5 connected | Account: {info.login} | Balance: {info.balance}")


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
    df = pd.DataFrame(np.array(all_rates, dtype=[('time','<i8'),('open','<f8'),('high','<f8'),('low','<f8'),('close','<f8'),('tick_volume','<u8'),('spread','<i4'),('real_volume','<u8')]))
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def get_symbol_tick_value(symbol):
    info = mt5.symbol_info(symbol)
    if info is None:
        return None, None, None
    return info.trade_tick_value, info.trade_tick_size, info.point


def _tf_name(timeframe):
    tf_map = {1: "M1", 5: "M5", 15: "M15", 30: "M30", 16385: "H1", 16388: "H4", 32769: "D1"}
    return tf_map.get(timeframe, f"TF{timeframe}")


def _update_trailing_stop(trade, bar, current_atr):
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

    risk = abs(trade.entry_price - trade.sl)
    reward = abs(trade.exit_price - trade.entry_price)
    trade.rr = reward / risk if risk > 0 else 0


def run_backtest():
    mt5_init()

    START_DATE = datetime(2026, 8, 18)
    END_DATE = datetime(2026, 8, 25, 23, 59, 59)
    days_back = (END_DATE - START_DATE).days + 2
    bars_per_day = {"M1": 1440, "M15": 96}
    max_bars = max(bars_per_day.values()) * days_back + 500

    symbols = ["XAUUSD", "GBPUSD", "AUDUSD"]
    symbol_tfs = {
        "XAUUSD": [mt5.TIMEFRAME_M1],
        "GBPUSD": [mt5.TIMEFRAME_M15],
        "AUDUSD": [mt5.TIMEFRAME_M15],
    }

    all_trades = []
    balance = INITIAL_BALANCE
    peak_balance = INITIAL_BALANCE

    for symbol in symbols:
        tfs = symbol_tfs[symbol]
        for tf in tfs:
            tf_name = _tf_name(tf)
            print(f"{symbol} {tf_name}...", end=" ", flush=True)

            df = get_ohlc(symbol, tf, max_bars)
            if df is None or len(df) < config.SWING_LOOKBACK + 30:
                print("skipped")
                continue

            start_idx = df[df["time"] >= pd.Timestamp(START_DATE)].index
            if len(start_idx) == 0:
                print("no data in range")
                continue
            start_bar = start_idx[0]

            tick_value, tick_size, point = get_symbol_tick_value(symbol)
            if tick_value is None or tick_value == 0:
                print("no tick data")
                continue

            atr_series = filters.calc_atr(df["high"], df["low"], df["close"], config.ATR_PERIOD)
            open_trades = []
            signals = 0

            for i in range(start_bar, len(df)):
                current_bar = df.iloc[i]
                current_time = current_bar["time"]
                current_atr = atr_series.iloc[i]

                for trade in open_trades:
                    if trade.result != "open":
                        continue
                    trade.bars_held += 1
                    _update_trailing_stop(trade, current_bar, current_atr)
                    if trade.bars_held >= config.MAX_BARS_IN_TRADE:
                        _close_trade(trade, current_bar, tick_value, tick_size)
                        balance += trade.profit
                        continue
                    if _check_exit(trade, current_bar):
                        _close_trade(trade, current_bar, tick_value, tick_size)
                        balance += trade.profit

                open_trades = [t for t in open_trades if t.result == "open"]

                total_open = sum(1 for t in all_trades if t.result == "open")
                if total_open >= MAX_CONCURRENT_TRADES:
                    continue
                if open_trades:
                    continue

                entry_mode = config.get_symbol_param(symbol, "ENTRY_MODE", config.ENTRY_MODE)

                if entry_mode == "pattern":
                    bars_needed = 200
                    window = df.iloc[max(0, i - bars_needed):i + 1]
                    if len(window) < 30:
                        continue
                    direction = pattern_detector.detect_pattern(window)
                    if direction is None:
                        continue
                    prev_bar = df.iloc[i - 1]
                    prev_close = prev_bar["close"]
                    atr_sl_mult = config.get_symbol_param(symbol, "ATR_SL_MULTIPLIER", config.ATR_SL_MULTIPLIER)
                    atr_sl_dist = current_atr * atr_sl_mult
                    if direction == "bullish":
                        atr_sl = prev_close - atr_sl_dist
                    else:
                        atr_sl = prev_close + atr_sl_dist
                    atr_tp_mult = config.get_symbol_param(symbol, "ATR_TP_MULTIPLIER", config.ATR_TP_MULTIPLIER)
                    atr_tp_dist = current_atr * atr_tp_mult
                    if direction == "bullish":
                        atr_tp = prev_close + atr_tp_dist
                    else:
                        atr_tp = prev_close - atr_tp_dist
                else:
                    swing_lb = config.get_symbol_param(symbol, "SWING_LOOKBACK", config.SWING_LOOKBACK)
                    window = df.iloc[max(0, i - swing_lb - 20):i + 1]
                    move = swing_detector.detect_current_move(window, lookback=swing_lb)
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
                    atr_sl_mult = config.get_symbol_param(symbol, "ATR_SL_MULTIPLIER", config.ATR_SL_MULTIPLIER)
                    atr_sl_dist = current_atr * atr_sl_mult
                    if direction == "bullish":
                        atr_sl = prev_close - atr_sl_dist
                    else:
                        atr_sl = prev_close + atr_sl_dist
                    atr_tp_mult = config.get_symbol_param(symbol, "ATR_TP_MULTIPLIER", config.ATR_TP_MULTIPLIER)
                    atr_tp_dist = current_atr * atr_tp_mult
                    if direction == "bullish":
                        atr_tp = prev_close + atr_tp_dist
                    else:
                        atr_tp = prev_close - atr_tp_dist

                sl_dist = abs(prev_close - atr_sl)
                if sl_dist == 0 or tick_size == 0 or tick_value == 0:
                    continue

                risk_amount = min(balance * RISK_PER_TRADE / 100.0, INITIAL_BALANCE * RISK_PER_TRADE / 100.0)
                sl_ticks = sl_dist / tick_size
                lot_size = risk_amount / (sl_ticks * tick_value)
                lot_size = max(0.01, round(lot_size, 2))
                lot_size = min(1.0, lot_size)

                trade = Trade(
                    symbol=symbol, timeframe=tf,
                    direction=direction,
                    entry_price=prev_close, sl=atr_sl, tp1=atr_tp,
                    entry_time=current_time, lot_size=lot_size,
                )
                open_trades.append(trade)
                all_trades.append(trade)
                signals += 1

            for trade in open_trades:
                if trade.result == "open":
                    last_bar = df.iloc[-1]
                    _close_trade(trade, last_bar, tick_value, tick_size)
                    balance += trade.profit

            print(f"{signals} signals")

    for trade in all_trades:
        if trade.result == "open":
            trade.exit_price = trade.entry_price
            trade.result = "loss"
            trade.profit = 0
            trade.exit_time = datetime.now()

    return all_trades, balance


def format_report(all_trades, final_balance):
    closed = [t for t in all_trades if t.exit_time is not None]

    by_day = {}
    for t in closed:
        day = t.entry_time.strftime("%Y-%m-%d")
        if day not in by_day:
            by_day[day] = []
        by_day[day].append(t)

    lines = []
    lines.append("KINGADE SCALPER - DAILY BACKTEST")
    lines.append("Aug 18 - Aug 25, 2026 | No Filters")
    lines.append("=" * 42)
    lines.append("")

    cum_pnl = 0
    cum_equity = INITIAL_BALANCE
    total_wins = 0
    total_losses = 0
    total_pnl = 0
    total_lots = 0

    for day in sorted(by_day.keys()):
        trades = by_day[day]
        wins = [t for t in trades if t.result == "win"]
        losses = [t for t in trades if t.result == "loss"]
        day_pnl = sum(t.profit for t in trades)
        day_lots = sum(t.lot_size for t in trades)
        cum_pnl += day_pnl
        cum_equity += day_pnl
        total_wins += len(wins)
        total_losses += len(losses)
        total_pnl += day_pnl
        total_lots += day_lots

        day_name = datetime.strptime(day, "%Y-%m-%d").strftime("%a")
        wr = len(wins) / len(trades) * 100 if trades else 0

        lines.append(f"{day} {day_name}")
        lines.append(f"  Trades: {len(trades)} | W: {len(wins)} | L: {len(losses)} | WR: {wr:.0f}%")
        lines.append(f"  P/L: ${day_pnl:+.2f} | Lots: {day_lots:.2f} | Equity: ${cum_equity:,.2f}")

        for t in trades:
            sym = t.symbol.replace("USD", "")
            direction = "BUY" if t.direction == "bullish" else "SELL"
            lines.append(f"    {t.entry_time.strftime('%H:%M')} {sym} {direction} {t.lot_size:.2f}lot | {t.result.upper()} | ${t.profit:+.2f} | R:R {t.rr:.2f}")
        lines.append("")

    total_trades = total_wins + total_losses
    overall_wr = total_wins / total_trades * 100 if total_trades else 0
    avg_rr_list = [t.rr for t in closed if t.rr > 0]
    avg_rr = np.mean(avg_rr_list) if avg_rr_list else 0

    lines.append("=" * 42)
    lines.append("OVERALL SUMMARY")
    lines.append("=" * 42)
    lines.append(f"Period: Aug 18-25, 2026 (7 days)")
    lines.append(f"Starting Balance: ${INITIAL_BALANCE:,.2f}")
    lines.append(f"Final Equity: ${cum_equity:,.2f}")
    lines.append(f"Total P/L: ${total_pnl:+.2f}")
    lines.append(f"Return: {(total_pnl / INITIAL_BALANCE) * 100:+.1f}%")
    lines.append(f"")
    lines.append(f"Total Trades: {total_trades}")
    lines.append(f"Wins: {total_wins} | Losses: {total_losses}")
    lines.append(f"Win Rate: {overall_wr:.1f}%")
    lines.append(f"Avg R:R: {avg_rr:.2f}")
    lines.append(f"Total Lots: {total_lots:.2f}")

    avg_win = np.mean([t.profit for t in closed if t.result == "win"]) if total_wins else 0
    avg_loss = np.mean([t.profit for t in closed if t.result == "loss"]) if total_losses else 0
    lines.append(f"Avg Win: ${avg_win:.2f}")
    lines.append(f"Avg Loss: ${avg_loss:.2f}")

    # By symbol
    sym_stats = {}
    for t in closed:
        s = t.symbol
        if s not in sym_stats:
            sym_stats[s] = {"trades": 0, "wins": 0, "pnl": 0.0, "lots": 0.0}
        sym_stats[s]["trades"] += 1
        if t.result == "win":
            sym_stats[s]["wins"] += 1
        sym_stats[s]["pnl"] += t.profit
        sym_stats[s]["lots"] += t.lot_size

    lines.append("")
    lines.append("BY SYMBOL:")
    for sym, st in sorted(sym_stats.items(), key=lambda x: x[1]["pnl"], reverse=True):
        wr = st["wins"] / st["trades"] * 100 if st["trades"] else 0
        lines.append(f"  {sym}: {st['trades']} trades | {wr:.0f}% WR | ${st['pnl']:+.2f} | {st['lots']:.2f} lots")

    return "\n".join(lines)


if __name__ == "__main__":
    print("Running weekly backtest (Aug 18-25)...")
    all_trades, final_balance = run_backtest()
    mt5.shutdown()

    report = format_report(all_trades, final_balance)
    print("\n" + report)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
    for chunk in chunks:
        resp = requests.post(url, data={"chat_id": CHAT_ID, "text": chunk}, timeout=30)
        print(f"Sent chunk: {resp.json().get('ok', False)}")

    print("Done!")
