# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import os
import json
import MetaTrader5 as mt5
import pandas as pd
import logging
import config

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mt5_credentials.json")


def _load_credentials():
    """Load credentials from file if available."""
    if not os.path.exists(CREDENTIALS_FILE):
        return {}
    try:
        with open(CREDENTIALS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def initialize():
    """Initialize connection to MetaTrader 5 terminal."""
    init_args = {}

    # Priority: config.py > credentials file > auto-detect (no login)
    if config.MT5_LOGIN and config.MT5_PASSWORD:
        init_args["login"] = config.MT5_LOGIN
        init_args["password"] = config.MT5_PASSWORD
        init_args["server"] = config.MT5_SERVER
    else:
        saved = _load_credentials()
        if saved.get("login"):
            init_args["login"] = saved["login"]
            if saved.get("password"):
                init_args["password"] = saved["password"]
            if saved.get("server"):
                init_args["server"] = saved["server"]

    if config.MT5_PATH:
        init_args["path"] = config.MT5_PATH
    init_args["timeout"] = config.MT5_TIMEOUT

    if not mt5.initialize(**init_args):
        error = mt5.last_error()
        logger.error(f"MT5 initialization failed: {error}")
        return False

    account_info = mt5.account_info()
    if account_info:
        logger.info(
            f"Connected to MT5 | Account: {account_info.login} | "
            f"Server: {account_info.server} | Balance: {account_info.balance}"
        )
    return True


def shutdown():
    """Shutdown MT5 connection."""
    mt5.shutdown()
    logger.info("MT5 connection closed")


def get_account_info():
    """Get current account information."""
    info = mt5.account_info()
    if info is None:
        logger.error(f"Failed to get account info: {mt5.last_error()}")
    return info


def get_symbol_info(symbol):
    """Get symbol properties and trading parameters."""
    info = mt5.symbol_info(symbol)
    if info is None:
        logger.warning(f"Symbol {symbol} not found")
    return info


def get_available_symbols():
    """Get list of all symbols available for trading."""
    symbols = mt5.symbols_get()
    if symbols is None:
        logger.error(f"Failed to get symbols: {mt5.last_error()}")
        return []
    return [s.name for s in symbols if s.visible]


def get_ohlc(symbol, timeframe, count):
    """Get OHLC data as a pandas DataFrame."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        logger.warning(f"No data for {symbol} timeframe {timeframe}")
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def get_positions(symbol=None):
    """Get open positions, optionally filtered by symbol."""
    if symbol:
        positions = mt5.positions_get(symbol=symbol)
    else:
        positions = mt5.positions_get()
    if positions is None:
        return []
    return list(positions)


def get_positions_by_magic(symbol=None):
    """Get open positions managed by this bot (by magic number)."""
    if symbol:
        positions = mt5.positions_get(symbol=symbol)
    else:
        positions = mt5.positions_get()
    if positions is None:
        return []
    return [p for p in positions if p.magic == config.MAGIC_NUMBER]


def send_market_order(symbol, order_type, lot_size, sl, tp, comment=""):
    """Send a market order with SL and TP."""
    symbol_info = get_symbol_info(symbol)
    if symbol_info is None:
        return None

    if not symbol_info.trade_mode:
        logger.warning(f"Trading disabled for {symbol}")
        return None

    price = symbol_info.ask if order_type == mt5.ORDER_TYPE_BUY else symbol_info.bid
    point = symbol_info.point
    digits = symbol_info.digits

    sl = round(sl, digits)
    tp = round(tp, digits)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": config.SLIPPAGE,
        "magic": config.MAGIC_NUMBER,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    result = mt5.order_send(request)
    if result is None:
        logger.error(f"Order send failed: {mt5.last_error()}")
        return None

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(
            f"Order rejected for {symbol}: {result.comment} "
            f"(code={result.retcode})"
        )
        return None

    logger.info(
        f"ORDER EXECUTED | {symbol} | "
        f"{'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL'} | "
        f"Lot: {lot_size} | Price: {result.price} | "
        f"SL: {sl} | TP: {tp}"
    )
    return result


def close_position(ticket):
    """Close an open position by ticket."""
    position = mt5.positions_get(ticket=ticket)
    if not position:
        logger.error(f"Position {ticket} not found")
        return None
    position = position[0]

    close_type = (
        mt5.ORDER_TYPE_SELL
        if position.type == mt5.ORDER_TYPE_BUY
        else mt5.ORDER_TYPE_BUY
    )
    symbol_info = get_symbol_info(position.symbol)
    if symbol_info is None:
        logger.error(f"Cannot get symbol info for {position.symbol}")
        return None
    price = symbol_info.bid if position.type == mt5.ORDER_TYPE_BUY else symbol_info.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": close_type,
        "position": ticket,
        "price": price,
        "deviation": config.SLIPPAGE,
        "magic": config.MAGIC_NUMBER,
        "comment": "kingade_close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Failed to close position {ticket}: {result}")
        return None

    logger.info(f"Position {ticket} closed on {position.symbol}")
    return result
