import logging
import MetaTrader5 as mt5
import mt5_connector as mt5c
import swing_detector
import fibonacci
import filters
import config

logger = logging.getLogger(__name__)


def analyze_symbol(symbol, timeframe):
    """Analyze a single symbol on a given timeframe for a Kingade setup.

    Uses ATR-based SL/TP (matching backtest) instead of fibonacci extension.
    Returns a signal dict if a valid entry is found, otherwise None.
    """
    bars_needed = max(config.SWING_LOOKBACK + 20, 200)
    df = mt5c.get_ohlc(symbol, timeframe, bars_needed)
    if df is None or len(df) < config.SWING_LOOKBACK:
        return None

    # Detect the current move from swing points
    move = swing_detector.detect_current_move(df)
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

    # ATR-based SL (matching backtest exactly)
    if config.USE_ATR_SL:
        atr_sl_dist = current_atr * config.ATR_SL_MULTIPLIER
        if direction == "bullish":
            atr_sl = prev_close - atr_sl_dist
        else:
            atr_sl = prev_close + atr_sl_dist
    else:
        atr_sl = entry_zone["sl"]

    # ATR-based TP (tight scalper target)
    atr_tp_dist = current_atr * config.ATR_TP_MULTIPLIER
    if direction == "bullish":
        atr_tp = prev_close + atr_tp_dist
    else:
        atr_tp = prev_close - atr_tp_dist

    # Skip if SL distance too small for broker minimum
    sl_dist = abs(prev_close - atr_sl)
    if sl_dist < config.MIN_STOP_DISTANCE:
        return None

    timeframe_name = _tf_name(timeframe)
    signal = {
        "symbol": symbol,
        "timeframe": timeframe,
        "timeframe_name": timeframe_name,
        "direction": entry_zone["direction"],
        "entry_price": prev_close,
        "entry_zone_high": entry_zone["entry_zone_high"],
        "entry_zone_low": entry_zone["entry_zone_low"],
        "sl": atr_sl,
        "tp1": atr_tp,
        "tp2": entry_zone.get("tp2", atr_tp),
        "swing_high": sh_price,
        "swing_low": sl_price,
        "current_price": prev_close,
        "move_direction": direction,
        "atr": current_atr,
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
