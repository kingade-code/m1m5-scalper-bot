import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
import filters, pattern_detector
from fpdf import FPDF
import requests
import json
import time

MT5_CHUNK_SIZE = 60000
TELEGRAM_TOKEN = "8803542513:AAF4TtMmcWIHAj88xNxsjHH8NYxqHMUfwag"
CHAT_ID = "6412335897"


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
    entry_time: str = ""
    exit_time: str = ""


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
    df = pd.DataFrame(np.array(all_rates, dtype=[
        ('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'),
        ('close', '<f8'), ('tick_volume', '<u8'), ('spread', '<i4'), ('real_volume', '<u8')
    ]))
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def backtest_config(df, tick_value, tick_size, sl_m, tp_m, tr_s, tr_st, config_name):
    atr_series = filters.calc_atr(df["high"], df["low"], df["close"], 14)
    trades = []
    open_trade = None
    equity = 1000.0
    peak_equity = 1000.0
    max_dd = 0.0
    equity_curve = [1000.0]

    for i in range(200, len(df)):
        bar = df.iloc[i]
        atr = atr_series.iloc[i]
        if atr < 0.00001:
            continue

        if open_trade is not None:
            open_trade.bars_held += 1
            tsd = atr * tr_s
            tssd = atr * tr_st
            if open_trade.direction == 1:
                if bar["high"] - open_trade.entry_price >= tsd:
                    ns = bar["high"] - tssd
                    if open_trade.trailing_sl is None or ns > open_trade.trailing_sl:
                        open_trade.trailing_sl = ns
            else:
                if open_trade.entry_price - bar["low"] >= tsd:
                    ns = bar["low"] + tssd
                    if open_trade.trailing_sl is None or ns < open_trade.trailing_sl:
                        open_trade.trailing_sl = ns

            eff_sl = open_trade.trailing_sl if open_trade.trailing_sl else open_trade.sl

            if open_trade.bars_held >= 60:
                exit_p = bar["close"]
            elif open_trade.direction == 1:
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
            open_trade.exit_time = str(bar["time"])
            risk = abs(open_trade.entry_price - open_trade.sl)
            reward = abs(exit_p - open_trade.entry_price)
            open_trade.rr = reward / risk if risk > 0 else 0
            if open_trade.direction == 1:
                open_trade.profit = (exit_p - open_trade.entry_price) * open_trade.lot_size * 100000
            else:
                open_trade.profit = (open_trade.entry_price - exit_p) * open_trade.lot_size * 100000
            open_trade.result = "win" if open_trade.profit >= 0 else "loss"
            equity += open_trade.profit
            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity * 100 if peak_equity > 0 else 0
            if dd > max_dd:
                max_dd = dd
            equity_curve.append(equity)
            trades.append(open_trade)
            open_trade = None
            continue

        window = df.iloc[max(0, i - 200):i + 1]
        if len(window) < 30:
            continue
        direction = pattern_detector.detect_pattern(window)
        if direction == 0:
            continue

        prev_close = df.iloc[i - 1]["close"]
        sl_dist_val = atr * sl_m
        tp_dist_val = atr * tp_m
        if direction == 1:
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

        open_trade = Trade(
            entry_price=prev_close, sl=sl_p, tp1=tp_p,
            direction=direction, lot_size=lot,
            entry_time=str(df.iloc[i - 1]["time"])
        )

    if open_trade is not None:
        last = df.iloc[-1]["close"]
        open_trade.exit_price = last
        open_trade.exit_time = str(df.iloc[-1]["time"])
        risk = abs(open_trade.entry_price - open_trade.sl)
        reward = abs(last - open_trade.entry_price)
        open_trade.rr = reward / risk if risk > 0 else 0
        if open_trade.direction == 1:
            open_trade.profit = (last - open_trade.entry_price) * open_trade.lot_size * 100000
        else:
            open_trade.profit = (open_trade.entry_price - last) * open_trade.lot_size * 100000
        open_trade.result = "win" if open_trade.profit >= 0 else "loss"
        equity += open_trade.profit
        equity_curve.append(equity)
        trades.append(open_trade)

    wins = [t for t in trades if t.result == "win"]
    losses = [t for t in trades if t.result == "loss"]
    wr = len(wins) / len(trades) * 100 if trades else 0
    avg_rr = np.mean([t.rr for t in trades if t.rr > 0]) if trades else 0
    total_pnl = sum(t.profit for t in trades)
    gp = sum(t.profit for t in wins) if wins else 0
    gl = abs(sum(t.profit for t in losses)) if losses else 1
    pf = gp / gl if gl > 0 else 999
    avg_win = np.mean([t.profit for t in wins]) if wins else 0
    avg_loss = np.mean([t.profit for t in losses]) if losses else 0
    avg_bars = np.mean([t.bars_held for t in trades]) if trades else 0
    consec_w = 0; max_cw = 0
    consec_l = 0; max_cl = 0
    for t in trades:
        if t.result == "win":
            consec_w += 1; consec_l = 0
            if consec_w > max_cw: max_cw = consec_w
        else:
            consec_l += 1; consec_w = 0
            if consec_l > max_cl: max_cl = consec_l

    return {
        "config_name": config_name,
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "wr": wr,
        "avg_rr": avg_rr,
        "total_pnl": total_pnl,
        "pf": pf,
        "equity": equity,
        "max_dd": max_dd,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "avg_bars": avg_bars,
        "max_cw": max_cw,
        "max_cl": max_cl,
        "equity_curve": equity_curve,
        "sl_m": sl_m,
        "tp_m": tp_m,
        "tr_s": tr_s,
        "tr_st": tr_st,
    }


def generate_pdf(result, filename):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, "Kingade Scalper Bot", ln=True, align="C")
    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 8, "Backtest Report - {}".format(result["config_name"]), ln=True, align="C")
    pdf.ln(5)

    # Config
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Configuration", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "SL: {}x ATR | TP: {}x ATR | Trail Start: {}x ATR | Trail Step: {}x ATR".format(
        result["sl_m"], result["tp_m"], result["tr_s"], result["tr_st"]), ln=True)
    pdf.cell(0, 6, "Symbol: XAUUSD | Timeframe: M1 | Period: {} bars".format(
        len(result["trades"])), ln=True)
    pdf.ln(5)

    # Performance
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Performance Summary", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(95, 6, "Total Trades: {}".format(len(result["trades"])), ln=False)
    pdf.cell(95, 6, "Win Rate: {:.1f}%".format(result["wr"]), ln=True)
    pdf.cell(95, 6, "Wins: {} | Losses: {}".format(len(result["wins"]), len(result["losses"])), ln=False)
    pdf.cell(95, 6, "Avg RR: {:.2f}".format(result["avg_rr"]), ln=True)
    pdf.cell(95, 6, "Profit Factor: {:.2f}".format(result["pf"]), ln=False)
    pdf.cell(95, 6, "Max Drawdown: {:.1f}%".format(result["max_dd"]), ln=True)
    pdf.cell(95, 6, "Total P/L: ${:+,.2f}".format(result["total_pnl"]), ln=False)
    pdf.cell(95, 6, "Final Equity: ${:,.2f}".format(result["equity"]), ln=True)
    pdf.cell(95, 6, "Avg Win: ${:+,.2f}".format(result["avg_win"]), ln=False)
    pdf.cell(95, 6, "Avg Loss: ${:+,.2f}".format(result["avg_loss"]), ln=True)
    pdf.cell(95, 6, "Avg Bars Held: {:.0f}".format(result["avg_bars"]), ln=False)
    pdf.cell(95, 6, "Max Consec Wins: {} | Losses: {}".format(result["max_cw"], result["max_cl"]), ln=True)
    pdf.ln(5)

    # Equity curve (simple ASCII art style using bars)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Equity Curve", ln=True)
    pdf.set_font("Helvetica", "", 8)
    eq = result["equity_curve"]
    if len(eq) > 1:
        min_eq = min(eq)
        max_eq = max(eq)
        rng = max_eq - min_eq if max_eq != min_eq else 1
        bar_width = 190
        num_points = min(60, len(eq))
        step = max(1, len(eq) // num_points)
        sampled = [eq[i] for i in range(0, len(eq), step)]
        for j, v in enumerate(sampled):
            normalized = (v - min_eq) / rng
            bar_len = int(normalized * bar_width)
            label = "${:>10,.0f}".format(v)
            pdf.cell(35, 4, label, ln=False)
            pdf.set_fill_color(0, 200, 0) if v >= 1000 else pdf.set_fill_color(200, 0, 0)
            pdf.cell(bar_len, 4, "", ln=True, fill=True)
    pdf.ln(5)

    # Trade list (last 30)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Recent Trades (last 30)", ln=True)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(25, 5, "Entry", ln=False)
    pdf.cell(20, 5, "Dir", ln=False)
    pdf.cell(20, 5, "Result", ln=False)
    pdf.cell(25, 5, "P/L", ln=False)
    pdf.cell(20, 5, "RR", ln=False)
    pdf.cell(25, 5, "Bars", ln=False)
    pdf.cell(45, 5, "Exit Time", ln=True)
    pdf.set_font("Helvetica", "", 8)
    for t in result["trades"][-30:]:
        entry_str = "{:.2f}".format(t.entry_price)[-6:]
        pdf.cell(25, 4, entry_str, ln=False)
        dir_str = "BUY" if t.direction == 1 else "SELL" if t.direction == -1 else "???"
        pdf.cell(20, 4, dir_str, ln=False)
        color = (0, 150, 0) if t.result == "win" else (200, 0, 0)
        pdf.set_text_color(*color)
        pdf.cell(20, 4, t.result.upper(), ln=False)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(25, 4, "${:+,.2f}".format(t.profit), ln=False)
        pdf.cell(20, 4, "{:.2f}".format(t.rr), ln=False)
        pdf.cell(25, 4, str(t.bars_held), ln=False)
        exit_t = t.exit_time[:16] if t.exit_time else ""
        pdf.cell(45, 4, exit_t, ln=True)

    pdf.output(filename)
    return filename


def send_telegram_doc(filepath, caption):
    url = "https://api.telegram.org/bot{}/sendDocument".format(TELEGRAM_TOKEN)
    with open(filepath, "rb") as f:
        r = requests.post(url, data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                          files={"document": f}, timeout=30)
    return r.json().get("ok", False)


if __name__ == "__main__":
    mt5.initialize()
    print("MT5 connected | Balance: {}".format(mt5.account_info().balance))

    df = get_ohlc("XAUUSD", mt5.TIMEFRAME_M1, 12872)
    info = mt5.symbol_info("XAUUSD")
    tv, ts_val = info.trade_tick_value, info.trade_tick_size
    mt5.shutdown()

    print("XAUUSD M1 | {} bars\n".format(len(df)))

    configs = [
        ("Option A - Current Config", 2.0, 2.5, 1.0, 0.15),
        ("Option B - Best WR (79%)", 2.5, 3.0, 0.5, 0.05),
        ("Option C - Balanced", 2.5, 3.5, 0.75, 0.10),
    ]

    results = []
    for name, sl, tp, trs, trss in configs:
        print("Running: {}...".format(name), flush=True)
        r = backtest_config(df, tv, ts_val, sl, tp, trs, trss, name)
        results.append(r)
        print("  WR={:.1f}% RR={:.2f} P/L=${:+,.0f} PF={:.2f} DD={:.1f}%".format(
            r["wr"], r["avg_rr"], r["total_pnl"], r["pf"], r["max_dd"]))

    # Generate PDFs
    for r in results:
        fname = r["config_name"].replace(" ", "_").replace("-", "") + ".pdf"
        fpath = "C:/Users/kinga/Documents/My Site/M1-M5 scalping/{}".format(fname)
        generate_pdf(r, fpath)
        print("Generated: {}".format(fname))

    # Send to Telegram
    for r in results:
        fname = r["config_name"].replace(" ", "_").replace("-", "") + ".pdf"
        fpath = "C:/Users/kinga/Documents/My Site/M1-M5 scalping/{}".format(fname)
        caption = "<b>{}</b>\nWR: {:.1f}% | RR: {:.2f} | PF: {:.2f}\nP/L: ${:+,.0f} | DD: {:.1f}%".format(
            r["config_name"], r["wr"], r["avg_rr"], r["pf"], r["total_pnl"], r["max_dd"])
        ok = send_telegram_doc(fpath, caption)
        print("Sent {}: {}".format(fname, "OK" if ok else "FAILED"))
        time.sleep(1)

    # Summary comparison
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print("{:<25} {:>8} {:>8} {:>8} {:>14} {:>8} {:>10}".format(
        "Config", "Trades", "WR%", "Avg RR", "P/L", "PF", "Max DD%"))
    print("-" * 80)
    for r in results:
        print("{:<25} {:>8} {:>7.1f}% {:>8.2f} ${:>12,.0f} {:>8.2f} {:>9.1f}%".format(
            r["config_name"], len(r["trades"]), r["wr"], r["avg_rr"],
            r["total_pnl"], r["pf"], r["max_dd"]))

    print("\nAll 3 PDFs sent to Telegram!")
