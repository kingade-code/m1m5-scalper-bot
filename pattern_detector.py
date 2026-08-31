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
    
    if lower > body * 2 and body / full < 0.35 and body / full >= min_body and c > o:
        return 1
    if upper > body * 2 and body / full < 0.35 and body / full >= min_body and o > c:
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
    
    if full <= 0:
        return 0
    
    if pc < po and c > o and o <= pc and c >= po and body / full >= min_body:
        return 1
    if pc > po and c < o and o >= pc and c <= po and body / full >= min_body:
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
    
    return 0
