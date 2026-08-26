import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
import filters, pattern_detector
from fpdf import FPDF
import requests
import time

MT5_CHUNK_SIZE = 60000
TELEGRAM_TOKEN = "8803542513:AAF4TtMmcWIHAj88xNxsjHH8NYxqHMUfwag"
CHAT_ID = "6412335897"


@dataclass
class Trade:
    entry_price: float = 0.0
    sl: float = 0.0
    tp1: float = 0.0
    direction: int = 0
    profit: float = 0.0
    result: str = "open"
    bars_held: int = 0
    trailing_sl: Optional[float] = None
    rr: float = 0.0
    lot_size: float = 0.01
    entry_time: str = ""
    exit_time: str = ""
    symbol: str = ""


def get_ohlc(symbol, tf, start_ts, end_ts):
    all_rates = []
    rates = mt5.copy_rates_range(symbol, tf, start_ts, end_ts)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(np.array(rates, dtype=[
        ('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'),
        ('close', '<f8'), ('tick_volume', '<u8'), ('spread', '<i4'), ('real_volume', '<u8')
    ]))
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def backtest_symbol(df, tick_value, tick_size, symbol, sl_m, tp_m, tr_s, tr_st):
    atr_series = filters.calc_atr(df["high"], df["low"], df["close"], 14)
    trades = []
    open_trade = None
    equity = 1000.0
    peak_equity = 1000.0
    max_dd = 0.0

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
            direction=direction, lot_size=lot, symbol=symbol,
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
        trades.append(open_trade)

    return trades, equity, max_dd


def generate_pdf(all_trades, sym_results, start_date, end_date):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=10)

    # --- Page 1: Summary ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Kingade Scalper Bot - Weekly Backtest Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "Period: {} to {} | Config: Option B (SL=2.5x TP=3.0x TS=0.5x TSS=0.05x)".format(start_date, end_date), ln=True, align="C")
    pdf.cell(0, 7, "Symbols: XAUUSD, GBPUSD, AUDUSD | Timeframe: M1", ln=True, align="C")
    pdf.ln(5)

    # Portfolio summary
    total_trades = len(all_trades)
    wins = [t for t in all_trades if t.result == "win"]
    losses = [t for t in all_trades if t.result == "loss"]
    wr = len(wins) / total_trades * 100 if total_trades else 0
    total_pnl = sum(t.profit for t in all_trades)
    gp = sum(t.profit for t in wins) if wins else 0
    gl = abs(sum(t.profit for t in losses)) if losses else 1
    pf = gp / gl if gl > 0 else 0
    avg_rr = np.mean([t.rr for t in all_trades if t.rr > 0]) if all_trades else 0
    avg_win = np.mean([t.profit for t in wins]) if wins else 0
    avg_loss = np.mean([t.profit for t in losses]) if losses else 0

    # Summary table
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "PORTFOLIO SUMMARY", ln=True)
    pdf.set_font("Helvetica", "", 10)
    col_w = 47
    pdf.set_fill_color(40, 40, 40)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(col_w, 7, "Total Trades", border=1, align="C", fill=True)
    pdf.cell(col_w, 7, "Win Rate", border=1, align="C", fill=True)
    pdf.cell(col_w, 7, "Avg RR", border=1, align="C", fill=True)
    pdf.cell(col_w, 7, "Profit Factor", border=1, align="C", fill=True)
    pdf.cell(col_w, 7, "Total P/L", border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.cell(col_w, 7, str(total_trades), border=1, align="C")
    pdf.cell(col_w, 7, "{:.1f}%".format(wr), border=1, align="C")
    pdf.cell(col_w, 7, "{:.2f}".format(avg_rr), border=1, align="C")
    pdf.cell(col_w, 7, "{:.2f}".format(pf), border=1, align="C")
    color = (0, 120, 0) if total_pnl >= 0 else (200, 0, 0)
    pdf.set_text_color(*color)
    pdf.cell(col_w, 7, "${:+,.2f}".format(total_pnl), border=1, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    # Per-symbol table
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "PER-SYMBOL BREAKDOWN", ln=True)
    pdf.set_font("Helvetica", "B", 9)
    headers = ["Symbol", "Trades", "Wins", "Losses", "WR%", "Avg RR", "P/L", "PF", "Avg Win", "Avg Loss"]
    hw = [25, 18, 18, 18, 20, 20, 32, 20, 32, 32]
    pdf.set_fill_color(40, 40, 40)
    pdf.set_text_color(255, 255, 255)
    for j, h in enumerate(headers):
        pdf.cell(hw[j], 7, h, border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    for sym, data in sym_results.items():
        t_list = data["trades"]
        w_list = [t for t in t_list if t.result == "win"]
        l_list = [t for t in t_list if t.result == "loss"]
        s_wr = len(w_list) / len(t_list) * 100 if t_list else 0
        s_rr = np.mean([t.rr for t in t_list if t.rr > 0]) if t_list else 0
        s_pnl = sum(t.profit for t in t_list)
        s_gp = sum(t.profit for t in w_list) if w_list else 0
        s_gl = abs(sum(t.profit for t in l_list)) if l_list else 1
        s_pf = s_gp / s_gl if s_gl > 0 else 0
        s_aw = np.mean([t.profit for t in w_list]) if w_list else 0
        s_al = np.mean([t.profit for t in l_list]) if l_list else 0
        vals = [sym, str(len(t_list)), str(len(w_list)), str(len(l_list)),
                "{:.1f}%".format(s_wr), "{:.2f}".format(s_rr),
                "${:+,.0f}".format(s_pnl), "{:.2f}".format(s_pf),
                "${:+,.0f}".format(s_aw), "${:+,.0f}".format(s_al)]
        for j, v in enumerate(vals):
            if j == 6:
                c = (0, 120, 0) if s_pnl >= 0 else (200, 0, 0)
                pdf.set_text_color(*c)
            pdf.cell(hw[j], 6, v, border=1, align="C")
            pdf.set_text_color(0, 0, 0)
        pdf.ln()
    pdf.ln(5)

    # Daily breakdown
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "DAILY BREAKDOWN", ln=True)
    pdf.set_font("Helvetica", "B", 9)
    dh = [30, 22, 22, 22, 22, 32, 22, 32]
    pdf.set_fill_color(40, 40, 40)
    pdf.set_text_color(255, 255, 255)
    for j, h in enumerate(["Date", "Trades", "Wins", "Losses", "WR%", "P/L", "PF", "Cumul P/L"]):
        pdf.cell(dh[j], 7, h, border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    cumul = 0.0
    sorted_trades = sorted(all_trades, key=lambda t: t.entry_time[:10])
    by_date = {}
    for t in sorted_trades:
        d = t.entry_time[:10]
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(t)
    for date_str, day_trades in sorted(by_date.items()):
        dw = [t for t in day_trades if t.result == "win"]
        dl = [t for t in day_trades if t.result == "loss"]
        d_wr = len(dw) / len(day_trades) * 100 if day_trades else 0
        d_pnl = sum(t.profit for t in day_trades)
        d_gp = sum(t.profit for t in dw) if dw else 0
        d_gl = abs(sum(t.profit for t in dl)) if dl else 1
        d_pf = d_gp / d_gl if d_gl > 0 else 0
        cumul += d_pnl
        vals = [date_str, str(len(day_trades)), str(len(dw)), str(len(dl)),
                "{:.0f}%".format(d_wr), "${:+,.0f}".format(d_pnl),
                "{:.2f}".format(d_pf), "${:+,.0f}".format(cumul)]
        for j, v in enumerate(vals):
            if j in (5, 7):
                c = (0, 120, 0) if (d_pnl >= 0 if j == 5 else cumul >= 0) else (200, 0, 0)
                pdf.set_text_color(*c)
            pdf.cell(dh[j], 6, v, border=1, align="C")
            pdf.set_text_color(0, 0, 0)
        pdf.ln()

    # --- Page 2: All trades table ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "ALL TRADES", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 7)
    th = [8, 18, 16, 12, 14, 22, 22, 14, 22, 18, 14, 32]
    headers2 = ["#", "Symbol", "Entry", "Dir", "Lot", "SL", "TP", "RR", "P/L", "Result", "Bars", "Entry Time"]
    pdf.set_fill_color(40, 40, 40)
    pdf.set_text_color(255, 255, 255)
    for j, h in enumerate(headers2):
        pdf.cell(th[j], 6, h, border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 7)
    for idx, t in enumerate(all_trades):
        dir_str = "BUY" if t.direction == 1 else "SELL"
        entry_s = "{:.2f}".format(t.entry_price)[-8:]
        sl_s = "{:.2f}".format(t.sl)[-8:]
        tp_s = "{:.2f}".format(t.tp1)[-8:]
        entry_t = t.entry_time[:16] if t.entry_time else ""
        vals = [str(idx + 1), t.symbol, entry_s, dir_str, "{:.2f}".format(t.lot_size),
                sl_s, tp_s, "{:.2f}".format(t.rr),
                "${:+,.0f}".format(t.profit), t.result.upper(), str(t.bars_held), entry_t]
        for j, v in enumerate(vals):
            if j == 8:
                c = (0, 120, 0) if t.profit >= 0 else (200, 0, 0)
                pdf.set_text_color(*c)
            if j == 9:
                c = (0, 120, 0) if t.result == "win" else (200, 0, 0)
                pdf.set_text_color(*c)
            pdf.cell(th[j], 5, v, border=1, align="C")
            pdf.set_text_color(0, 0, 0)
        pdf.ln()

    fname = "C:/Users/kinga/Documents/My Site/M1-M5 scalping/Weekly_Report_OptionB.pdf"
    pdf.output(fname)
    return fname


def send_telegram_doc(filepath, caption):
    url = "https://api.telegram.org/bot{}/sendDocument".format(TELEGRAM_TOKEN)
    with open(filepath, "rb") as f:
        r = requests.post(url, data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                          files={"document": f}, timeout=30)
    return r.json().get("ok", False)


if __name__ == "__main__":
    mt5.initialize()
    print("MT5 connected | Balance: {}".format(mt5.account_info().balance))

    from datetime import datetime, timedelta
    start_dt = datetime(2026, 8, 18)
    end_dt = datetime(2026, 8, 25, 23, 59)
    start = int(start_dt.timestamp())
    end = int(end_dt.timestamp())
    start_date = "2026-08-18"
    end_date = "2026-08-25"

    symbols = ["XAUUSD", "GBPUSD", "AUDUSD"]
    all_trades = []
    sym_results = {}

    # Option B config
    SL_M = 2.5
    TP_M = 3.0
    TR_S = 0.5
    TR_ST = 0.05

    for sym in symbols:
        info = mt5.symbol_info(sym)
        if info is None:
            print("Cannot get info for {}".format(sym))
            continue
        tv = info.trade_tick_value
        ts_val = info.trade_tick_size

        df = get_ohlc(sym, mt5.TIMEFRAME_M1, start, end)
        if df is None or len(df) < 200:
            print("No data for {}".format(sym))
            continue

        print("Backtesting {} | {} bars | {} to {}".format(sym, len(df), df.iloc[0]["time"], df.iloc[-1]["time"]), flush=True)
        trades, eq, dd = backtest_symbol(df, tv, ts_val, sym, SL_M, TP_M, TR_S, TR_ST)
        sym_results[sym] = {"trades": trades, "equity": eq, "max_dd": dd}
        all_trades.extend(trades)
        print("  {} trades | P/L ${:+,.0f} | DD {:.1f}%".format(len(trades), sum(t.profit for t in trades), dd))

    mt5.shutdown()

    all_trades.sort(key=lambda t: t.entry_time)

    fname = generate_pdf(all_trades, sym_results, start_date, end_date)
    print("\nPDF generated: {}".format(fname))

    total_pnl = sum(t.profit for t in all_trades)
    wins = [t for t in all_trades if t.result == "win"]
    wr = len(wins) / len(all_trades) * 100 if all_trades else 0

    caption = "<b>Weekly Backtest Report (Option B)</b>\nPeriod: {} to {}\nTrades: {} | WR: {:.1f}% | P/L: ${:+,.0f}".format(
        start_date, end_date, len(all_trades), wr, total_pnl)
    ok = send_telegram_doc(fname, caption)
    print("Sent: {}".format("OK" if ok else "FAILED"))
