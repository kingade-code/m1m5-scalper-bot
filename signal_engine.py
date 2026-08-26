# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import logging
import MetaTrader5 as mt5
import mt5_connector as mt5c
import swing_detector
import fibonacci
import filters
import pattern_detector
import config

logger = logging.getLogger(__name__)


def analyze_symbol(symbol, timeframe):
    """Analyze a single symbol on a given timeframe for a Kingade setup.

    Supports two entry modes:
    - "fibonacci": Fibonacci retracement zone (default for forex pairs)
    - "pattern": Candlestick pattern detection (Hammer/Star for gold)
    
    Uses ATR-based SL/TP.
    Returns a signal dict if a valid entry is found, otherwise None.
    """
    entry_mode = config.get_symbol_param(symbol, "ENTRY_MODE", config.ENTRY_MODE)
    
    if entry_mode == "pattern":
        return _analyze_pattern(symbol, timeframe)
    else:
        return _analyze_fibonacci(symbol, timeframe)


def _analyze_pattern(symbol, timeframe):
    """Analyze using candlestick pattern detection (Hammer/Star)."""
    bars_needed = 200
    df = mt5c.get_ohlc(symbol, timeframe, bars_needed)
    if df is None or len(df) < 30:
        return None

    # Detect pattern (returns 1, -1, or 0)
    raw_direction = pattern_detector.detect_pattern(df)
    if raw_direction == 0:
        return None

    # Convert int to string for internal use
    direction = "bullish" if raw_direction == 1 else "bearish"
    signal_direction = "buy" if raw_direction == 1 else "sell"

    # Use second-to-last candle (last closed)
    prev_bar = df.iloc[-2]
    prev_close = prev_bar["close"]

    # Trend filter: only trade in direction of H1 trend
    if not filters.check_trend_filter(df, direction, symbol):
        logger.debug(f"{symbol} {_tf_name(timeframe)}: rejected by trend filter")
        return None

    # Momentum filter: RSI + candle body ratio
    if not filters.check_momentum_filter(df, direction):
        logger.debug(f"{symbol} {_tf_name(timeframe)}: rejected by momentum filter")
        return None

    # ATR for SL/TP calculation
    atr_series = filters.calc_atr(df["high"], df["low"], df["close"], config.ATR_PERIOD)
    current_atr = atr_series.iloc[-2]

    # Spread in price (0.3 pip = 0.03 for XAUUSD)
    spread = config.get_symbol_param(symbol, "SPREAD", 0)
    spread_price = spread * 0.10  # Convert pips to price

    # ATR-based SL + spread
    atr_sl_mult = config.get_symbol_param(symbol, "ATR_SL_MULTIPLIER", config.ATR_SL_MULTIPLIER)
    atr_sl_dist = current_atr * atr_sl_mult + spread_price
    if direction == "bullish":
        atr_sl = prev_close - atr_sl_dist
    else:
        atr_sl = prev_close + atr_sl_dist

    # ATR-based TP
    atr_tp_mult = config.get_symbol_param(symbol, "ATR_TP_MULTIPLIER", config.ATR_TP_MULTIPLIER)
    atr_tp_dist = current_atr * atr_tp_mult + spread_price
    if direction == "bullish":
        atr_tp = prev_close + atr_tp_dist
    else:
        atr_tp = prev_close - atr_tp_dist

    # Skip if SL distance too small
    sl_dist = abs(prev_close - atr_sl)
    if sl_dist < config.MIN_STOP_DISTANCE:
        return None

    timeframe_name = _tf_name(timeframe)
    signal = {
        "symbol": symbol,
        "timeframe": timeframe,
        "timeframe_name": timeframe_name,
        "direction": signal_direction,
        "entry_price": prev_close,
        "entry_zone_high": prev_close,
        "entry_zone_low": prev_close,
        "sl": atr_sl,
        "tp1": atr_tp,
        "tp2": atr_tp,
        "swing_high": 0,
        "swing_low": 0,
        "current_price": prev_close,
        "move_direction": direction,
        "atr": current_atr,
        "entry_mode": "pattern",
    }

    logger.info(
        f"SIGNAL | {symbol} {timeframe_name} | "
        f"{signal['direction'].upper()} | "
        f"Entry: {prev_close:.5f} | "
        f"SL: {signal['sl']:.5f} | TP: {signal['tp1']:.5f} | "
        f"ATR: {current_atr:.5f} | Pattern: Hammer/Star"
    )

    return signal


def _analyze_fibonacci(symbol, timeframe):
    """Analyze using Fibonacci retracement (original method)."""
    swing_lb = config.get_symbol_param(symbol, "SWING_LOOKBACK", config.SWING_LOOKBACK)
    bars_needed = max(swing_lb + 20, 200)
    df = mt5c.get_ohlc(symbol, timeframe, bars_needed)
    if df is None or len(df) < swing_lb:
        return None

    # Detect the current move from swing points
    move = swing_detector.detect_current_move(df, lookback=swing_lb)
    if move is None:
        logger.debug(f"{symbol} {_tf_name(timeframe)}: no swing move detected")
        return None

    direction = move["direction"]
    sh_price = move["swing_high"][1]
    sl_price = move["swing_low"][1]

    # Calculate Fibonacci levels
    levels = fibonacci.calculate_retracement_levels(sh_price, sl_price, direction)
    if levels is None:
        logger.debug(f"{symbol} {_tf_name(timeframe)}: fib levels None")
        return None

    entry_zone = fibonacci.get_entry_zone(levels, direction)
    if entry_zone is None:
        logger.debug(f"{symbol} {_tf_name(timeframe)}: entry zone None")
        return None

    # Use second-to-last candle (last closed)
    prev_bar = df.iloc[-2]
    prev_close = prev_bar["close"]

    if not fibonacci.is_price_in_entry_zone(prev_close, entry_zone):
        logger.debug(f"{symbol} {_tf_name(timeframe)}: price {prev_close:.5f} not in zone [{entry_zone['entry_zone_low']:.5f} - {entry_zone['entry_zone_high']:.5f}]")
        return None

    # Confirmation check
    if config.REQUIRE_CONFIRMATION:
        if direction == "bullish" and prev_close < entry_zone["entry_zone_low"]:
            return None
        if direction == "bearish" and prev_close > entry_zone["entry_zone_high"]:
            return None

    # Trend filter: only trade in direction of H1 trend
    if not filters.check_trend_filter(df, direction, symbol):
        logger.debug(f"{symbol} {_tf_name(timeframe)}: rejected by trend filter")
        return None

    # Momentum filter: RSI + candle body ratio
    if not filters.check_momentum_filter(df, direction):
        logger.debug(f"{symbol} {_tf_name(timeframe)}: rejected by momentum filter")
        return None

    # ATR for SL/TP calculation
    atr_series = filters.calc_atr(df["high"], df["low"], df["close"], config.ATR_PERIOD)
    current_atr = atr_series.iloc[-2]

    # Spread in price (0.3 pip = 0.03 for XAUUSD)
    spread = config.get_symbol_param(symbol, "SPREAD", 0)
    spread_price = spread * 0.10  # Convert pips to price

    # ATR-based SL (matching backtest exactly)
    atr_sl_mult = config.get_symbol_param(symbol, "ATR_SL_MULTIPLIER", config.ATR_SL_MULTIPLIER)
    if config.USE_ATR_SL:
        atr_sl_dist = current_atr * atr_sl_mult + spread_price
        if direction == "bullish":
            atr_sl = prev_close - atr_sl_dist
        else:
            atr_sl = prev_close + atr_sl_dist
    else:
        atr_sl = entry_zone["sl"]

    # ATR-based TP (tight scalper target)
    atr_tp_mult = config.get_symbol_param(symbol, "ATR_TP_MULTIPLIER", config.ATR_TP_MULTIPLIER)
    atr_tp_dist = current_atr * atr_tp_mult + spread_price
    if direction == "bullish":
        atr_tp = prev_close + atr_tp_dist
    else:
        atr_tp = prev_close - atr_tp_dist

    # Skip if SL distance too small for broker minimum
    sl_dist = abs(prev_close - atr_sl)
    if sl_dist < config.MIN_STOP_DISTANCE:
        return None

    timeframe_name = _tf_name(timeframe)
    fib_direction = entry_zone["direction"]
    signal = {
        "symbol": symbol,
        "timeframe": timeframe,
        "timeframe_name": timeframe_name,
        "direction": "buy" if fib_direction == "bullish" else "sell",
        "entry_price": prev_close,
        "entry_zone_high": entry_zone["entry_zone_high"],
        "entry_zone_low": entry_zone["entry_zone_low"],
        "sl": atr_sl,
        "tp1": atr_tp,
        "tp2": entry_zone.get("tp2", atr_tp),
        "swing_high": sh_price,
        "swing_low": sl_price,
        "current_price": prev_close,
        "move_direction": fib_direction,
        "atr": current_atr,
        "entry_mode": "fibonacci",
    }

    logger.info(
        f"SIGNAL | {symbol} {timeframe_name} | "
        f"{signal['direction'].upper()} | "
        f"Entry: {prev_close:.5f} | "
        f"SL: {signal['sl']:.5f} | TP: {signal['tp1']:.5f} | "
        f"ATR: {current_atr:.5f}"
    )

    return signal


def _tf_name(timeframe):
    """Convert MT5 timeframe constant to readable name."""
    tf_map = {
        1: "M1", 5: "M5", 15: "M15", 30: "M30",
        16385: "H1", 16388: "H4", 32769: "D1",
    }
    return tf_map.get(timeframe, f"TF{timeframe}")
