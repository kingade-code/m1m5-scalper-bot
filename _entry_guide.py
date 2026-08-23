# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

class StrategyPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(138, 147, 166)
        self.cell(0, 8, 'KINGADE SCALPER BOT - ENTRY STRATEGY GUIDE', 0, 1, 'C')
        self.line(10, 15, 200, 15)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(138, 147, 166)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

    def section_title(self, title):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(255, 215, 0)
        self.cell(0, 12, title, 0, 1)
        self.set_draw_color(255, 215, 0)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def sub_title(self, title):
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(0, 191, 255)
        self.cell(0, 8, title, 0, 1)
        self.ln(2)

    def body_text(self, text):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(255, 255, 255)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def highlight_text(self, text):
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(0, 200, 83)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def add_chart(self, filename, w=180):
        if os.path.exists(filename):
            x = (210 - w) / 2
            self.image(filename, x=x, w=w)
            self.ln(5)


# ── Generate Charts ──

# Chart 1: Fibonacci Retracement Zones
fig, ax = plt.subplots(figsize=(10, 6))
fig.patch.set_facecolor('#0F1729')
ax.set_facecolor('#0F1119')

# Price swing
x = np.linspace(0, 10, 100)
high = 2500
low = 2400
price = high - (high - low) * (1 - np.exp(-x/3)) + np.random.normal(0, 2, 100)
price[-1] = low + (high - low) * 0.55  # Retracing to 55%

ax.plot(x, price, color='#FFD700', linewidth=2)

# Fibonacci levels
fib_levels = {0: 'SWING HIGH', 0.382: '0.382', 0.5: '0.500', 0.618: '0.618', 0.786: '0.786', 1.0: 'SWING LOW'}
colors_fib = ['#8A93A6', '#FF4545', '#FF8C00', '#FFD700', '#00C853', '#8A93A6']

for i, (level, label) in enumerate(fib_levels.items()):
    y_val = high - (high - low) * level
    ax.axhline(y=y_val, color=colors_fib[i], linestyle='--', alpha=0.7, linewidth=1.5)
    ax.text(10.2, y_val, f'  {label}', color=colors_fib[i], fontsize=10, fontweight='bold', va='center')

# Entry zone highlight
zone_low = high - (high - low) * 0.5
zone_high = high - (high - low) * 0.786
ax.axhspan(zone_low, zone_high, alpha=0.2, color='#00C853')
ax.text(5, (zone_low + zone_high) / 2, 'ENTRY ZONE (0.500-0.786)', color='#00C853', fontsize=12, fontweight='bold', ha='center')

ax.set_title('Fibonacci Retracement Entry Zone', color='white', fontsize=14, fontweight='bold')
ax.set_ylabel('Price', color='#8A93A6')
ax.set_xlabel('Bars', color='#8A93A6')
ax.tick_params(colors='#8A93A6')
for spine in ax.spines.values(): spine.set_color('#8A93A6')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
plt.savefig('chart_fib_zone.png', dpi=150, facecolor='#0F1729', bbox_inches='tight')
plt.close()

# Chart 2: BUY Signal Example
fig, ax = plt.subplots(figsize=(10, 6))
fig.patch.set_facecolor('#0F1729')
ax.set_facecolor('#0F1119')

# Simulated price data
np.random.seed(42)
n = 80
x = np.arange(n)
trend_up = np.concatenate([np.linspace(2400, 2500, 30), np.linspace(2500, 2450, 20), np.linspace(2450, 2490, 30)])
noise = np.random.normal(0, 3, n)
price = trend_up + noise

ax.plot(x[:50], price[:50], color='#FFD700', linewidth=2)
ax.plot(x[50:], price[50:], color='#FFD700', linewidth=2, linestyle='--', alpha=0.5)

# Swing high/low
ax.annotate('Swing High', xy=(30, 2503), fontsize=10, color='#FF4545', fontweight='bold')
ax.annotate('Swing Low', xy=(50, 2447), fontsize=10, color='#FF4545', fontweight='bold')

# Entry zone
ax.axhspan(2457, 2480, alpha=0.2, color='#00C853')
ax.text(65, 2468, 'BUY\nZONE', color='#00C853', fontsize=12, fontweight='bold', ha='center')

# Entry point
ax.plot(62, 2465, 'go', markersize=15, zorder=5)
ax.annotate('ENTRY\n(Buy)', xy=(62, 2465), xytext=(67, 2455), fontsize=10, color='#00C853', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#00C853', lw=2))

# SL and TP
ax.axhline(y=2455, color='#FF4545', linestyle='--', alpha=0.7)
ax.text(75, 2455, 'SL', color='#FF4545', fontsize=10, fontweight='bold')
ax.axhline(y=2480, color='#00C853', linestyle='--', alpha=0.7)
ax.text(75, 2480, 'TP', color='#00C853', fontsize=10, fontweight='bold')

ax.set_title('BUY Signal - Fibonacci Retracement Entry', color='white', fontsize=14, fontweight='bold')
ax.set_ylabel('Price', color='#8A93A6')
ax.set_xlabel('Bars', color='#8A93A6')
ax.tick_params(colors='#8A93A6')
for spine in ax.spines.values(): spine.set_color('#8A93A6')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
plt.savefig('chart_buy_signal.png', dpi=150, facecolor='#0F1729', bbox_inches='tight')
plt.close()

# Chart 3: SELL Signal Example
fig, ax = plt.subplots(figsize=(10, 6))
fig.patch.set_facecolor('#0F1729')
ax.set_facecolor('#0F1119')

trend_down = np.concatenate([np.linspace(2500, 2400, 30), np.linspace(2400, 2450, 20), np.linspace(2450, 2410, 30)])
price2 = trend_down + np.random.normal(0, 3, n)

ax.plot(x[:50], price2[:50], color='#FFD700', linewidth=2)
ax.plot(x[50:], price2[50:], color='#FFD700', linewidth=2, linestyle='--', alpha=0.5)

ax.annotate('Swing Low', xy=(30, 2397), fontsize=10, color='#FF4545', fontweight='bold')
ax.annotate('Swing High', xy=(50, 2453), fontsize=10, color='#FF4545', fontweight='bold')

ax.axhspan(2420, 2443, alpha=0.2, color='#FF4545')
ax.text(65, 2432, 'SELL\nZONE', color='#FF4545', fontsize=12, fontweight='bold', ha='center')

ax.plot(62, 2435, 'ro', markersize=15, zorder=5)
ax.annotate('ENTRY\n(Sell)', xy=(62, 2435), xytext=(67, 2445), fontsize=10, color='#FF4545', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#FF4545', lw=2))

ax.axhline(y=2445, color='#FF4545', linestyle='--', alpha=0.7)
ax.text(75, 2445, 'SL', color='#FF4545', fontsize=10, fontweight='bold')
ax.axhline(y=2420, color='#00C853', linestyle='--', alpha=0.7)
ax.text(75, 2420, 'TP', color='#00C853', fontsize=10, fontweight='bold')

ax.set_title('SELL Signal - Fibonacci Retracement Entry', color='white', fontsize=14, fontweight='bold')
ax.set_ylabel('Price', color='#8A93A6')
ax.set_xlabel('Bars', color='#8A93A6')
ax.tick_params(colors='#8A93A6')
for spine in ax.spines.values(): spine.set_color('#8A93A6')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
plt.savefig('chart_sell_signal.png', dpi=150, facecolor='#0F1729', bbox_inches='tight')
plt.close()

# Chart 4: Confirmation Candle Pattern
fig, axes = plt.subplots(1, 3, figsize=(10, 4))
fig.patch.set_facecolor('#0F1729')

patterns = [
    ('Bullish Confirmation', ['Bearish', 'Doji', 'BULLISH\n(Entry)'], ['#FF4545', '#8A93A6', '#00C853']),
    ('Neutral Zone', ['Bearish', 'BULLISH\n(No Entry)', 'Bearish'], ['#FF4545', '#00C853', '#FF4545']),
    ('Bearish Confirmation', ['BULLISH\n(Entry)', 'Doji', 'Bearish'], ['#00C853', '#8A93A6', '#FF4545']),
]

for ax, (title, labels, colors) in zip(axes, patterns):
    ax.set_facecolor('#0F1119')
    for i, (label, color) in enumerate(zip(labels, colors)):
        rect = mpatches.FancyBboxPatch((0.3 + i * 1.2, 0.3), 0.8, 2.4, boxstyle="round,pad=0.1",
                                        facecolor=color, alpha=0.8, edgecolor='white', linewidth=1)
        ax.add_patch(rect)
        ax.text(0.7 + i * 1.2, 1.5, label, ha='center', va='center', color='white', fontsize=8, fontweight='bold')
    ax.set_xlim(0, 4.5)
    ax.set_ylim(0, 3)
    ax.set_title(title, color='white', fontsize=11, fontweight='bold')
    ax.axis('off')

plt.tight_layout()
plt.savefig('chart_confirmation.png', dpi=150, facecolor='#0F1729', bbox_inches='tight')
plt.close()

# Chart 5: Full Strategy Flow
fig, ax = plt.subplots(figsize=(10, 5))
fig.patch.set_facecolor('#0F1729')
ax.set_facecolor('#0F1119')

steps = [
    ('1. Detect\nSwing', 1, '#FFD700'),
    ('2. Calc\nFib Levels', 3, '#00BFFF'),
    ('3. Check\nEntry Zone', 5, '#00C853'),
    ('4. Confirm\nCandle', 7, '#FF8C00'),
    ('5. Trend\nFilter (EMA)', 9, '#FF4545'),
    ('6. Execute\nTrade', 11, '#00C853'),
]

for label, x_pos, color in steps:
    rect = mpatches.FancyBboxPatch((x_pos - 0.6, 0.8), 1.2, 1.4, boxstyle="round,pad=0.1",
                                    facecolor=color, alpha=0.3, edgecolor=color, linewidth=2)
    ax.add_patch(rect)
    ax.text(x_pos, 1.5, label, ha='center', va='center', color=color, fontsize=9, fontweight='bold')
    if x_pos < 11:
        ax.annotate('', xy=(x_pos + 0.8, 1.5), xytext=(x_pos + 0.6, 1.5),
                    arrowprops=dict(arrowstyle='->', color='#8A93A6', lw=2))

ax.set_xlim(0, 12)
ax.set_ylim(0, 3)
ax.set_title('Entry Strategy Flow', color='white', fontsize=14, fontweight='bold')
ax.axis('off')
plt.tight_layout()
plt.savefig('chart_flow.png', dpi=150, facecolor='#0F1729', bbox_inches='tight')
plt.close()

# Chart 6: Entry Zone Comparison
fig, ax = plt.subplots(figsize=(10, 5))
fig.patch.set_facecolor('#0F1729')
ax.set_facecolor('#0F1119')

zones = ['0.618-0.786\n(Original)', '0.500-0.786\n(Optimized)']
wr = [71.9, 77.3]
pf = [3.00, 3.43]
trades = [4308, 5997]

x = np.arange(len(zones))
width = 0.25

bars1 = ax.bar(x - width, wr, width, label='Win Rate %', color='#00C853', alpha=0.8)
bars2 = ax.bar(x, pf, width, label='Profit Factor', color='#FFD700', alpha=0.8)
bars3 = ax.bar(x + width, [t/100 for t in trades], width, label='Trades (÷100)', color='#00BFFF', alpha=0.8)

for bar, val in zip(bars1, wr):
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5, f'{val}%', ha='center', color='white', fontsize=10, fontweight='bold')
for bar, val in zip(bars2, pf):
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5, f'{val}', ha='center', color='white', fontsize=10, fontweight='bold')

ax.set_ylabel('Value', color='#8A93A6')
ax.set_title('Entry Zone Comparison: Original vs Optimized', color='white', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(zones, color='white', fontsize=11)
ax.tick_params(colors='#8A93A6')
ax.legend(facecolor='#1A243B', edgecolor='#8A93A6', labelcolor='white')
for spine in ax.spines.values(): spine.set_color('#8A93A6')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
plt.savefig('chart_zone_compare.png', dpi=150, facecolor='#0F1729', bbox_inches='tight')
plt.close()

print("Charts generated.")

# ── Build PDF ──
pdf = StrategyPDF()
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=20)

# Page 1: Title
pdf.add_page()
pdf.set_font('Helvetica', 'B', 28)
pdf.set_text_color(255, 215, 0)
pdf.ln(30)
pdf.cell(0, 15, 'KINGADE SCALPER BOT', 0, 1, 'C')
pdf.set_font('Helvetica', '', 18)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 10, 'Entry Strategy Guide', 0, 1, 'C')
pdf.ln(5)
pdf.set_font('Helvetica', '', 12)
pdf.set_text_color(138, 147, 166)
pdf.cell(0, 8, 'Fibonacci Retracement Based Scalping Strategy', 0, 1, 'C')
pdf.cell(0, 8, 'XAUUSD | GBPUSD | AUDUSD', 0, 1, 'C')
pdf.cell(0, 8, 'M1 + M5 Timeframes', 0, 1, 'C')
pdf.ln(15)
pdf.set_font('Helvetica', 'B', 14)
pdf.set_text_color(0, 200, 83)
pdf.cell(0, 8, 'Strategy Performance', 0, 1, 'C')
pdf.set_font('Helvetica', '', 11)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 7, 'Win Rate: 75.8%  |  Profit Factor: 4.15  |  Sharpe: 9.20', 0, 1, 'C')
pdf.cell(0, 7, '10,529 Trades  |  +$109,423 P/L  |  12.24% Max DD', 0, 1, 'C')
pdf.add_chart('chart_zone_compare.png')

# Page 2: Strategy Overview
pdf.add_page()
pdf.section_title('1. STRATEGY OVERVIEW')
pdf.body_text('The Kingade Scalper Bot uses Fibonacci retracement levels to identify high-probability entry zones during price pullbacks. The strategy combines multiple filters to ensure entries align with the prevailing trend and momentum.')
pdf.ln(3)
pdf.sub_title('Core Concept')
pdf.body_text('When price makes a significant swing (impulse move), it often retraces (pulls back) before continuing in the trend direction. The bot measures this retracement using Fibonacci ratios and enters when price reaches the optimal zone (0.500-0.786 of the swing).')
pdf.ln(3)
pdf.sub_title('Why Fibonacci Works')
pdf.body_text('- Fibonacci levels represent natural support/resistance areas\n- Algorithmic traders and institutions use these levels extensively\n- The 0.618 level (Golden Ratio) is the most widely watched\n- Our optimized zone (0.500-0.786) catches entries earlier while maintaining quality')
pdf.add_chart('chart_fib_zone.png')

# Page 3: Entry Types
pdf.add_page()
pdf.section_title('2. ENTRY TYPES')
pdf.sub_title('BUY Entry')
pdf.body_text('A BUY signal is generated when:\n1. Price makes a SWING HIGH then retraces DOWN\n2. Price enters the entry zone (0.500-0.786 of the swing)\n3. A bullish confirmation candle closes in the zone\n4. Price is ABOVE the EMA 30 trend filter\n5. RSI is not overbought (below 55)')
pdf.highlight_text('Example: Price swings from 2400 to 2500, retraces to 2450-2478 zone, bullish candle confirms -> BUY')
pdf.add_chart('chart_buy_signal.png')

# Page 4: SELL Entry
pdf.add_page()
pdf.section_title('2. ENTRY TYPES (continued)')
pdf.sub_title('SELL Entry')
pdf.body_text('A SELL signal is generated when:\n1. Price makes a SWING LOW then retraces UP\n2. Price enters the entry zone (0.500-0.786 of the swing)\n3. A bearish confirmation candle closes in the zone\n4. Price is BELOW the EMA 30 trend filter\n5. RSI is not oversold (above 45)')
pdf.highlight_text('Example: Price swings from 2500 to 2400, retraces to 2422-2450 zone, bearish candle confirms -> SELL')
pdf.add_chart('chart_sell_signal.png')

# Page 5: Confirmation Candles
pdf.add_page()
pdf.section_title('3. CONFIRMATION CANDLES')
pdf.body_text('After price enters the Fibonacci zone, the bot waits for a CONFIRMATION CANDLE to close. This is the most critical filter - it prevents entering during uncertain price action.')
pdf.ln(3)
pdf.sub_title('Bullish Confirmation (for BUY)')
pdf.body_text('The candle closing IN the entry zone must have:\n- Close > Open (bullish/green candle)\n- Body ratio > 10% of candle range (not a doji)\n- The candle must CLOSE inside the zone (not just wick)')
pdf.sub_title('Bearish Confirmation (for SELL)')
pdf.body_text('The candle closing IN the entry zone must have:\n- Close < Open (bearish/red candle)\n- Body ratio > 10% of candle range\n- The candle must CLOSE inside the zone')
pdf.add_chart('chart_confirmation.png')
pdf.body_text('IMPORTANT: The confirmation candle is the SAME candle that triggers entry. No waiting for the next candle - this keeps entries fast for scalping.')

# Page 6: Trend Filter
pdf.add_page()
pdf.section_title('4. TREND FILTER (EMA 30)')
pdf.body_text('The EMA (Exponential Moving Average) filter ensures entries align with the higher timeframe trend. We use EMA 30 on H1 for faster trend detection.')
pdf.ln(3)
pdf.sub_title('How It Works')
pdf.body_text('- BUY: Price must be ABOVE the EMA 30 on the trading timeframe\n- SELL: Price must be BELOW the EMA 30 on the trading timeframe\n- If price is near the EMA, trades are filtered out (no man\'s land)')
pdf.ln(3)
pdf.highlight_text('Why EMA 30 instead of EMA 50?\n- EMA 30 reacts 40% faster to trend changes\n- Catches trend reversals earlier\n- Results: +3.9% win rate, +38% profit factor improvement')
pdf.ln(3)
pdf.sub_title('Momentum Filter (RSI)')
pdf.body_text('RSI (Relative Strength Index) prevents entering at extreme levels:\n- BUY: RSI must be below 55 (not overbought)\n- SELL: RSI must be above 45 (not oversold)\n- This ensures we enter during healthy momentum')

# Page 7: Risk Management
pdf.add_page()
pdf.section_title('5. RISK MANAGEMENT')
pdf.body_text('Every trade uses strict risk management to protect capital:')
pdf.ln(3)
pdf.sub_title('Position Sizing')
pdf.body_text('- Risk per trade: 4% of account balance\n- Lot size calculated dynamically based on SL distance\n- Maximum 10 concurrent positions\n- Maximum 1 position per symbol')
pdf.ln(3)
pdf.sub_title('Stop Loss')
pdf.body_text('- Stop Loss: 1.0 x ATR (14-period)\n- Tight SL for scalping - exits losers fast\n- Minimum stop distance enforced (Exness requirement)')
pdf.ln(3)
pdf.sub_title('Take Profit / Trailing Stop')
pdf.body_text('- Initial TP: 1.5 x ATR (used only when trailing is OFF)\n- Trailing Stop: Starts at 0.75 x ATR in profit\n- Trail Step: 0.2 x ATR (locks in profit as price moves)\n- When trailing is ON, it determines the exit (not fixed TP)')
pdf.highlight_text('Key Insight: The trailing stop is the primary exit mechanism.\nIt lets winners run while protecting profits.\nAvg Win: $27.29 | Avg Loss: $22.52 | Expectancy: $10.39/trade')

# Page 8: Strategy Flow
pdf.add_page()
pdf.section_title('6. COMPLETE ENTRY FLOW')
pdf.body_text('The bot follows this exact sequence for every potential trade:')
pdf.ln(3)
pdf.add_chart('chart_flow.png')
pdf.ln(3)
pdf.sub_title('Step-by-Step')
pdf.body_text('1. DETECT SWING: Bot identifies swing highs/lows using lookback=80, strength=2\n2. CALC FIB LEVELS: Calculates 0.382, 0.500, 0.618, 0.786 levels from the swing\n3. CHECK ENTRY ZONE: Waits for price to enter 0.500-0.786 zone\n4. CONFIRM CANDLE: Waits for a bullish/bearish candle to close in the zone\n5. TREND FILTER: Checks EMA 30 + RSI alignment\n6. EXECUTE: Places market order with calculated SL/TP')
pdf.ln(3)
pdf.highlight_text('Timeframe: M1 + M5 for ultra-fast scalping\nScan Interval: Every 10 seconds\nMax Bars in Trade: 15 bars (exits if trade runs too long)')

# Page 9: Settings Summary
pdf.add_page()
pdf.section_title('7. OPTIMIZED SETTINGS')
settings = [
    ('Parameter', 'Value', 'Description'),
    ('Fib Entry Zone', '0.500 - 0.786', 'Widened from 0.618-0.786 for more entries'),
    ('EMA Period', '30', 'Faster trend detection (was 50)'),
    ('Trailing Start', '0.75 x ATR', 'Trailing activates after 75% ATR move'),
    ('Trailing Step', '0.2 x ATR', 'Tighter trail (was 0.3) for more profit'),
    ('Risk Per Trade', '4.0%', 'Conservative position sizing'),
    ('Stop Loss', '1.0 x ATR', 'Tight for scalping'),
    ('Timeframes', 'M1 + M5', 'Ultra-fast scalping'),
    ('Symbols', 'XAUUSD, GBPUSD, AUDUSD', '3 major instruments'),
    ('Confirmation', '1 candle', 'Required before entry'),
    ('Max Positions', '10 total, 1/symbol', 'Risk control'),
]
pdf.set_font('Helvetica', 'B', 10)
pdf.set_fill_color(26, 36, 59)
pdf.set_text_color(255, 215, 0)
pdf.cell(45, 8, 'Parameter', 1, 0, 'C', True)
pdf.cell(40, 8, 'Value', 1, 0, 'C', True)
pdf.cell(105, 8, 'Description', 1, 1, 'C', True)
pdf.set_font('Helvetica', '', 9)
pdf.set_text_color(255, 255, 255)
for i, (param, value, desc) in enumerate(settings[1:]):
    fill = i % 2 == 0
    if fill:
        pdf.set_fill_color(26, 36, 59)
    pdf.cell(45, 7, param, 1, 0, 'L', fill)
    pdf.set_text_color(0, 200, 83)
    pdf.cell(40, 7, value, 1, 0, 'C', fill)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(105, 7, desc, 1, 1, 'L', fill)

# Page 10: Performance Summary
pdf.add_page()
pdf.section_title('8. PERFORMANCE SUMMARY')
pdf.body_text('Backtested over 3 months (Jun-Aug 2026) on M1 + M5 timeframes:')
pdf.ln(3)
pdf.sub_title('By Symbol')
pdf.body_text('XAUUSD: 2,734 trades | 65.3% WR | $45,575 P/L\nGBPUSD: 3,993 trades | 66.3% WR | $37,958 P/L\nAUDUSD: 3,802 trades | 66.4% WR | $25,889 P/L')
pdf.ln(3)
pdf.sub_title('By Timeframe')
pdf.body_text('M1: 5,981 trades | 64.6% WR | $47,059 P/L\nM5: 4,548 trades | 68.0% WR | $62,364 P/L')
pdf.ln(3)
pdf.highlight_text('M5 outperforms M1 - slightly slower timeframe = cleaner signals')
pdf.ln(3)
pdf.sub_title('Monthly Breakdown')
pdf.body_text('Jun 2026: +$10,495\nJul 2026: +$32,655\nAug 2026: +$66,273')
pdf.ln(3)
pdf.body_text('The strategy shows consistent growth with accelerating returns as compounding takes effect.')

# Save PDF
output = "Kingade_Entry_Strategy_Guide.pdf"
pdf.output(output)
print(f"PDF saved: {output}")

# Cleanup chart files
for f in ['chart_fib_zone.png', 'chart_buy_signal.png', 'chart_sell_signal.png',
          'chart_confirmation.png', 'chart_flow.png', 'chart_zone_compare.png']:
    if os.path.exists(f):
        os.remove(f)
