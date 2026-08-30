# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Candlestick pattern library for backtesting.

Every detector consumes the same wire format as pattern_detector: a pandas
window `df` (or a 4-row slice) and returns 1 (bullish), -1 (bearish) or 0.
The signal candle is always the last CLOSED candle (df.iloc[-2]); three-candle
patterns read df.iloc[-3] / df.iloc[-4]. This guarantees no look-ahead when
the engine acts at the open of the next bar.

'current' == the live Kingade combination (hammer/star first, then engulfing),
mirroring pattern_detector.detect_pattern's precedence.
"""
import numpy as np

MIN_FULL = 0.01  # minimum candle range (price units) to call it a candle


def _ohlc(df, off=-2):
    r = df.iloc[off]
    return (float(r["open"]), float(r["high"]),
            float(r["low"]), float(r["close"]))


# ─── single-candle patterns ─────────────────────────────────────
def hammer(df):
    o, h, l, c = _ohlc(df)
    body = abs(c - o)
    full = h - l
    if full < MIN_FULL or body / full >= 0.35 or c <= o:
        return 0
    if (min(o, c) - l) > 2 * body:
        return 1
    return 0


def shooting_star(df):
    o, h, l, c = _ohlc(df)
    body = abs(c - o)
    full = h - l
    if full < MIN_FULL or body / full >= 0.35 or o <= c:
        return 0
    if (h - max(o, c)) > 2 * body:
        return -1
    return 0


def marubozu(df):
    o, h, l, c = _ohlc(df)
    body = abs(c - o)
    full = h - l
    if full < MIN_FULL or body < 0.6 * full:
        return 0
    if (h - max(o, c)) <= 0.2 * body and (min(o, c) - l) <= 0.2 * body:
        return 1 if c > o else -1
    return 0


def doji(df):
    o, h, l, c = _ohlc(df)
    po, _, _, pc = _ohlc(df, -3)
    body = abs(c - o)
    full = h - l
    if full < MIN_FULL or body > 0.1 * full:
        return 0
    if pc < po:
        return 1
    if pc > po:
        return -1
    return 0


def dragonfly_doji(df):
    o, h, l, c = _ohlc(df)
    body = abs(c - o)
    full = h - l
    if full < MIN_FULL or body > 0.1 * full:
        return 0
    if (min(o, c) - l) >= 0.6 * full and (h - max(o, c)) <= 0.1 * full:
        return 1
    return 0


def gravestone_doji(df):
    o, h, l, c = _ohlc(df)
    body = abs(c - o)
    full = h - l
    if full < MIN_FULL or body > 0.1 * full:
        return 0
    if (h - max(o, c)) >= 0.6 * full and (min(o, c) - l) <= 0.1 * full:
        return -1
    return 0


# ─── two-candle patterns ────────────────────────────────────────
def engulfing(df):
    po, _, _, pc = _ohlc(df, -3)
    o, h, l, c = _ohlc(df)
    if pc < po and c > o and o <= pc and c >= po:
        return 1
    if pc > po and c < o and o >= pc and c <= po:
        return -1
    return 0


def harami(df):
    po, _, _, pc = _ohlc(df, -3)
    o, h, l, c = _ohlc(df)
    if max(o, c) < max(po, pc) and min(o, c) > min(po, pc):
        if pc < po:
            return 1
        if pc > po:
            return -1
    return 0


def inside_bar(df):
    po, ph, pl, pc = _ohlc(df, -3)
    _, h, l, _ = _ohlc(df)
    if (ph - pl) < MIN_FULL:
        return 0
    if h < ph and l > pl:
        if pc < po:
            return 1
        if pc > po:
            return -1
    return 0


def tweezer(df):
    po, ph, pl, pc = _ohlc(df, -3)
    _, h, l, _ = _ohlc(df)
    tol = 0.05              # highs/lows within 5 cents count as equal
    if abs(h - ph) <= tol and pc > po:
        return -1           # tweezer top after an up move
    if abs(l - pl) <= tol and pc < po:
        return 1            # tweezer bottom after a down move
    return 0


# ─── three-candle / continuation patterns ───────────────────────
def morning_star(df):
    o1, h1, l1, c1 = _ohlc(df, -4)   # first: big bearish
    o2, h2, l2, c2 = _ohlc(df, -3)   # middle: small body (star)
    o, _, _, c = _ohlc(df)           # last: bullish, closes above mid of first
    b1 = abs(c1 - o1)
    if (h1 - l1) < MIN_FULL or b1 < 0.4 * (h1 - l1) or c1 >= o1:
        return 0
    b2 = abs(c2 - o2)
    if (h2 - l2) < MIN_FULL or b2 > 0.4 * (h2 - l2):
        return 0
    if c > o and c > (o1 + c1) / 2:
        return 1
    return 0


def evening_star(df):
    o1, h1, l1, c1 = _ohlc(df, -4)
    o2, h2, l2, c2 = _ohlc(df, -3)
    o, _, _, c = _ohlc(df)
    b1 = abs(c1 - o1)
    if (h1 - l1) < MIN_FULL or b1 < 0.4 * (h1 - l1) or c1 <= o1:
        return 0
    b2 = abs(c2 - o2)
    if (h2 - l2) < MIN_FULL or b2 > 0.4 * (h2 - l2):
        return 0
    if o > c and c < (o1 + c1) / 2:
        return -1
    return 0


def three_white_soldiers(df):
    o1, _, _, c1 = _ohlc(df, -4)
    o2, _, _, c2 = _ohlc(df, -3)
    o, _, _, c = _ohlc(df)
    if o1 < c1 and o2 < c2 and o < c:
        if c2 > c1 and c > c2 and o2 > o1 and o > o2:
            return 1
    return 0


def three_black_crows(df):
    o1, _, _, c1 = _ohlc(df, -4)
    o2, _, _, c2 = _ohlc(df, -3)
    o, _, _, c = _ohlc(df)
    if o1 > c1 and o2 > c2 and o > c:
        if c2 < c1 and c < c2 and o2 < o1 and o < o2:
            return -1
    return 0


# ─── combinations ───────────────────────────────────────────────
def hammer_star(df):
    v = hammer(df)
    return v if v else shooting_star(df)


def current(df):
    v = hammer(df)
    if v:
        return v
    v = shooting_star(df)
    if v:
        return v
    return engulfing(df)


PATTERNS = {
    "current": current,
    "hammer": hammer,
    "shooting_star": shooting_star,
    "engulfing": engulfing,
    "hammer_star": hammer_star,
    "doji": doji,
    "dragonfly_doji": dragonfly_doji,
    "gravestone_doji": gravestone_doji,
    "marubozu": marubozu,
    "harami": harami,
    "inside_bar": inside_bar,
    "tweezer": tweezer,
    "morning_star": morning_star,
    "evening_star": evening_star,
    "three_white_soldiers": three_white_soldiers,
    "three_black_crows": three_black_crows,
}


def precompute(df, name):
    """Return {bar_time: signal} where signal = detector result actionable
    at that bar (using the bar just before it as the last closed candle)."""
    fn = PATTERNS[name]
    n = len(df)
    lut = {}
    times = df["time"].to_numpy()
    for t in range(4, n):
        v = fn(df.iloc[t - 4: t + 1])
        if v:
            lut[times[t]] = int(v)
    return lut