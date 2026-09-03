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
TIMEFRAMES = [mt5.TIMEFRAME_M1]

# ─── Swing Detection ──────────────────────────────────────────────
SWING_LOOKBACK = 100  # Optimized: higher = better WR (66.7%)
SWING_STRENGTH = 2  # Lower = more swing points = more signals

# ─── Fibonacci Settings ───────────────────────────────────────────
FIB_ENTRY_LOW = 0.5
FIB_ENTRY_HIGH = 0.786

# ─── Risk Management ─────────────────────────────────────────────
RISK_PERCENT = 1.0
MAX_POSITIONS = 2
MAX_POSITIONS_PER_SYMBOL = 1
MAGIC_NUMBER = 777777
SLIPPAGE = 3

# ─── Manual Trade Guard ──────────────────────────────────────────
# Closes/cancels anything NOT placed by this bot or another controlled
# EA. Manual MT5 terminal trades carry magic 0 here, so they get killed
# on the next 5s scan. Other EAs using the same account can be exempted.
MANUAL_TRADE_GUARD = True
# Whitelist bots running on this PC so the guard doesn't touch them.
# 888888 = CHOCH Strategy (main.py --mode live, running now). Only
# currently-running bots are whitelisted; add others here as-needed.
GUARD_EXEMPT_MAGICS = {888888}
GUARD_DEBUG = False             # log-but-don't-close mode (testing only)

# ─── Symbol Filter ────────────────────────────────────────────────
AUTO_DISCOVER_SYMBOLS = False
SYMBOL_LIST = ["BTCUSD"]

# ─── Per-Symbol Overrides ────────────────────────────────────────
# Gold needs different settings due to wider ATR
SYMBOL_OVERRIDES = {
    "XAUUSD": {
        "TIMEFRAMES": [mt5.TIMEFRAME_M1],
        # Profitable UTC hours from the 6-month time-of-day study (M5).
        # Best: 23:00 then 14:00/02:00/04:00/13:00; 15:00/10:00/09:00 bleed.
        "SESSION_ALLOW_HOURS": [22, 23, 0, 1, 2, 3, 4, 13, 14],
        # Profitable UTC hours from the M1 time-of-day study (Feb-Aug 2026).
        # All hours that are net-profitable across all M1 patterns (aggregate),
        # so any M1 signal whose pattern is not individually gated can still
        # trade in historically profitable times. The per-pattern
        # SESSION_PATTERN_HOURS_M1 map does the finer gating.
        "SESSION_ALLOW_HOURS_M1": [1, 5, 6, 11, 19, 20, 21, 22],
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
        "TIMEFRAMES": [mt5.TIMEFRAME_M1],
        # Profitable UTC hours from the 6-month time-of-day study (M5).
        # Best: 10:00, then 00:00-03:00, 06:00, 13:00; 01:00/16:00/22:00 bleed.
        "SESSION_ALLOW_HOURS": [0, 2, 3, 6, 10, 13, 21],
        # Profitable UTC hours from the M1 study (Jul 2024-Jan 2025; STALE -
        # no recent BTC M1 exists, applied per user request). All hours that
        # are net-profitable across all M1 patterns (aggregate), so any M1
        # signal whose pattern is not individually gated can still trade in
        # historically profitable times.
        "SESSION_ALLOW_HOURS_M1": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 21, 22],
        "TRAILING_ENABLED": True,
        "TRAILING_START_ATR": 0.3,
        "TRAILING_STEP_ATR": 0.1,
        "TRAIL_ACTIVATE_R": 1.0,  # staircase trail engages at 1R (1:2) profit
        "USE_OPEN_RR": True,
        "SWING_LOOKBACK": 40,
        "ENTRY_MODE": "pattern",
        "SPREAD": 1.0,
        "RR_RATIO": 3.0,
        "SL_PIP_BUFFER": 10.0,     # M1 entries ~0.29 * M1 ATR (gold: 0.5/1.7)
        "SL_PIP_BUFFER_M5": 20.0,  # M5 entries ~0.32 * M5 ATR (63/34 * 10), per-user request
        "REVERSE_CLOSE_DISTANCE": 4.0,
        "WICK_GUARD": 0.0,       # disabled: catch every trend-aligned setup
        "RANGE_EDGE_ATR": 1.5,   # loosened: was 1.0, allow more candidates through
        "ZONE_MAX_DIST_ATR": 1.0,  # loosened: was 0.6 global, widen zone acceptance
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
# Dead-band for the EMA10/100 trend filter. When the two EMAs are within
# this fraction of the slow EMA of each other, the market is treated as flat
# and BOTH directions are allowed (loosens the strict directional gate that
# otherwise rejects flat-but-old-trend signals). 0.0 = strict, unchanged.
TREND_FILTER_DEAD_BAND = 0.0005

# ─── CHoCH Filter ───────────────────────────────────────────────
USE_CHOCH = False

# ─── Momentum Filter ──────────────────────────────────────────────
USE_MOMENTUM_FILTER = False
RSI_PERIOD = 14
RSI_OVERSOLD = 55
RSI_OVERBOUGHT = 45
# MIN_BODY_RATIO is ALSO the pattern-detector doji guard: a Hammer/Star/
# Engulfing signal candle must have a body of at least this fraction of its
# full height, so doji/indecision candles are not mistaken for entries.
# (0.10 rejects ~30% of raw detector hits that are near-doji.)
MIN_BODY_RATIO = 0.10

# Hammer/Star: lower or upper wick must be >= this × body.
# (4× forces a genuinely long tail; 2× was too loose.)
MIN_HAMMER_WICK_RATIO = 4.0

# Engulfing: minimum body/full ratio for the engulfing candle itself
# so tiny-doji engulfers don't count. (Also passes the doji guard
# via MIN_BODY_RATIO, but this keeps the engulfing candle robust.)
ENGULF_MIN_BODY_RATIO = 0.30

# Engulfing: engulfing candle's full range must be >= this × previous
# candle's full range, so the engulfing is clearly larger.
ENGULF_MIN_SIZE_RATIO = 1.5

# Marubozu (continuation-with-trend): a strong full-body candle with
# minimal wicks. Fires in line with the trend (bullish=long, bearish=short)
# when the body is at least this fraction of the candle's full range and
# each wick is at most this fraction of the body.
MARUBOZU_MIN_BODY_RATIO = 0.70    # body must cover >= 70% of the full range
MARUBOZU_MAX_WICK_RATIO = 0.05    # each wick <= 5% of the body (tiny wicks only)

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

# ─── Time-of-Day (Session) Filter ──────────────────────────────────
# Reject signals whose entry time falls OUTSIDE the allowed UTC hours
# (SESSION_ALLOW_HOURS), keeping entries in the historically profitable
# times of day. Off by default; globally enabled via USE_SESSION_FILTER
# or per-symbol with SESSION_ALLOW_HOURS in SYMBOL_OVERRIDES. Empty/None
# allow-list = all hours allowed (filter disabled for that symbol).
USE_SESSION_FILTER = False
SESSION_ALLOW_HOURS = []

# Per-pattern, per-symbol time-of-day gating (verified from the 6-month M5
# time-of-day study). Keyed by symbol -> {pattern_name (detect_pattern_name):
# [UTC entry hours that are permitted]}. Applied on top of SESSION_ALLOW_HOURS
# when USE_SESSION_FILTER is on: a signal's pattern must be present here and
# the entry hour must be in that pattern's allow-list to pass. A pattern absent
# from this map is not hour-gated (any SESSION_ALLOW_HOURS still applies).
# Profitable-hour conclusions:
#   MARUBOZU net-positive on both symbols; XAU 01/08/17/05, BTC 13/03/00/06.
#   ENGULFING mixed; BTC edge almost entirely 10:00 + 00:00.
#   HAMMER weakest; gate gold hammer tight or disable.
SESSION_PATTERN_HOURS = {
    "XAUUSD": {
        "bull_marubozu": [23, 0, 1, 2, 22],
        "bear_marubozu": [1, 8, 5, 4, 14, 22, 23],
        "bull_engulf": [2, 3, 4, 12, 18, 20, 23],
        "bear_engulf": [2, 13, 14, 19, 20, 23],
        "hammer": [0, 7, 14, 23],
        "inverse_hammer": [2, 3, 5, 7, 17, 22, 23],
    },
    "BTCUSD": {
        "bull_marubozu": [0, 3, 6, 13, 17, 20, 21],
        "bear_marubozu": [3, 13, 15, 17, 20],
        "bull_engulf": [3, 9, 10, 11],
        "bear_engulf": [0, 2, 5, 8, 9, 21],
        "hammer": [2, 6, 11, 14, 18],
        "inverse_hammer": [6, 10, 13, 17],
    },
}

# Per-pattern, per-symbol M1 time-of-day gating (from the M1 study; BTC is
# STALE Jul 2024-Jan 2025, no recent BTC M1 exists). Applied on top of
# SESSION_ALLOW_HOURS_M1 when USE_SESSION_FILTER is on and the signal is M1.
# Same semantics as SESSION_PATTERN_HOURS but for the M1 timeframe. Hour sets
# are ALL hours with positive expectancy per trade (>= 3 trades) for that
# pattern, not just the best few — the filter stays open to every historically
# profitable hour.
SESSION_PATTERN_HOURS_M1 = {
    "XAUUSD": {
        "bull_marubozu": [1, 5, 6, 9, 11, 12, 14, 16, 18, 19, 20],
        "bear_marubozu": [0, 5, 12, 14, 15, 17, 19, 20],
        "bull_engulf": [2, 3, 5, 11, 21, 22, 23],
        "bear_engulf": [1, 2, 3, 6, 10, 11, 14, 15, 16, 17, 19, 20],
        "hammer": [3, 4, 8, 10, 13, 15, 16],
        "inverse_hammer": [1, 10, 11, 12, 17, 18, 19, 20],
    },
    "BTCUSD": {
        "bull_marubozu": [0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 17, 19, 20, 21, 22, 23],
        "bear_marubozu": [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 21, 22],
        "bull_engulf": [2, 5, 6, 7, 9, 10, 11, 14, 15, 17, 20, 21, 22],
        "bear_engulf": [1, 3, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23],
        "hammer": [5, 12, 14, 19, 20],
        "inverse_hammer": [0, 2, 4, 5, 7, 9, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
    },
}

# ─── Demand/Supply Zone Filter ─────────────────────────────────────
# Only allow a pattern/fib signal when price is acting AT a dema/supply
# zone: bullish signals near support (demand), bearish signals near
# resistance (supply). ZONES_LOOKBACK bars are searched for swing pivots,
# clustered into zones, then current price must be within
# ZONE_MAX_DIST_ATR*ATR of the relevant zone band for the signal to pass.
# 0 distance = disabled.
USE_ZONE_FILTER = True
ZONE_LOOKBACK = 500
ZONE_MAX_DIST_ATR = 0.6
ZONE_MIN_TOUCHES = 2

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

# ─── Staircase trailing (user rejected; Fibonacci 2/3/5/7 ladder backtests
# worse). Left False so the rejected Fibonacci staircase can NEVER re-enable
# silently if the Open-RR ratchet is turned back on.
USE_STAIRCASE_TRAIL = False
STAIRCASE_LOCK_R = 1.0   # lock (milestone - 1)R behind price

# Activation R for the classic ATR staircase trail (_manage_trailing_stop).
# The trail only engages once the position is up TRAIL_ACTIVATE_R (1R = 1:2).
# 1R is measured from the original entry-to-stop distance. Set >1 to let
# winners run further before the trail locks in.
TRAIL_ACTIVATE_R = 1.0

# Fibonacci gap increments applied above the base 2/3/5/7 ladder, so the
# milestones extend 9, 12, 17, 25, 38, 59, ... toward infinity.
_STAIRCASE_FIB_GAPS = [
    2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 34.0, 55.0, 89.0, 144.0,
    233.0, 377.0, 610.0, 987.0, 1597.0, 2584.0, 4181.0,
]


def staircase_lock_r(rr):
    """Return the lock-R for the staircase trail given an unrealized R
    multiple `rr`. Ladder 2/3/5/7 then Fibonacci gaps to infinity; the stop
    locks (current_milestone - STAIRCASE_LOCK_R) behind. 0 if rr is below
    the first milestone (no protective move yet)."""
    base = [2.0, 3.0, 5.0, 7.0]
    if rr < base[0] or STAIRCASE_LOCK_R < 0:
        return 0.0
    cur = base[0]
    for b in base[1:]:
        if b <= rr:
            cur = b
        else:
            return max(cur - STAIRCASE_LOCK_R, 0.0)
    i = 0
    while True:
        gap = _STAIRCASE_FIB_GAPS[i] if i < len(_STAIRCASE_FIB_GAPS) \
            else _STAIRCASE_FIB_GAPS[-1] * 1.618
        nxt = cur + gap
        if nxt <= rr:
            cur = nxt
            i += 1
        else:
            break
    return max(cur - STAIRCASE_LOCK_R, 0.0)

# ─── Logging ──────────────────────────────────────────────────────
LOG_LEVEL = "DEBUG"
LOG_FILE = "m1m5_scalper.log"

# ─── Telegram ─────────────────────────────────────────────────────
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = "8803542513:AAF4TtMmcWIHAj88xNxsjHH8NYxqHMUfwag"
TELEGRAM_CHAT_IDS = [6412335897]  # Private chat
TELEGRAM_GROUP_CHAT_ID = -1002127450559  # KINGADE FOREX group
TELEGRAM_GROUP_THREAD_ID = 3  # FREE SIGNALS topic

# ─── Telegram Command Channel ────────────────────────────────────
# Long-polls getUpdates and honours /help /status /pause /resume /config
# from TELEGRAM_CHAT_IDS. Does not affect notifications. 0 = disabled.
COMMAND_POLL_SECONDS = 10   # how often to poll for commands (<= scan cycle)

# ─── Scan Interval ────────────────────────────────────────────────
SCAN_INTERVAL_SECONDS = 5

# ─── Daily Drawdown Limit ─────────────────────────────────────────
# Once the day's intraday equity drawdown (peak-to-trough, including
# floating losses on open positions) reaches this % of the day's starting
# balance, the bot pauses ALL new entries until the next UTC day. Re-arms
# automatically at the midnight UTC boundary. 0 = disabled.
DAILY_DRAWDOWN_ENABLED = True
DAILY_DRAWDOWN_PCT = 10.0
