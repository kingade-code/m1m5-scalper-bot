import sys
sys.path.insert(0, "C:/Users/kinga/Documents/My Site/M1-M5 scalping")
from fpdf import FPDF
import math


class StrategyPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, "Kingade Scalper Bot  |  Strategy Guide  |  Confidential", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 190, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, "Kingade Forex  |  Page {}".format(self.page_no()), align="C")

    def section_title(self, title, num=""):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(0, 100, 50)
        self.cell(0, 12, "{} {}".format(num, title), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 150, 70)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 80, self.get_y())
        self.set_line_width(0.2)
        self.ln(6)

    def sub_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(40, 40, 40)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 5.5, text)
        self.ln(3)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(50, 50, 50)
        x = self.get_x()
        self.cell(8, 5.5, chr(8226))
        self.multi_cell(0, 5.5, text)

    def draw_hammer(self, x, y, scale=1.0, label=""):
        s = scale
        # Body (small rectangle)
        self.set_fill_color(0, 180, 80)
        self.rect(x + 3 * s, y + 8 * s, 6 * s, 4 * s, "F")
        # Wick (line above)
        self.set_draw_color(0, 180, 80)
        self.set_line_width(1.2 * s)
        self.line(x + 6 * s, y + 8 * s, x + 6 * s, y + 1 * s)
        # Long shadow (line below)
        self.line(x + 6 * s, y + 12 * s, x + 6 * s, y + 25 * s)
        self.set_line_width(0.2)
        if label:
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(0, 120, 50)
            self.set_xy(x - 2 * s, y + 27 * s)
            self.cell(16 * s, 5, label, align="C")

    def draw_star(self, x, y, scale=1.0, label=""):
        s = scale
        # Body (small rectangle, red)
        self.set_fill_color(220, 50, 50)
        self.rect(x + 3 * s, y + 10 * s, 6 * s, 4 * s, "F")
        # Wick above (long)
        self.set_draw_color(220, 50, 50)
        self.set_line_width(1.2 * s)
        self.line(x + 6 * s, y + 10 * s, x + 6 * s, y + 1 * s)
        # Small shadow below
        self.line(x + 6 * s, y + 14 * s, x + 6 * s, y + 18 * s)
        self.set_line_width(0.2)
        if label:
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(180, 30, 30)
            self.set_xy(x - 2 * s, y + 20 * s)
            self.cell(16 * s, 5, label, align="C")

    def draw_candle(self, x, y, color, body_h=8, wick_up=5, wick_dn=5, s=1.0):
        r, g, b = color
        self.set_fill_color(r, g, b)
        self.set_draw_color(r, g, b)
        # Body
        self.rect(x, y + wick_up * s, 5 * s, body_h * s, "F")
        # Wick up
        self.set_line_width(1.0 * s)
        self.line(x + 2.5 * s, y, x + 2.5 * s, y + wick_up * s)
        # Wick down
        self.line(x + 2.5 * s, y + (wick_up + body_h) * s, x + 2.5 * s, y + (wick_up + body_h + wick_dn) * s)
        self.set_line_width(0.2)

    def draw_trade_setup(self, x, y):
        # Entry candle
        self.draw_candle(x, y, (0, 180, 80), body_h=6, wick_up=3, wick_dn=3, s=1.5)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(0, 100, 50)
        self.set_xy(x - 5, y + 20)
        self.cell(20, 4, "ENTRY", align="C")

        # SL line
        self.set_draw_color(220, 50, 50)
        self.set_line_width(0.5)
        self.line(x - 15, y + 35, x + 30, y + 35)
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(220, 50, 50)
        self.set_xy(x - 15, y + 36)
        self.cell(20, 4, "SL (-2.5x ATR)")

        # TP line
        self.set_draw_color(0, 150, 70)
        self.line(x - 15, y - 10, x + 30, y - 10)
        self.set_text_color(0, 150, 70)
        self.set_xy(x - 15, y - 16)
        self.cell(20, 4, "TP (+3.0x ATR)")

        # Trail line
        self.set_draw_color(0, 100, 200)
        self.set_line_width(0.3)
        self.set_dash_pattern(2, 2)
        self.line(x - 15, y + 5, x + 30, y + 5)
        self.set_dash_pattern()
        self.set_text_color(0, 100, 200)
        self.set_xy(x + 20, y + 1)
        self.cell(25, 4, "TRAIL (0.5x)")

    def draw_trade_flow(self, x, y):
        # Step boxes
        steps = [
            ("1. SCANNING", "Bot checks M1\ncandles every\n10 seconds", (240, 240, 240)),
            ("2. PATTERN\n   DETECTED", "Hammer or Star\nfound on M1", (220, 255, 220)),
            ("3. ENTRY", "Buy/Sell at\nclose of signal\ncandle", (200, 240, 255)),
            ("4. SL & TP\n   SET", "SL = -2.5x ATR\nTP = +3.0x ATR", (255, 240, 200)),
            ("5. TRAILING\n   STOP", "Moves up as\nprice goes in\nour favor", (230, 220, 255)),
            ("6. EXIT", "TP hit = WIN\nSL hit = LOSS\n60 bars = CLOSE", (255, 230, 230)),
        ]

        box_w = 28
        box_h = 22
        gap = 3
        for i, (title, desc, color) in enumerate(steps):
            bx = x + i * (box_w + gap)
            r, g, b = color
            self.set_fill_color(r, g, b)
            self.set_draw_color(100, 100, 100)
            self.rect(bx, y, box_w, box_h, "DF")
            # Arrow
            if i < len(steps) - 1:
                self.set_draw_color(0, 120, 60)
                self.set_line_width(0.6)
                ax = bx + box_w
                self.line(ax, y + box_h / 2, ax + gap, y + box_h / 2)
                self.line(ax + gap - 2, y + box_h / 2 - 2, ax + gap, y + box_h / 2)
                self.line(ax + gap - 2, y + box_h / 2 + 2, ax + gap, y + box_h / 2)
                self.set_line_width(0.2)

            self.set_font("Helvetica", "B", 5.5)
            self.set_text_color(30, 30, 30)
            self.set_xy(bx + 1, y + 1)
            self.multi_cell(box_w - 2, 3.5, title, align="C")
            self.set_font("Helvetica", "", 5)
            self.set_text_color(80, 80, 80)
            self.set_xy(bx + 1, y + 11)
            self.multi_cell(box_w - 2, 3.2, desc, align="C")


def generate():
    pdf = StrategyPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)

    # ==================== PAGE 1: COVER ====================
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(0, 100, 50)
    pdf.cell(0, 15, "KINGADE SCALPER BOT", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "Strategy Guide & Documentation", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_draw_color(0, 150, 70)
    pdf.set_line_width(1)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    info = [
        "Version: 2.1.0",
        "Strategy: M1 Candlestick Pattern Scalping",
        "Symbols: XAUUSD (Gold), GBPUSD, AUDUSD",
        "Risk Per Trade: 4% of equity",
        "License: KNG-XXXX-XXXX-XXXX required",
    ]
    for line in info:
        pdf.cell(0, 7, line, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(20)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 6, "Confidential  |  Kingade Forex  |  kingade.fx@gmail.com", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Purchase: https://sellix.io/kingadebot", align="C", new_x="LMARGIN", new_y="NEXT")

    # ==================== PAGE 2: STRATEGY OVERVIEW ====================
    pdf.add_page()
    pdf.section_title("Strategy Overview", "01")

    pdf.body_text(
        "The Kingade Scalper Bot is an automated trading system that executes short-term trades on the "
        "1-minute (M1) timeframe. It uses candlestick pattern recognition to identify high-probability "
        "reversal setups, entering trades with tight risk management and dynamic trailing stops."
    )

    pdf.sub_title("Core Philosophy")
    pdf.body_text(
        "The strategy is built on three pillars:\n"
        "1. Pattern Recognition: Identifying Hammer and Shooting Star candlestick patterns on M1.\n"
        "2. Risk Management: Fixed 4% risk per trade with ATR-based stop losses.\n"
        "3. Profit Maximization: Trailing stop that locks in profits as price moves in our favor."
    )

    pdf.sub_title("How It Works (Quick Summary)")
    pdf.draw_trade_flow(10, pdf.get_y() + 2)
    pdf.ln(30)

    pdf.body_text(
        "The bot scans XAUUSD on the M1 timeframe every 10 seconds. When it detects a valid "
        "Hammer (bullish) or Shooting Star (bearish) pattern, it enters a trade in the opposite "
        "direction. The stop loss is set at 2.5x ATR, the take profit at 3.0x ATR, and a trailing "
        "stop activates after 0.5x ATR profit, stepping by 0.05x ATR."
    )

    # ==================== PAGE 3: PATTERN DETECTION ====================
    pdf.add_page()
    pdf.section_title("Pattern Detection", "02")

    pdf.sub_title("Hammer (Bullish Signal)")
    pdf.body_text(
        "A Hammer is a bullish reversal candlestick that appears at the bottom of a downtrend. "
        "It has a small body near the top and a long lower shadow (at least 2x the body size). "
        "This indicates that sellers pushed price down but buyers stepped in and pushed it back up."
    )
    pdf.draw_hammer(30, pdf.get_y() + 2, scale=2.0, label="HAMMER")
    pdf.set_xy(90, pdf.get_y() - 30)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(90, 5.5,
        "Characteristics:\n"
        "- Small body near the top of the candle\n"
        "- Long lower shadow (2x+ body size)\n"
        "- Little or no upper shadow\n"
        "- Appears after a downtrend\n"
        "- Signal: BUY (bullish reversal)"
    )
    pdf.ln(15)

    pdf.sub_title("Shooting Star (Bearish Signal)")
    pdf.body_text(
        "A Shooting Star is a bearish reversal candlestick that appears at the top of an uptrend. "
        "It has a small body near the bottom and a long upper shadow (at least 2x the body size). "
        "This indicates that buyers pushed price up but sellers stepped in and pushed it back down."
    )
    pdf.draw_star(30, pdf.get_y() + 2, scale=2.0, label="SHOOTING STAR")
    pdf.set_xy(90, pdf.get_y() - 25)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(90, 5.5,
        "Characteristics:\n"
        "- Small body near the bottom of the candle\n"
        "- Long upper shadow (2x+ body size)\n"
        "- Little or no lower shadow\n"
        "- Appears after an uptrend\n"
        "- Signal: SELL (bearish reversal)"
    )

    # ==================== PAGE 4: TRADE SETUP ====================
    pdf.add_page()
    pdf.section_title("Trade Setup & Execution", "03")

    pdf.sub_title("Entry Rules")
    pdf.body_text(
        "When a valid pattern is detected, the bot places a market order:\n\n"
        "BUY (Hammer detected):\n"
        "  - Entry: Close price of the signal candle\n"
        "  - Stop Loss: Entry - (2.5 x ATR)\n"
        "  - Take Profit: Entry + (3.0 x ATR)\n"
        "  - Lot Size: Based on 4% risk of current equity\n\n"
        "SELL (Shooting Star detected):\n"
        "  - Entry: Close price of the signal candle\n"
        "  - Stop Loss: Entry + (2.5 x ATR)\n"
        "  - Take Profit: Entry - (3.0 x ATR)\n"
        "  - Lot Size: Based on 4% risk of current equity"
    )

    pdf.sub_title("Visual Trade Setup")
    y_start = pdf.get_y() + 3
    pdf.draw_trade_setup(60, y_start)
    pdf.ln(38)

    pdf.sub_title("Lot Size Calculation")
    pdf.body_text(
        "The bot calculates lot size dynamically based on account equity:\n\n"
        "  Risk Amount = min(Equity x 4%, $40)\n"
        "  SL Distance = Entry - SL (in points)\n"
        "  Lot Size = Risk Amount / (SL Distance x Tick Value)\n\n"
        "This means as your account grows, the bot trades larger positions. "
        "On a $1,000 account, risk is $40 per trade. On $10,000, risk is $400."
    )

    # ==================== PAGE 5: TRAILING STOP ====================
    pdf.add_page()
    pdf.section_title("Trailing Stop Mechanism", "04")

    pdf.body_text(
        "The trailing stop is the key profit-locking mechanism. Once a trade is in profit by "
        "0.5x ATR, the stop loss starts following price upward (for buys) or downward (for sells)."
    )

    pdf.sub_title("How the Trailing Stop Works")
    pdf.body_text(
        "Parameters:\n"
        "  - Trail Start: 0.5x ATR (activates after this much profit)\n"
        "  - Trail Step: 0.05x ATR (how tightly the SL follows price)\n\n"
        "Example on XAUUSD (ATR = $5.00):\n"
        "  - Trail Start = $2.50 (SL moves after $2.50 profit)\n"
        "  - Trail Step = $0.25 (SL moves in $0.25 increments)\n\n"
        "Timeline:\n"
        "  1. Entry at $4620.00, SL at $4607.50, TP at $4635.00\n"
        "  2. Price rises to $4622.50 (+$2.50) -> Trail activates\n"
        "  3. SL moves from $4607.50 to $4622.25 (trail step applied)\n"
        "  4. Price rises to $4625.00 -> SL moves to $4624.75\n"
        "  5. Price rises to $4627.00 -> SL moves to $4626.75\n"
        "  6. Price drops to $4626.75 -> SL hit, trade closed at +$6.75 profit\n"
    )

    pdf.sub_title("Visual Trailing Stop")
    y0 = pdf.get_y() + 2
    # Draw price chart
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.3)
    # Axes
    pdf.line(20, y0 + 60, 180, y0 + 60)  # x-axis
    pdf.line(20, y0, 20, y0 + 60)  # y-axis

    # Price line (going up then pulling back)
    points = [(20, 55), (30, 50), (40, 48), (50, 42), (60, 38), (70, 35),
              (80, 30), (90, 28), (100, 25), (110, 22), (120, 20), (130, 24),
              (140, 28), (150, 32)]
    pdf.set_draw_color(0, 100, 200)
    pdf.set_line_width(0.8)
    for i in range(len(points) - 1):
        px1, py1 = points[i]
        px2, py2 = points[i + 1]
        pdf.line(px1, y0 + py1, px2, y0 + py2)

    # SL line (trailing)
    sl_points = [(20, 58), (30, 58), (40, 58), (50, 58), (60, 50), (70, 47),
                 (80, 42), (90, 40), (100, 37), (110, 34), (120, 32), (130, 32),
                 (140, 32), (150, 32)]
    pdf.set_draw_color(220, 50, 50)
    pdf.set_line_width(0.5)
    pdf.set_dash_pattern(3, 2)
    for i in range(len(sl_points) - 1):
        px1, py1 = sl_points[i]
        px2, py2 = sl_points[i + 1]
        pdf.line(px1, y0 + py1, px2, y0 + py2)
    pdf.set_dash_pattern()

    # TP line
    pdf.set_draw_color(0, 180, 80)
    pdf.set_line_width(0.5)
    pdf.line(20, y0 + 18, 150, y0 + 18)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(0, 150, 70)
    pdf.set_xy(152, y0 + 15)
    pdf.cell(25, 5, "TP (+3.0x ATR)")

    # Entry line
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.3)
    pdf.line(20, y0 + 55, 30, y0 + 55)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(20, y0 + 56)
    pdf.cell(20, 4, "ENTRY")

    # Labels
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(220, 50, 50)
    pdf.set_xy(152, y0 + 29)
    pdf.cell(25, 5, "TRAILING SL")
    pdf.set_text_color(0, 100, 200)
    pdf.set_xy(152, y0 + 40)
    pdf.cell(25, 5, "PRICE")
    pdf.set_text_color(150, 150, 150)
    pdf.set_xy(100, y0 + 61)
    pdf.cell(20, 4, "TIME ->")

    pdf.set_xy(10, y0 + 70)

    # ==================== PAGE 6: RISK MANAGEMENT ====================
    pdf.add_page()
    pdf.section_title("Risk Management", "05")

    pdf.sub_title("Position Sizing")
    pdf.body_text(
        "Every trade risks exactly 4% of current account equity, capped at $40 per trade.\n\n"
        "  $1,000 account  -> $40 risk per trade\n"
        "  $5,000 account  -> $200 risk per trade\n"
        "  $10,000 account -> $400 risk per trade (capped)\n\n"
        "This ensures the bot grows position sizes as the account grows, "
        "while protecting against catastrophic losses."
    )

    pdf.sub_title("Stop Loss")
    pdf.body_text(
        "The stop loss is ATR-based, set at 2.5x the 14-period ATR.\n\n"
        "  ATR measures actual market volatility\n"
        "  Higher ATR = wider stop (accommodates market noise)\n"
        "  Lower ATR = tighter stop (faster exits)\n\n"
        "This means the stop adapts to current market conditions, "
        "not a fixed dollar amount."
    )

    pdf.sub_title("Maximum Trade Duration")
    pdf.body_text(
        "If neither SL nor TP is hit within 60 M1 bars (1 hour), "
        "the trade is closed at market price. This prevents the bot "
        "from holding positions through unfavorable conditions."
    )

    pdf.sub_title("Risk Parameters Summary")
    # Table
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(0, 100, 50)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(60, 8, "Parameter", border=1, align="C", fill=True)
    pdf.cell(50, 8, "Value", border=1, align="C", fill=True)
    pdf.cell(70, 8, "Description", border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(50, 50, 50)
    rows = [
        ("Risk Per Trade", "4%", "Fixed % of equity"),
        ("Max Risk Amount", "$40", "Capped per trade"),
        ("SL Multiplier", "2.5x ATR", "Stop loss distance"),
        ("TP Multiplier", "3.0x ATR", "Take profit target"),
        ("Trail Start", "0.5x ATR", "When trailing activates"),
        ("Trail Step", "0.05x ATR", "Trailing increment"),
        ("Max Hold", "60 bars", "Force close after 1 hour"),
        ("Scan Interval", "10 sec", "How often bot checks"),
    ]
    for i, (param, val, desc) in enumerate(rows):
        if i % 2 == 0:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.cell(60, 7, param, border=1, align="C", fill=True)
        pdf.cell(50, 7, val, border=1, align="C", fill=True)
        pdf.cell(70, 7, desc, border=1, align="C", fill=True)
        pdf.ln()

    # ==================== PAGE 7: BACKTEST RESULTS ====================
    pdf.add_page()
    pdf.section_title("Backtest Results", "06")

    pdf.sub_title("Configuration Tested")
    pdf.body_text(
        "Symbol: XAUUSD  |  Timeframe: M1  |  Period: ~9 days (12,872 bars)\n"
        "SL: 2.5x ATR  |  TP: 3.0x ATR  |  Trail Start: 0.5x ATR  |  Trail Step: 0.05x ATR\n"
        "Initial Equity: $1,000  |  Risk: 4% per trade"
    )

    pdf.sub_title("Results")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(0, 100, 50)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(60, 8, "Metric", border=1, align="C", fill=True)
    pdf.cell(60, 8, "Value", border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    bt_rows = [
        ("Total Trades", "1,440"),
        ("Win Rate", "79.0%"),
        ("Avg Risk:Reward", "0.51"),
        ("Profit Factor", "1.50"),
        ("Total P/L", "+$5,911,190*"),
        ("Max Consec Wins", "15+"),
        ("Max Drawdown", "~5%"),
    ]
    for i, (m, v) in enumerate(bt_rows):
        if i % 2 == 0:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.cell(60, 7, m, border=1, align="C", fill=True)
        pdf.cell(60, 7, v, border=1, align="C", fill=True)
        pdf.ln()

    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "* Backtest results with compounding. Real results will vary due to max lot cap, slippage, and spread.", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf.sub_title("Why Option B Was Chosen")
    pdf.body_text(
        "We tested 3 configurations:\n\n"
        "  Option A (Original): SL=2.0 TP=2.5 Trail=1.0 Step=0.15\n"
        "    -> 59% WR, losing money. Trail too wide, winners reverse.\n\n"
        "  Option B (Selected): SL=2.5 TP=3.0 Trail=0.5 Step=0.05\n"
        "    -> 79% WR, highest P/L, best profit factor.\n\n"
        "  Option C (Balanced): SL=2.5 TP=3.5 Trail=0.75 Step=0.10\n"
        "    -> 75% WR, lower drawdown but less profit.\n\n"
        "Option B was selected because it has the highest win rate (79%), "
        "highest total profit, and best profit factor (1.50). The tighter "
        "trailing stop locks in profits quickly, preventing winners from "
        "reversing into losses."
    )

    # ==================== PAGE 8: MULTI-SYMBOL ====================
    pdf.add_page()
    pdf.section_title("Multi-Symbol Setup", "07")

    pdf.sub_title("Symbol Configuration")
    pdf.body_text(
        "The bot trades three symbols simultaneously, each with optimized settings:"
    )

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(0, 100, 50)
    pdf.set_text_color(255, 255, 255)
    headers = ["Symbol", "Entry Mode", "SL", "TP", "Trail", "Timeframe"]
    hw = [30, 35, 25, 25, 30, 35]
    for j, h in enumerate(headers):
        pdf.cell(hw[j], 8, h, border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(50, 50, 50)
    sym_rows = [
        ("XAUUSD", "Pattern (Hammer/Star)", "2.5x ATR", "3.0x ATR", "0.5x / 0.05x", "M1"),
        ("GBPUSD", "Fibonacci Retracement", "4.0x ATR", "5.0x ATR", "1.0x / 0.12x", "M15"),
        ("AUDUSD", "Fibonacci Retracement", "4.0x ATR", "5.0x ATR", "1.0x / 0.12x", "M15"),
    ]
    for i, row in enumerate(sym_rows):
        if i % 2 == 0:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)
        for j, v in enumerate(row):
            pdf.cell(hw[j], 7, v, border=1, align="C", fill=True)
        pdf.ln()

    pdf.ln(5)
    pdf.sub_title("Fibonacci Entry (Forex Pairs)")
    pdf.body_text(
        "For GBPUSD and AUDUSD, the bot uses Fibonacci retracement levels "
        "instead of candlestick patterns:\n\n"
        "  1. Detects swing highs and lows on M15 timeframe\n"
        "  2. Calculates Fibonacci retracement levels (0.5 - 0.786)\n"
        "  3. Enters when price pulls back into the Fibonacci zone\n"
        "  4. Uses wider SL/TP due to lower ATR on forex pairs"
    )

    pdf.sub_title("Risk Controls")
    pdf.body_text(
        "- Maximum 1 position per symbol\n"
        "- Maximum 10 total positions across all symbols\n"
        "- Each position has independent SL/TP\n"
        "- No hedging (won't open opposite positions on same symbol)\n"
        "- All trades use FOK filling mode (required by Exness)"
    )

    # ==================== PAGE 9: LICENSE ====================
    pdf.add_page()
    pdf.section_title("License & Activation", "08")

    pdf.sub_title("License Tiers")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(0, 100, 50)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(45, 8, "Tier", border=1, align="C", fill=True)
    pdf.cell(45, 8, "Key Prefix", border=1, align="C", fill=True)
    pdf.cell(45, 8, "Price", border=1, align="C", fill=True)
    pdf.cell(45, 8, "Duration", border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    tiers = [
        ("Free Trial", "N/A", "Free", "3 days"),
        ("Monthly", "KNG-M", "$99/month", "30 days"),
        ("Annual", "KNG-A", "$499/year", "365 days"),
        ("Lifetime", "KNG-L", "$999", "Forever"),
    ]
    for i, (tier, prefix, price, dur) in enumerate(tiers):
        if i % 2 == 0:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.cell(45, 7, tier, border=1, align="C", fill=True)
        pdf.cell(45, 7, prefix, border=1, align="C", fill=True)
        pdf.cell(45, 7, price, border=1, align="C", fill=True)
        pdf.cell(45, 7, dur, border=1, align="C", fill=True)
        pdf.ln()

    pdf.ln(5)
    pdf.sub_title("How to Activate")
    pdf.body_text(
        "1. Copy the license key provided after purchase\n"
        "2. Place it in the bot folder as 'license.json'\n"
        "3. Run 'python main.py'\n"
        "4. The bot validates the key on startup\n"
        "5. If valid, trading begins immediately\n\n"
        "The bot also checks for updates from GitHub on every startup, "
        "so you'll always have the latest version."
    )

    pdf.sub_title("Support")
    pdf.body_text(
        "Email: kingade.fx@gmail.com\n"
        "Telegram: @KingAdeFx\n"
        "Website: https://sellix.io/kingadebot\n\n"
        "For Exness account setup, use our referral link:\n"
        "https://one.exnesstrack.net/a/0fpwztsr9d"
    )

    # Save
    fname = "C:/Users/kinga/Documents/My Site/M1-M5 scalping/Kingade_Strategy_Guide.pdf"
    pdf.output(fname)
    return fname


if __name__ == "__main__":
    print("Generating strategy guide PDF...")
    fname = generate()
    print("Saved: {}".format(fname))

    import requests
    TELEGRAM_TOKEN = "8803542513:AAF4TtMmcWIHAj88xNxsjHH8NYxqHMUfwag"
    CHAT_ID = "6412335897"
    url = "https://api.telegram.org/bot{}/sendDocument".format(TELEGRAM_TOKEN)
    with open(fname, "rb") as f:
        r = requests.post(url, data={"chat_id": CHAT_ID, "caption": "<b>Kingade Scalper Bot - Strategy Guide</b>\nComplete strategy documentation with illustrations", "parse_mode": "HTML"},
                          files={"document": f}, timeout=30)
    print("Sent: {}".format(r.json().get("ok", False)))
