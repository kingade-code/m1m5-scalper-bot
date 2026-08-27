# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import MetaTrader5 as mt5

# ─── MT5 Connection ───────────────────────────────────────────────
MT5_PATH = None
MT5_LOGIN = None
MT5_PASSWORD = None
MT5_SERVER = None
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
MAX_RISK_PER_TRADE = 20.0  # Hard cap: max $20 risk per trade
MAX_POSITIONS = 1
MAX_POSITIONS_PER_SYMBOL = 1
MAX_LOT = 0.10  # Cap lot size to prevent risk blowup on tight SL
MAGIC_NUMBER = 777777
SLIPPAGE = 3

# ─── Symbol Filter ────────────────────────────────────────────────
AUTO_DISCOVER_SYMBOLS = False
SYMBOL_LIST = ["XAUUSD", "GBPUSD", "AUDUSD"]

# ─── Per-Symbol Overrides ────────────────────────────────────────
# Gold needs different settings due to wider ATR
SYMBOL_OVERRIDES = {
    "XAUUSD": {
        "TIMEFRAMES": [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5],
        "TRAILING_START_ATR": 0.3,
        "TRAILING_STEP_ATR": 0.1,
        "SWING_LOOKBACK": 40,
        "ENTRY_MODE": "pattern",
        "SPREAD": 0.3,
        "RR_RATIO": 4.0,
        "MIN_STOP_DISTANCE": 1.0,
        "SL_PIP_BUFFER": 0.5,  # 5 pips above/below wick
    },
    "GBPUSD": {
        "TIMEFRAMES": [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5],
        "TRAILING_START_ATR": 0.3,
        "TRAILING_STEP_ATR": 0.1,
        "SWING_LOOKBACK": 40,
        "ENTRY_MODE": "fibonacci",
        "SPREAD": 0.2,
        "RR_RATIO": 4.0,
        "MIN_STOP_DISTANCE": 0.0005,
        "MAX_SL_DISTANCE": 0.005,
        "SL_PIP_BUFFER": 0.0005,  # 5 pips
    },
    "AUDUSD": {
        "TIMEFRAMES": [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5],
        "TRAILING_START_ATR": 0.3,
        "TRAILING_STEP_ATR": 0.1,
        "SWING_LOOKBACK": 40,
        "ENTRY_MODE": "fibonacci",
        "SPREAD": 0.2,
        "RR_RATIO": 4.0,
        "MIN_STOP_DISTANCE": 0.0005,
        "MAX_SL_DISTANCE": 0.005,
        "SL_PIP_BUFFER": 0.0005,  # 5 pips
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
ENTRY_MODE = "fibonacci"
REQUIRE_CONFIRMATION = False

# ─── Trend Filter ─────────────────────────────────────────────────
USE_TREND_FILTER = True

# ─── CHoCH Filter ───────────────────────────────────────────────
USE_CHOCH = False

# ─── Momentum Filter ──────────────────────────────────────────────
USE_MOMENTUM_FILTER = False
RSI_PERIOD = 14
RSI_OVERSOLD = 55
RSI_OVERBOUGHT = 45
MIN_BODY_RATIO = 0.10

# ─── ATR ─────────────────────────────────────────────────────────
ATR_PERIOD = 14
MIN_STOP_DISTANCE = 1.0

# ─── Trailing Stop ────────────────────────────────────────────────
USE_TRAILING_STOP = True
TRAILING_START_ATR = 1.0
TRAILING_STEP_ATR = 0.12

# ─── Max Bars in Trade ────────────────────────────────────────────
MAX_BARS_IN_TRADE = 15

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
SCAN_INTERVAL_SECONDS = 5
