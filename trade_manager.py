# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import logging
import MetaTrader5 as mt5
import mt5_connector as mt5c
import filters
import config
import telegram_notifier as tg

logger = logging.getLogger(__name__)

# Track bar counts for max-bars exit
_bar_counts = {}
# Track open times for each position
_open_times = {}


def calculate_lot_size(symbol, entry_price, sl_price):
    """Calculate lot size based on risk percentage of account balance."""
    account = mt5c.get_account_info()
    if account is None:
        logger.error("Cannot calculate lot size: no account info")
        return None

    symbol_info = mt5c.get_symbol_info(symbol)
    if symbol_info is None:
        return None

    risk_amount = account.balance * config.RISK_PERCENT / 100.0
    sl_distance = abs(entry_price - sl_price)

    if sl_distance == 0:
        logger.warning("SL distance is zero, cannot calculate lot size")
        return None

    tick_size = symbol_info.trade_tick_size
    tick_value = symbol_info.trade_tick_value

    if tick_value == 0 or tick_size == 0:
        logger.warning(f"Invalid tick data for {symbol}")
        return None

    sl_ticks = sl_distance / tick_size
    lot_size = risk_amount / (sl_ticks * tick_value)

    volume_step = symbol_info.volume_step
    min_volume = symbol_info.volume_min
    max_volume = symbol_info.volume_max

    lot_size = max(min_volume, lot_size)
    lot_size = min(max_volume, lot_size)
    lot_size = round(lot_size / volume_step) * volume_step
    lot_size = round(lot_size, 2)

    logger.info(
        f"Lot size calc | {symbol} | Balance: {account.balance} | "
        f"Risk: {config.RISK_PERCENT}% ({risk_amount:.2f}) | "
        f"SL dist: {sl_distance:.5f} | Lot: {lot_size}"
    )

    return lot_size


def can_open_trade(symbol):
    """Check if we can open a new trade on this symbol."""
    all_positions = mt5c.get_positions_by_magic()
    if len(all_positions) >= config.MAX_POSITIONS:
        return False

    symbol_positions = mt5c.get_positions_by_magic(symbol)
    if len(symbol_positions) >= config.MAX_POSITIONS_PER_SYMBOL:
        return False

    return True


def has_existing_signal(symbol, timeframe):
    """Check if we already have an open position for this symbol+timeframe."""
    positions = mt5c.get_positions_by_magic(symbol)
    for pos in positions:
        if pos.comment and _tf_from_comment(pos.comment) == str(timeframe):
            return True
    return False


def execute_signal(signal):
    """Execute a trading signal by opening a market order."""
    symbol = signal["symbol"]

    if not can_open_trade(symbol):
        logger.info(f"Skipping {symbol}: position limits reached")
        return False

    order_type = mt5.ORDER_TYPE_BUY if signal["direction"] == "buy" else mt5.ORDER_TYPE_SELL

    lot_size = calculate_lot_size(symbol, signal["entry_price"], signal["sl"])
    if lot_size is None or lot_size <= 0:
        logger.error(f"Invalid lot size for {symbol}")
        return False

    comment = f"kingade_{signal['timeframe_name']}"

    result = mt5c.send_market_order(
        symbol=symbol,
        order_type=order_type,
        lot_size=lot_size,
        sl=signal["sl"],
        tp=signal["tp1"],
        comment=comment,
    )

    if result is not None:
        _bar_counts[result.order] = 0
        _open_times[result.order] = mt5.symbol_info_tick(symbol).time

    return result is not None


def manage_open_positions():
    """Manage open positions: trailing stop + max bars exit."""
    positions = mt5c.get_positions_by_magic()
    for pos in positions:
        ticket = pos.ticket
        symbol = pos.symbol

        # Get current ATR for trailing stop (use first configured timeframe)
        atr = _get_current_atr(symbol, config.TIMEFRAMES[0])
        if atr is None:
            continue

        # Get current tick
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            continue

        current_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        # Calculate trailing stop
        if config.USE_TRAILING_STOP:
            _manage_trailing_stop(pos, current_price, atr)

        # Track bar count and force close if max bars exceeded
        _manage_max_bars(pos)


def _get_current_atr(symbol, timeframe):
    """Get current ATR value for a symbol+timeframe."""
    try:
        import mt5_connector as mt5c
        df = mt5c.get_ohlc(symbol, timeframe, config.ATR_PERIOD + 10)
        if df is None or len(df) < config.ATR_PERIOD:
            return None
        atr_series = filters.calc_atr(df["high"], df["low"], df["close"], config.ATR_PERIOD)
        return atr_series.iloc[-1]
    except Exception:
        return None


def _manage_trailing_stop(pos, current_price, atr):
    """Update trailing stop for a profitable position."""
    ticket = pos.ticket
    symbol = pos.symbol
    direction = "buy" if pos.type == mt5.ORDER_TYPE_BUY else "sell"
    entry = pos.price_open
    current_sl = pos.sl

    trail_start = atr * config.get_symbol_param(symbol, "TRAILING_START_ATR", config.TRAILING_START_ATR)
    trail_step = atr * config.get_symbol_param(symbol, "TRAILING_STEP_ATR", config.TRAILING_STEP_ATR)

    new_sl = None

    if direction == "buy":
        unrealized = current_price - entry
        if unrealized >= trail_start:
            candidate = current_price - trail_step
            if candidate > current_sl:
                new_sl = candidate
    else:
        unrealized = entry - current_price
        if unrealized >= trail_start:
            candidate = current_price + trail_step
            if current_sl == 0 or candidate < current_sl:
                new_sl = candidate

    if new_sl is not None:
        symbol_info = mt5.symbol_info(pos.symbol)
        if symbol_info:
            new_sl = round(new_sl, symbol_info.digits)

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": new_sl,
            "tp": pos.tp,
            "magic": config.MAGIC_NUMBER,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(
                f"TRAILING STOP | {symbol} #{ticket} | "
                f"SL: {current_sl:.5f} -> {new_sl:.5f}"
            )
        else:
            logger.debug(f"Trailing stop update failed for #{ticket}: {result}")


def _manage_max_bars(pos):
    """Force close position if held for more than MAX_BARS_IN_TRADE bars."""
    ticket = pos.ticket
    symbol = pos.symbol
    tf = config.TIMEFRAMES[0]

    key = f"{ticket}"
    if key not in _bar_counts:
        _bar_counts[key] = 0

    # Check new candle
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, 2)
    if rates is None or len(rates) < 2:
        return

    last_bar_time = rates[-1]["time"]
    prev_bar_time = rates[-2]["time"]

    if last_bar_time > prev_bar_time:
        _bar_counts[key] += 1

    if _bar_counts[key] >= config.MAX_BARS_IN_TRADE:
        logger.info(
            f"MAX BARS EXIT | {symbol} #{ticket} | "
            f"Held {_bar_counts[key]} bars (max: {config.MAX_BARS_IN_TRADE})"
        )
        profit = pos.profit
        mt5c.close_position(ticket)
        tg.notify_trade_closed(pos, profit)
        _bar_counts.pop(key, None)


def _tf_from_comment(comment):
    """Extract timeframe string from order comment."""
    if comment.startswith("kingade_"):
        return comment[8:]
    return ""
