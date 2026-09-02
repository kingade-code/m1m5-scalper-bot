# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
"""Candlestick pattern detection for entry signals.

Hammer/Star pattern: high-probability reversal signals on gold M1.
"""
import logging
import numpy as np
import pandas as pd
import config

logger = logging.getLogger(__name__)


def _min_body_ratio(symbol):
    """Smallest real-body fraction a pattern candle must have (guards
    doji/indecision candles masquerading as Hammer/Star/Engulfing)."""
    return config.get_symbol_param(symbol or "XAUUSD", "MIN_BODY_RATIO", 0.10)


def _hammer_wick_ratio(symbol):
    """Minimum lower (or upper) wick / body ratio for Hammer/Star."""
    return config.get_symbol_param(symbol or "XAUUSD", "MIN_HAMMER_WICK_RATIO", 4.0)


def _engulf_min_body_ratio(symbol):
    """Minimum body/full ratio for the engulfing candle itself."""
    return config.get_symbol_param(symbol or "XAUUSD", "ENGULF_MIN_BODY_RATIO", 0.30)


def _engulf_min_size_ratio(symbol):
    """Minimum ratio of engulfing-candle full range / previous-candle full range."""
    return config.get_symbol_param(symbol or "XAUUSD", "ENGULF_MIN_SIZE_RATIO", 1.5)


def _marubozu_min_body_ratio(symbol):
    """Minimum body/full fraction for a Marubozu (large-bodied, no-wick candle)."""
    return config.get_symbol_param(symbol or "XAUUSD", "MARUBOZU_MIN_BODY_RATIO", 0.70)


def _marubozu_max_wick_ratio(symbol):
    """Maximum each wick / body fraction allowed for a Marubozu."""
    return config.get_symbol_param(symbol or "XAUUSD", "MARUBOZU_MAX_WICK_RATIO", 0.12)


def detect_marubozu(df, symbol=None):
    """Detect a Marubozu (strong full-body candle with minimal wicks) on the
    last closed candle.

    Continuation-with-trend signal: return 1 (bullish) for a long green body
    with tiny wicks, -1 (bearish) for a long red body with tiny wicks, else 0.
    The downstream trend filter gates it into the prevailing direction.

    Requirements: the body must cover >= MARUBOZU_MIN_BODY_RATIO of the full
    range, each wick must be <= MARUBOZU_MAX_WICK_RATIO of the body (tiny
    wicks), and the candle must CONNECT with the previous candle — its range
    must overlap the prior bar's range so no opening gap is left before it.
    """
    if df is None or len(df) < 3:
        return 0

    bar = df.iloc[-2]
    prev = df.iloc[-3]
    o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]
    po, ph, pl, pc = prev["open"], prev["high"], prev["low"], prev["close"]

    body = abs(c - o)
    full = h - l
    if full <= 0 or body <= 0:
        return 0

    # No-gap continuity: the marubozu must connect with the previous candle.
    # Its range must overlap the prior bar's range — a candle that gaps away
    # from the prior close is rejected, not counted as a valid pattern.
    if ph < l or pl > h:
        return 0

    min_body = _marubozu_min_body_ratio(symbol)
    max_wick = _marubozu_max_wick_ratio(symbol)
    body_frac = body / full
    if body_frac < min_body:
        return 0

    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)
    if lower_wick > body * max_wick or upper_wick > body * max_wick:
        return 0

    return 1 if c > o else -1


def detect_hammer_star(df, symbol=None):
    """Detect Hammer (bullish) or Shooting Star (bearish) on the last closed candle.
    
    Returns: 1 (bullish), -1 (bearish), or 0 (none)
    """
    if df is None or len(df) < 3:
        return 0
    
    bar = df.iloc[-2]
    o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]
    
    body = abs(c - o)
    full = h - l
    if full < 0.01:
        return 0
    
    lower = min(o, c) - l
    upper = h - max(o, c)
    min_body = _min_body_ratio(symbol)
    wick_ratio = _hammer_wick_ratio(symbol)
    
    if lower > body * wick_ratio and body / full < 0.35 and body / full >= min_body and c > o:
        return 1
    if upper > body * wick_ratio and body / full < 0.35 and body / full >= min_body and o > c:
        return -1

    return 0


def detect_engulfing(df, symbol=None):
    """Detect Bullish or Bearish Engulfing on the last two closed candles.
    
    Returns: 1 (bullish), -1 (bearish), or 0 (none)
    """
    if df is None or len(df) < 4:
        return 0
    
    prev = df.iloc[-3]
    curr = df.iloc[-2]
    
    po, pc = prev["open"], prev["close"]
    o, h, l, c = curr["open"], curr["high"], curr["low"], curr["close"]
    
    body = abs(c - o)
    full = h - l
    min_body = _min_body_ratio(symbol)
    engulf_min_body = _engulf_min_body_ratio(symbol)
    engulf_min_size = _engulf_min_size_ratio(symbol)
    
    if full <= 0:
        return 0
    
    # Engulfing candle must be clearly larger than the previous candle:
    # its full range >= ENGULF_MIN_SIZE_RATIO × previous full range.
    prev_full = prev["high"] - prev["low"]
    if prev_full <= 0 or full < prev_full * engulf_min_size:
        return 0
    
    if pc < po and c > o and o <= pc and c >= po and body / full >= min_body \
            and body / full >= engulf_min_body:
        return 1
    if pc > po and c < o and o >= pc and c <= po and body / full >= min_body \
            and body / full >= engulf_min_body:
        return -1
    
    return 0


def detect_pattern(df, pattern_name=None, symbol=None):
    """Detect Hammer/Star and Engulfing patterns for entry signals.
    
    Returns: 1 (bullish), -1 (bearish), or 0 (none)
    """
    check_symbol = symbol or "XAUUSD"
    entry_mode = config.get_symbol_param(
        check_symbol, "ENTRY_MODE", config.ENTRY_MODE
    )
    
    if entry_mode != "pattern":
        return 0
    
    hammer = detect_hammer_star(df, symbol=symbol)
    if hammer != 0:
        return hammer
    
    engulf = detect_engulfing(df, symbol=symbol)
    if engulf != 0:
        return engulf

    marubozu = detect_marubozu(df, symbol=symbol)
    if marubozu != 0:
        return marubozu

    return 0


def detect_pattern_name(df, symbol=None):
    """Return a human-readable label of the formation that fired on the last
    closed candle, or '' if none. Mirrors detect_pattern entry precedence."""
    check_symbol = symbol or "XAUUSD"
    if config.get_symbol_param(check_symbol, "ENTRY_MODE", config.ENTRY_MODE) != "pattern":
        return ""

    h = detect_hammer_star(df, symbol=symbol)
    if h == 1:
        return "hammer"
    if h == -1:
        return "inverse_hammer"

    e = detect_engulfing(df, symbol=symbol)
    if e == 1:
        return "bull_engulf"
    if e == -1:
        return "bear_engulf"

    m = detect_marubozu(df, symbol=symbol)
    if m == 1:
        return "bull_marubozu"
    if m == -1:
        return "bear_marubozu"

    return ""
