# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import logging
import time
import MetaTrader5 as mt5
import mt5_connector as mt5c
import filters
import config
import telegram_notifier as tg

logger = logging.getLogger(__name__)

# Track bar counts for max-bars exit
_bar_counts = {}


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
    # Cap risk at $20 per trade
    risk_amount = min(risk_amount, config.MAX_RISK_PER_TRADE)
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

    if lot_size > config.MAX_LOT:
        logger.warning(f"Capping lot from {lot_size} to {config.MAX_LOT}")
        lot_size = config.MAX_LOT

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
    tf_name_map = {1: "M1", 5: "M5", 15: "M15", 30: "M30", 16385: "H1", 16388: "H4", 32769: "D1"}
    tf_name = tf_name_map.get(timeframe, str(timeframe))
    for pos in positions:
        if pos.comment and _tf_from_comment(pos.comment) == tf_name:
            return True
    return False


_COMMENT_BUDGET = 31  # Exness rejects comments with '|'/'=' field combos; keep plain ASCII


def _num_fits(value, budget):
    """Format a price to the most decimals that fit `budget` chars."""
    for dec in (4, 3, 2, 1, 0):
        s = "%.*f" % (dec, value)
        if len(s) <= budget:
            return s
    return "%.0f" % value


def _build_comment(timeframe_name, wick, sl):
    """Order comment: kg_<TF> w<wick> sl<SL> (space-separated).

    Exness-MT5 rejects the previously used '|w=...|sl=...' form with
    'Invalid "comment" argument', so no pipes or equals signs. Stays
    <= 31 chars total; precision degrades only when the price needs it."""
    prefix = "kg_" + timeframe_name
    n_fields = (1 if wick is not None else 0) + (1 if sl is not None else 0)
    marker_len = (1 if wick is not None else 0) + (2 if sl is not None else 0)
    per = (_COMMENT_BUDGET - len(prefix) - marker_len) // n_fields if n_fields else 0
    parts = [prefix]
    if wick is not None:
        parts.append("w" + _num_fits(wick, per - 1))
    if sl is not None:
        parts.append("sl" + _num_fits(sl, per - 2))
    return " ".join(parts)[:_COMMENT_BUDGET]


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

    comment = _build_comment(signal["timeframe_name"],
                             signal.get("signal_wick"),
                             signal.get("sl"))

    result = mt5c.send_market_order(
        symbol=symbol,
        order_type=order_type,
        lot_size=lot_size,
        sl=signal["sl"],
        tp=None if config.USE_OPEN_RR else signal["tp1"],
        comment=comment,
    )

    if result is not None:
        _bar_counts[str(result.order)] = 0

    return result


_guard_last_notify = 0.0
GUARD_NOTIFY_INTERVAL = 60.0  # cap Telegram spam if user keeps placing trades


def _guard_notify(closed, cancelled):
    """Throttled Telegram notice about positions/orders the guard killed."""
    global _guard_last_notify
    now = time.monotonic()
    if now - _guard_last_notify < GUARD_NOTIFY_INTERVAL:
        return
    _guard_last_notify = now
    lines = []
    for t, s, m, pr in closed:
        lines.append(f"\u2022 closed #{t} {s} magic {m} pnl {pr:+.2f}")
    for t, s, m in cancelled:
        lines.append(f"\u2022 cancelled order #{t} {s} magic {m}")
    try:
        tg.send_message(
            "<b>MANUAL TRADE GUARD</b>\nAny trade/order not placed by the "
            "bot or its exempted EAs is closed immediately. Just now:\n"
            + "\n".join(lines))
    except Exception as e:
        logger.error(f"GUARD notify failed: {e}")


def _manage_manual_trades():
    """Close/cancel ANY position or pending order whose magic is neither
    this bot's nor an exempted EA's. Manual MT5 terminal trades have
    magic 0, so they never survive a 5s scan cycle."""
    exempt = {config.MAGIC_NUMBER} | set(config.GUARD_EXEMPT_MAGICS)
    closed, cancelled = [], []
    for p in mt5.positions_get() or []:
        if p.magic in exempt:
            continue
        if config.GUARD_DEBUG:
            logger.warning(f"GUARD[debug] WOULD close #{p.ticket} {p.symbol} "
                           f"magic={p.magic} vol={p.volume} pnl={p.profit:.2f}")
        else:
            try:
                mt5c.close_position(p.ticket)
            except Exception as e:
                logger.error(f"GUARD close failed #{p.ticket}: {e}")
                continue
            logger.warning(f"GUARD: closed manual position #{p.ticket} "
                           f"{p.symbol} magic={p.magic} vol={p.volume} "
                           f"pnl={p.profit:.2f}")
            closed.append((p.ticket, p.symbol, p.magic, p.profit))
    for o in mt5.orders_get() or []:
        if o.magic in exempt:
            continue
        if config.GUARD_DEBUG:
            logger.warning(f"GUARD[debug] WOULD cancel order #{o.ticket} "
                           f"{o.symbol} magic={o.magic}")
        else:
            try:
                res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE,
                                      "order": o.ticket})
            except Exception as e:
                logger.error(f"GUARD cancel failed #{o.ticket}: {e}")
                continue
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                logger.warning(f"GUARD: cancelled order #{o.ticket} "
                               f"{o.symbol} magic={o.magic}")
                cancelled.append((o.ticket, o.symbol, o.magic))
    if closed or cancelled:
        _guard_notify(closed, cancelled)


def manage_open_positions():
    """Manage open positions: reverse-close + trailing stop + max bars exit."""
    if config.MANUAL_TRADE_GUARD:
        _manage_manual_trades()
    positions = mt5c.get_positions_by_magic()
    for pos in positions:
        ticket = pos.ticket
        symbol = pos.symbol

        # Get current tick
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            continue

        current_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        # Close early if price reverses toward SL and reaches the signal wick
        if _manage_reverse_close(pos, current_price):
            continue

        # Calculate trailing stop (RR-step ratchet when open RR is active,
        # otherwise the classic ATR trail)
        if config.USE_OPEN_RR:
            _manage_rr_step_trail(pos, current_price)
        elif config.USE_TRAILING_STOP and config.get_symbol_param(
                symbol, "TRAILING_ENABLED", True):
            atr = _get_current_atr(symbol, config.TIMEFRAMES[0])
            if atr is not None:
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
            min_dist = config.MIN_STOP_DISTANCE * symbol_info.point
            if direction == "buy" and (current_price - new_sl) < min_dist:
                new_sl = current_price - min_dist
            elif direction == "sell" and (new_sl - current_price) < min_dist:
                new_sl = current_price + min_dist

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
            tg.notify_sl_trail(symbol, ticket, direction, current_sl, new_sl, current_price, pos.profit)
        else:
            logger.debug(f"Trailing stop update failed for #{ticket}: {result}")


def _manage_rr_step_trail(pos, current_price):
    """Open-RR ratchet (live mirror of the backtest `_update_rr_trail`).

    No take-profit on the position. Once unrealized profit reaches
    RR_TRAIL_START_R * original-SL-distance, the stop locks in
    (milestone - RR_TRAIL_LOCK_R) * SL-distance, stepping every
    RR_TRAIL_STEP_R R (3R -> ~2R, 5R -> ~4R, 7R -> ~6R, ...).
    The original SL is read from the order comment so the risk basis
    survives stop modifications.
    """
    ticket = pos.ticket
    symbol = pos.symbol
    direction = "buy" if pos.type == mt5.ORDER_TYPE_BUY else "sell"
    entry = pos.price_open
    original_sl = _original_sl_from_comment(pos.comment)
    if original_sl is None:
        return

    sl_distance = abs(entry - original_sl)
    if sl_distance <= 0:
        return

    unrealized = (current_price - entry) if direction == "buy" else (entry - current_price)
    if unrealized <= 0:
        return

    rr = unrealized / sl_distance
    if rr < config.RR_TRAIL_START_R:
        return

    milestone = config.RR_TRAIL_START_R + (
        (rr - config.RR_TRAIL_START_R) // config.RR_TRAIL_STEP_R
    ) * config.RR_TRAIL_STEP_R
    lock_r = milestone - config.RR_TRAIL_LOCK_R
    if lock_r <= 0:
        return

    lock_price = entry + lock_r * sl_distance if direction == "buy" else entry - lock_r * sl_distance
    current_sl = pos.sl

    if direction == "buy" and lock_price <= current_sl:
        return
    if direction == "sell" and (current_sl == 0 or lock_price >= current_sl):
        return

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info:
        lock_price = round(lock_price, symbol_info.digits)
        min_dist = config.MIN_STOP_DISTANCE * symbol_info.point
        if direction == "buy" and (current_price - lock_price) < min_dist:
            lock_price = current_price - min_dist
        elif direction == "sell" and (lock_price - current_price) < min_dist:
            lock_price = current_price + min_dist

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol": symbol,
        "sl": lock_price,
        "tp": 0.0,
        "magic": config.MAGIC_NUMBER,
    }

    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(
            f"RR TRAIL | {symbol} #{ticket} | {direction.upper()} | "
            f"reached ~{milestone:.1f}R ({rr:.2f}R) | "
            f"SL: {pos.sl:.5f} -> {lock_price:.5f}"
        )
        try:
            tg.notify_sl_trail(symbol, ticket, direction, pos.sl, lock_price,
                               current_price, pos.profit)
        except Exception as e:
            logger.debug(f"RR trail notify failed: {e}")
    else:
        logger.debug(f"RR trail update failed for #{ticket}: {result}")


def _manage_reverse_close(pos, current_price):
    """Close trade early if price reverses toward SL and reaches the
    wick of the hammer/engulfing signal candle.

    The wick is read from the order comment (kg_M1 w<price>).
    Only fires when price has already moved against the entry (i.e. the
    market reversed) AND is within REVERSE_CLOSE_DISTANCE of the wick.
    Returns True if the position was closed.
    """
    if not config.USE_REVERSE_CLOSE:
        return False

    symbol = pos.symbol
    direction = "buy" if pos.type == mt5.ORDER_TYPE_BUY else "sell"

    wick = _signal_wick_from_comment(pos.comment)
    if wick is None:
        return False

    rc_dist = config.get_symbol_param(
        symbol, "REVERSE_CLOSE_DISTANCE", config.REVERSE_CLOSE_DISTANCE
    )

    trigger = False
    if direction == "buy":
        # Price dropped toward SL and got close to the bullish wick (low)
        if current_price < pos.price_open and current_price <= wick + rc_dist:
            trigger = True
    else:
        # Price rose toward SL and got close to the bearish wick (high)
        if current_price > pos.price_open and current_price >= wick - rc_dist:
            trigger = True

    if not trigger:
        return False

    profit = pos.profit
    logger.info(
        f"REVERSE CLOSE | {symbol} #{pos.ticket} | "
        f"Price {current_price:.5f} near signal wick {wick:.5f} | "
        f"Profit (unrealized): {profit:.2f}"
    )
    mt5c.close_position(pos.ticket)
    tg.notify_trade_closed(pos, profit)
    _bar_counts.pop(str(pos.ticket), None)
    return True


def _original_sl_from_comment(comment):
    """Extract the ORIGINAL entry stop-loss from the order comment
    (kg_TF w<wick> sl<SL>) so RR trailing always measures risk against
    the untouched initial stop even after SL modifications."""
    if not comment:
        return None
    for tok in comment.split():
        if tok.startswith("sl") and len(tok) > 2:
            try:
                return float(tok[2:])
            except ValueError:
                continue
    return None


def _signal_wick_from_comment(comment):
    """Extract signal candle wick from order comment (kg_TF w<wick> sl<sl>)."""
    if not comment:
        return None
    for tok in comment.split():
        if tok.startswith("w") and len(tok) > 1:
            try:
                return float(tok[1:])
            except ValueError:
                return None
    return None


def _manage_max_bars(pos):
    """Force close position if held for more than MAX_BARS_IN_TRADE bars.

    Bars are counted on the trade's own entry timeframe (parsed from the
    order comment), matching the backtest's per-timeframe bar counting.
    """
    ticket = pos.ticket
    symbol = pos.symbol

    tf = _entry_timeframe(pos.comment)
    if tf is None:
        return

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
            f"MAX BARS EXIT | {symbol} #{ticket} | {_tf_from_comment(pos.comment) or '?'} | "
            f"Held {_bar_counts[key]} bars (max: {config.MAX_BARS_IN_TRADE})"
        )
        profit = pos.profit
        mt5c.close_position(ticket)
        tg.notify_trade_closed(pos, profit)
        _bar_counts.pop(key, None)


def _tf_from_comment(comment):
    """Extract timeframe string from order comment."""
    if comment.startswith("kg_"):
        return comment[3:].split(" ", 1)[0]
    if comment.startswith("kingade_"):
        return comment[8:].split("|", 1)[0].split(" ", 1)[0]
    return ""


def _entry_timeframe(comment):
    """MT5 timeframe for a position's entry TF (from order comment).

    Falls back to the first configured timeframe if the comment can't be
    parsed, so max-bars tracking is never silently disabled.
    """
    tf_map = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5}
    name = _tf_from_comment(comment)
    if name in tf_map:
        return tf_map[name]
    return config.TIMEFRAMES[0]
