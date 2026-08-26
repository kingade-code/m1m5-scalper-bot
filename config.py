# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import MetaTrader5 as mt5

# ─── MT5 Connection ───────────────────────────────────────────────
MT5_PATH = None
MT5_LOGIN = 476188356
MT5_PASSWORD = "Trail123@"
MT5_SERVER = "Exness-MT5Trial9"
MT5_TIMEOUT = 10_000

# ─── Timeframes ───────────────────────────────────────────────────
TIMEFRAMES = [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5]

# ─── Swing Detection ──────────────────────────────────────────────
SWING_LOOKBACK = 100  # Optimized: higher = better WR (66.7%)
SWING_STRENGTH = 2  # Lower = more swing points = more signals

# ─── Fibonacci Settings ───────────────────────────────────────────
FIB_ENTRY_LOW = 0.5
FIB_ENTRY_HIGH = 0.786

# ─── Risk Management ─────────────────────────────────────────────
RISK_PERCENT = 4.0
MAX_POSITIONS = 1
MAX_POSITIONS_PER_SYMBOL = 1
MAGIC_NUMBER = 777777
SLIPPAGE = 3

# ─── Symbol Filter ────────────────────────────────────────────────
AUTO_DISCOVER_SYMBOLS = False
SYMBOL_LIST = ["XAUUSD", "GBPUSD", "AUDUSD"]

# ─── Per-Symbol Overrides ────────────────────────────────────────
# Gold needs different settings due to wider ATR
SYMBOL_OVERRIDES = {
    "XAUUSD": {
        "TIMEFRAMES": [mt5.TIMEFRAME_M1],
        "ATR_SL_MULTIPLIER": 2.5,
        "ATR_TP_MULTIPLIER": 5.0,
        "TRAILING_START_ATR": 0.5,
        "TRAILING_STEP_ATR": 0.15,
        "SWING_LOOKBACK": 40,
        "TREND_EMA_PERIOD": 30,
        "ENTRY_MODE": "pattern",
        "SPREAD": 0.3,
        "RR_RATIO": 2.5,
    },
}

def get_symbol_param(symbol, param, default=None):
    """Get config param, checking symbol overrides first."""
    if symbol in SYMBOL_OVERRIDES and param in SYMBOL_OVERRIDES[symbol]:
        return SYMBOL_OVERRIDES[symbol][param]
    return globals().get(param, default)

def get_symbol_timeframes(symbol):
    """Get timeframes for a symbol, checking overrides first."""
    if symbol in SYMBOL_OVERRIDES and "TIMEFRAMES" in SYMBOL_OVERRIDES[symbol]:
        return SYMBOL_OVERRIDES[symbol]["TIMEFRAMES"]
    return TIMEFRAMES

# ─── Entry Mode ───────────────────────────────────────────────────
# "fibonacci" = Fibonacci retracement zone (default for forex)
# "pattern" = Candlestick pattern detection (Hammer/Star for gold)
ENTRY_MODE = "fibonacci"
REQUIRE_CONFIRMATION = False
CONFIRMATION_CANDLES = 1

# ─── Trend Filter ─────────────────────────────────────────────────
USE_TREND_FILTER = True
TREND_EMA_PERIOD = 40  # Optimized: EMA40 + SL2.5 = 66.7% WR

# ─── Momentum Filter ──────────────────────────────────────────────
USE_MOMENTUM_FILTER = False
RSI_PERIOD = 14
RSI_OVERSOLD = 55  # Relaxed RSI filter
RSI_OVERBOUGHT = 45  # Relaxed RSI filter
MIN_BODY_RATIO = 0.10  # Lower bar for more entries

# ─── ATR Stop Loss ───────────────────────────────────────────────
USE_ATR_SL = True
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 4.0  # V2: SL4.0 = 62.4% WR, RR 1:1.48, PF 3.36
MIN_STOP_DISTANCE = 1.0  # Minimum SL distance in price points

# ─── Scalper TP ───────────────────────────────────────────────────
ATR_TP_MULTIPLIER = 5.0  # V2: TP5.0 = higher RR, PF 3.36

# ─── Trailing Stop ────────────────────────────────────────────────
USE_TRAILING_STOP = True
TRAILING_START_ATR = 1.0  # V2: wider trail start = higher RR
TRAILING_STEP_ATR = 0.12  # V2: tighter step = better profit capture

# ─── Max Bars in Trade ────────────────────────────────────────────
MAX_BARS_IN_TRADE = 15  # Very fast exits for scalping

# ─── Logging ──────────────────────────────────────────────────────
LOG_LEVEL = "DEBUG"
LOG_FILE = "m1m5_scalper.log"

# ─── Telegram ─────────────────────────────────────────────────────
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = "8803542513:AAF4TtMmcWIHAj88xNxsjHH8NYxqHMUfwag"
TELEGRAM_CHAT_IDS = [6412335897]  # Private chat
TELEGRAM_GROUP_CHAT_ID = -1002127450559  # KINGADE FOREX group
TELEGRAM_GROUP_THREAD_ID = 3  # FREE SIGNALS topic

# ─── Scan Interval ────────────────────────────────────────────────
SCAN_INTERVAL_SECONDS = 10
