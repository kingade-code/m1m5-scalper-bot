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


def bt(df, tick_value, tick_size, sl_m, tp_m, tr_s, tr_st):
    atr_s = filters.calc_atr(df["high"], df["low"], df["close"], 14)
    trades = []
    ot = None
    eq = 1000.0

    for i in range(200, len(df)):
        bar = df.iloc[i]
        atr = atr_s.iloc[i]
        if atr < 0.00001:
            continue

        if ot is not None:
            ot.bars_held += 1
            tsd = atr * tr_s
            tssd = atr * tr_st
            if ot.direction == "bullish":
                if bar["high"] - ot.entry_price >= tsd:
                    ns = bar["high"] - tssd
                    if ot.trailing_sl is None or ns > ot.trailing_sl:
                        ot.trailing_sl = ns
            else:
                if ot.entry_price - bar["low"] >= tsd:
                    ns = bar["low"] + tssd
                    if ot.trailing_sl is None or ns < ot.trailing_sl:
                        ot.trailing_sl = ns

            eff = ot.trailing_sl if ot.trailing_sl else ot.sl

            if ot.bars_held >= 60:
                ep = bar["close"]
            elif ot.direction == "bullish":
                if bar["low"] <= eff:
                    ep = eff
                elif bar["high"] >= ot.tp1:
                    ep = ot.tp1
                else:
                    continue
            else:
                if bar["high"] >= eff:
                    ep = eff
                elif bar["low"] <= ot.tp1:
                    ep = ot.tp1
                else:
                    continue

            ot.exit_price = ep
            risk = abs(ot.entry_price - ot.sl)
            reward = abs(ep - ot.entry_price)
            ot.rr = reward / risk if risk > 0 else 0
            if ot.direction == "bullish":
                ot.profit = (ep - ot.entry_price) * ot.lot_size * 100000
            else:
                ot.profit = (ot.entry_price - ep) * ot.lot_size * 100000
            ot.result = "win" if ot.profit >= 0 else "loss"
            eq += ot.profit
            trades.append(ot)
            ot = None
            continue

        window = df.iloc[max(0, i - 200):i + 1]
        if len(window) < 30:
            continue
        direction = pattern_detector.detect_pattern(window)
        if direction is None:
            continue

        prev_close = df.iloc[i - 1]["close"]
        sl_dist_val = atr * sl_m
        tp_dist_val = atr * tp_m
        if direction == "bullish":
            sl_p = prev_close - sl_dist_val
            tp_p = prev_close + tp_dist_val
        else:
            sl_p = prev_close + sl_dist_val
            tp_p = prev_close - tp_dist_val

        if abs(prev_close - sl_p) < 5.0:
            continue

        risk_amt = min(eq * 4.0 / 100.0, 40.0)
        sl_ticks = abs(prev_close - sl_p) / tick_size if tick_size > 0 else 1
        lot = risk_amt / (sl_ticks * tick_value) if tick_value > 0 else 0.01
        lot = max(0.01, min(1.0, round(lot, 2)))

        ot = Trade(entry_price=prev_close, sl=sl_p, tp1=tp_p, direction=direction, lot_size=lot)

    if ot is not None:
        last = df.iloc[-1]["close"]
        ot.exit_price = last
        risk = abs(ot.entry_price - ot.sl)
        reward = abs(last - ot.entry_price)
        ot.rr = reward / risk if risk > 0 else 0
        if ot.direction == "bullish":
            ot.profit = (last - ot.entry_price) * ot.lot_size * 100000
        else:
            ot.profit = (ot.entry_price - last) * ot.lot_size * 100000
        ot.result = "win" if ot.profit >= 0 else "loss"
        eq += ot.profit
        trades.append(ot)

    return trades, eq


if __name__ == "__main__":
    mt5.initialize()
    print("MT5 connected | Balance: {}".format(mt5.account_info().balance))

    df = get_ohlc("XAUUSD", mt5.TIMEFRAME_M1, 12872)
    info = mt5.symbol_info("XAUUSD")
    tv, ts_val = info.trade_tick_value, info.trade_tick_size
    mt5.shutdown()

    print("XAUUSD M1 | {} bars\n".format(len(df)))

    configs = [
        (2.5, 3.0, 0.5, 0.05), (2.5, 3.5, 0.5, 0.05), (2.5, 4.0, 0.5, 0.05),
        (2.5, 3.0, 0.75, 0.10), (2.5, 3.5, 0.75, 0.10), (2.5, 4.0, 0.75, 0.10),
        (2.5, 3.0, 1.0, 0.10), (2.5, 3.5, 1.0, 0.10), (2.5, 4.0, 1.0, 0.10), (2.5, 4.5, 1.0, 0.10), (2.5, 5.0, 1.0, 0.10),
        (2.5, 3.0, 1.0, 0.15), (2.5, 3.5, 1.0, 0.15), (2.5, 4.0, 1.0, 0.15), (2.5, 4.5, 1.0, 0.15), (2.5, 5.0, 1.0, 0.15),
        (2.5, 3.5, 1.5, 0.15), (2.5, 4.0, 1.5, 0.15), (2.5, 4.5, 1.5, 0.15), (2.5, 5.0, 1.5, 0.15),
        (2.5, 3.5, 1.5, 0.20), (2.5, 4.0, 1.5, 0.20), (2.5, 4.5, 1.5, 0.20), (2.5, 5.0, 1.5, 0.20),
        (2.5, 4.0, 2.0, 0.20), (2.5, 4.5, 2.0, 0.20), (2.5, 5.0, 2.0, 0.20),
        (2.5, 4.0, 2.0, 0.25), (2.5, 4.5, 2.0, 0.25), (2.5, 5.0, 2.0, 0.25),
        (2.5, 4.0, 2.5, 0.25), (2.5, 4.5, 2.5, 0.25), (2.5, 5.0, 2.5, 0.25),
        (2.5, 5.0, 3.0, 0.30), (2.5, 5.0, 3.0, 0.40),
        (2.0, 4.0, 1.5, 0.15), (2.0, 4.5, 1.5, 0.15), (2.0, 5.0, 1.5, 0.15),
        (2.0, 4.0, 2.0, 0.20), (2.0, 4.5, 2.0, 0.20), (2.0, 5.0, 2.0, 0.20),
        (2.0, 5.0, 2.5, 0.25), (2.0, 5.0, 3.0, 0.30),
    ]

    results = []
    for idx, (sl, tp, ts, tss) in enumerate(configs):
        tr, eq = bt(df, tv, ts_val, sl, tp, ts, tss)
        if not tr:
            continue
        w = [t for t in tr if t.result == "win"]
        l = [t for t in tr if t.result == "loss"]
        wr = len(w) / len(tr) * 100
        rr = np.mean([t.rr for t in tr if t.rr > 0]) if tr else 0
        pnl = sum(t.profit for t in tr)
        gp = sum(t.profit for t in w) if w else 0
        gl = abs(sum(t.profit for t in l)) if l else 1
        pf = gp / gl if gl > 0 else 999
        results.append({"sl": sl, "tp": tp, "ts": ts, "tss": tss, "n": len(tr), "wr": wr, "rr": rr, "pnl": pnl, "eq": eq, "pf": pf})
        print("  [{}/{}] SL{} TP{} TS{} TSS{} -> {} trades {:.1f}% WR RR {:.2f} P/L ${:+,.0f}".format(
            idx + 1, len(configs), sl, tp, ts, tss, len(tr), wr, rr, pnl), flush=True)

    good = [r for r in results if r["wr"] >= 74.0]
    if not good:
        good = [r for r in results if r["wr"] >= 70.0]

    good.sort(key=lambda x: x["rr"] * (x["wr"] / 100), reverse=True)

    print("\n" + "=" * 90)
    print("TOP CONFIGS (74%+ WR, sorted by RR x WR%)")
    print("=" * 90)
    print("{:>4} {:>4} {:>6} {:>6} {:>5} {:>6} {:>6} {:>14} {:>6} {:>12}".format(
        "SL", "TP", "Trail", "Step", "#", "WR%", "RR", "P/L", "PF", "Equity"))
    print("-" * 90)
    for r in good[:20]:
        print("{:>4.1f} {:>4.1f} {:>6.2f} {:>6.2f} {:>5} {:>5.1f}% {:>6.2f} ${:>12,.0f} {:>6.2f} ${:>10,.0f}".format(
            r["sl"], r["tp"], r["ts"], r["tss"], r["n"], r["wr"], r["rr"], r["pnl"], r["pf"], r["eq"]))

    if good:
        b = good[0]
        print("\nBEST: SL={}x TP={}x Trail={}x Step={}x".format(b["sl"], b["tp"], b["ts"], b["tss"]))
        print("  WR={:.1f}% RR={:.2f} P/L=${:+,.0f} PF={:.2f} Equity=${:,.0f}".format(
            b["wr"], b["rr"], b["pnl"], b["pf"], b["eq"]))
