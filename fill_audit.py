# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Live-fill vs backtest-model audit.

For every closed XAUUSD bot trade (magic 777777), replay what the backtest
engine would have done from the same entry moment, bar-by-bar, using M1
server bars and the live 0.3/0.1 ATR trailing, TP 1:4, wick+/-0.5 SL,
max-bars 45, 0.30 spread + 0.10 stop-slip model. Compare realised vs
modelled exit, price deltas and net P/L, and bucket the divergences.
Saves fill_audit.json and prints the summary.
"""
import json
import os
import sys
import datetime
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
sys.path.insert(0, BASE)
import backtest_m1_trend as bt  # noqa: E402
import config as cfg  # noqa: E402
import filters  # noqa: E402

OUT = os.path.join(BASE, "fill_audit.json")
ATR_PERIOD = cfg.ATR_PERIOD          # 14
BUFFER = cfg.get_symbol_param("XAUUSD", "SL_PIP_BUFFER", 0.5)
RR = cfg.get_symbol_param("XAUUSD", "RR_RATIO", 4.0)
SPREAD = 0.30
SLIP = 0.10
T_START = 0.3
T_STEP = 0.1
MAX_BARS = cfg.MAX_BARS_IN_TRADE     # 45
MIN_STOP = cfg.MIN_STOP_DISTANCE * 0.01   # 1.0 point on XAUUSD

FROM = datetime.datetime(2026, 8, 1, tzinfo=datetime.timezone.utc)


def fetch_trades():
    now = datetime.datetime.now(datetime.timezone.utc)
    from_ts = int(FROM.timestamp())
    to_ts = int(now.timestamp()) + 60
    deals = mt5.history_deals_get(from_ts, to_ts) or []
    orders = mt5.history_orders_get(from_ts, to_ts) or []
    order_map = {o.ticket: o for o in orders if o.magic == cfg.MAGIC_NUMBER}
    by_ticket = {}
    for d in deals:
        if d.magic != cfg.MAGIC_NUMBER or d.symbol != "XAUUSD":
            continue
        by_ticket.setdefault(d.position_id, []).append(d)

    trades = []
    for pid, ds in by_ticket.items():
        ins = [d for d in ds if d.type in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL)
               and d.entry in (mt5.DEAL_ENTRY_IN, mt5.DEAL_ENTRY_INOUT)]
        outs = [d for d in ds
                if d.type in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL)
                and d.entry in (mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT)]
        if not ins or not outs:
            continue
        entry_deal = ins[0]
        exit_deal = outs[-1]
        direction = "buy" if entry_deal.type == mt5.DEAL_TYPE_BUY else "sell"
        o = order_map.get(pid)
        trades.append({
            "ticket": pid,
            "direction": direction,
            "entry_time": int(entry_deal.time),       # UTC epoch
            "entry_price": entry_deal.price,
            "exit_time": int(exit_deal.time),
            "exit_price": exit_deal.price,
            "volume": entry_deal.volume,
            "commission": sum(d.commission for d in ds),
            "swap": sum(d.swap for d in ds),
            "realized": sum(d.profit for d in ds),
            "net_realized": sum(d.profit + d.commission + d.swap for d in ds),
            "sl": o.sl if o else None,
            "tp": o.tp if o else None,
            "comment": entry_deal.comment,
        })
    return trades


def _wick(trade):
    c = trade["comment"] or ""
    if "|w=" in c:
        try:
            return float(c.split("|w=", 1)[1])
        except ValueError:
            return None
    return None


def replay(trade, df):
    """Bar-by-bar exit replay from the ACTUAL entry, live mechanics.
    Returns (model_exit, model_reason, model_bar_idx, model_profit,
             eff_sl_at_close_bar, held_bars_at_close)."""
    direction = trade["direction"]
    entry = trade["entry_price"]
    wick = _wick(trade)
    sl = wick - BUFFER if direction == "buy" and wick else trade["sl"]
    if direction == "sell" and wick:
        sl = wick + BUFFER
    tp = entry + abs(entry - sl) * RR if direction == "buy" else \
        entry - abs(entry - sl) * RR
    if sl is None or sl == 0 or tp is None or tp == 0:
        return None

    entry_ts = trade["entry_time"]
    live_exit_ts = trade["exit_time"]
    atr_series = filters.calc_atr(df["high"], df["low"], df["close"],
                                  ATR_PERIOD)
    start = df["time"].searchsorted(pd.Timestamp(entry_ts, unit="s"),
                                    side="right")  # bar AFTER entry
    trailing_sl = None
    eff_sl = sl
    exit_reason = None
    exit_price = None
    exit_idx = None
    exit_ts = None
    held = 0
    live_exit_eff_sl = sl
    for i in range(start, len(df)):
        bar = df.iloc[i]
        held += 1  # engine increments before checks
        atr = atr_series[i]
        # trailing (engine _update_trailing_stop, 0.3/0.1 ATR)
        if atr > 0:
            ts = atr * T_START
            tst = atr * T_STEP
            if direction == "buy" and (bar["high"] - entry) >= ts:
                cand = bar["high"] - tst
                if trailing_sl is None or cand > trailing_sl:
                    trailing_sl = cand
            elif direction == "sell" and (entry - bar["low"]) >= ts:
                cand = bar["low"] + tst
                if trailing_sl is None or cand < trailing_sl:
                    trailing_sl = cand
        eff_sl = sl
        if trailing_sl is not None:
            eff_sl = max(sl, trailing_sl) if direction == "buy" \
                else min(sl, trailing_sl)
        if i == len(df) - 1:
            live_exit_eff_sl = eff_sl
        # exits
        if direction == "buy":
            if bar["low"] <= eff_sl:
                exit_reason = "sl"; exit_price = eff_sl
            elif bar["high"] >= tp:
                exit_reason = "tp"; exit_price = tp
        else:
            if bar["high"] >= eff_sl:
                exit_reason = "sl"; exit_price = eff_sl
            elif bar["low"] <= tp:
                exit_reason = "tp"; exit_price = tp
        if exit_reason is None and held >= MAX_BARS:
            exit_reason = "maxbars"; exit_price = bar["close"]
        if exit_reason is not None:
            exit_idx = i
            exit_ts = int(bar["time"].timestamp())
            # model costs
            if direction == "buy":
                exit_price -= SPREAD
                if exit_reason == "sl":
                    exit_price -= SLIP
            else:
                exit_price += SPREAD
                if exit_reason == "sl":
                    exit_price += SLIP
            break
    return {"reason": exit_reason, "exit_price": exit_price,
            "exit_ts": exit_ts, "held_bars": held,
            "eff_sl_lc": live_exit_eff_sl, "sl": sl, "tp": tp}


def main():
    bt.mt5_init()
    trades = fetch_trades()
    if not trades:
        print("no live trades found")
        return
    sym = mt5.symbol_info("XAUUSD")
    results = []
    for tr in trades:
        pre = tr["entry_time"] - 60 * 60
        post = tr["exit_time"] + 120
        rates = mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_M1, pre, post)
        if rates is None or len(rates) < ATR_PERIOD + 2:
            continue
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        m = replay(tr, df)
        if m is None:
            continue
        reason = m["reason"]
        model_exit = m["exit_price"]
        if model_exit is None:
            model_exit = tr["exit_price"]  # model still open at live close
            reason = "model_hold"
        diff_usd = (model_exit - tr["entry_price"]) * 100 * tr["volume"] \
            if tr["direction"] == "buy" else \
            (tr["entry_price"] - model_exit) * 100 * tr["volume"]
        # model $ uses real tick scaling like the engine
        tick_size = sym.trade_tick_size
        if reason == "sl":
            pdiff = model_exit - tr["entry_price"] \
                if tr["direction"] == "buy" else tr["entry_price"] - model_exit
        elif reason == "tp":
            pdiff = model_exit - tr["entry_price"] \
                if tr["direction"] == "buy" else tr["entry_price"] - model_exit
        else:
            pdiff = model_exit - tr["entry_price"] \
                if tr["direction"] == "buy" else tr["entry_price"] - model_exit
        model_profit = tr["volume"] * (pdiff / tick_size) * sym.trade_tick_value \
            if tick_size > 0 else diff_usd
        gap = tr["net_realized"] - model_profit
        bucket = "match"
        if reason == "tp" and tr["tp"] and tr["exit_price"] < tr["tp"] - 0.01:
            bucket = "cut_before_tp"
        elif reason == "maxbars":
            bucket = "maxbars"
        elif reason == "model_hold":
            bucket = "model_hold"
        elif reason == "sl":
            bucket = "sl_fill"
        results.append({
            **{k: tr[k] for k in ("ticket", "direction", "entry_time",
                                  "entry_price", "exit_time", "exit_price",
                                  "volume", "net_realized")},
            "model_reason": reason, "model_exit_price": model_exit,
            "model_exit_ts": m["exit_ts"], "model_profit": round(model_profit, 2),
            "realized_gap_usd": round(gap, 2),
            "sl": m["sl"], "tp": m["tp"], "eff_sl_at_lc": m["eff_sl_lc"],
            "held": m["held_bars"], "bucket": bucket,
        })

    with open(OUT, "w") as f:
        json.dump({"meta": {"window_from": "2026-08-01", "trades": len(results)},
                   "trades": results}, f, indent=2)

    total_model = sum(r["model_profit"] for r in results)
    total_real = sum(r["net_realized"] for r in results)
    n = len(results)
    model_wins = sum(1 for r in results if r["model_profit"] > 0)
    real_wins = sum(1 for r in results if r["net_realized"] > 0)
    by_bucket = {}
    for r in results:
        by_bucket.setdefault(r["bucket"], []).append(r["realized_gap_usd"])
    print(f"trades audited: {n}")
    print(f"  realized net P/L : ${total_real:,.2f}")
    print(f"  model net P/L    : ${total_model:,.2f}   (same entries/fills)")
    print(f"  expectation gap  : ${total_real - total_model:+,.2f}  "
          f"(${(total_real - total_model)/max(n,1):+.2f}/trade)")
    print(f"  win rate  live {100*real_wins/max(n,1):.1f}%  "
          f"model {100*model_wins/max(n,1):.1f}%")
    print("buckets:")
    for b, g in sorted(by_bucket.items(), key=lambda kv: -abs(sum(kv[1]))):
        print(f"  {b:14s} n={len(g):3d}  gap ${sum(g):+10.2f}")
    # fill-quality subset: model & live exited same minute on SL
    fin = [r for r in results if r["bucket"] == "sl_fill"]
    if fin:
        sd = [r["exit_price"] - r["model_exit_price"]
              for r in fin if r["direction"] == "sell"]
        bd = [r["model_exit_price"] - r["exit_price"]
              for r in fin if r["direction"] == "buy"]
        worse = bd + sd
        print(f"  SL fills (n={len(fin)}): avg fill worse than model stop by "
              f"${np.mean(worse):+.4f}" if worse else
              f"  SL fills (n={len(fin)})")
    mt5.shutdown()


if __name__ == "__main__":
    main()