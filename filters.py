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
    """Check if trade direction aligns with higher timeframe trend.

    Uses H1 EMA50 as trend filter.
    If EMA50 is rising and price > EMA50 => uptrend => allow buys only.
    If EMA50 is falling and price < EMA50 => downtrend => allow sells only.

    Returns True if direction aligns with trend, False otherwise.
    """
    if not config.USE_TREND_FILTER:
        return True

    if symbol is None:
        return True

    import mt5_connector as mt5c

    ema_period = config.get_symbol_param(symbol, "TREND_EMA_PERIOD", config.TREND_EMA_PERIOD)
    h1_df = mt5c.get_ohlc(symbol, 1, ema_period + 50)  # M1 timeframe
    if h1_df is None or len(h1_df) < ema_period + 10:
        return True

    ema = calc_ema(h1_df["close"], ema_period)
    current_ema = ema.iloc[-1]
    prev_ema = ema.iloc[-2]
    current_price = h1_df.iloc[-1]["close"]

    ema_rising = current_ema > prev_ema
    ema_falling = current_ema < prev_ema

    if direction == "bullish" and (current_price > current_ema or ema_rising):
        return True
    if direction == "bearish" and (current_price < current_ema or ema_falling):
        return True

    return False


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

