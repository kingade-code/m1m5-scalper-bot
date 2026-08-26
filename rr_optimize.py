import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
import filters, pattern_detector

MT5_CHUNK_SIZE = 60000

@dataclass
class Trade:
    entry_price: float = 0.0
    sl: float = 0.0
    tp1: float = 0.0
    direction: str = ""
    profit: float = 0.0
    result: str = "open"
    bars_held: int = 0
    trailing_sl: Optional[float] = None
    rr: float = 0.0
    lot_size: float = 0.01


def get_ohlc(symbol, tf, count):
    all_rates = []
    fetched = 0
    while fetched < count:
        batch = min(MT5_CHUNK_SIZE, count - fetched)
        rates = mt5.copy_rates_from_pos(symbol, tf, fetched, batch)
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


def backtest(df, tick_value, tick_size, sl_mult, tp_mult, trail_start, trail_step):
    atr_series = filters.calc_atr(df["high"], df["low"], df["close"], 14)
    trades = []
    open_trade = None
    equity = 1000.0

    for i in range(200, len(df)):
        bar = df.iloc[i]
        atr = atr_series.iloc[i]
        if atr < 0.00001:
            continue

        if open_trade is not None:
            open_trade.bars_held += 1
            ts_dist = atr * trail_start
            tss_dist = atr * trail_step
            if open_trade.direction == "bullish":
                unr = bar["high"] - open_trade.entry_price
                if unr >= ts_dist:
                    ns = bar["high"] - tss_dist
                    if open_trade.trailing_sl is None or ns > open_trade.trailing_sl:
                        open_trade.trailing_sl = ns
            else:
                unr = open_trade.entry_price - bar["low"]
                if unr >= ts_dist:
                    ns = bar["low"] + tss_dist
                    if open_trade.trailing_sl is None or ns < open_trade.trailing_sl:
                        open_trade.trailing_sl = ns

            eff_sl = open_trade.trailing_sl if open_trade.trailing_sl else open_trade.sl

            if open_trade.bars_held >= 60:
                exit_p = bar["close"]
            elif open_trade.direction == "bullish":
                if bar["low"] <= eff_sl:
                    exit_p = eff_sl
                elif bar["high"] >= open_trade.tp1:
                    exit_p = open_trade.tp1
                else:
                    continue
            else:
                if bar["high"] >= eff_sl:
                    exit_p = eff_sl
                elif bar["low"] <= open_trade.tp1:
                    exit_p = open_trade.tp1
                else:
                    continue

            open_trade.exit_price = exit_p
            risk = abs(open_trade.entry_price - open_trade.sl)
            reward = abs(exit_p - open_trade.entry_price)
            open_trade.rr = reward / risk if risk > 0 else 0
            if open_trade.direction == "bullish":
                open_trade.profit = (exit_p - open_trade.entry_price) * open_trade.lot_size * 100000
            else:
                open_trade.profit = (open_trade.entry_price - exit_p) * open_trade.lot_size * 100000
            open_trade.result = "win" if open_trade.profit >= 0 else "loss"
            equity += open_trade.profit
            trades.append(open_trade)
            open_trade = None
            continue

        window = df.iloc[max(0, i - 200):i + 1]
        if len(window) < 30:
            continue
        direction = pattern_detector.detect_pattern(window)
        if direction is None:
            continue

        prev_close = df.iloc[i - 1]["close"]
        sl_dist_val = atr * sl_mult
        tp_dist_val = atr * tp_mult
        if direction == "bullish":
            sl_p = prev_close - sl_dist_val
            tp_p = prev_close + tp_dist_val
        else:
            sl_p = prev_close + sl_dist_val
            tp_p = prev_close - tp_dist_val

        if abs(prev_close - sl_p) < 5.0:
            continue

        risk_amt = min(equity * 4.0 / 100.0, 40.0)
        sl_ticks = abs(prev_close - sl_p) / tick_size if tick_size > 0 else 1
        lot = risk_amt / (sl_ticks * tick_value) if tick_value > 0 else 0.01
        lot = max(0.01, min(1.0, round(lot, 2)))

        open_trade = Trade(entry_price=prev_close, sl=sl_p, tp1=tp_p, direction=direction, lot_size=lot)

    if open_trade is not None:
        last = df.iloc[-1]["close"]
        open_trade.exit_price = last
        risk = abs(open_trade.entry_price - open_trade.sl)
        reward = abs(last - open_trade.entry_price)
        open_trade.rr = reward / risk if risk > 0 else 0
        if open_trade.direction == "bullish":
            open_trade.profit = (last - open_trade.entry_price) * open_trade.lot_size * 100000
        else:
            open_trade.profit = (open_trade.entry_price - last) * open_trade.lot_size * 100000
        open_trade.result = "win" if open_trade.profit >= 0 else "loss"
        equity += open_trade.profit
        trades.append(open_trade)

    return trades, equity


if __name__ == "__main__":
    mt5.initialize()
    print(f"MT5 connected | Balance: {mt5.account_info().balance}")

    df = get_ohlc("XAUUSD", mt5.TIMEFRAME_M1, 12872)
    info = mt5.symbol_info("XAUUSD")
    tv, ts = info.trade_tick_value, info.trade_tick_size
    mt5.shutdown()

    print(f"XAUUSD M1 | {len(df)} bars")

    configs = [
        (1.5, 2.0, 0.5, 0.10), (1.5, 2.5, 0.5, 0.10), (1.5, 3.0, 0.5, 0.10), (1.5, 3.5, 0.5, 0.10), (1.5, 4.0, 0.5, 0.10),
        (2.0, 2.0, 0.5, 0.10), (2.0, 2.5, 0.5, 0.10), (2.0, 3.0, 0.5, 0.10), (2.0, 3.5, 0.5, 0.10), (2.0, 4.0, 0.5, 0.10), (2.0, 4.5, 0.5, 0.10), (2.0, 5.0, 0.5, 0.10),
        (2.0, 2.5, 0.75, 0.10), (2.0, 3.0, 0.75, 0.10), (2.0, 3.5, 0.75, 0.10), (2.0, 4.0, 0.75, 0.10),
        (2.0, 2.5, 1.0, 0.15), (2.0, 3.0, 1.0, 0.15), (2.0, 3.5, 1.0, 0.15), (2.0, 4.0, 1.0, 0.15),
        (2.0, 3.0, 0.75, 0.15), (2.0, 3.5, 0.75, 0.15), (2.0, 4.0, 0.75, 0.15), (2.0, 4.5, 0.75, 0.15),
        (2.0, 3.5, 0.5, 0.15), (2.0, 4.0, 0.5, 0.15), (2.0, 4.5, 0.5, 0.15), (2.0, 5.0, 0.5, 0.15),
        (2.5, 3.0, 0.5, 0.10), (2.5, 3.5, 0.5, 0.10), (2.5, 4.0, 0.5, 0.10), (2.5, 4.5, 0.5, 0.10), (2.5, 5.0, 0.5, 0.10),
        (2.5, 3.5, 0.75, 0.15), (2.5, 4.0, 0.75, 0.15), (2.5, 4.5, 0.75, 0.15), (2.5, 5.0, 0.75, 0.15),
        (1.5, 3.0, 0.75, 0.10), (1.5, 3.5, 0.75, 0.10), (1.5, 4.0, 0.75, 0.10),
        (1.5, 2.5, 0.5, 0.15), (1.5, 3.0, 0.5, 0.15), (1.5, 3.5, 0.5, 0.15), (1.5, 4.0, 0.5, 0.15),
    ]

    results = []
    for idx, (sl, tp, ts_start, ts_step) in enumerate(configs):
        trades, equity = backtest(df, tv, ts, sl, tp, ts_start, ts_step)
        if not trades:
            continue
        wins = [t for t in trades if t.result == "win"]
        losses = [t for t in trades if t.result == "loss"]
        wr = len(wins) / len(trades) * 100
        avg_rr = np.mean([t.rr for t in trades if t.rr > 0]) if trades else 0
        pnl = sum(t.profit for t in trades)
        gp = sum(t.profit for t in wins) if wins else 0
        gl = abs(sum(t.profit for t in losses)) if losses else 1
        pf = gp / gl if gl > 0 else 999
        results.append({"sl": sl, "tp": tp, "ts": ts_start, "tss": ts_step,
                         "trades": len(trades), "wr": wr, "rr": avg_rr,
                         "pnl": pnl, "equity": equity, "pf": pf})
        print(f"  [{idx+1}/{len(configs)}] SL{sl} TP{tp} TS{ts_start} TSS{ts_step} -> {len(trades)} trades, {wr:.1f}% WR, RR {avg_rr:.2f}, P/L ${pnl:+,.2f}", flush=True)

    good = [r for r in results if r["wr"] >= 74.0]
    if not good:
        good = [r for r in results if r["wr"] >= 70.0]

    good.sort(key=lambda x: x["rr"] * (x["wr"] / 100), reverse=True)

    print(f"\n{'='*85}")
    print(f"TOP CONFIGS (74%+ WR, sorted by RR x WR%)")
    print(f"{'='*85}")
    print(f"{'SL':>4} {'TP':>4} {'Trail':>6} {'Step':>6} {'#':>5} {'WR%':>6} {'RR':>6} {'P/L':>12} {'PF':>6} {'Equity':>10}")
    print(f"{'-'*85}")
    for r in good[:20]:
        print(f"{r['sl']:>4.1f} {r['tp']:>4.1f} {r['ts']:>6.2f} {r['tss']:>6.2f} {r['trades']:>5} {r['wr']:>5.1f}% {r['rr']:>6.2f} ${r['pnl']:>10,.2f} {r['pf']:>6.2f} ${r['equity']:>8,.2f}")

    if good:
        best = good[0]
        print(f"\nBEST: SL={best['sl']}x TP={best['tp']}x Trail={best['ts']}x Step={best['tss']}x")
        print(f"  WR={best['wr']:.1f}% RR={best['rr']:.2f} P/L=${best['pnl']:+,.2f} PF={best['pf']:.2f} Equity=${best['equity']:,.2f}")
