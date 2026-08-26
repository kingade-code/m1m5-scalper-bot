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


def detect_hammer_star(df):
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
    
    if lower > body * 2 and body / full < 0.35 and c > o:
        return 1
    if upper > body * 2 and body / full < 0.35 and o > c:
        return -1
    
    return 0


def detect_pattern(df, pattern_name=None):
    """Detect Hammer/Star pattern for gold entry signals.
    
    Returns: 1 (bullish), -1 (bearish), or 0 (none)
    """
    entry_mode = config.get_symbol_param(
        "XAUUSD", "ENTRY_MODE", config.ENTRY_MODE
    )
    
    if entry_mode != "pattern":
        return 0
    
    return detect_hammer_star(df)
