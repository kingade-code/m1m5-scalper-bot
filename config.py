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
RISK_PERCENT = 3.0
MAX_POSITIONS = 2
MAX_POSITIONS_PER_SYMBOL = 1
MAX_LOT = 0.10  # Cap lot size to prevent risk blowup on tight SL
MAGIC_NUMBER = 777777
SLIPPAGE = 3

# ─── Manual Trade Guard ──────────────────────────────────────────
# Closes/cancels anything NOT placed by this bot or another controlled
# EA. Manual MT5 terminal trades carry magic 0 here, so they get killed
# on the next 5s scan. Other EAs using the same account can be exempted.
MANUAL_TRADE_GUARD = True
GUARD_EXEMPT_MAGICS = {730411, 234100}  # amt_order_flow_bot.py; liquidity-sweep bot (DC, magic 234100)
GUARD_DEBUG = False             # log-but-don't-close mode (testing only)

# ─── Symbol Filter ────────────────────────────────────────────────
AUTO_DISCOVER_SYMBOLS = False
SYMBOL_LIST = ["XAUUSD", "BTCUSD"]

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
        "REVERSE_CLOSE_DISTANCE": 0.2,  # 2 pips from signal wick
        "WICK_GUARD": 0.0,  # disabled: catch every trend-aligned setup
        "RANGE_EDGE_ATR": 1.0,  # A/B-validated (3.4m: PF 7.8->11.6, maxDD 3.3%->1.1%); M1 only
    },
    # BTCUSD (live since 2026-08-29; both this bot and the DC liquidity-
    # sweep bot trade it on this account). Buffers ATR-scaled to gold
    # (M1 ATR(14) ~34 vs gold ~1.7 => x10), spread is a placeholder
    # (weekend quote was $7; live hours are ~$0.5-1.5). Trailing disabled
    # and RR cut to 1:3 by user request.
    "BTCUSD": {
        "TIMEFRAMES": [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5],
        "TRAILING_ENABLED": False,
        "TRAILING_START_ATR": 0.3,
        "TRAILING_STEP_ATR": 0.1,
        "SWING_LOOKBACK": 40,
        "ENTRY_MODE": "pattern",
        "SPREAD": 1.0,
        "RR_RATIO": 3.0,
        "SL_PIP_BUFFER": 10.0,     # M1 entries ~0.29 * M1 ATR (gold: 0.5/1.7)
        "SL_PIP_BUFFER_M5": 20.0,  # M5 entries ~0.32 * M5 ATR (63/34 * 10), per-user request
        "REVERSE_CLOSE_DISTANCE": 4.0,
        "WICK_GUARD": 0.0,       # disabled: catch every trend-aligned setup
        "RANGE_EDGE_ATR": 0.0,   # disabled for BTC first look
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

# ─── Range-Edge Gate (A/B, M1 mean-reversion fade) ─────────────────
# Require an M1 pattern entry within RANGE_EDGE_ATR*ATR of the current
# move's swing low (buys) / swing high (sells). A/B backtest on M1
# showed +58.5% vs +28.7% baseline at 1.0 with the EMA trend filter ON;
# it HURT on M5 (+26.3% vs +33.6%), so the gate is applied to M1 only.
# 0 = disabled (backward compatible). Enable via SYMBOL_OVERRIDES.
RANGE_EDGE_ATR = 0.0

# ─── Ranging-Market Filter ────────────────────────────────────────
# Reject pattern/fib signals while the market is consolidating. On the
# signal timeframe's last RANGING_LOOKBACK closed bars the market counts
# as "ranging" when BOTH:
#   range width (max high - min low) <= RANGING_MAX_RANGE_ATR * ATR
#   net move (|first close - last close|) <= RANGING_MAX_MOVE_ATR * ATR
# A tight range with little net travel = chop, not a tradeable push.
# 0 disables the width/move check. Enable per-symbol via SYMBOL_OVERRIDES.
USE_RANGING_FILTER = True
RANGING_LOOKBACK = 60
RANGING_MAX_RANGE_ATR = 4.0
RANGING_MAX_MOVE_ATR = 2.0

# ─── Trailing Stop ────────────────────────────────────────────────
USE_TRAILING_STOP = True
TRAILING_START_ATR = 1.0
TRAILING_STEP_ATR = 0.12

# ─── Reverse Close (Failed Setup Exit) ─────────────────────────────
# If price reverses toward the SL and reaches the wick of the
# hammer/engulfing signal candle (within REVERSE_CLOSE_DISTANCE),
# close the trade early instead of waiting for the SL to be hit.
# NOTE: A/B backtest showed this reduces returns (+5.2% vs +35.5%
# without it), so it is disabled by default. Re-enable with caution.
USE_REVERSE_CLOSE = False
REVERSE_CLOSE_DISTANCE = 0.2  # 2 pips from signal wick (0.1 = 1 pip on gold)

# ─── Max Bars in Trade (counted on the trade's own entry timeframe) ──
MAX_BARS_IN_TRADE = 200

# ─── Same-symbol cooldown between trades (0 = off; only an OPEN
#     position blocks a new entry, per user request) ────────────────
TRADE_COOLDOWN_SECONDS = 0

# ─── Open RR + RR-step trailing ──────────────────────────────────
# 1:infinity RR — no fixed take-profit. The stop ratchets up in steps
# once the trade moves past the start milestone:
#   hit +3R  -> stop locks ~2R
#   hit +5R  -> stop locks ~4R
#   hit +7R  -> stop locks ~6R   (and so on, every RR_TRAIL_STEP_R R)
# Winners ride until they reverse into the ratcheted stop or hit
# MAX_BARS_IN_TRADE. ATR trailing is bypassed while this is on.
USE_OPEN_RR = True
RR_TRAIL_START_R = 3.0   # first milestone: start ratcheting at +3R
RR_TRAIL_STEP_R = 2.0    # ratchet every 2R after the start point
RR_TRAIL_LOCK_R = 1.0    # lock (milestone - 1)R behind price

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
