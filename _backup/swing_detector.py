# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import logging
import numpy as np
import config

logger = logging.getLogger(__name__)


def find_swing_highs(highs, strength=None):
    """Find swing high indices in an array of high prices.

    A swing high is a bar whose high is higher than `strength` bars
    on each side.

    Returns list of (index, price) tuples sorted newest-first.
    """
    if strength is None:
        strength = config.SWING_STRENGTH
    n = len(highs)
    swings = []
    for i in range(strength, n - strength):
        is_swing = True
        for j in range(1, strength + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_swing = False
                break
        if is_swing:
            swings.append((i, highs[i]))
    swings.sort(key=lambda x: x[0], reverse=True)
    return swings


def find_swing_lows(lows, strength=None):
    """Find swing low indices in an array of low prices.

    A swing low is a bar whose low is lower than `strength` bars
    on each side.

    Returns list of (index, price) tuples sorted newest-first.
    """
    if strength is None:
        strength = config.SWING_STRENGTH
    n = len(lows)
    swings = []
    for i in range(strength, n - strength):
        is_swing = True
        for j in range(1, strength + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_swing = False
                break
        if is_swing:
            swings.append((i, lows[i]))
    swings.sort(key=lambda x: x[0], reverse=True)
    return swings


def detect_current_move(df, lookback=None):
    """Detect the most recent significant swing high and swing low
    to define the current price move.

    Returns dict with:
        - direction: 'bullish' or 'bearish'
        - swing_high: (index, price)
        - swing_low: (index, price)
        - swing_high_time: timestamp of swing high bar
        - swing_low_time: timestamp of swing low bar
    Returns None if no valid swing pair found.
    """
    if lookback is None:
        lookback = config.SWING_LOOKBACK

    if len(df) < lookback:
        lookback = len(df)

    data = df.tail(lookback).copy()
    data.reset_index(drop=True, inplace=True)

    swing_highs = find_swing_highs(data["high"].values)
    swing_lows = find_swing_lows(data["low"].values)

    if not swing_highs or not swing_lows:
        return None

    # Determine current leg direction from the most recent swing point
    most_recent_high_idx = swing_highs[0][0]
    most_recent_low_idx = swing_lows[0][0]

    # Get the last candle index
    last_idx = len(data) - 1

    if most_recent_high_idx > most_recent_low_idx:
        # Most recent swing is a high → current leg is bearish (down from high)
        # Need to find the swing LOW that preceded this swing HIGH
        sh = swing_highs[0]
        # Find the most recent swing low that came before the swing high
        sl = None
        for idx, price in swing_lows:
            if idx < sh[0]:
                sl = (idx, price)
                break
        if sl is None:
            return None

        direction = "bearish"
    else:
        # Most recent swing is a low → current leg is bullish (up from low)
        sl = swing_lows[0]
        # Find the most recent swing high that came before the swing low
        sh = None
        for idx, price in swing_highs:
            if idx < sl[0]:
                sh = (idx, price)
                break
        if sh is None:
            return None

        direction = "bullish"

    # Convert local indices back to original DataFrame indices
    offset = len(df) - lookback
    sh_global = (sh[0] + offset, sh[1])
    sl_global = (sl[0] + offset, sl[1])

    return {
        "direction": direction,
        "swing_high": sh_global,
        "swing_low": sl_global,
        "swing_high_time": (
            df.iloc[sh_global[0]]["time"] if sh_global[0] < len(df) else None
        ),
        "swing_low_time": (
            df.iloc[sl_global[0]]["time"] if sl_global[0] < len(df) else None
        ),
    }
