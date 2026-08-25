import requests
from fpdf import FPDF
from datetime import datetime

TELEGRAM_TOKEN = "8803542513:AAF4TtMmcWIHAj88xNxsjHH8NYxqHMUfwag"
CHAT_ID = "6412335897"

# Results from the backtest we already ran
R = {
    "initial_balance": 1000.0,
    "final_balance": 57091.32,
    "total_pnl": 56091.32,
    "total_pnl_pct": 5609.13,
    "total_trades": 10908,
    "wins": 8410,
    "losses": 2498,
    "win_rate": 77.1,
    "profit_factor": 1.96,
    "avg_rr": 0.44,
    "expectancy": 5.14,
    "avg_bars_held": 5.4,
    "max_dd": 261.98,
    "max_dd_pct": 10.30,
    "sharpe": 4.43,
    "recovery": 214.10,
    "calmar": 544.84,
    "avg_win": 13.64,
    "avg_loss": -23.48,
    "largest_win": 130.98,
    "largest_loss": -228.41,
    "tf_stats": {
        "M1": {"trades": 6594, "wins": 5105, "pnl": 31670.52},
        "M15": {"trades": 4314, "wins": 3305, "pnl": 24420.80},
    },
    "sym_stats": {
        "GBPUSD": {"trades": 4002, "wins": 3082, "pnl": 21482.42},
        "AUDUSD": {"trades": 4105, "wins": 3165, "pnl": 19194.15},
        "XAUUSD": {"trades": 2801, "wins": 2163, "pnl": 15414.74},
    },
    "monthly": {
        "2026-02": 1643.70,
        "2026-03": 2814.98,
        "2026-04": 3022.34,
        "2026-05": 4124.58,
        "2026-06": 4991.47,
        "2026-07": 4852.55,
        "2026-08": 34641.70,
    },
}


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(255, 140, 0)
        self.cell(0, 14, "KINGADE SCALPER BOT", new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_font("Helvetica", "", 12)
        self.set_text_color(100, 100, 100)
        self.cell(0, 7, "Backtest Performance Report", new_x="LMARGIN", new_y="NEXT", align="C")
        self.cell(0, 5, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)
        self.set_draw_color(255, 140, 0)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Kingade Scalper Bot | Page {self.page_no()}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(255, 140, 0)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(255, 140, 0)
        self.set_line_width(0.4)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def stat(self, label, value, bold=False):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 60, 60)
        self.cell(95, 7, label)
        s = "B" if bold else ""
        self.set_font("Helvetica", s, 10)
        self.set_text_color(30, 30, 30)
        self.cell(0, 7, str(value), new_x="LMARGIN", new_y="NEXT")

    def big_stat(self, label, value):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(60, 60, 60)
        self.cell(95, 9, label)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(0, 150, 0) if "+" in str(value) or float(str(value).replace("$","").replace(",","").replace("%","").replace("(","").replace(")","").replace("+","")) > 0 else self.set_text_color(200,0,0)
        self.cell(0, 9, str(value), new_x="LMARGIN", new_y="NEXT")

    def table_header(self, cols, widths):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(50, 50, 50)
        self.set_text_color(255, 255, 255)
        for i, c in enumerate(cols):
            self.cell(widths[i], 8, c, border=0, fill=True, align="C")
        self.ln()

    def table_row(self, cols, widths, alt=False):
        self.set_font("Helvetica", "", 9)
        self.set_fill_color(245, 245, 245) if alt else self.set_fill_color(255, 255, 255)
        self.set_text_color(40, 40, 40)
        for i, c in enumerate(cols):
            a = "L" if i == 0 else "R"
            self.cell(widths[i], 7, str(c), border=0, fill=True, align=a)
        self.ln()


def generate_pdf():
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Config
    pdf.section_title("CONFIGURATION")
    pdf.stat("Strategy", "Hammer/Star (M1) + Fibonacci Zone (M15)")
    pdf.stat("Entry Mode", "No filters - pure pattern/zone entry")
    pdf.stat("Risk Per Trade", "4.0%")
    pdf.stat("ATR SL Multiplier", "XAUUSD: 2.0x | Forex: 4.0x")
    pdf.stat("ATR TP Multiplier", "XAUUSD: 2.5x | Forex: 5.0x")
    pdf.stat("Trailing Stop", "Start: 1.0x ATR | Step: 0.15x ATR")
    pdf.stat("Trend Filter", "DISABLED")
    pdf.stat("Momentum Filter", "DISABLED")
    pdf.stat("Confirmation", "DISABLED")
    pdf.stat("Symbols", "XAUUSD, GBPUSD, AUDUSD")
    pdf.stat("Timeframes", "M1 (Gold), M15 (Forex)")
    pdf.stat("Backtest Period", "6 Months (Feb - Aug 2026)")
    pdf.ln(5)

    # Account
    pdf.section_title("ACCOUNT SUMMARY")
    pdf.big_stat("Initial Balance", f"${R['initial_balance']:,.2f}")
    pdf.big_stat("Final Balance", f"${R['final_balance']:,.2f}")
    pdf.big_stat("Net Profit/Loss", f"${R['total_pnl']:,.2f} (+{R['total_pnl_pct']:.2f}%)")
    pdf.ln(5)

    # Trade Stats
    pdf.section_title("TRADE STATISTICS")
    pdf.stat("Total Trades", f"{R['total_trades']:,}")
    pdf.stat("Winning Trades", f"{R['wins']:,}")
    pdf.stat("Losing Trades", f"{R['losses']:,}")
    pdf.stat("Win Rate", f"{R['win_rate']:.1f}%", bold=True)
    pdf.stat("Profit Factor", f"{R['profit_factor']:.2f}", bold=True)
    pdf.stat("Average R:R", f"{R['avg_rr']:.2f}")
    pdf.stat("Expectancy/Trade", f"${R['expectancy']:.2f}")
    pdf.stat("Avg Bars Held", f"{R['avg_bars_held']:.1f}")
    pdf.ln(5)

    # Risk
    pdf.section_title("RISK METRICS")
    pdf.stat("Max Drawdown", f"${R['max_dd']:,.2f}")
    pdf.stat("Max Drawdown %", f"{R['max_dd_pct']:.2f}%", bold=True)
    pdf.stat("Sharpe Ratio", f"{R['sharpe']:.2f}", bold=True)
    pdf.stat("Recovery Factor", f"{R['recovery']:.2f}")
    pdf.stat("Calmar Ratio", f"{R['calmar']:.2f}")
    pdf.ln(5)

    # Win/Loss
    pdf.section_title("WIN / LOSS BREAKDOWN")
    pdf.stat("Average Win", f"${R['avg_win']:,.2f}")
    pdf.stat("Average Loss", f"${R['avg_loss']:,.2f}")
    pdf.stat("Largest Win", f"${R['largest_win']:,.2f}")
    pdf.stat("Largest Loss", f"${R['largest_loss']:,.2f}")
    pdf.ln(5)

    # By Timeframe
    pdf.section_title("PERFORMANCE BY TIMEFRAME")
    w = [45, 40, 40, 65]
    pdf.table_header(["Timeframe", "Trades", "Win Rate", "P/L"], w)
    for i, (tf, s) in enumerate(sorted(R["tf_stats"].items())):
        wr = s["wins"] / s["trades"] * 100
        pdf.table_row([tf, str(s["trades"]), f"{wr:.1f}%", f"${s['pnl']:,.2f}"], w, alt=(i % 2 == 0))
    pdf.ln(5)

    # By Symbol
    pdf.section_title("PERFORMANCE BY SYMBOL")
    w = [45, 40, 40, 65]
    pdf.table_header(["Symbol", "Trades", "Win Rate", "P/L"], w)
    for i, (sym, s) in enumerate(sorted(R["sym_stats"].items(), key=lambda x: x[1]["pnl"], reverse=True)):
        wr = s["wins"] / s["trades"] * 100
        pdf.table_row([sym, str(s["trades"]), f"{wr:.1f}%", f"${s['pnl']:,.2f}"], w, alt=(i % 2 == 0))
    pdf.ln(5)

    # Monthly
    pdf.section_title("MONTHLY PROFIT / LOSS")
    w = [50, 65, 75]
    pdf.table_header(["Month", "P/L", "Cumulative"], w)
    cum = 0
    for i, (m, pnl) in enumerate(sorted(R["monthly"].items())):
        cum += pnl
        pdf.table_row([m, f"${pnl:,.2f}", f"${cum:,.2f}"], w, alt=(i % 2 == 0))
    pdf.ln(5)

    # Equity curve
    pdf.section_title("EQUITY CURVE")
    vals = [1000, 2644, 5459, 8481, 12606, 17597, 22450, 57091]
    mn, mx = min(vals), max(vals)
    h = 12
    pdf.set_font("Courier", "", 7)
    pdf.set_text_color(40, 40, 40)
    for row in range(h, -1, -1):
        thresh = mn + (mx - mn) * row / h
        line = ""
        for v in vals:
            line += "#" if v >= thresh else " "
        if row == h:
            lbl = f"${mx:>9,.0f} |"
        elif row == 0:
            lbl = f"${mn:>9,.0f} |"
        elif row == h // 2:
            lbl = f"${(mx+mn)/2:>9,.0f} |"
        else:
            lbl = " " * 11 + "|"
        pdf.cell(0, 4, lbl + line, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 4, " " * 11 + "+" + "-" * len(vals), new_x="LMARGIN", new_y="NEXT")

    # Disclaimer
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 4,
        "DISCLAIMER: Past performance does not guarantee future results. "
        "Trading forex and commodities carries significant risk. "
        "Backtest results are simulated and may not reflect real market conditions "
        "including slippage, spreads, and execution delays. "
        "Only trade with capital you can afford to lose.")

    path = "C:/Users/kinga/Documents/My Site/M1-M5 scalping/Kingade_Backtest_Report.pdf"
    pdf.output(path)
    return path


def send_pdf(path):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    with open(path, "rb") as f:
        resp = requests.post(url, data={"chat_id": CHAT_ID, "caption": "Kingade Scalper Bot - Full Backtest Report (No Filters, 6 Months, 3 Symbols)"}, files={"document": f}, timeout=120)
    data = resp.json()
    print(f"Sent: {data.get('ok', False)}")
    return data.get("ok", False)


if __name__ == "__main__":
    print("Generating PDF...")
    path = generate_pdf()
    print(f"PDF saved: {path}")

    print("Sending to Telegram...")
    send_pdf(path)
    print("Done!")
