import requests
from fpdf import FPDF
from datetime import datetime

TELEGRAM_TOKEN = "8803542513:AAF4TtMmcWIHAj88xNxsjHH8NYxqHMUfwag"
CHAT_ID = "6412335897"

DAYS = [
    {"date": "2026-08-18", "day": "Mon", "trades": 38, "wins": 20, "losses": 18, "pnl": -53.18, "lots": 3.15, "equity": 946.82},
    {"date": "2026-08-19", "day": "Tue", "trades": 158, "wins": 115, "losses": 43, "pnl": 1726.28, "lots": 13.29, "equity": 2673.10},
    {"date": "2026-08-20", "day": "Wed", "trades": 317, "wins": 217, "losses": 100, "pnl": 2135.11, "lots": 28.62, "equity": 4808.21},
    {"date": "2026-08-21", "day": "Thu", "trades": 461, "wins": 310, "losses": 151, "pnl": 2731.75, "lots": 42.56, "equity": 7539.96},
    {"date": "2026-08-22", "day": "Fri", "trades": 561, "wins": 375, "losses": 186, "pnl": 3948.35, "lots": 58.23, "equity": 11488.31},
    {"date": "2026-08-23", "day": "Sat", "trades": 48, "wins": 29, "losses": 19, "pnl": 171.55, "lots": 7.03, "equity": 14387.86},
    {"date": "2026-08-24", "day": "Sun", "trades": 416, "wins": 270, "losses": 146, "pnl": 2771.94, "lots": 45.32, "equity": 17159.81},
    {"date": "2026-08-25", "day": "Mon", "trades": 244, "wins": 180, "losses": 64, "pnl": 2882.92, "lots": 27.26, "equity": 20042.72},
]

SYMBOLS = [
    {"name": "XAUUSD (M1)", "trades": 1942, "wins": 1263, "losses": 679, "pnl": 11271.76, "lots": 189.08},
    {"name": "GBPUSD (M15)", "trades": 147, "wins": 129, "losses": 18, "pnl": 3351.85, "lots": 28.42},
    {"name": "AUDUSD (M15)", "trades": 150, "wins": 141, "losses": 9, "pnl": 4419.11, "lots": 48.59},
]

INITIAL = 1000.0


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(255, 140, 0)
        self.cell(0, 14, "KINGADE SCALPER BOT", new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_font("Helvetica", "", 11)
        self.set_text_color(100, 100, 100)
        self.cell(0, 7, "Backtest Performance Report", new_x="LMARGIN", new_y="NEXT", align="C")
        self.cell(0, 6, f"Aug 18-25, 2026 | No Filters | 3 Symbols | M1+M15", new_x="LMARGIN", new_y="NEXT", align="C")
        self.cell(0, 5, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(3)
        self.set_draw_color(255, 140, 0)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Kingade Scalper Bot | Page {self.page_no()}", align="C")

    def section(self, title):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(255, 140, 0)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(255, 140, 0)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def kv(self, label, value, bold=False):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 60, 60)
        self.cell(95, 7, label)
        s = "B" if bold else ""
        self.set_font("Helvetica", s, 10)
        self.set_text_color(30, 30, 30)
        self.cell(0, 7, str(value), new_x="LMARGIN", new_y="NEXT")

    def big(self, label, value):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(60, 60, 60)
        self.cell(95, 10, label)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(0, 140, 0)
        self.cell(0, 10, str(value), new_x="LMARGIN", new_y="NEXT")

    def tbl_header(self, cols, widths):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(50, 50, 50)
        self.set_text_color(255, 255, 255)
        for i, c in enumerate(cols):
            self.cell(widths[i], 8, c, border=0, fill=True, align="C")
        self.ln()

    def tbl_row(self, cols, widths, alt=False):
        self.set_font("Helvetica", "", 9)
        self.set_fill_color(245, 245, 245) if alt else self.set_fill_color(255, 255, 255)
        self.set_text_color(40, 40, 40)
        for i, c in enumerate(cols):
            a = "L" if i == 0 else "R"
            if i == 3 and "$" in str(c):
                if c.startswith("+"):
                    self.set_text_color(0, 140, 0)
                elif c.startswith("-"):
                    self.set_text_color(200, 0, 0)
            self.cell(widths[i], 7, str(c), border=0, fill=True, align=a)
            self.set_text_color(40, 40, 40)
        self.ln()


def generate():
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Config
    pdf.section("CONFIGURATION")
    pdf.kv("Strategy", "Hammer/Star (M1) + Fibonacci Zone (M15)")
    pdf.kv("Entry Mode", "No filters - pure pattern/zone entry")
    pdf.kv("Risk Per Trade", "4.0%")
    pdf.kv("ATR SL", "XAUUSD: 2.0x | Forex: 4.0x")
    pdf.kv("ATR TP", "XAUUSD: 2.5x | Forex: 5.0x")
    pdf.kv("Trailing Stop", "Start: 1.0x ATR | Step: 0.15x ATR")
    pdf.kv("Trend Filter", "OFF")
    pdf.kv("Momentum Filter", "OFF")
    pdf.kv("Confirmation", "OFF")
    pdf.kv("Symbols", "XAUUSD, GBPUSD, AUDUSD")
    pdf.kv("Timeframes", "M1 (Gold), M15 (Forex)")
    pdf.kv("Period", "Aug 18-25, 2026 (7 days)")
    pdf.ln(5)

    # Overall
    final = DAYS[-1]["equity"]
    total_pnl = final - INITIAL
    total_return = (total_pnl / INITIAL) * 100
    total_trades = sum(d["trades"] for d in DAYS)
    total_wins = sum(d["wins"] for d in DAYS)
    total_losses = sum(d["losses"] for d in DAYS)
    total_lots = sum(d["lots"] for d in DAYS)
    wr = total_wins / total_trades * 100 if total_trades else 0
    avg_win = sum(d["pnl"] for d in DAYS if d["pnl"] > 0) / total_wins if total_wins else 0
    avg_loss = sum(d["pnl"] for d in DAYS if d["pnl"] < 0) / total_losses if total_losses else 0

    pdf.section("ACCOUNT SUMMARY")
    pdf.big("Starting Balance", f"${INITIAL:,.2f}")
    pdf.big("Final Equity", f"${final:,.2f}")
    pdf.big("Total P/L", f"${total_pnl:+,.2f} ({total_return:+.1f}%)")
    pdf.ln(3)

    pdf.section("TRADE STATISTICS")
    pdf.kv("Total Trades", f"{total_trades:,}")
    pdf.kv("Winning Trades", f"{total_wins:,}")
    pdf.kv("Losing Trades", f"{total_losses:,}")
    pdf.kv("Win Rate", f"{wr:.1f}%", bold=True)
    pdf.kv("Total Lots Traded", f"{total_lots:,.2f}")
    pdf.kv("Avg Trades/Day", f"{total_trades // len(DAYS)}")
    pdf.kv("Avg Win/Trade", f"${avg_win:+.2f}")
    pdf.kv("Avg Loss/Trade", f"${avg_loss:+.2f}")
    pdf.ln(5)

    # Daily
    pdf.section("DAILY BREAKDOWN")
    w = [28, 16, 22, 22, 22, 30, 32, 28]
    pdf.tbl_header(["Date", "Day", "Trades", "Wins", "Losses", "P/L", "Equity", "Lots"], w)
    for i, d in enumerate(DAYS):
        pnl_str = f"${d['pnl']:+,.2f}"
        pdf.tbl_row([
            d["date"], d["day"], str(d["trades"]),
            str(d["wins"]), str(d["losses"]),
            pnl_str, f"${d['equity']:,.2f}", f"{d['lots']:.2f}"
        ], w, alt=(i % 2 == 0))

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(50, 50, 50)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(28, 8, "TOTAL", border=0, fill=True, align="L")
    pdf.cell(16, 8, "", border=0, fill=True, align="R")
    pdf.cell(22, 8, str(total_trades), border=0, fill=True, align="R")
    pdf.cell(22, 8, str(total_wins), border=0, fill=True, align="R")
    pdf.cell(22, 8, str(total_losses), border=0, fill=True, align="R")
    pdf.cell(30, 8, f"${total_pnl:+,.2f}", border=0, fill=True, align="R")
    pdf.cell(32, 8, f"${final:,.2f}", border=0, fill=True, align="R")
    pdf.cell(28, 8, f"{total_lots:.2f}", border=0, fill=True, align="R")
    pdf.ln(8)

    # By Symbol
    pdf.section("PERFORMANCE BY SYMBOL")
    w2 = [40, 25, 25, 25, 35, 30]
    pdf.tbl_header(["Symbol", "Trades", "Wins", "Losses", "P/L", "Lots"], w2)
    for i, s in enumerate(SYMBOLS):
        pdf.tbl_row([
            s["name"], str(s["trades"]), str(s["wins"]),
            str(s["losses"]), f"${s['pnl']:+,.2f}", f"{s['lots']:.2f}"
        ], w2, alt=(i % 2 == 0))
    pdf.ln(5)

    # P/L Bar Chart
    pdf.section("DAILY P/L VISUAL")
    max_pnl = max(abs(d["pnl"]) for d in DAYS)
    pdf.set_font("Courier", "", 8)
    for d in DAYS:
        pnl = d["pnl"]
        bar_len = int(abs(pnl) / max_pnl * 40) if max_pnl > 0 else 0
        bar = "+" * bar_len if pnl >= 0 else "-" * bar_len
        if pnl >= 0:
            pdf.set_text_color(0, 130, 0)
        else:
            pdf.set_text_color(200, 0, 0)
        pdf.cell(0, 5, f"  {d['date']} {d['day']} | ${pnl:>+10,.2f} | {bar}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(40, 40, 40)
    pdf.ln(3)

    # Equity Curve
    pdf.section("EQUITY CURVE")
    equities = [INITIAL] + [d["equity"] for d in DAYS]
    mn, mx = min(equities), max(equities)
    h = 10
    pdf.set_font("Courier", "", 7)
    pdf.set_text_color(40, 40, 40)
    for row in range(h, -1, -1):
        thresh = mn + (mx - mn) * row / h
        line = ""
        for v in equities:
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
    pdf.cell(0, 4, " " * 11 + "+" + "-" * len(equities), new_x="LMARGIN", new_y="NEXT")

    # Key Insights
    pdf.ln(5)
    pdf.section("KEY INSIGHTS")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(40, 40, 40)
    insights = [
        f"1. {total_trades:,} trades in 7 days averaging {total_trades // 7}/day",
        f"2. Win rate of {wr:.1f}% with zero filters - pure entry execution",
        f"3. AUDUSD best performer: 94% WR with Fibonacci entries",
        f"4. GBPUSD second: 87% WR with Fibonacci entries",
        f"5. XAUUSD M1 drives volume: 1,942 trades, 65% Hammer/Star WR",
        f"6. Equity grew every day except Monday (first session)",
        f"7. $1K grew to ${final:,.2f} in 7 trading days",
        f"8. Profitable across all 3 symbols simultaneously",
    ]
    for ins in insights:
        pdf.cell(0, 6, ins, new_x="LMARGIN", new_y="NEXT")

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


def send(path):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    with open(path, "rb") as f:
        resp = requests.post(url, data={"chat_id": CHAT_ID, "caption": "Kingade Scalper Bot - Full Backtest Report (No Filters, Aug 18-25, 2026)"}, files={"document": f}, timeout=120)
    print(f"Sent: {resp.json().get('ok', False)}")


if __name__ == "__main__":
    print("Generating PDF...")
    path = generate()
    print(f"Saved: {path}")
    print("Sending...")
    send(path)
    print("Done!")
