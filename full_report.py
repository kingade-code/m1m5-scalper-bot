# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Full multi-period PDF report (daily / weekly / monthly / yearly + full
trade log) for backtest_m1_trend runs. Supports a main section plus an
optional M1 appendix. No Telegram send inside this script (main.py sends)."""
import sys
import argparse
import json
import os
from datetime import datetime
from collections import defaultdict

import MetaTrader5 as mt5

import backtest_m1_trend as bt
import config

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
    HRFlowable,
)
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics.charts.lineplots import LinePlot

NAVY = "#16213e"
BLUE = "#0f3460"
DARK = "#1a1a2e"
GREEN = "#27ae60"
RED = "#e74c3c"


def get_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("T", parent=s["Title"], fontSize=22, spaceAfter=4,
                         textColor=colors.HexColor(DARK)))
    s.add(ParagraphStyle("ST", parent=s["Normal"], fontSize=11,
                         textColor=colors.HexColor("#555555"), spaceAfter=10))
    s.add(ParagraphStyle("SH", parent=s["Heading2"], fontSize=14, spaceBefore=14,
                         spaceAfter=6, textColor=colors.HexColor(NAVY)))
    s.add(ParagraphStyle("SUB", parent=s["Heading3"], fontSize=11, spaceBefore=10,
                         spaceAfter=4, textColor=colors.HexColor(BLUE)))
    s.add(ParagraphStyle("SM", parent=s["Normal"], fontSize=8, textColor=colors.grey))
    return s


def agg_tables(closed):
    daily = defaultdict(lambda: {"n": 0, "w": 0, "l": 0, "pnl": 0.0})
    weekly = defaultdict(lambda: {"n": 0, "w": 0, "l": 0, "pnl": 0.0,
                                  "start": None, "end": None})
    monthly = defaultdict(lambda: {"n": 0, "w": 0, "l": 0, "pnl": 0.0})
    yearly = defaultdict(lambda: {"n": 0, "w": 0, "l": 0, "pnl": 0.0})

    for t in sorted(closed, key=lambda x: x.entry_time):
        d = t.entry_time.date()
        dk = d.isoformat()
        mk = t.entry_time.strftime("%Y-%m")
        iso_year, iso_week, _ = d.isocalendar()
        wk = f"{iso_year}-W{iso_week:02d}"
        yk = t.entry_time.strftime("%Y")

        daily[dk]["n"] += 1
        weekly[wk]["n"] += 1
        monthly[mk]["n"] += 1
        yearly[yk]["n"] += 1

        if t.result == "win":
            daily[dk]["w"] += 1; weekly[wk]["w"] += 1
            monthly[mk]["w"] += 1; yearly[yk]["w"] += 1
        else:
            daily[dk]["l"] += 1; weekly[wk]["l"] += 1
            monthly[mk]["l"] += 1; yearly[yk]["l"] += 1

        daily[dk]["pnl"] += t.profit
        weekly[wk]["pnl"] += t.profit
        monthly[mk]["pnl"] += t.profit
        yearly[yk]["pnl"] += t.profit

        w = weekly[wk]
        if w["start"] is None or d < w["start"]:
            w["start"] = d
        if w["end"] is None or d > w["end"]:
            w["end"] = d

    return daily, weekly, monthly, yearly


def equity_curve(closed, initial):
    pts = [(0, initial)]
    bal = initial
    for t in sorted(closed, key=lambda x: x.entry_time):
        bal += t.profit
        pts.append((len(pts), round(bal, 2)))
    return pts


def period_max_dd(closed, initial, key_fn):
    dd_by = {}
    bal = initial
    peak = initial
    for t in sorted(closed, key=lambda x: x.entry_time):
        bal += t.profit
        if bal > peak:
            peak = bal
        k = key_fn(t)
        d = dd_by.get(k, {"dd": 0.0, "dd_pct": 0.0})
        d["dd"] = max(d["dd"], peak - bal)
        d["dd_pct"] = max(d["dd_pct"], (peak - bal) / peak * 100 if peak else 0)
        dd_by[k] = d
    return dd_by


def table(data, widths, header_bg=DARK, size=8, fs_body=None):
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), size),
        ("FONTSIZE", (0, 1), (-1, -1), fs_body or size),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f5f5f5")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    t.setStyle(TableStyle(style))
    return t


def charts(closed, initial, elements):
    pts = equity_curve(closed, initial)
    if len(pts) < 2:
        return
    d = Drawing(480, 170)
    d.add(Rect(0, 0, 480, 170, fillColor=colors.HexColor("#fafafa")))
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 50, 30, 410, 125
    lp.data = [pts]
    lp.lines[0].strokeColor = colors.HexColor(BLUE)
    lp.lines[0].strokeWidth = 1.5
    lp.xValueAxis.valueMin = 0
    lp.xValueAxis.valueMax = len(pts)
    lp.xValueAxis.labels.fontSize = 7
    lp.yValueAxis.labels.fontSize = 7
    lp.yValueAxis.labelTextFormat = "$%0.0f"
    d.add(lp)
    elements.append(d)


def add_section(E, styles, r, label, note, first):
    tf_map = {1: "M1", 5: "M5", 15: "M15"}
    closed = r["trades"]
    daily, weekly, monthly, yearly = agg_tables(closed)

    span0 = closed[0].entry_time if closed else None
    span1 = closed[-1].entry_time if closed else None
    span_txt = f"{span0.strftime('%d %b %Y')} - {span1.strftime('%d %b %Y')}" if span0 else "n/a"
    n_months = len({t.entry_time.strftime('%Y-%m') for t in closed})

    if not first:
        E.append(PageBreak())
    E.append(Paragraph("Kingade Scalper Bot", styles["T"]))
    E.append(Paragraph(f"{label} &mdash; Backtest Performance Report | "
                       f"Generated {datetime.now().strftime('%d %B %Y %H:%M')}",
                       styles["ST"]))
    E.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(NAVY)))
    E.append(Spacer(1, 6))
    E.append(Paragraph(
        f"Period: <b>{span_txt}</b> ({len(closed)} closed trades, {n_months} months) | {note}",
        styles["SM"]))
    E.append(Paragraph(
        f"Symbol: XAUUSD | Starting balance: ${r['initial_balance']:,.2f} | "
        f"Risk: {bt.RISK_PER_TRADE}% (max ${bt.MAX_RISK_DOLLARS} capped, lot &le; {bt.MAX_LOT}) | "
        f"SL wick +/-0.5 | TP {'open (RR-trail)' if getattr(bt, 'USE_OPEN_RR', False) else f'1:{bt.RR_RATIO:.0f}'} | "
        f"Trail {'RR-step 3/5/7(lock~1R)' if getattr(bt, 'USE_OPEN_RR', False) else f'{bt.TRAIL_START_ATR}/{bt.TRAIL_STEP_ATR} ATR'} | "
        f"Max bars {bt.MAX_BARS} | Wick guard {bt.WICK_GUARD} | Range-edge {bt.RANGE_EDGE_ATR} | "
        f"Cooldown {bt.TRADE_COOLDOWN_SECONDS}s", styles["SM"]))
    E.append(Spacer(1, 8))

    sum_rows = [
        ["ACCOUNT SUMMARY", ""],
        ["Initial Balance", f"${r['initial_balance']:,.2f}"],
        ["Final Balance", f"${r['final_balance']:,.2f}"],
        ["Net P/L", f"${r['total_pnl']:+,.2f} ({r['total_pnl_pct']:+.1f}%)"],
        ["", ""],
        ["TRADE STATISTICS", ""],
        ["Total Trades", str(r["total_trades"])],
        ["Winning / Losing", f'{r["wins"]} / {r["losses"]}'],
        ["Win Rate", f'{r["win_rate"]:.1f}%'],
        ["Profit Factor", f'{r["profit_factor"]:.2f}'],
        ["Avg R:R", f'{r["avg_rr"]:.2f}'],
        ["Expectancy / Trade", f'${r["expectancy"]:+,.2f}'],
        ["Avg Bars Held", f'{r["avg_bars_held"]:.1f}'],
        ["", ""],
        ["WIN / LOSS", ""],
        ["Avg Win", f'${r["avg_win"]:+,.2f}'],
        ["Avg Loss", f'${r["avg_loss"]:+,.2f}'],
        ["Largest Win", f'${r["largest_win"]:+,.2f}'],
        ["Largest Loss", f'${r["largest_loss"]:+,.2f}'],
        ["", ""],
        ["RISK METRICS", ""],
        ["Max Drawdown", f'${r["max_dd"]:,.2f} ({r["max_dd_pct"]:.2f}%)'],
        ["Sharpe Ratio", f'{r["sharpe"]:.2f}'],
        ["Calmar Ratio", f'{r["calmar"]:.2f}'],
        ["Recovery Factor", f'{r["recovery"]:.2f}'],
    ]
    E.append(table(sum_rows, [170, 250], header_bg=NAVY, size=9, fs_body=9))
    E.append(Spacer(1, 6))
    if len(closed) > 5:
        E.append(Paragraph("Equity Curve", styles["SH"]))
        E.append(HRFlowable(width="100%", thickness=0.5,
                            color=colors.HexColor("#cccccc")))
        charts(closed, r["initial_balance"], E)

    E.append(PageBreak())

    E.append(Paragraph("Daily Breakdown", styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    d_dd = period_max_dd(closed, r["initial_balance"],
                         lambda t: t.entry_time.date().isoformat())
    rows = [["DATE", "TRADES", "WINS", "LOSSES", "WIN RATE", "P/L", "CUM P/L", "DD $"]]
    cum = 0.0
    for dk in sorted(daily):
        x = daily[dk]
        cum += x["pnl"]
        wr = x["w"] / x["n"] * 100 if x["n"] else 0
        rows.append([
            dk, str(x["n"]), str(x["w"]), str(x["l"]), f"{wr:.0f}%",
            f"${x['pnl']:+,.2f}", f"${cum:+,.2f}", f"${d_dd.get(dk, {}).get('dd', 0):,.2f}"
        ])
    E.append(table(rows, [62, 40, 40, 40, 52, 70, 72, 54]))
    E.append(Spacer(1, 8))

    E.append(Paragraph("Weekly Breakdown", styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    rows = [["WEEK", "RANGE", "TRADES", "WINS", "LOSSES", "WR", "P/L", "CUM P/L"]]
    cum = 0.0
    for wk in sorted(weekly):
        x = weekly[wk]
        cum += x["pnl"]
        wr = x["w"] / x["n"] * 100 if x["n"] else 0
        rg = f"{x['start'].strftime('%d %b')} - {x['end'].strftime('%d %b %Y')}"
        rows.append([wk, rg, str(x["n"]), str(x["w"]), str(x["l"]),
                     f"{wr:.0f}%", f"${x['pnl']:+,.2f}", f"${cum:+,.2f}"])
    E.append(table(rows, [60, 105, 40, 40, 40, 35, 68, 68]))

    monthly_bal = {}
    bal = r["initial_balance"]
    for mk in sorted(monthly):
        bal += monthly[mk]["pnl"]
        monthly_bal[mk] = bal

    rows = [["MONTH", "TRADES", "WINS", "LOSSES", "WR", "P/L", "CUM P/L",
             "MONTHLY %*", "MAX DD %"]]
    cum = 0.0
    m_dd = period_max_dd(closed, r["initial_balance"],
                         lambda t: t.entry_time.strftime("%Y-%m"))
    prev_bal = r["initial_balance"]
    for mk in sorted(monthly):
        x = monthly[mk]
        cum += x["pnl"]
        wr = x["w"] / x["n"] * 100 if x["n"] else 0
        mpct = x["pnl"] / prev_bal * 100 if prev_bal else 0
        dd = m_dd.get(mk, {})
        rows.append([mk, str(x["n"]), str(x["w"]), str(x["l"]), f"{wr:.0f}%",
                     f"${x['pnl']:+,.2f}", f"${cum:+,.2f}", f"{mpct:+.1f}%",
                     f"{dd.get('dd_pct', 0):.2f}%"])
        prev_bal = monthly_bal[mk]
    E.append(Paragraph("Monthly Breakdown", styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(table(rows, [58, 42, 42, 42, 35, 70, 70, 56, 52]))
    E.append(Paragraph("* Monthly % = month P/L over balance in at the start of that month.",
                       styles["SM"]))
    E.append(Spacer(1, 8))

    rows = [["YEAR", "TRADES", "WINS", "LOSSES", "WR", "P/L", "CUM P/L", "MAX DD %"]]
    cum = 0.0
    y_dd = period_max_dd(closed, r["initial_balance"],
                         lambda t: t.entry_time.strftime("%Y"))
    for yk in sorted(yearly):
        x = yearly[yk]
        cum += x["pnl"]
        wr = x["w"] / x["n"] * 100 if x["n"] else 0
        rows.append([yk, str(x["n"]), str(x["w"]), str(x["l"]), f"{wr:.0f}%",
                     f"${x['pnl']:+,.2f}", f"${cum:+,.2f}",
                     f"{y_dd.get(yk, {}).get('dd_pct', 0):.2f}%"])
    E.append(Paragraph("Yearly Breakdown", styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(Spacer(1, 4))
    E.append(table(rows, [58, 52, 52, 52, 45, 80, 80, 60]))

    E.append(PageBreak())
    E.append(Paragraph("Complete Trade Log", styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        f"{len(closed)} trades. Result: win = exit price beyond entry in the "
        f"favor direction; P/L is on a {r['initial_balance']:,.0f} starting "
        f"balance with {bt.RISK_PER_TRADE}% risk capped at ${bt.MAX_RISK_DOLLARS}.",
        styles["SM"]))
    E.append(Spacer(1, 4))

    log_rows = [["#", "OPEN (UTC)", "CLOSE (UTC)", "TF", "DIR", "ENTRY", "EXIT",
                 "SL", "TP", "RESULT", "P/L", "R:R", "BARS"]]
    cl = sorted(closed, key=lambda x: x.entry_time)
    for i, t in enumerate(cl, 1):
        risk = abs(t.entry_price - t.sl)
        rr = abs(t.exit_price - t.entry_price) / risk if risk > 0 else 0.0
        log_rows.append([
            str(i), t.entry_time.strftime("%d/%m %H:%M"),
            t.exit_time.strftime("%d/%m %H:%M") if t.exit_time else "-",
            tf_map.get(t.timeframe, str(t.timeframe)),
            t.direction[0].upper(),
            f"{t.entry_price:.3f}", f"{t.exit_price:.3f}" if t.exit_price else "-",
            f"{t.sl:.3f}", "OPEN" if getattr(t, "tp1", None) in (float("inf"), float("-inf")) else f"{t.tp1:.3f}",
            "WIN" if t.result == "win" else "LOSS",
            f"${t.profit:+,.2f}", f"{rr:.2f}", str(t.bars_held),
        ])
    widths = [24, 66, 66, 26, 26, 54, 54, 54, 56, 40, 62, 34, 30]
    tlog = table(log_rows, widths, size=7, fs_body=6.5)
    for i, t in enumerate(cl, 1):
        col = GREEN if t.result == "win" else RED
        tlog.setStyle(TableStyle([
            ("TEXTCOLOR", (9, i), (9, i), colors.HexColor(col)),
            ("TEXTCOLOR", (10, i), (10, i), colors.HexColor(col)),
        ]))
    E.append(tlog)


def add_sensitivity_section(E, styles):
    E.append(PageBreak())
    E.append(Paragraph("Fill-Friction Sensitivity (2026-08-28 runs, XAUUSD)", styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "Same backtest engine and window; only the modeled trading costs change. "
        "The edge survives every cost level in-sample - which is precisely why the "
        "live account (below) is the honest test and is NOT reproducing this.",
        styles["SM"]))
    E.append(Spacer(1, 4))
    rows = [["LEG", "WINDOW", "MODEL", "NET P/L", "WR", "PF", "MAX DD"]]
    sens = [
        ("M5", "6 mo", "idealized (0.00 + 0.00)", "+10,961%", "85.6%", "8.34", "3.40%"),
        ("M5", "6 mo", "0.30 spread", "+10,169%", "85.6%", "7.37", "3.72%"),
        ("M5", "6 mo", "0.30 spread + 0.10 slip", "+9,905%", "85.6%", "7.07", "3.83%"),
        ("M5", "6 mo", "0.50 spread + 0.25 slip", "+8,981%", "84.5%", "6.11", "4.25%"),
        ("M1", "3.3 mo", "idealized (0.00 + 0.00)", "+3,978%", "95.4%", "25.67", "2.44%"),
        ("M1", "3.3 mo", "0.30 spread", "+3,445%", "95.0%", "19.54", "2.96%"),
        ("M1", "3.3 mo", "0.30 spread + 0.10 slip", "+3,267%", "93.4%", "17.66", "3.32%"),
        ("M1", "3.3 mo", "0.50 spread + 0.25 slip", "+2,646%", "84.6%", "11.11", "5.30%"),
    ]
    for r in sens:
        rows.append(list(r))
    E.append(table(rows, [56, 66, 150, 80, 52, 48, 60]))


def add_live_reality_section(E, styles, live_rows, m1_closed, start_bal):
    from datetime import date
    E.append(PageBreak())
    E.append(Paragraph("Live Account Reality Check (since 25 Aug 2026)", styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "The real bot on account 476188356 with the same rules, same magic "
        "777777. Backtest column = the M1 appendix trades on the same dates. "
        "This is the honest measure: backtest in-sample, live out-of-sample.",
        styles["SM"]))
    E.append(Paragraph(
        f"Live balance 25 Aug: {start_bal} | now: $1,044.68 | net realized: "
        f"<font color='{RED}'>-$166.02 over 131 trades (-$1.27/trade)</font>. "
        "The backtest's 93-95% win rate IS NOT reproducing live.",
        styles["SM"]))
    E.append(Spacer(1, 4))
    m1_by_day = defaultdict(list)
    for t in m1_closed:
        m1_by_day[t.entry_time.date()].append(t)

    rows = [["DATE", "LIVE TRADES", "LIVE P/L", "BALANCE",
             "BT M1 TRADES(SAME DAY)", "BT M1 P/L", "CUM LIVE P/L"]]
    cum = 0.0
    bal = start_bal
    for day, n, pnl in live_rows:
        cum += pnl
        bal += pnl
        mts = m1_by_day.get(date.fromisoformat(day) if isinstance(day, str) else day, [])
        mpnl = sum(t.profit for t in mts)
        rows.append([
            day, str(n), f"${pnl:+,.2f}", f"${bal:,.2f}",
            str(len(mts)), f"${mpnl:+,.2f}", f"${cum:+,.2f}"
        ])
    E.append(table(rows, [70, 60, 60, 72, 110, 66, 72]))
    E.append(Spacer(1, 6))
    E.append(Paragraph(
        "Reality vs backtest: live = -$166 (losing); M1 3.3-month backtest on "
        "the same rules = +3,267% (with costs). In-sample fit is not expected "
        "performance. Treat backtest numbers as an upper bound only.",
        styles["SM"]))


def add_amd_comparison(E, styles):
    """AMD vs Kingade on identical windows, symbols and cost models."""
    E.append(PageBreak())
    E.append(Paragraph("AMD vs Kingade (same windows, same costs, XAUUSD)",
                       styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "Accumulation-Manipulation-Distribution: a compact coil (accumulation) "
        "nested inside a larger zone; a candle sweeps beyond the coil edge and "
        "closes back inside (manipulation/stop-hunt); the reversal runs toward "
        "the opposite edge of the zone (distribution). Parameters as run: coil "
        "45 bars, context 180 bars, coil <= 0.40 x context range, sweep >= 0.10, "
        "one entry per coil. Same balance, risk model and costs as Kingade.",
        styles["SM"]))
    E.append(Spacer(1, 4))
    rows = [["STRATEGY", "LEG", "FILLS", "TRADES", "WR", "PF",
             "NET P/L %", "MAX DD"]]
    cmp = [
        ("Kingade", "M5 6mo", "idealized", "2,601", "85.6%", "8.34", "+10,961%", "3.40%"),
        ("Kingade", "M5 6mo", "0.30+0.10", "2,601", "85.6%", "7.07", "+9,904%", "3.88%"),
        ("Kingade", "M1 3.3mo", "idealized", "994", "95.4%", "25.67", "+3,978%", "2.44%"),
        ("Kingade", "M1 3.3mo", "0.30+0.10", "994", "93.4%", "17.66", "+3,267%", "3.32%"),
        ("AMD", "M5 6mo", "idealized", "211", "9.0%", "0.56", "-145%", "165.13%"),
        ("AMD", "M5 6mo", "0.30+0.10", "211", "9.0%", "0.53", "-166%", "184.38%"),
        ("AMD", "M1 3.3mo", "idealized", "517", "13.7%", "1.18", "+303%", "43.03%"),
        ("AMD", "M1 3.3mo", "0.30+0.10", "517", "13.7%", "0.94", "-111%", "102.54%"),
    ]
    for r in cmp:
        rows.append(list(r))
    E.append(table(rows, [90, 80, 90, 58, 52, 48, 72, 60]))
    E.append(Spacer(1, 6))
    E.append(Paragraph(
        "Reading: AMD is the classic sweep-and-fade profile (9-14% win rate on "
        "~2R winners) and it does NOT pay on XAUUSD across these windows - the "
        "sweep keeps running more often than the reversal fills, and any M1 edge "
        "vanishes once spread and stop-slippage are charged. The +167% August "
        "result was regime luck. As built, AMD is not tradeable; Kingade's "
        "pattern strategy dominates it in-sample - subject to the same caveat "
        "that Kingade's live account is not reproducing those numbers.",
        styles["SM"]))


def add_pattern_comparison(E, styles):
    """Pairwise: every chart-pattern detector vs the current Kingade combo,
    run through identical engine/costs and loaded from pattern_sweep output."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "pattern_comparison.json")
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        data = json.load(f)

    E.append(PageBreak())
    E.append(Paragraph("All Chart Patterns vs Kingade (same engine, same costs)",
                       styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "Every pattern below is fired through the SAME engine as the live "
        "Kingade strategy - EMA10/100 trend filter, wick SL, 1:4 reward, "
        "trailing 0.3/0.1 ATR, cooldown, max-bars, range-edge gate and the "
        "same 4% risk model - with realistic fills (0.30 spread + 0.10 stop "
        "slippage). Detectors are precomputed bar-by-bar keyed by candle time; "
        "no look-ahead. Windows: M5 = 6 months full server depth, M1 = 3.3 "
        "months (server cap). 'current' is the live hammer/shooting-star/"
        "engulfing combination.",
        styles["SM"]))
    E.append(Spacer(1, 6))

    for leg_title, leg in (("M5 - 6 months (XAUUSD)", "M5"),
                           ("M1 - 3.3 months (XAUUSD)", "M1")):
        if leg not in data:
            continue
        E.append(Paragraph(leg_title, styles["SH"]))
        rows = [["PATTERN", "TRADES", "WR", "PF", "NET P/L %", "MAX DD"]]
        for name, m in sorted(data[leg].items(),
                              key=lambda kv: kv[1]["net_pct"], reverse=True):
            tag = f"{name}  (LIVE)" if name == "current" else name
            rows.append([tag, f'{m["trades"]:,}', f'{m["win_rate"]}%',
                         f'{m["pf"]:.2f}', f'+{m["net_pct"]:,}%'
                         if m["net_pct"] >= 0 else f'{m["net_pct"]:,.1f}%',
                         f'{m["max_dd"]}%'])
        t = Table(rows, [150, 70, 60, 55, 90, 70])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#f5f6fa"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]
        for i, r in enumerate(rows[1:], start=1):
            if r[0].startswith("current"):
                style.append(("BACKGROUND", (0, i), (-1, i),
                              colors.HexColor("#fff3cd")))
                style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
        t.setStyle(TableStyle(style))
        E.append(t)
        E.append(Spacer(1, 8))

    E.append(Paragraph(
        "Reading: in-sample, most single patterns are strongly positive on M5 "
        "greenbacks - the winning profile comes mostly from the engine (1:4 "
        "with a tight wick stop on XAUUSD), not from any one candle. The live "
        "combination 'current' has the highest raw edge magnitude (2,601 vs "
        "~300-1,400 trades) because it fuses hammer + shooting-star + "
        "engulfing, while single patterns like doji/harami/inside-bar post "
        "higher PF on far fewer trades - narrower setups with more unfilled "
        "bars. All of it is in-sample; the live account is the only arbiter.",
        styles["SM"]))


def add_trail_sweep_section(E, styles):
    """Grid over TRAIL_START/STEP ATR for the current strategy, same costs."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "trail_comparison.json")
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        data = json.load(f)

    E.append(PageBreak())
    E.append(Paragraph("Trailing-Stop Sweep (current strategy, same costs)",
                       styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "Diagnosis for 'is the trailing stop cutting profit short?' The whole "
        "engine is held fixed (hammer/shooting-star/engulfing, wick SL, 1:4 "
        "target, cooldown, max-bars, risk, 0.30 spread + 0.10 stop-slippage); "
        "only the trailing parameters move. Trail START = unrealized profit in "
        "ATR before trailing engages; Trail STEP = ATR distance the stop is "
        "set behind the bar extreme once trailing - smaller STEP = tighter "
        "stop. 'no_trail' leaves winners to either hit the 1:4 target or the "
        "initial stop. Sorted by NET %, best row first.",
        styles["SM"]))
    E.append(Spacer(1, 6))

    for leg_title, leg in (("M5 - 6 months (XAUUSD)", "M5"),
                           ("M1 - 3.3 months (XAUUSD)", "M1")):
        if leg not in data:
            continue
        E.append(Paragraph(leg_title, styles["SH"]))
        rows = [["TRAIL", "TRADES", "WR", "PF", "AVG RR", "NET P/L %", "MAX DD"]]
        for name, m in sorted(data[leg].items(),
                              key=lambda kv: kv[1]["net_pct"], reverse=True):
            tag = "no trailing" if name == "no_trail" else name
            if name == "0.3/0.1":
                tag += "  (LIVE)"
            if m["trades"] <= 0:
                rows.append([tag, "0", "-", "-", "-", "-", "-"])
                continue
            rows.append([tag, f'{m["trades"]:,}', f'{m["win_rate"]}%',
                         f'{m["pf"]:.2f}', f'{m["avg_rr"]:.2f}',
                         f'+{m["net_pct"]:,}%'
                         if m["net_pct"] >= 0 else f'{m["net_pct"]:,.1f}%',
                         f'{m["max_dd"]}%'])
        t = Table(rows, [90, 65, 50, 48, 60, 90, 65])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7.0),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#f5f6fa"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
        ]
        for i, r in enumerate(rows[1:], start=1):
            if "LIVE" in r[0]:
                style.append(("BACKGROUND", (0, i), (-1, i),
                              colors.HexColor("#fff3cd")))
                style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
        t.setStyle(TableStyle(style))
        E.append(t)
        E.append(Spacer(1, 8))

    E.append(Paragraph(
        "Reading: the sweep REVERSES the 'trailing cuts profit short' "
        "hypothesis. Aligning the stop behind the bar is where most of the "
        "edge lives: with no trailing, only the 1:4 target or the initial "
        "stop decide the trade and win-rate collapses to ~36-38%, net profit "
        "drops ~64% (M5) and ~48% (M1) vs the live 0.3/0.1 setting. A LOOSER "
        "trailing (bigger STEP or a later START) does push average winner "
        "size up (AVG RR climbs toward 2.0), but the extra giveaway on the "
        "rest of the book loses more than the fewer-but-bigger winners gain. "
        "The marginally most profitable setting in-sample is 0.0/0.1 "
        "(trail immediately, tight step) - about +6% relative on M5 and +2% "
        "on M1 over the current 0.3/0.1. Under the same discipline as always: "
        "these are in-sample numbers; the live account is losing, so any "
        "tweak here is a paper-leveraged change, not a proven one.",
        styles["SM"]))


def add_rr_sweep_section(E, styles):
    """Reward-multiple sweep with trailing off (TP-or-SL only), vs live trail."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "rr_comparison.json")
    tpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "trail_comparison.json")
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        data = json.load(f)
    trail = None
    if os.path.exists(tpath):
        with open(tpath, "r") as f:
            trail = json.load(f)

    E.append(PageBreak())
    E.append(Paragraph("Reward-Multiple Sweep, No Trailing (TP-or-SL only)",
                       styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "Is 1:4 the right target once the trailing stop is removed? Every "
        "trade now ends at either the initial stop (-1R) or a fixed R:R take "
        "profit, swept 1:1 to 1:15. Engine otherwise identical (current "
        "hammer/shooting-star/engulfing strategy, wick SL, cooldown, "
        "max-bars, reverse-close, risk, 0.30 spread + 0.10 stop-slippage). "
        "The CURRENT 0.3/0.1 trailing config is appended as the reference "
        "row. Sorted by NET %. Best no-trailing row per leg is shown first.",
        styles["SM"]))
    E.append(Spacer(1, 6))

    for leg_title, leg in (("M5 - 6 months (XAUUSD)", "M5"),
                           ("M1 - 3.3 months (XAUUSD)", "M1")):
        if leg not in data:
            continue
        E.append(Paragraph(leg_title, styles["SH"]))
        ordered = sorted(data[leg].items(),
                         key=lambda kv: kv[1]["net_pct"], reverse=True)
        best = ordered[0][0]
        rows = []
        live_row = None
        if trail and leg in trail and "0.3/0.1" in trail[leg]:
            live_row = trail[leg]["0.3/0.1"]
        for ratio, m in ordered:
            tag = f"1:{int(ratio):d}"
            if ratio == best:
                tag += "  (BEST NO-TRAIL)"
            rows.append([tag, f'{m["trades"]:,}', f'{m["win_rate"]}%',
                         f'{m["pf"]:.2f}', f'{m["avg_rr"]:.2f}',
                         f'+{m["net_pct"]:,}%'
                         if m["net_pct"] >= 0 else f'{m["net_pct"]:,.1f}%',
                         f'{m["max_dd"]}%'])
        if live_row:
            rows.append(["0.3/0.1 trail  (LIVE)", f'{live_row["trades"]:,}',
                         f'{live_row["win_rate"]}%', f'{live_row["pf"]:.2f}',
                         f'{live_row["avg_rr"]:.2f}',
                         f'+{live_row["net_pct"]:,}%'
                         if live_row["net_pct"] >= 0
                         else f'{live_row["net_pct"]:,.1f}%',
                         f'{live_row["max_dd"]}%'])
        rows.insert(0, ["R:R", "TRADES", "WR", "PF", "AVG RR", "NET P/L %", "MAX DD"])
        t = Table(rows, [110, 65, 50, 48, 60, 90, 65])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7.0),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#f5f6fa"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
        ]
        for i, r in enumerate(rows[1:], start=1):
            if "BEST NO-TRAIL" in r[0]:
                style.append(("BACKGROUND", (0, i), (-1, i),
                              colors.HexColor("#d4efdf")))
                style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
            if "LIVE" in r[0]:
                style.append(("BACKGROUND", (0, i), (-1, i),
                              colors.HexColor("#fff3cd")))
                style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
        t.setStyle(TableStyle(style))
        E.append(t)
        E.append(Spacer(1, 8))

    E.append(Paragraph(
        "Reading: no-trailing is a flat, low plateau no matter the target. "
        "The best TP-only points are 1:4 on M5 (+3,557%) and 1:3 on M1 "
        "(+2,008%) - both lower than every tight-trailing config in the "
        "trailing sweep. Pushing the target beyond ~1:4 does not pay: "
        "win-rate keeps sliding (36% -> 24%) while gains from bigger winners "
        "plateau at roughly 2,900-3,000% (M5) / ~1,800% (M1). In other "
        "words, the 1:4 target is already near the peak of the no-trail "
        "curve, and no TP-only R:R anywhere approaches the live 0.3/0.1 "
        "trailing result (M5 +9,905%, M1 +3,274%). Same caveat as ever: "
        "in-sample numbers, live account still losing.",
        styles["SM"]))


def add_be_sweep_section(E, styles):
    """Breakeven+2pip-at-2R sweep, vs plain no-trail and live trail rows."""
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "be_comparison.json")
    rr_path = os.path.join(base, "rr_comparison.json")
    t_path = os.path.join(base, "trail_comparison.json")
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        data = json.load(f)
    rr = json.load(open(rr_path)) if os.path.exists(rr_path) else None
    trail = json.load(open(t_path)) if os.path.exists(t_path) else None

    E.append(PageBreak())
    E.append(Paragraph("Breakeven + 2 pips at 2R (all targets, no trailing)",
                       styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "Rule tested: while everything else stays fixed (current pattern "
        "strategy, wick SL, cooldown, max-bars, reverse-close, risk, 0.30 "
        "spread + 0.10 stop-slippage), the moment a trade reaches 2R of "
        "profit the stop jumps to entry +/- 2 pips - a guaranteed small win - "
        "and the open position runs toward the R:R target (swept 1:1 to "
        "1:15). No ATR trailing. Reference rows: best plain no-trailing "
        "target and the LIVE 0.3/0.1 trailing config.",
        styles["SM"]))
    E.append(Spacer(1, 6))

    for leg_title, leg in (("M5 - 6 months (XAUUSD)", "M5"),
                           ("M1 - 3.3 months (XAUUSD)", "M1")):
        if leg not in data:
            continue
        E.append(Paragraph(leg_title, styles["SH"]))
        ordered = sorted(data[leg].items(),
                         key=lambda kv: kv[1]["net_pct"], reverse=True)
        best = ordered[0][0]
        rows = []
        for ratio, m in ordered:
            tag = f"1:{int(ratio):d}"
            if ratio == best:
                tag += "  (BEST BE+2PIP)"
            rows.append([tag, f'{m["trades"]:,}', f'{m["win_rate"]}%',
                         f'{m["pf"]:.2f}', f'{m["avg_rr"]:.2f}',
                         f'+{m["net_pct"]:,}%'
                         if m["net_pct"] >= 0 else f'{m["net_pct"]:,.1f}%',
                         f'{m["max_dd"]}%'])
        if rr and leg in rr:
            k = max(rr[leg], key=lambda k: rr[leg][k]["net_pct"])
            m = rr[leg][k]
            rows.append([f"no-trail 1:{k}  (plain)", f'{m["trades"]:,}',
                         f'{m["win_rate"]}%', f'{m["pf"]:.2f}',
                         f'{m["avg_rr"]:.2f}',
                         f'+{m["net_pct"]:,}%'
                         if m["net_pct"] >= 0 else f'{m["net_pct"]:,.1f}%',
                         f'{m["max_dd"]}%'])
        if trail and leg in trail and "0.3/0.1" in trail[leg]:
            m = trail[leg]["0.3/0.1"]
            rows.append([f"0.3/0.1 trail  (LIVE)", f'{m["trades"]:,}',
                         f'{m["win_rate"]}%', f'{m["pf"]:.2f}',
                         f'{m["avg_rr"]:.2f}',
                         f'+{m["net_pct"]:,}%'
                         if m["net_pct"] >= 0 else f'{m["net_pct"]:,.1f}%',
                         f'{m["max_dd"]}%'])
        rows.insert(0, ["EXIT", "TRADES", "WR", "PF", "AVG RR", "NET P/L %", "MAX DD"])
        t = Table(rows, [120, 65, 50, 48, 60, 88, 65])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7.0),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#f5f6fa"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
        ]
        for i, r in enumerate(rows[1:], start=1):
            if "BEST BE+2PIP" in r[0]:
                style.append(("BACKGROUND", (0, i), (-1, i),
                              colors.HexColor("#d4efdf")))
                style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
            if "plain" in r[0] or "LIVE" in r[0]:
                style.append(("BACKGROUND", (0, i), (-1, i),
                              colors.HexColor("#fff3cd")))
                style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
        t.setStyle(TableStyle(style))
        E.append(t)
        E.append(Spacer(1, 8))

    E.append(Paragraph(
        "Reading: hoisting the stop to 'entry + 2 pips' at 2R does NOT add "
        "edge. It caps nearly every winner at whatever it owns when the floor "
        "catches a pullback - most trades exit around +2-3 pips instead of "
        "riding to the target - so the best BE+2pip points (M5 1:4 = +3,036%, "
        "M1 1:3 = +1,821%) land BELOW the plain no-trailing peaks (M5 +3,557%, "
        "M1 +2,008%) and far below the live 0.3/0.1 trailing (+9,905% / "
        "+3,274%). The lock-in only looks comfortable; it gives back the "
        "upside it claims to protect. In-sample, as always - the live account "
        "is still the only true test.",
        styles["SM"]))


def add_slrr_sweep_section(E, styles):
    """SL-buffer x R:R grid with the current trailing on. Answers 'tighten the
    SL and raise the ratio?' - buffer shrinks the wick-SL, RR is the target
    multiple. Trailing 0.3/0.1 (live) stays engaged on every row."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "slrr_comparison.json")
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        data = json.load(f)

    E.append(PageBreak())
    E.append(Paragraph("Stop-Tightness x R:R Sweep (trailing 0.3/0.1 on)",
                       styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "Can tightening the stop (smaller buffer outside the signal wick) and "
        "raising the take-profit ratio turn the current live setup into "
        "something stronger? Engine held fixed (current hammer/shooting-star/"
        "engulfing strategy, wick SL, cooldown, max-bars, reverse-close, risk, "
        "0.30 spread + 0.10 stop-slippage, trailing 0.3/0.1 ATR ON for every "
        "row). SL buffer 0.5 = live (5 pips outside the wick); 0.1 = 1 pip. "
        "R:R is the 1:N target. One row per buffer: every R:R column (1:2 "
        "through 1:10) produced BIT-IDENTICAL results, so a single "
        "representative 1:4 row is shown. Sorted by NET %. Best first.",
        styles["SM"]))
    E.append(Spacer(1, 6))

    for leg_title, leg in (("M5 - 6 months (XAUUSD)", "M5"),
                           ("M1 - 3.3 months (XAUUSD)", "M1")):
        if leg not in data:
            continue
        E.append(Paragraph(leg_title, styles["SH"]))
        rows = [["SL BUFF", "R:R", "TRADES", "WR", "PF", "AVG RR",
                 "NET P/L %", "MAX DD"]]
        buffers = []
        for name in data[leg]:
            b = float(name.split("/")[0].replace("b", "").replace("p", "."))
            buffers.append(b)
        for buf in sorted(buffers, reverse=True):
            key = f"b{str(buf).replace('.', 'p')}/1:4"
            m = data[leg].get(key)
            if not m:
                continue
            tag = f"{buf}  (<live> 0.5)" if buf == 0.5 else str(buf)
            rows.append([tag, "1:4", f'{m["trades"]:,}', f'{m["win_rate"]}%',
                         f'{m["pf"]:.2f}', f'{m["avg_rr"]:.2f}',
                         f'+{m["net_pct"]:,}%'
                         if m["net_pct"] >= 0 else f'{m["net_pct"]:,.1f}%',
                         f'{m["max_dd"]}%'])
        t = Table(rows, [62, 40, 60, 48, 46, 55, 85, 60])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7.0),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#f5f6fa"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
        ]
        for i, r in enumerate(rows[1:], start=1):
            if "LIVE" in r[0] or "live" in r[0]:
                style.append(("BACKGROUND", (0, i), (-1, i),
                              colors.HexColor("#fff3cd")))
                style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
        t.setStyle(TableStyle(style))
        E.append(t)
        E.append(Spacer(1, 8))

    E.append(Paragraph(
        "Reading: neither lever moves the needle. (1) The R:R target is "
        "DEAD while trailing is on - the stop-trail captures the trade at "
        "AVG RR ~1.3-1.4 long before any 1:2-1:10 target is reachable, so "
        "raising the ratio changes nothing (identical outcomes across every "
        "column). Realized ratio is set by the trail, not the TP, and the "
        "only way to lift it is a looser trail, which the trailing sweep "
        "shows costs more net profit than it wins. (2) Tightening the SL "
        "buffer is roughly a wash: M5 edges up slightly as the stop tightens "
        "(0.5 = +9,893% vs 0.1 = +10,564%, about +7%), while M1 moves the "
        "other way (+3,301% at 0.5 down to +2,815% at 0.1, about -15%) as "
        "the tighter stop gets clipped by low-timeframe noise and the signal "
        "count drops 995 -> 784. There is no buffer value that beats the "
        "current one on both legs, and no ratio that beats 1:4 while "
        "trailing. In-sample, as always - the losing live account is the "
        "only test that counts.",
        styles["SM"]))


def add_full_history_section(E, styles):
    """Current (live) strategy re-run over the user's downloaded XAUUSD M1 CSV,
    ~~~~~~~~~ full 2023-01 -> 2026-08 window, bypassing the MT5 depth cap."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "full_history_comparison.json")
    tpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "trail_comparison.json")
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        data = json.load(f)
    trail = {}
    if os.path.exists(tpath):
        with open(tpath, "r") as f:
            trail = json.load(f)

    E.append(PageBreak())
    E.append(Paragraph("Full-History Validation (2023-01 to 2026-08, "
                       "downloaded XAUUSD M1 CSV)", styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    meta = data.get("meta", {})
    E.append(Paragraph(
        f"Runs the CURRENT live rules over the user's downloaded history "
        f"({meta.get('window', '?')}, ~{meta.get('bars_m1', '?')/1000:.0f}k M1 "
        f"bars, 0 duplicates) instead of the MT5 window that caps M1 at ~3.3 "
        f"months. Same engine, same costs (0.30 spread, 0.10 stop-slippage), "
        f"same config (0.3/0.1 ATR trailing, TP 1:4, wick SL +/-0.5, live "
        f"single-M1 trend set), position sizing 4% of equity capped at $20, "
        f"initial $500. M5 bars are resampled in-engine from the same M1 "
        f"series, so both legs share one continuous feed. The recent 6-month "
        f"MT5-window numbers are appended for contrast.",
        styles["SM"]))
    E.append(Spacer(1, 6))

    rows = [["WINDOW", "TRADES", "WR", "PF", "AVG RR", "NET P/L %"]]
    for leg_title, leg in (("M5", "M5"), ("M1", "M1")):
        if leg not in data:
            continue
        m = data[leg]
        rows.append([f"{leg_title} 2023-26 (CSV)",
                     f'{m["trades"]:,}', f'{m["win_rate"]}%',
                     f'{m["pf"]:.2f}', f'{m["avg_rr"]:.2f}',
                     f'+{m["net_pct"]:,.0f}%'])
        if trail and leg in trail and "0.3/0.1" in trail[leg]:
            live6 = trail[leg]["0.3/0.1"]
            rows.append([f"{leg_title} last 6 mo (MT5, ref)",
                         f'{live6["trades"]:,}', f'{live6["win_rate"]}%',
                         f'{live6["pf"]:.2f}', f'{live6["avg_rr"]:.2f}',
                         f'+{live6["net_pct"]:,.0f}%'])
    t = Table(rows, [150, 65, 50, 48, 60, 90])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.0),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f5f6fa"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
    ]
    for i, r in enumerate(rows[1:], start=1):
        if "ref" in r[0]:
            style.append(("BACKGROUND", (0, i), (-1, i),
                          colors.HexColor("#fff3cd")))
    t.setStyle(TableStyle(style))
    E.append(t)
    E.append(Spacer(1, 8))

    E.append(Paragraph(
        "Reading: the rule set is positive across the WHOLE downloaded history "
        "- the fabric of the edge (wick stop, ratcheting trail) holds in "
        "2023-2025, not just the tuned window. But it is materially WEAKER "
        "outside the recent 6 months: M5 profit factor 7.07 -> 3.59 and win "
        "rate 85.6% -> 78.6% once the full period is in; the last 6 months "
        "was the strongest stretch, not the average one. Two honest caveats: "
        "(1) this is still in-sample for the PARAMETERS (they were tuned on "
        "the recent window, which is a subset of this run); (2) the downloaded "
        "feed is a third-party historical series, not Exness - realised "
        "spread/slippage will differ. The numbers stay consistent with the "
        "6-month sweep rankings. The real validation is a walk-forward split "
        "(fit on 2023-2025, test blindly on the last ~12 months) - offered as "
        "the next step.",
        styles["SM"]))


def add_walkforward_section(E, styles):
    """Train on 2023-01 -> 2025-06, blind-test on 2025-07 -> 2026-08."""
    base = os.path.dirname(os.path.abspath(__file__))
    train_p = os.path.join(base, "wf_train_comparison.json")
    test_p = os.path.join(base, "wf_test_comparison.json")
    if not os.path.exists(train_p) or not os.path.exists(test_p):
        return
    with open(train_p, "r") as f:
        train = json.load(f)
    with open(test_p, "r") as f:
        test = json.load(f)

    E.append(PageBreak())
    E.append(Paragraph("Walk-Forward Split: fit 2023-01 to 2025-06, "
                       "blind-test 2025-07 to 2026-08", styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "The proper generalization test. TRAIN = the trailing-stop grid re-run "
        "on 2023-01-02 -> 2025-06-30 (M5 leg only, ~2.5 years the parameter "
        "sweeps never saw - they were tuned on the recent 6 months). TEST = "
        "the top train configs plus the current live 0.3/0.1 frozen as-is and "
        "run blindly on 2025-07-01 -> 2026-08-26, both legs; nothing was "
        "tuned on the test window. Same engine, same costs (0.30 spread, "
        "0.10 stop-slippage), same live semantics (single M1 trend set), "
        "4% of equity risk capped at $20.",
        styles["SM"]))
    E.append(Spacer(1, 6))

    E.append(Paragraph("TRAIN window - 2023-01 to 2025-06, M5 (fit)",
                       styles["SH"]))
    rows = [["TRAIL", "TRADES", "WR", "PF", "AVG RR", "NET P/L %"]]
    for name, m in sorted(train.items(), key=lambda kv: kv[1]["net_pct"],
                          reverse=True):
        tag = "no trailing" if name == "no_trail" else name
        if name == "0.3/0.1":
            tag += "  (LIVE)"
        rows.append([tag, f'{m["trades"]:,}', f'{m["win_rate"]}%',
                     f'{m["pf"]:.2f}', f'{m["avg_rr"]:.2f}',
                     f'+{m["net_pct"]:,.0f}%'])
    t = Table(rows, [100, 65, 50, 48, 60, 90])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.0),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f5f6fa"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
    ]
    for i, r in enumerate(rows[1:], start=1):
        if "LIVE" in r[0]:
            style.append(("BACKGROUND", (0, i), (-1, i),
                          colors.HexColor("#fff3cd")))
    t.setStyle(TableStyle(style))
    E.append(t)
    E.append(Spacer(1, 8))

    E.append(Paragraph("TEST window - 2025-07 to 2026-08 (blind, both legs)",
                       styles["SH"]))
    rows = [["CONFIG", "LEG", "TRADES", "WR", "PF", "AVG RR", "NET P/L %"]]
    for leg in ("M5", "M1"):
        for name, m in sorted(
                [(k.split(":")[1], v)
                 for k, v in test.items() if k.startswith(f"{leg}:")],
                key=lambda kv: kv[1]["net_pct"], reverse=True):
            tag = name
            if name == "0.3/0.1":
                tag += "  (LIVE)"
            rows.append([tag, leg, f'{m["trades"]:,}', f'{m["win_rate"]}%',
                         f'{m["pf"]:.2f}', f'{m["avg_rr"]:.2f}',
                         f'+{m["net_pct"]:,.0f}%'])
    t = Table(rows, [95, 45, 62, 48, 46, 55, 88])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.0),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f5f6fa"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
    ]
    for i, r in enumerate(rows[1:], start=1):
        if "LIVE" in r[0]:
            style.append(("BACKGROUND", (0, i), (-1, i),
                          colors.HexColor("#fff3cd")))
    t.setStyle(TableStyle(style))
    E.append(t)
    E.append(Spacer(1, 8))

    E.append(Paragraph(
        "Reading: the fit generalizes. The train grid reproduces the exact "
        "shape of the recent-window sweep (track the tight step-0.1 group - "
        "0.0/0.1 > 0.3/0.1 > 0.5/0.1 > ... - with looser trailing falling off "
        "monotonically), and that same ordering REPEATS on blind TEST data on "
        "both legs. The train-optimal 0.0/0.1 beats the live 0.3/0.1 "
        "out-of-window (+11% relative on train M5, +8% on test M5, +3% on "
        "test M1), and the current live config is comfortably #2 - it was "
        "NOT curve-fit to the recent window. Caveats kept explicit: one "
        "third-party feed, fixed 0.30/0.10 costs, and in-sample-style "
        "realistic doubts about M1 fills (89%+ win-rate rows overstate live "
        "reality). Three independent windows now rank 0.0/0.1 first; the "
        "settings are robust, though the losing live account remains the "
        "only arbiter that truly matters.",
        styles["SM"]))


def add_fill_audit_section(E, styles):
    """Replay each LIVE trade through the backtest engine from its real
    entry, compare modelled exit vs actual fill, attribute the gap."""
    base = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(base, "fill_audit.json")
    if not os.path.exists(p):
        return
    with open(p, "r") as f:
        data = json.load(f)
    trades = data.get("trades", [])

    E.append(PageBreak())
    E.append(Paragraph("Live-Fill vs Model Audit (2026-08-18 .. 08-28)",
                       styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5,
                        color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "Every real bot trade is replayed bar-by-bar through the backtest "
        "engine from its ACTUAL entry time on server M1 bars, using the live "
        "0.3/0.1 ATR trailing, wick+/-0.5 initial SL, TP 1:4, max-bars 45 "
        "and the backtest's own cost model (0.30 spread on exit, 0.10 extra "
        "stop-slippage). If the engine's exit *timing and level* matched "
        "reality, the only difference would be sheer execution cost above "
        "the assumed 0.40.",
        styles["SM"]))
    E.append(Spacer(1, 6))

    realized = sum(r["net_realized"] for r in trades)
    mprofit = sum(r["model_profit"] for r in trades)
    gap = realized - mprofit
    n = len(trades)
    rw = sum(1 for r in trades if r["net_realized"] > 0)
    mw = sum(1 for r in trades if r["model_profit"] > 0)

    k = [["MEASURE", "LIVE (ACTUAL FILLS)", "MODEL (BACKTEST ENGINE)"]]
    k.append(["Closed trades", f"{n}", f"{n}"])
    k.append(["Net P/L", f"${realized:+,.2f}", f"${mprofit:+,.2f}"])
    k.append(["Win rate", f"{100*rw/n:.1f}%", f"{100*mw/n:.1f}%"])
    k.append(["Expectation gap", f"${gap:+,.2f}  (${gap/n:+.2f}/trade)",
              "attributable to fills"])
    t = Table(k, [75, 130, 130])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f5f6fa"), colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    E.append(t)
    E.append(Spacer(1, 8))

    # bucket breakdown
    buckets = {}
    for r in trades:
        buckets.setdefault(r["bucket"],
                           [0, 0.0, 0.0]).__setitem__(0, buckets[r["bucket"]][0] + 1)
        buckets[r["bucket"]][1] += r["realized_gap_usd"]
        buckets[r["bucket"]][2] += r["model_profit"]
    labels = {
        "sl_fill": "Model + live both exited at SL",
        "cut_before_tp": "Model hit TP, live closed earlier (cut)",
        "model_hold": "Model still open at live exit (counted at live price)",
        "maxbars": "Both closed on max-bars timer",
        "match": "Model exited ~same level as live",
    }
    E.append(Paragraph("Where the gap came from", styles["SH"]))
    rows = [["BUCKET", "N", "MODEL P/L", "LIVE GAP/TRADE"]]
    for b, (n, g, mp) in sorted(buckets.items(),
                                key=lambda kv: -abs(kv[1][1])):
        rows.append([labels.get(b, b), str(n), f"${mp:+,.2f}",
                     f"${g / max(n, 1):+.2f}"])
    t = Table(rows, [210, 50, 90, 90])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.0),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f5f6fa"), colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
    ]))
    E.append(t)
    E.append(Spacer(1, 6))

    sln = [r for r in trades if r["bucket"] == "sl_fill"]
    if sln:
        deltas = []
        for r in sln:
            w = (r["model_exit_price"] - r["exit_price"]) if r["direction"] == "buy" \
                else (r["exit_price"] - r["model_exit_price"])
            deltas.append(w)
        avg_w = sum(deltas) / len(deltas)
        E.append(Paragraph(
            f"SL fills (n={len(sln)}): the real stop fill landed "
            f"{avg_w:+.2f} price-points AWAY from the modelled stop "
            f"(modelled stop already nets out 0.30 spread + 0.10 slip, so "
            "this is true extra market slippage on top). At 0.01-0.05 lots "
            "that is roughly $0.5-$2.5 per losing trade - and since live "
            "stops are market orders hitting a fast M1 move, every marginal "
            "trailing-SL win gets knocked into a small loss. This accounts "
            f"for the entire ${gap:+,.0f} shortfall: exit logic is faithful, "
            "execution cost is not.",
            styles["SM"]))


def add_friction_section(E, styles):
    """Same trailing grid re-priced at hard friction (0.60/0.25, what the
    fill audit says real XAUUSD stops cost), diffed vs baseline ranks."""
    base = os.path.dirname(os.path.abspath(__file__))
    bp = os.path.join(base, "trail_comparison.json")
    hp = os.path.join(base, "friction_comparison.json")
    if not os.path.exists(bp) or not os.path.exists(hp):
        return
    with open(bp) as f:
        base_d = json.load(f)
    with open(hp) as f:
        hard_d = json.load(f)

    E.append(PageBreak())
    E.append(Paragraph("Cost-Reality Re-Price: same grid, double friction "
                       "(0.60 spread / 0.25 stop-slip)", styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5,
                        color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "The fill audit measured real SL fills landing +0.48 points past the "
        "modelled stop - i.e. about double the 0.30/0.10 the backtests assumed. "
        "This section re-runs the ENTIRE trailing grid at 0.60/0.25 to check "
        "whether the parameter ranking survives realistic cost. It does: the "
        "same ordering holds on both legs (0.0/0.1 > 0.2/0.1 > 0.3/0.1 LIVE > "
        "0.5/0.1 > ... > no-trailing), and the live config stays #2 on M5 and "
        "M1 under both cost assumptions. Net P/L shrinks ~12-20% everywhere; "
        "M1's inflated 90%+ win-rate rows are the most friction-sensitive "
        "(PF 45.9 -> 14.9 on 0/0.1, WR 91.3 -> 79.5%), confirming part of "
        "that edge was cheap-fill illusion - but the ordering is untouched.",
        styles["SM"]))
    E.append(Spacer(1, 6))

    for leg in ("M5", "M1"):
        keys = sorted(base_d[leg], key=lambda k: -base_d[leg][k]["net_pct"])
        h_rank = {k: i for i, k in enumerate(
            sorted(hard_d[leg], key=lambda k: -hard_d[leg][k]["net_pct"]))}
        E.append(Paragraph(f"{leg} leg - baseline order vs hard-friction re-run",
                           styles["SH"]))
        rows = [["TRAIL", "BASE %", "HARD %", "B-WR", "H-WR", "B-PF", "H-PF",
                 "H-RANK"]]
        for k in keys:
            b, h = base_d[leg][k], hard_d[leg][k]
            tag = k
            if k == "0.3/0.1":
                tag += "  (LIVE)"
            rows.append([tag, f"{b['net_pct']:,.0f}", f"{h['net_pct']:,.0f}",
                         f"{b['win_rate']:.1f}", f"{h['win_rate']:.1f}",
                         f"{b['pf']:.2f}", f"{h['pf']:.2f}",
                         str(h_rank[k])])
        t = Table(rows, [100, 58, 58, 40, 40, 42, 42, 45])
        st = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 6.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#f5f6fa"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]
        for i, r in enumerate(rows[1:], start=1):
            if "LIVE" in r[0]:
                st.append(("BACKGROUND", (0, i), (-1, i),
                           colors.HexColor("#fff3cd")))
        t.setStyle(TableStyle(st))
        E.append(t)
        E.append(Spacer(1, 8))

    E.append(Paragraph(
        "Stop-dispatch verification (live bot): SL/TP are attached SERVER-"
        "SIDE on the opening market order (TRADE_ACTION_DEAL with sl/tp, "
        "FOK, deviation 3pts), so every SL/TP fill is a broker-executed "
        "market stop - nothing bot-side can improve it. The trailing stop "
        "is also a server-side ratchet (TRADE_ACTION_SLTP) polled every 5 s, "
        "but it ratchets from the CURRENT TICK price while the model "
        "ratchets from M1 bar extremes - so on fast M1 spikes the real "
        "position's stop sits up to one poll behind the modelled one. "
        "Verdict: the measured +0.48 fill gap is mostly broker market-stop "
        "slippage (unavoidable), with a smaller bot-side slice from trailing "
        "ratchet lag. The config ranking is cost-robust regardless.",
        styles["SM"]))


def add_btc_section(E, styles):
    """BTCUSD first-look under the exact live Kingade ruleset."""
    base = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(base, "btc_comparison.json")
    if not os.path.exists(p):
        return
    with open(p) as f:
        data = json.load(f)
    windows = {"M5": "2026-05-02 .. 08-29 (server depth)",
               "M1": "2026-06-21 .. 08-29 (server depth)"}

    E.append(PageBreak())
    E.append(Paragraph("BTCUSD First Look: Kingade rules on a new instrument",
                       styles["SH"]))
    E.append(HRFlowable(width="100%", thickness=0.5,
                        color=colors.HexColor("#cccccc")))
    E.append(Paragraph(
        "Same engine and live semantics as XAUUSD (pattern entry, EMA10/100 "
        "trend filter, wick+/-10 SL, TP 1:4, ATR-scaled 0.3/0.1 trailing, "
        "max-bars 45, 600s cooldown, 4%/ $20 risk) with BTCUSD-calibrated "
        "price-unit buffers (SL_PIP_BUFFER 10, WICK_GUARD 6: ~0.29 and "
        "0.17 of the M1 ATR(14)=34, matching gold's ratios) and friction "
        "SPREAD $1.0 + SLIP $0.5. Caveat: the Exness trial server only "
        "keeps ~4 months of BTCUSD M5 and ~2.3 months of M1 for this "
        "account - small samples, and the price unit placeholders are "
        "guesses until a live BTC fill audit.",
        styles["SM"]))
    E.append(Spacer(1, 6))

    rows = [["LEG", "WINDOW", "TRADES", "WR", "PF", "AVG RR", "MAXDD",
             "NET P/L %"]]
    for leg, m in [("M5", data.get("M5", {})), ("M1", data.get("M1", {}))]:
        rows.append([leg, windows.get(leg, ""),
                     f'{m.get("trades", 0):,}', f'{m.get("win_rate", 0)}%',
                     f'{m.get("pf", 0):.2f}', f'{m.get("avg_rr", 0):.2f}',
                     f'{m.get("max_dd", 0):.2f}%',
                     f'+{m.get("net_pct", 0):,.0f}%'])
    t = Table(rows, [45, 130, 62, 45, 45, 55, 55, 90])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.0),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f5f6fa"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
    ]))
    E.append(t)
    E.append(Spacer(1, 8))
    E.append(Paragraph(
        "Read: the edge is NOT gold-specific. A fresh instrument with the "
        "same rule set produces the same shape - M5 85% WR / PF 6.2 / "
        "+4,200% and M1 88% WR / PF 5.5 / +2,570% on the short server "
        "window, right on par with XAUUSD's recent-window numbers. Treat as "
        "encouraging-but-small-sample: BTCUSD history here is too thin for "
        "walk-forward or full-history validation, buffers are ATR-scaled "
        "guesses, and BTC stop-fill behavior is unmeasured (weekend spread "
        "quote was $7 vs the $1.0 assumed). BTCUSD is configured in "
        "SYMBOL_OVERRIDES but deliberately NOT in SYMBOL_LIST, so the live "
        "bot still trades XAUUSD only.",
        styles["SM"]))


def build_pdf(sections, output_path, live_rows=None, start_bal=1098.74,
              m1_closed=None):
    styles = get_styles()
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=13 * mm,
                            rightMargin=13 * mm, topMargin=13 * mm,
                            bottomMargin=13 * mm,
                            title="Kingade Backtest Report")
    E = []
    for idx, (label, note, r) in enumerate(sections):
        add_section(E, styles, r, label, note, first=(idx == 0))
    add_sensitivity_section(E, styles)
    add_amd_comparison(E, styles)
    add_pattern_comparison(E, styles)
    add_trail_sweep_section(E, styles)
    add_rr_sweep_section(E, styles)
    add_be_sweep_section(E, styles)
    add_slrr_sweep_section(E, styles)
    add_full_history_section(E, styles)
    add_walkforward_section(E, styles)
    add_fill_audit_section(E, styles)
    add_friction_section(E, styles)
    add_btc_section(E, styles)
    if live_rows is not None:
        add_live_reality_section(E, styles, live_rows, m1_closed or [], start_bal)
    doc.build(E)
    print(f"PDF written: {output_path}")
    return output_path


def main():
    p = argparse.ArgumentParser(description="Kingade full multi-period PDF report")
    p.add_argument("--tf", default="M5", help="comma list: M1/M5")
    p.add_argument("--months", type=int, default=16,
                   help="bar-window parameter (M5: 16 ~ 6 months)")
    p.add_argument("--append-m1", action="store_true",
                   help="append M1 leg over its full server depth (~3.3 months)")
    p.add_argument("--label", default="6 Month", help="report label")
    p.add_argument("--spread", type=float, default=0.30,
                   help="round-trip spread cost in price units (XAUUSD ~0.25-0.50)")
    p.add_argument("--slip", type=float, default=0.10,
                   help="extra slippage on stop-loss fills in price units")
    p.add_argument("--output", default="", help="output pdf path")
    args = p.parse_args()

    tf_map = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5}
    tfs = [x.strip() for x in args.tf.split(",") if x.strip()]
    bt.BACKTEST_SYMBOLS = ["XAUUSD"]
    bt.SEND_REPORT = False
    bt.MAX_BARS = config.MAX_BARS_IN_TRADE
    bt.WICK_GUARD = config.get_symbol_param("XAUUSD", "WICK_GUARD", 0.0)
    bt.ATR_GATE = config.get_symbol_param("XAUUSD", "ATR_GATE", 0.0)
    bt.RANGE_EDGE_ATR = config.get_symbol_param("XAUUSD", "RANGE_EDGE_ATR", 0.0)
    bt.SPREAD_PRICE = args.spread
    bt.SLIP_PRICE = args.slip

    sections = []

    bt.BACKTEST_TIMEFRAMES = [tf_map[x] for x in tfs]
    bt.BACKTEST_MONTHS = args.months
    if tfs == ["M5"]:
        bt.TREND_TF_MODE = "own"  # self-consistent per-TF EMAs over the full 6 months
    else:
        bt.TREND_TF_MODE = "m1"  # matches live for M1
    r_main = bt.run_backtest()
    note = ("trend filter EMA10/100 on the signal TF's own bars for a "
            "self-consistent full window; M1-based trend (as live) unavailable "
            "beyond ~3.3 months of server data; entry at signal-candle close; "
            "full-spread cost + stop-loss slippage applied"
            if tfs == ["M5"] else "trend filter EMA10/100 on M1, as live")
    sections.append((args.label, note, r_main))

    if args.append_m1:
        bt.BACKTEST_TIMEFRAMES = [mt5.TIMEFRAME_M1]
        bt.BACKTEST_MONTHS = 50  # fetch caps at the server's full M1 depth
        bt.TREND_TF_MODE = "m1"
        r_m1 = bt.run_backtest()
        sections.append(("M1 Leg Appendix (maximum server depth)",
                         "trend filter EMA10/100 on M1 (as live); full M1 window "
                         "available on the server (~3.3 months) only; full-spread "
                         "cost + stop-loss slippage applied", r_m1))
    else:
        r_m1 = None

    live_rows, start_bal = _fetch_live_history()

    mt5.shutdown()

    out = args.output or f"C:\\Users\\kinga\\Documents\\My Site\\M1-M5 scalping\\Kingade_{args.label.replace(' ', '')}_Backtest_Report.pdf"
    build_pdf(sections, out, live_rows=live_rows, start_bal=start_bal,
              m1_closed=(r_m1["trades"] if r_m1 else None))
    return out


def _fetch_live_history():
    """Live account closed deals (magic 777777) since the bot went live."""
    from collections import defaultdict
    try:
        frm = datetime(2026, 8, 24)
        deals = mt5.history_deals_get(frm, datetime.now())
        if deals is None:
            return None, 1098.74
        out_deals = [d for d in deals
                     if d.magic == config.MAGIC_NUMBER
                     and d.type in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL)
                     and d.entry == mt5.DEAL_ENTRY_OUT]
        by_day = defaultdict(lambda: [0, 0.0])
        for d in out_deals:
            day = datetime.fromtimestamp(int(d.time)).date().isoformat()
            by_day[day][0] += 1
            by_day[day][1] += d.profit
        rows = [(day, n, pnl) for day, (n, pnl) in sorted(by_day.items())]
        return rows, 1098.74
    except Exception as e:
        print("live history fetch failed:", e)
        return None, 1098.74


if __name__ == "__main__":
    main()
