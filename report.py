"""
Kingade Scalper Bot - Full Weekly PDF Report Generator
Generates a detailed PDF report with daily drawdown, weekly stats,
cumulative interest, win/loss breakdown, and equity curve.
"""

import sys
import os
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, HRFlowable, Image
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF

import config
import backtest as bt


# ─── Styles ───────────────────────────────────────────────────────
def get_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        'ReportTitle', parent=styles['Title'],
        fontSize=22, spaceAfter=6, textColor=colors.HexColor('#1a1a2e')
    ))
    styles.add(ParagraphStyle(
        'ReportSubtitle', parent=styles['Normal'],
        fontSize=11, textColor=colors.HexColor('#555555'), spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        'SectionHeader', parent=styles['Heading2'],
        fontSize=14, spaceBefore=16, spaceAfter=6,
        textColor=colors.HexColor('#16213e'), borderWidth=0
    ))
    styles.add(ParagraphStyle(
        'SubSection', parent=styles['Heading3'],
        fontSize=11, spaceBefore=8, spaceAfter=4,
        textColor=colors.HexColor('#0f3460')
    ))
    styles.add(ParagraphStyle(
        'SmallText', parent=styles['Normal'],
        fontSize=8, textColor=colors.grey
    ))
    return styles


# ─── Data Collection ──────────────────────────────────────────────
def collect_trade_data():
    """Run backtest and collect all trade data."""
    print("Running backtest for report data...")
    result = bt.run_backtest()
    return result


def build_daily_data(trades):
    """Aggregate trades by day."""
    daily = defaultdict(lambda: {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "profit": 0.0, "loss_amt": 0.0})

    for t in trades:
        day = t.entry_time.date()
        daily[day]["trades"] += 1
        daily[day]["pnl"] += t.profit
        if t.result == "win":
            daily[day]["wins"] += 1
            daily[day]["profit"] += t.profit
        else:
            daily[day]["losses"] += 1
            daily[day]["loss_amt"] += t.profit

    return dict(sorted(daily.items()))


def build_weekly_data(trades):
    """Aggregate trades by ISO week."""
    weekly = defaultdict(lambda: {
        "trades": 0, "wins": 0, "losses": 0, "pnl": 0.0,
        "profit": 0.0, "loss_amt": 0.0, "start_date": None, "end_date": None
    })

    for t in trades:
        d = t.entry_time.date()
        iso_year, iso_week, _ = d.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        w = weekly[key]
        w["trades"] += 1
        w["pnl"] += t.profit
        if t.result == "win":
            w["wins"] += 1
            w["profit"] += t.profit
        else:
            w["losses"] += 1
            w["loss_amt"] += t.profit

        if w["start_date"] is None or d < w["start_date"]:
            w["start_date"] = d
        if w["end_date"] is None or d > w["end_date"]:
            w["end_date"] = d

    return dict(sorted(weekly.items()))


def build_monthly_data(trades):
    """Aggregate trades by month."""
    monthly = defaultdict(lambda: {
        "trades": 0, "wins": 0, "losses": 0, "pnl": 0.0,
        "profit": 0.0, "loss_amt": 0.0
    })

    for t in trades:
        key = t.entry_time.strftime("%Y-%m")
        m = monthly[key]
        m["trades"] += 1
        m["pnl"] += t.profit
        if t.result == "win":
            m["wins"] += 1
            m["profit"] += t.profit
        else:
            m["losses"] += 1
            m["loss_amt"] += t.profit

    return dict(sorted(monthly.items()))


def calc_daily_drawdown(trades, initial_balance):
    """Calculate daily drawdown from equity curve."""
    daily = build_daily_data(trades)
    balance = initial_balance
    peak = initial_balance
    daily_dd = {}

    for day, data in sorted(daily.items()):
        balance += data["pnl"]
        if balance > peak:
            peak = balance
        dd = peak - balance
        dd_pct = (dd / peak * 100) if peak > 0 else 0
        daily_dd[day] = {"balance": balance, "peak": peak, "dd": dd, "dd_pct": dd_pct}

    return daily_dd


# ─── PDF Building ─────────────────────────────────────────────────
def build_pdf(result, output_path):
    """Build the full PDF report."""
    styles = get_styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    elements = []
    trades = result["trades"]
    initial_balance = result["initial_balance"]
    final_balance = result["final_balance"]

    daily = build_daily_data(trades)
    weekly = build_weekly_data(trades)
    monthly = build_monthly_data(trades)
    daily_dd = calc_daily_drawdown(trades, initial_balance)

    # ─── Page 1: Title & Account Summary ───────────────────────────
    elements.append(Paragraph("Kingade Scalper Bot", styles['ReportTitle']))
    elements.append(Paragraph(
        f"Full Performance Report | Generated {datetime.now().strftime('%d %B %Y %H:%M')}",
        styles['ReportSubtitle']
    ))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#16213e')))
    elements.append(Spacer(1, 8))

    # Account Summary Table
    summary_data = [
        ["ACCOUNT SUMMARY", "", "", ""],
        ["Initial Balance", f"${initial_balance:,.2f}", "Total Trades", str(result['total_trades'])],
        ["Final Balance", f"${final_balance:,.2f}", "Winning Trades", str(result['wins'])],
        ["Net P/L", f"${result['total_pnl']:,.2f} ({result['total_pnl_pct']:+.1f}%)", "Losing Trades", str(result['losses'])],
        ["Risk Per Trade", f"{config.RISK_PERCENT}%", "Win Rate", f"{result['win_rate']:.1f}%"],
        ["", "", "Profit Factor", f"{result['profit_factor']:.2f}"],
        ["", "", "Avg R:R", f"{result['avg_rr']:.2f}"],
    ]

    t = Table(summary_data, colWidths=[120, 130, 120, 130])
    t.setStyle(TableStyle([
        ('SPAN', (0, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (3, 0), colors.HexColor('#16213e')),
        ('TEXTCOLOR', (0, 0), (3, 0), colors.white),
        ('FONTNAME', (0, 0), (3, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (3, 0), 11),
        ('ALIGN', (0, 0), (3, 0), 'CENTER'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8))

    # Risk Metrics Table
    risk_data = [
        ["RISK METRICS", "", "", ""],
        ["Max Drawdown", f"${result['max_dd']:,.2f}", "Max Drawdown %", f"{result['max_dd_pct']:.2f}%"],
        ["Sharpe Ratio", f"{result['sharpe']:.2f}", "Calmar Ratio", f"{result['calmar']:.2f}"],
        ["Recovery Factor", f"{result['recovery']:.2f}", "Expectancy/Trade", f"${result['expectancy']:,.2f}"],
        ["Avg Win", f"${result['avg_win']:,.2f}", "Avg Loss", f"${result['avg_loss']:,.2f}"],
        ["Largest Win", f"${result['largest_win']:,.2f}", "Largest Loss", f"${result['largest_loss']:,.2f}"],
        ["Avg Bars Held", f"{result['avg_bars_held']:.1f}", "", ""],
    ]

    t2 = Table(risk_data, colWidths=[120, 130, 120, 130])
    t2.setStyle(TableStyle([
        ('SPAN', (0, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (3, 0), colors.HexColor('#0f3460')),
        ('TEXTCOLOR', (0, 0), (3, 0), colors.white),
        ('FONTNAME', (0, 0), (3, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (3, 0), 11),
        ('ALIGN', (0, 0), (3, 0), 'CENTER'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 8))

    # By Timeframe
    tf_data = [["TIMEFRAME", "TRADES", "WINS", "LOSSES", "WIN RATE", "P/L"]]
    for tf_n, s in sorted(result["tf_stats"].items()):
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] else 0
        tf_data.append([
            tf_n, str(s['trades']), str(s['wins']), str(s['losses']),
            f"{wr:.1f}%", f"${s['pnl']:,.2f}"
        ])

    t3 = Table(tf_data, colWidths=[80, 70, 70, 70, 80, 110])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t3)
    elements.append(PageBreak())

    # ─── Page 2: Monthly Summary ───────────────────────────────────
    elements.append(Paragraph("Monthly Performance", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc')))
    elements.append(Spacer(1, 4))

    mon_data = [["MONTH", "TRADES", "WINS", "LOSSES", "WIN RATE", "P/L", "CUMULATIVE"]]
    cum = 0
    for month, data in sorted(monthly.items()):
        cum += data["pnl"]
        wr = (data["wins"] / data["trades"] * 100) if data["trades"] else 0
        pnl_str = f"${data['pnl']:,.2f}"
        mon_data.append([
            month, str(data['trades']), str(data['wins']), str(data['losses']),
            f"{wr:.1f}%", pnl_str, f"${cum:,.2f}"
        ])

    t4 = Table(mon_data, colWidths=[70, 60, 55, 55, 70, 90, 90])
    t4.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (5, 1), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t4)
    elements.append(Spacer(1, 12))

    # ─── Equity Curve Chart ────────────────────────────────────────
    elements.append(Paragraph("Equity Curve", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc')))
    elements.append(Spacer(1, 4))

    # Build cumulative balance from trades
    bal = initial_balance
    eq_data = [[0, initial_balance]]
    for t in sorted(trades, key=lambda x: x.entry_time):
        bal += t.profit
        eq_data.append([len(eq_data), round(bal, 2)])

    if len(eq_data) > 2:
        d = Drawing(480, 180)
        # Background
        d.add(Rect(0, 0, 480, 180, fillColor=colors.HexColor('#fafafa'), strokeColor=None))

        lp = LinePlot()
        lp.x = 50
        lp.y = 30
        lp.width = 410
        lp.height = 130
        lp.data = [eq_data]
        lp.lines[0].strokeColor = colors.HexColor('#0f3460')
        lp.lines[0].strokeWidth = 1.5
        lp.lines[0].symbol = None

        lp.xValueAxis.valueMin = 0
        lp.xValueAxis.valueMax = len(eq_data)
        lp.xValueAxis.labels.fontSize = 7
        lp.yValueAxis.labels.fontSize = 7
        lp.yValueAxis.labelTextFormat = '$%0.0f'

        d.add(lp)
        elements.append(d)

    elements.append(Spacer(1, 12))

    # ─── Page 3+: Weekly Breakdown ─────────────────────────────────
    elements.append(PageBreak())
    elements.append(Paragraph("Weekly Breakdown", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc')))
    elements.append(Spacer(1, 4))

    week_cum = 0
    for week, data in sorted(weekly.items()):
        week_cum += data["pnl"]
        wr = (data["wins"] / data["trades"] * 100) if data["trades"] else 0
        date_range = f"{data['start_date'].strftime('%d %b')} - {data['end_date'].strftime('%d %b %Y')}" if data['start_date'] and data['end_date'] else week

        # Week header
        pnl_color = '#27ae60' if data["pnl"] >= 0 else '#e74c3c'
        elements.append(Paragraph(
            f"<b>{week}</b> ({date_range}) &mdash; "
            f"<font color='{pnl_color}'>${data['pnl']:+,.2f}</font> | "
            f"Cumulative: ${week_cum:,.2f}",
            styles['SubSection']
        ))

        week_header = ["DATE", "TRADES", "WINS", "LOSSES", "WIN RATE", "P/L", "BALANCE"]
        week_rows = [week_header]

        day_bal = initial_balance
        # Get balance up to this week's start
        for prev_week, prev_data in sorted(weekly.items()):
            if prev_week >= week:
                break
            day_bal += prev_data["pnl"]

        for day, ddata in sorted(daily.items()):
            if day < data["start_date"] or day > data["end_date"]:
                continue
            day_bal += ddata["pnl"]
            d_wr = (ddata["wins"] / ddata["trades"] * 100) if ddata["trades"] else 0
            day_pnl_color = 'green' if ddata["pnl"] >= 0 else 'red'
            week_rows.append([
                day.strftime("%a %d %b"),
                str(ddata['trades']),
                str(ddata['wins']),
                str(ddata['losses']),
                f"{d_wr:.0f}%",
                f"${ddata['pnl']:+,.2f}",
                f"${day_bal:,.2f}"
            ])

        t5 = Table(week_rows, colWidths=[85, 55, 50, 55, 60, 80, 80])
        t5.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (5, 1), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f8f8')]),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t5)
        elements.append(Spacer(1, 10))

    # ─── Page 4+: Daily Drawdown Detail ────────────────────────────
    elements.append(PageBreak())
    elements.append(Paragraph("Daily Drawdown Analysis", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc')))
    elements.append(Spacer(1, 4))

    dd_header = ["DATE", "P/L", "BALANCE", "PEAK", "DRAWDOWN", "DD %"]
    dd_rows = [dd_header]

    for day, dd in sorted(daily_dd.items()):
        day_pnl = daily[day]["pnl"]
        dd_color = 'red' if dd["dd"] > 0 else 'green'
        dd_rows.append([
            day.strftime("%a %d %b %Y"),
            f"${day_pnl:+,.2f}",
            f"${dd['balance']:,.2f}",
            f"${dd['peak']:,.2f}",
            f"${dd['dd']:,.2f}",
            f"{dd['dd_pct']:.2f}%"
        ])

    t6 = Table(dd_rows, colWidths=[100, 80, 85, 85, 80, 60])
    t6.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f3460')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f8f8')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t6)
    elements.append(Spacer(1, 12))

    # ─── Drawdown Chart ────────────────────────────────────────────
    elements.append(Paragraph("Drawdown Chart", styles['SectionHeader']))
    dd_chart_data = [[i, round(dd["dd_pct"], 2)] for i, (day, dd) in enumerate(sorted(daily_dd.items()))]

    if len(dd_chart_data) > 2:
        d2 = Drawing(480, 150)
        d2.add(Rect(0, 0, 480, 150, fillColor=colors.HexColor('#fafafa'), strokeColor=None))

        lp2 = LinePlot()
        lp2.x = 50
        lp2.y = 25
        lp2.width = 410
        lp2.height = 110
        lp2.data = [dd_chart_data]
        lp2.lines[0].strokeColor = colors.HexColor('#e74c3c')
        lp2.lines[0].strokeWidth = 1.2

        lp2.xValueAxis.valueMin = 0
        lp2.xValueAxis.valueMax = len(dd_chart_data)
        lp2.xValueAxis.labels.fontSize = 7
        lp2.yValueAxis.labels.fontSize = 7
        lp2.yValueAxis.labelTextFormat = '%0.1f%%'

        d2.add(lp2)
        elements.append(d2)

    # ─── Page 5: Trade Log ─────────────────────────────────────────
    elements.append(PageBreak())
    elements.append(Paragraph("Complete Trade Log", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc')))
    elements.append(Spacer(1, 4))

    log_header = ["#", "DATE/TIME", "TF", "DIR", "ENTRY", "EXIT", "SL", "TP", "RESULT", "P/L", "BARS"]
    log_rows = [log_header]

    for i, t in enumerate(sorted(trades, key=lambda x: x.entry_time), 1):
        tf_n = bt._tf_name(t.timeframe)
        result_color = 'WIN' if t.result == 'win' else 'LOSS'
        log_rows.append([
            str(i),
            t.entry_time.strftime("%d/%m %H:%M"),
            tf_n,
            t.direction[0].upper(),
            f"{t.entry_price:.2f}",
            f"{t.exit_price:.2f}" if t.exit_price else "-",
            f"{t.sl:.2f}",
            f"{t.tp1:.2f}",
            result_color,
            f"${t.profit:+,.2f}",
            str(t.bars_held),
        ])

    t7 = Table(log_rows, colWidths=[28, 72, 32, 28, 52, 52, 52, 52, 38, 65, 30])
    t7.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('FONTSIZE', (0, 1), (-1, -1), 6.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#dddddd')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f8f8')]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    # Color win/loss rows
    for i, t in enumerate(sorted(trades, key=lambda x: x.entry_time), 1):
        if t.result == 'win':
            t7.setStyle(TableStyle([
                ('TEXTCOLOR', (8, i), (8, i), colors.HexColor('#27ae60')),
                ('TEXTCOLOR', (9, i), (9, i), colors.HexColor('#27ae60')),
            ]))
        else:
            t7.setStyle(TableStyle([
                ('TEXTCOLOR', (8, i), (8, i), colors.HexColor('#e74c3c')),
                ('TEXTCOLOR', (9, i), (9, i), colors.HexColor('#e74c3c')),
            ]))

    elements.append(t7)

    # ─── Build ─────────────────────────────────────────────────────
    doc.build(elements)
    print(f"\nReport saved: {output_path}")
    return output_path


# ─── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import telegram_notifier as tg

    result = collect_trade_data()

    report_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = os.path.join(report_dir, f"FibBot_Report_{timestamp}.pdf")

    build_pdf(result, output_path)

    tg.send_message(f"<b>Backtest Report Generated</b>\n\nTrades: {result['total_trades']} | WR: {result['win_rate']:.1f}%\nP/L: ${result['total_pnl']:+,.2f} ({result['total_pnl_pct']:+.1f}%)")
    tg.send_document(output_path, caption=f"Kingade Backtest Report - {result['total_trades']} trades, {result['win_rate']:.1f}% WR")

    mt5.shutdown()
