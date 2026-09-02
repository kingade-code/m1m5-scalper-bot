# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
"""Full backtest PDF report generator (reportlab / navy theme).

Matches the shared document format used by daily_report.py, report.py and
full_report.py: same brand colors, table styling and section headers.

Consumes a results dict with the same shape produced by backtest_m1_trend.py.
No hardcoded results and no hardcoded Telegram token; sends via telegram_notifier.
"""
import sys
import os
import json
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, HRFlowable,
)
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics.charts.lineplots import LinePlot

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import config

# ─── Shared brand palette (must match daily_report / report / full_report) ───
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


def _table(data, widths, header_bg=DARK, size=8):
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), size),
        ("FONTSIZE", (0, 1), (-1, -1), size),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f5f5f5")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _summary_table(R, styles):
    data = [
        ["ACCOUNT SUMMARY", "", "", ""],
        ["Initial Balance", f"${R.get('initial_balance', 0):,.2f}",
         "Total Trades", str(R.get("total_trades", 0))],
        ["Final Balance", f"${R.get('final_balance', 0):,.2f}",
         "Winning Trades", str(R.get("wins", 0))],
        ["Net P/L", f"${R.get('total_pnl', 0):,.2f} ({R.get('total_pnl_pct', 0):+.1f}%)",
         "Losing Trades", str(R.get("losses", 0))],
        ["Risk Per Trade", f"{config.RISK_PERCENT}%",
         "Win Rate", f"{R.get('win_rate', 0):.1f}%"],
        ["", "", "Profit Factor", f"{R.get('profit_factor', 0):.2f}"],
        ["", "", "Avg R:R", f"{R.get('avg_rr', 0):.2f}"],
    ]
    return _table(data, [120, 130, 120, 130], NAVY, 9)


def _risk_table(R):
    data = [
        ["RISK METRICS", "", "", ""],
        ["Max Drawdown", f"${R.get('max_dd', 0):,.2f}",
         "Max Drawdown %", f"{R.get('max_dd_pct', 0):.2f}%"],
        ["Sharpe Ratio", f"{R.get('sharpe', 0):.2f}",
         "Calmar Ratio", f"{R.get('calmar', 0):.2f}"],
        ["Recovery Factor", f"{R.get('recovery', 0):.2f}",
         "Expectancy/Trade", f"${R.get('expectancy', 0):,.2f}"],
        ["Avg Win", f"${R.get('avg_win', 0):,.2f}",
         "Avg Loss", f"${R.get('avg_loss', 0):,.2f}"],
        ["Largest Win", f"${R.get('largest_win', 0):,.2f}",
         "Largest Loss", f"${R.get('largest_loss', 0):,.2f}"],
    ]
    return _table(data, [120, 130, 120, 130], BLUE, 9)


def _by_table(title, key_name, data, sort_pnl=False):
    if not data:
        return []
    rows = [[key_name.upper(), "TRADES", "WINS", "WIN RATE", "P/L"]]
    items = sorted(data.items())
    if sort_pnl:
        items = sorted(data.items(), key=lambda kv: kv[1].get("pnl", 0), reverse=True)
    for name, s in items:
        trades = s.get("trades", 0)
        wins = s.get("wins", 0)
        wr = (wins / trades * 100) if trades else 0
        rows.append([str(name), str(trades), str(wins), f"{wr:.1f}%", f"${s.get('pnl', 0):,.2f}"])
    out = []
    out.append(Paragraph(title, get_styles()["SH"]))
    out.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    out.append(Spacer(1, 4))
    out.append(_table(rows, [110, 70, 60, 90, 110], DARK, 8))
    out.append(Spacer(1, 10))
    return out


def _monthly_table(R):
    monthly = R.get("monthly") or {}
    if not monthly:
        return Spacer(1, 1)
    rows = [["MONTH", "P/L", "CUMULATIVE"]]
    cum = 0
    for m, pnl in sorted(monthly.items(), key=lambda kv: kv[0]):
        if isinstance(pnl, dict):
            pnl = pnl.get("pnl", 0) if "pnl" in pnl else pnl.get("total", 0)
        cum += pnl
        rows.append([m, f"${pnl:,.2f}", f"${cum:,.2f}"])
    return _table(rows, [90, 120, 120], NAVY, 8)


def _equity_chart(R):
    vals = R.get("equity_curve")
    if not vals or len(vals) < 2:
        return Spacer(1, 1)
    pts = list(enumerate(vals))
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
    return d


def generate_pdf(R=None, output_path=None):
    """Build the full backtest PDF. `R` is a results dict; if None it is loaded
    from backtest_2mo.json (or backtest.json) so the report always uses real data."""
    if R is None:
        for cand in ("backtest_2mo.json", "backtest.json"):
            p = os.path.join(BASE, cand)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                R = data.get("results") if isinstance(data, dict) and "results" in data else data
                break
    if R is None:
        raise RuntimeError("No results provided and no backtest JSON found.")

    styles = get_styles()
    out = output_path or os.path.join(
        BASE, f"Kingade_Backtest_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")

    doc = SimpleDocTemplate(out, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    elements = []

    elements.append(Paragraph("Kingade Scalper Bot", styles["T"]))
    elements.append(Paragraph(
        f"Full Performance Report | Generated {datetime.now().strftime('%d %B %Y %H:%M')}",
        styles["ST"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(NAVY)))
    elements.append(Spacer(1, 8))

    elements.append(_summary_table(R, styles))
    elements.append(Spacer(1, 8))
    elements.append(_risk_table(R))
    elements.append(Spacer(1, 12))

    elements.extend(_by_table("Performance By Timeframe", "timeframe", R.get("tf_stats") or {}))
    elements.extend(_by_table("Performance By Symbol", "symbol", R.get("sym_stats") or {}, sort_pnl=True))
    elements.append(PageBreak())

    elements.append(Paragraph("Monthly Performance", styles["SH"]))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    elements.append(Spacer(1, 4))
    elements.append(_monthly_table(R))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Equity Curve", styles["SH"]))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    elements.append(Spacer(1, 4))
    elements.append(_equity_chart(R))

    doc.build(elements)
    print(f"Report saved: {out}")
    return out


def send(path, caption=None):
    import telegram_notifier as tg
    cap = caption or f"Kingade Backtest Report ({datetime.now().strftime('%d %b %Y')})"
    ok = tg.send_document(path, caption=cap)
    print("SENT" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    path = generate_pdf()
    send(path)