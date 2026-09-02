# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import numpy as np
import pandas as pd
import config


def calc_ema(series, period):
    """Calculate Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def calc_rsi(series, period=14):
    """Calculate Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def calc_atr(high, low, close, period=14):
    """Calculate Average True Range."""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=1).mean()
    return atr


def check_trend_filter(df, direction, symbol=None):
    """Check if trade direction aligns with MA trend filter.

    Fast EMA(10) vs Slow EMA(100) on M1:
    - Uptrend: fast EMA > slow EMA => allow buys
    - Downtrend: fast EMA < slow EMA => allow sells

    Returns True if direction aligns with trend, False otherwise.
    """
    if not config.USE_TREND_FILTER:
        return True

    if symbol is None:
        return True

    import mt5_connector as mt5c

    fast_period = 10
    slow_period = 100
    need_bars = slow_period + 50

    trend_df = mt5c.get_ohlc(symbol, 1, need_bars)  # M1 trend
    if trend_df is None or len(trend_df) < slow_period + 10:
        return True

    fast_ema = calc_ema(trend_df["close"], fast_period)
    slow_ema = calc_ema(trend_df["close"], slow_period)

    fast_now = fast_ema.iloc[-1]
    slow_now = slow_ema.iloc[-1]

    uptrend = fast_now > slow_now
    downtrend = fast_now < slow_now

    direction = direction.lower() if direction else direction

    # Dead-band: if the two EMAs are essentially converged (not a clear
    # trend), allow either direction instead of the strict directional gate.
    dead_band = float(config.TREND_FILTER_DEAD_BAND)
    if dead_band > 0 and slow_now != 0:
        gap = abs(fast_now - slow_now) / abs(slow_now)
        if gap <= dead_band:
            return True

    if direction == "bullish" and uptrend:
        return True
    if direction == "bearish" and downtrend:
        return True

    return False


def check_ranging_filter(df, symbol=None):
    """Reject signals while the market is consolidating (ranging).

    On the signal timeframe's last RANGING_LOOKBACK closed bars the
    market counts as "ranging" when BOTH:
      - range width (max high - min low) <= RANGING_MAX_RANGE_ATR * ATR
      - net move (|first close - last close|) <= RANGING_MAX_MOVE_ATR * ATR
    A tight range with little net travel is chop, not a tradeable push,
    so trend-continuation set-ups inside it are skipped.

    Setting either threshold to 0 disables that check. Enabled per-symbol
    via config SYMBOL_OVERRIDES / global USE_RANGING_FILTER.

    Returns True if trading is allowed (market not ranging), False if the
    market is consolidating.
    """
    use = config.get_symbol_param(
        symbol, "USE_RANGING_FILTER", config.USE_RANGING_FILTER
    )
    if not use:
        return True

    lookback = int(config.get_symbol_param(
        symbol, "RANGING_LOOKBACK", config.RANGING_LOOKBACK))
    max_range = float(config.get_symbol_param(
        symbol, "RANGING_MAX_RANGE_ATR", config.RANGING_MAX_RANGE_ATR))
    max_move = float(config.get_symbol_param(
        symbol, "RANGING_MAX_MOVE_ATR", config.RANGING_MAX_MOVE_ATR))

    if lookback <= 0 or (max_range <= 0 and max_move <= 0):
        return True

    win = df.iloc[-lookback - 1:-1]  # closed bars only, exclude forming bar
    if len(win) < 20:
        return True

    atr_period = int(config.get_symbol_param(
        symbol, "ATR_PERIOD", config.ATR_PERIOD))
    atr_series = calc_atr(df["high"], df["low"], df["close"], atr_period)
    ref_atr = atr_series.iloc[-2]
    if ref_atr <= 0:
        return True

    range_width = win["high"].max() - win["low"].min()
    net_move = abs(win["close"].iloc[-1] - win["close"].iloc[0])

    compact = max_range <= 0 or range_width <= max_range * ref_atr
    flat = max_move <= 0 or net_move <= max_move * ref_atr

    return not (compact and flat)


def check_momentum_filter(df, direction):
    """Check momentum confirmation using RSI and candle body ratio.

    RSI filter:
    - For buy: RSI should be < RSI_OVERSOLD (price pulled back enough)
    - For sell: RSI should be > RSI_OVERBOUGHT (price rallied enough)

    Body ratio filter:
    - Confirmation candle body should be > MIN_BODY_RATIO of total range
      to show real rejection/momentum.

    Returns True if momentum confirms, False otherwise.
    """
    if not config.USE_MOMENTUM_FILTER:
        return True

    rsi = calc_rsi(df["close"], config.RSI_PERIOD)
    current_rsi = rsi.iloc[-2]  # Last closed candle

    if direction == "bullish" and current_rsi > config.RSI_OVERSOLD:
        return False
    if direction == "bearish" and current_rsi < config.RSI_OVERBOUGHT:
        return False

    # Candle body ratio check on confirmation candle
    candle = df.iloc[-2]
    body = abs(candle["close"] - candle["open"])
    total_range = candle["high"] - candle["low"]

    if total_range > 0:
        body_ratio = body / total_range
        if body_ratio < config.MIN_BODY_RATIO:
            return False

    return True

