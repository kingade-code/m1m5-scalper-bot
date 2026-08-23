# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
"""Telegram notification module for Kingade Scalper Bot."""

import json
import os
import uuid
import urllib.request
import logging
import config

logger = logging.getLogger(__name__)

_boundary = uuid.uuid4().hex


def send_message(text, parse_mode="HTML"):
    """Send a message to all configured Telegram chats."""
    if not config.TELEGRAM_ENABLED:
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    success = False

    for chat_id in config.TELEGRAM_CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read())
            if result.get("ok"):
                success = True
        except Exception as e:
            logger.error(f"Telegram error (chat {chat_id}): {e}")

    return success


def send_signal_to_group(text, parse_mode="HTML"):
    """Send trade signal to the FREE SIGNALS topic in KINGADE FOREX group."""
    if not config.TELEGRAM_ENABLED:
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        payload = {
            "chat_id": config.TELEGRAM_GROUP_CHAT_ID,
            "message_thread_id": config.TELEGRAM_GROUP_THREAD_ID,
            "text": text,
            "parse_mode": parse_mode,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        if result.get("ok"):
            logger.info("Signal sent to FREE SIGNALS topic")
            return True
    except Exception as e:
        logger.error(f"Telegram group error: {e}")
    return False


def send_document(file_path, caption=""):
    """Send a file (PDF/PPTX) to all configured Telegram chats."""
    if not config.TELEGRAM_ENABLED:
        return False

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendDocument"
    filename = os.path.basename(file_path)
    success = False

    for chat_id in config.TELEGRAM_CHAT_IDS:
        try:
            boundary = uuid.uuid4().hex
            body = _encode_multipart(boundary, chat_id, file_path, filename, caption)
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            resp = urllib.request.urlopen(req, timeout=60)
            result = json.loads(resp.read())
            if result.get("ok"):
                success = True
                logger.info(f"File sent to {chat_id}: {filename}")
            else:
                logger.warning(f"Send file failed for {chat_id}: {result}")
        except Exception as e:
            logger.error(f"Telegram file error (chat {chat_id}): {e}")

    return success


def _encode_multipart(boundary, chat_id, file_path, filename, caption):
    """Build multipart/form-data body for file upload."""
    lines = []

    def add_field(name, value):
        lines.append(f"--{boundary}")
        lines.append(f'Content-Disposition: form-data; name="{name}"')
        lines.append("")
        lines.append(str(value))

    add_field("chat_id", chat_id)
    if caption:
        add_field("caption", caption)

    # File part
    lines.append(f"--{boundary}")
    lines.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"')
    lines.append("Content-Type: application/octet-stream")
    lines.append("")

    header = "\r\n".join(lines) + "\r\n"
    with open(file_path, "rb") as f:
        file_data = f.read()

    footer = f"\r\n--{boundary}--\r\n"
    return header.encode("utf-8") + file_data + footer.encode("utf-8")


def notify_signal(signal):
    """Send a new signal notification."""
    direction = signal["direction"].upper()
    emoji = "\U0001F7E2" if signal["direction"] == "buy" else "\U0001F534"

    text = (
        f"<b>{emoji} NEW SIGNAL - {direction}</b>\n\n"
        f"<b>Symbol:</b> {signal['symbol']}\n"
        f"<b>Timeframe:</b> {signal['timeframe_name']}\n"
        f"<b>Entry:</b> {signal['entry_price']:.2f}\n"
        f"<b>Stop Loss:</b> {signal['sl']:.2f}\n"
        f"<b>Take Profit:</b> {signal['tp1']:.2f}\n"
        f"<b>ATR:</b> {signal.get('atr', 0):.2f}\n\n"
        f"<i>Auto-executing...</i>"
    )
    send_signal_to_group(text)
    return send_message(text)


def notify_trade_opened(signal, result):
    """Send a trade execution notification."""
    direction = signal["direction"].upper()
    price = result.price if result else signal["entry_price"]

    text = (
        f"<b>\u2705 TRADE OPENED - {direction}</b>\n\n"
        f"<b>Symbol:</b> {signal['symbol']}\n"
        f"<b>Timeframe:</b> {signal['timeframe_name']}\n"
        f"<b>Direction:</b> {direction}\n"
        f"<b>Entry Price:</b> {price:.2f}\n"
        f"<b>Stop Loss:</b> {signal['sl']:.2f}\n"
        f"<b>Take Profit:</b> {signal['tp1']:.2f}\n"
        f"<b>Ticket:</b> #{result.order if result else 'N/A'}"
    )
    send_signal_to_group(text)
    return send_message(text)


def notify_trade_closed(position, profit):
    """Send trade closed notification."""
    direction = "BUY" if position.type == 0 else "SELL"
    emoji = "\U0001F4B0" if profit >= 0 else "\U0001F4B9"
    result = "WIN" if profit >= 0 else "LOSS"

    text = (
        f"<b>{emoji} TRADE CLOSED - {result}</b>\n\n"
        f"<b>Symbol:</b> {position.symbol}\n"
        f"<b>Direction:</b> {direction}\n"
        f"<b>Entry:</b> {position.price_open:.2f}\n"
        f"<b>Volume:</b> {position.volume}\n"
        f"<b>P/L:</b> ${profit:+.2f}\n"
        f"<b>Ticket:</b> #{position.ticket}"
    )
    send_signal_to_group(text)
    return send_message(text)


def notify_daily_summary(trades_today, pnl_today, balance):
    """Send end-of-day summary."""
    wins = sum(1 for t in trades_today if t.profit >= 0)
    losses = len(trades_today) - wins

    text = (
        f"<b>\U0001F4CA DAILY SUMMARY</b>\n\n"
        f"<b>Date:</b> {trades_today[0].entry_time.strftime('%d %b %Y') if trades_today else 'N/A'}\n"
        f"<b>Trades:</b> {len(trades_today)}\n"
        f"<b>Wins:</b> {wins} | <b>Losses:</b> {losses}\n"
        f"<b>Daily P/L:</b> ${pnl_today:+.2f}\n"
        f"<b>Balance:</b> ${balance:,.2f}"
    )
    return send_message(text)


def notify_error(error_msg):
    """Send error notification."""
    text = f"<b>\u26A0\uFE0F BOT ERROR</b>\n\n<code>{error_msg}</code>"
    return send_message(text)


def notify_bot_started():
    """Send bot startup notification."""
    tf_map = {1: "M1", 5: "M5", 15: "M15", 30: "M30"}
    tf_names = ", ".join(tf_map.get(tf, str(tf)) for tf in config.TIMEFRAMES)
    text = (
        f"<b>\U0001F680 KINGADE SCALPER BOT STARTED</b>\n\n"
        f"<b>Account:</b> {config.MT5_LOGIN or 'Live'}\n"
        f"<b>Symbols:</b> {', '.join(config.SYMBOL_LIST)}\n"
        f"<b>Timeframes:</b> {tf_names}\n"
        f"<b>Risk:</b> {config.RISK_PERCENT}%\n"
        f"<b>Trailing Stop:</b> {'ON' if config.USE_TRAILING_STOP else 'OFF'}\n"
        f"<b>Auto-Trade:</b> ON"
    )
    return send_message(text)
