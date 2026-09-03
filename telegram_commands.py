# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
"""Telegram command channel for Kingade Scalper Bot.

The bot is otherwise one-way (notifications only). This module lets the
operator send commands from an authorised Telegram chat and get replies:

  /help    - list available commands
  /status  - account, equity, open positions, pause/drawdown state
  /pause   - stop opening NEW trades (running positions still managed)
  /resume  - allow new trades again
  /config  - show key active configuration

Command polling is non-blocking and throttle-gated so it never slows the
5s scan loop. Only chats in TELEGRAM_CHAT_IDS are honoured; everything else
is ignored.
"""

import os
import json
import time
import logging
import urllib.request
from datetime import datetime, UTC

import config
import mt5_connector as mt5c
import telegram_notifier as tg

logger = logging.getLogger("telegram_commands")

_last_update_id = 0
_last_poll_time = 0.0
_last_error_at = 0.0
_error_repeat_secs = 300  # only log a poll failure once per 5 min

# The bot runs as a supervisor (parent) + worker (child) pair. Only the
# process that holds the single-instance lock must consume getUpdates,
# otherwise two Telegram long-poll consumers conflict (HTTP 409) and
# command handling breaks.
_DEFAULT_LOCK_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bot.lock.d")


def _lock_holder_pid(lock_dir=None):
    try:
        d = lock_dir or getattr(config, "LOCK_PID_DIR", _DEFAULT_LOCK_DIR)
        with open(os.path.join(d, "pid"), "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _is_lock_holder():
    """True only for the process that owns the single-instance lock."""
    return os.getpid() == _lock_holder_pid()


def _api_url():
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"


def _get_updates(offset, timeout=1):
    """Fetch pending updates via getUpdates (short long-poll). Returns a list
    of update dicts, or None on error/disabled."""
    if not config.TELEGRAM_ENABLED:
        return []
    url = f"{_api_url()}/getUpdates"
    payload = json.dumps({"offset": offset, "timeout": timeout,
                          "allowed_updates": ["message"]}).encode("utf-8")
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout + 5)
        result = json.loads(resp.read())
        if result.get("ok"):
            return result.get("result", [])
    except Exception as e:
        global _last_error_at
        now = time.time()
        if now - _last_error_at >= _error_repeat_secs:
            _last_error_at = now
            logger.error(f"getUpdates failed: {e}")
    return []


def _is_authorised(chat_id):
    """Commands are only honoured from the configured private chats."""
    return chat_id in [int(c) for c in config.TELEGRAM_CHAT_IDS]


def _command_and_args(text):
    parts = text.strip().split()
    if not parts:
        return "", []
    return parts[0].split("@")[0].lower(), parts[1:]


def _status_text():
    lines = []
    lines.append("<b>BOT STATUS</b>\n")
    acc = mt5c.get_account_info()
    if acc is not None:
        lines.append(f"Account: {acc.login} | {acc.server}")
        lines.append(f"Balance: <b>${acc.balance:,.2f}</b>")
        lines.append(f"Equity:  <b>${acc.equity:,.2f}</b>")
        lines.append(f"FreeMargin: ${acc.margin_free:,.2f}")
    else:
        lines.append("Account: unavailable")

    positions = mt5c.get_positions_by_magic() or []
    if positions:
        lines.append(f"\nOpen bot positions: <b>{len(positions)}</b>")
        for p in positions[:8]:
            side = "BUY" if p.type == 0 else "SELL"
            lines.append(f"  #{p.ticket} {p.symbol} {side} {p.volume} "
                         f"pnl ${p.profit:+.2f}")
    else:
        lines.append("\nOpen bot positions: 0")

    lines.append("\n<i>Run via /pause and /resume to control new entries.</i>")
    return "\n".join(lines)


def _config_text():
    enabled = config.get_symbol_param("BTCUSD", "USE_OPEN_RR", config.USE_OPEN_RR)
    lines = [
        "<b>ACTIVE CONFIG</b>",
        f"Symbols: {', '.join(config.SYMBOL_LIST)}",
        f"Timeframes: "
        f"{', '.join('M1' if t == 1 else 'M5' for t in config.TIMEFRAMES)} "
        f"(BTCUSD uses M1 only)",
        f"Risk: {config.RISK_PERCENT}% per trade",
        f"Max positions: {config.MAX_POSITIONS}",
        f"Scan interval: {config.SCAN_INTERVAL_SECONDS}s",
        f"Manual trade guard: {'ON' if config.MANUAL_TRADE_GUARD else 'OFF'}",
        f"Daily drawdown limit: "
        f"{'ON (-%.0f%%)' % config.DAILY_DRAWDOWN_PCT if config.DAILY_DRAWDOWN_ENABLED else 'OFF'}",
        f"Trailing: Open-RR={'ON' if enabled else 'OFF'}",
    ]
    return "\n".join(lines)


def _reply(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    url = f"{_api_url()}/sendMessage"
    data = json.dumps(payload).encode("utf-8")
    # Retry a few times: outbound HTTPS to api.telegram.org is flaky here and
    # a single-handshake failure otherwise drops the user's reply silently.
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data,
                                         headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read())
            if result.get("ok"):
                return True
            logger.warning(f"Command reply failed: {result}")
            return False
        except Exception as e:
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
            logger.error(f"Command reply error: {e}")
    return False


def _dispatch(chat_id, cmd, args):
    if cmd == "/help":
        _reply(chat_id,
               "<b>Commands</b>\n"
               "/help - this list\n"
               "/status - balance, equity, open positions\n"
               "/pause - stop opening new trades\n"
               "/resume - reopen trading\n"
               "/config - show active settings")
    elif cmd == "/status":
        _reply(chat_id, _status_text())
    elif cmd == "/pause":
        _set_paused_file(True)
        _reply(chat_id, "⏸ <b>PAUSED</b>\nNew entries stopped. "
                        "Open positions still managed. Send /resume to reopen.")
    elif cmd == "/resume":
        _set_paused_file(False)
        _reply(chat_id, "▶️ <b>RESUMED</b>\nTrading re-enabled.")
    elif cmd == "/config":
        _reply(chat_id, _config_text())
    else:
        _reply(chat_id, "Unknown command. Send /help for the list.")


def _set_paused_file(paused):
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PAUSED")
    try:
        if paused:
            with open(path, "w") as f:
                f.write("paused")
            logger.info("Command: bot PAUSED")
        else:
            if os.path.exists(path):
                os.remove(path)
            logger.info("Command: bot RESUMED")
    except OSError as e:
        logger.error(f"Could not update PAUSED file: {e}")


def poll(force=False):
    """Poll Telegram once and dispatch any pending commands. Throttled so it
    runs at most once every COMMAND_POLL_SECONDS. Returns True when one or more
    commands were handled (for logging). Only the lock-holding process may poll
    to avoid the getUpdates 409 conflict from the parent+child pair."""
    global _last_update_id, _last_poll_time
    if not config.TELEGRAM_ENABLED:
        return False
    if not _is_lock_holder():
        return False
    interval = getattr(config, "COMMAND_POLL_SECONDS", 10)
    now = time.time()
    if not force and (now - _last_poll_time) < interval:
        return False
    _last_poll_time = now

    # getUpdates is interruptible/flaky on this network: retry a couple of
    # times to ride out transient timeouts (a mostly-open long-poll is far
    # worse than a short retry when a send/receive fails).
    updates = None
    for _ in range(3):
        updates = _get_updates(_last_update_id + 1)
        if updates is not None:
            break
        time.sleep(0.5)
    if updates is None:
        return False
    handled = False
    for upd in updates or []:
        uid = upd.get("update_id")
        if uid is not None and uid > _last_update_id:
            _last_update_id = uid
        msg = upd.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        if chat_id is None:
            continue
        if not _is_authorised(chat_id):
            logger.debug(f"Ignoring command from unauthorised chat {chat_id}")
            continue
        cmd, args = _command_and_args(msg.get("text", ""))
        if cmd.startswith("/"):
            handled = True
            logger.info(f"Telegram command from {chat_id}: {cmd}")
            _dispatch(chat_id, cmd, args)
    return handled