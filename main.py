# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import os
import sys
import time
import signal
import logging
from datetime import datetime, UTC

# Console/boot logs must be UTF-8: the SIGNAL CONFIRMED log contains emoji
# (U+1F7E2/U+1F534) and would otherwise raise UnicodeEncodeError when
# stdout/stderr is redirected to a cp1252 file (e.g. pythonw + boot log).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import config
import mt5_connector as mt5c
import signal_engine
import trade_manager
import telegram_notifier as tg
import telegram_commands
import daily_report
import login_setup
import license_manager

# ─── Single Instance Lock ──────────────────────────────────────────
import subprocess
import shutil

_LOCK_DIRNAME = "bot.lock.d"
LOCK_PID_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), _LOCK_DIRNAME)
# Legacy single-file path kept for external tooling that reads/stale-clears it.
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.lock")

def _is_process_alive(pid):
    """Check if a process is alive (Windows-compatible)."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=5
        )
        return str(pid) in result.stdout
    except Exception:
        return False

def _acquire_lock():
    """Ensure only one bot instance runs. Kill stale locks if process is dead.
    NOTE: must NOT taskkill pythonw.exe here — the bot is launched via
    pythonw.exe by the auto-start batch files, so that would kill itself."""
    # Atomic claim: create a fresh lock directory. This is the single arbiter —
    # only one process can win os.makedirs() for a path that does not exist.
    # Anyone who loses the race aborts immediately. This removes the old
    # read-then-write TOCTOU that let two instances both proceed.
    if _try_claim_lock():
        return True
    # We lost the claim. Reuse the PID file (kept for compatibility/tooling).
    pid_file = os.path.join(LOCK_PID_DIR, "pid")
    try:
        with open(pid_file, "r") as f:
            old_pid = int(f.read().strip())
        if _is_process_alive(old_pid):
            print(f"Another bot instance is running (PID {old_pid}). Exiting.")
            return False
    except (ValueError, OSError):
        pass
    # The lock-holder's PID is dead (stale) — try to reclaim once.
    # NOTE: the dir contains a pid file, so os.rmdir() alone would fail
    # (OSError: not empty) and leave the stale lock forever, blocking every
    # future start. Remove all contents first so a crashed instance's lock
    # is always recoverable.
    try:
        for entry in os.listdir(LOCK_PID_DIR):
            ep = os.path.join(LOCK_PID_DIR, entry)
            if os.path.isfile(ep):
                os.remove(ep)
            else:
                shutil.rmtree(ep, ignore_errors=True)
        os.rmdir(LOCK_PID_DIR)
    except OSError:
        return False
    return _try_claim_lock()

def _try_claim_lock():
    """Atomically create the lock dir; on success write our PID. Returns bool."""
    try:
        os.makedirs(LOCK_PID_DIR)
    except FileExistsError:
        return False
    try:
        with open(os.path.join(LOCK_PID_DIR, "pid"), "w") as f:
            f.write(str(os.getpid()))
        return True
    except OSError:
        os.rmdir(LOCK_PID_DIR)
        return False

def _release_lock():
    """Remove lock on exit. Only the instance that holds it may release it."""
    try:
        pid_file = os.path.join(LOCK_PID_DIR, "pid")
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            if pid == os.getpid():
                os.rmdir(LOCK_PID_DIR)
    except Exception:
        pass

# ─── Pause Control ────────────────────────────────────────────────
PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PAUSED")

def _is_paused():
    """Check if bot is paused via PAUSED file."""
    return os.path.exists(PAUSE_FILE)

def _set_paused(paused=True):
    """Create or remove PAUSED file."""
    if paused:
        with open(PAUSE_FILE, "w") as f:
            f.write("paused")
        logger.info("Bot PAUSED")
        tg.send_message("⏸ <b>Bot PAUSED</b>")
    else:
        if os.path.exists(PAUSE_FILE):
            os.remove(PAUSE_FILE)
        logger.info("Bot RESUMED")
        tg.send_message("▶️ <b>Bot RESUMED</b>")

# ─── Daily Drawdown Limit ─────────────────────────────────────────
# Tracks the running intraday peak equity and pauses new entries once the
# day's drawdown (peak-to-trough equity, incl. floating P/L on open
# positions) reaches DAILY_DRAWDOWN_PCT % of the day's starting balance.
# Re-arms automatically at the UTC midnight boundary.
_dd_day_key = None          # YYYY-MM-DD (UTC) the tracker is armed for
_dd_start_balance = None    # account balance at arm time
_dd_peak_equity = None      # highest equity seen this day
_dd_triggered = None        # day key on which the limit fired


def _dd_today_key():
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _daily_drawdown_armed():
    """(Re)arm the daily drawdown tracker once per UTC day."""
    global _dd_day_key, _dd_start_balance, _dd_peak_equity, _dd_triggered
    today = _dd_today_key()
    if _dd_day_key != today:
        _dd_day_key = today
        acc = mt5c.get_account_info()
        _dd_start_balance = acc.balance if acc is not None else None
        _dd_peak_equity = acc.equity if acc is not None else None
        _dd_triggered = None
        logger.debug(
            f"Daily drawdown tracker armed for {today}: "
            f"start balance={_dd_start_balance:.2f}"
        )
    return True


def _daily_drawdown_triggered():
    """Return True if the day's equity drawdown has reached the limit and
    new entries must be paused. Also triggers a once-per-day Telegram notice."""
    global _dd_peak_equity, _dd_triggered
    if not config.DAILY_DRAWDOWN_ENABLED or config.DAILY_DRAWDOWN_PCT <= 0:
        return False
    if not _daily_drawdown_armed():
        return False
    today = _dd_today_key()

    acc = mt5c.get_account_info()
    if acc is None or _dd_start_balance is None or _dd_start_balance <= 0:
        return False
    current_equity = acc.equity

    # Once the limit has fired today, hold it until midnight UTC even if
    # equity later recovers (a -10% dip is a hard stop for the rest of the day).
    if _dd_triggered == today:
        return True

    # Track the running intraday equity peak.
    if current_equity > (_dd_peak_equity or current_equity):
        _dd_peak_equity = current_equity

    # Drawdown from the day's equity peak, as a % of the day's starting balance.
    if _dd_peak_equity is None:
        return False
    dd_pct = ((_dd_peak_equity - current_equity) / _dd_start_balance) * 100.0

    if dd_pct < config.DAILY_DRAWDOWN_PCT:
        return False

    # Limit reached — pause new entries for the rest of the day (once only).
    if _dd_triggered != today:
        _dd_triggered = today
        logger.warning(
            f"DAILY DRAWDOWN LIMIT HIT | day {today} | "
            f"{dd_pct:.1f}% (limit {config.DAILY_DRAWDOWN_PCT}%) | "
            f"equity {current_equity:.2f} from peak {_dd_peak_equity:.2f} | "
            f"new entries paused until midnight UTC"
        )
        try:
            tg.send_message(
                f"\u26d4 <b>DAILY DRAWDOWN LIMIT HIT</b>\n"
                f"Equity down {dd_pct:.1f}% today (limit "
                f"{config.DAILY_DRAWDOWN_PCT:.0f}%).\n"
                f"New entries paused until midnight UTC."
            )
        except Exception as e:
            logger.error(f"DD notify failed: {e}")
    return True


# ─── Market Hours ─────────────────────────────────────────────────
_market_paused = False

# Instruments that trade 24/7 (crypto). Their presence in SYMBOL_LIST
# keeps the bot alive on weekends / outside forex hours.
_CRYPTO_ALWAYS_ON = {"BTCUSD"}

def _is_market_open():
    """Check if any configured market is open.
    Forex: opens Sunday 22:00 UTC, closes Friday 22:00 UTC.
    Crypto in SYMBOL_LIST trades 24/7, so weekends stay live for them."""
    now = datetime.now(UTC)
    weekday = now.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun

    if any(s in _CRYPTO_ALWAYS_ON for s in config.SYMBOL_LIST):
        return True
    # Saturday: always closed
    if weekday == 5:
        return False
    # Sunday before 22:00 UTC: closed
    if weekday == 6 and now.hour < 22:
        return False
    # Friday after 22:00 UTC: closed
    if weekday == 4 and now.hour >= 22:
        return False
    return True

def _check_market_hours():
    """Auto-pause at market close, auto-resume at market open."""
    global _market_paused
    
    if _is_market_open():
        # Clean up stale PAUSED file from a previous session on startup
        if _is_paused() and os.path.exists(PAUSE_FILE):
            with open(PAUSE_FILE, "r") as f:
                content = f.read().strip()
            if content == "market_closed":
                os.remove(PAUSE_FILE)
                logger.info("Cleaned up stale market_closed pause file")
        if _market_paused:
            _market_paused = False
            if _is_paused():
                os.remove(PAUSE_FILE)
            logger.info("Market OPENED - Bot RESUMED")
            tg.send_message("🟢 <b>Market OPENED</b> - Bot resumed scanning")
        return True
    else:
        if not _market_paused:
            _market_paused = True
            with open(PAUSE_FILE, "w") as f:
                f.write("market_closed")
            logger.info("Market CLOSED - Bot PAUSED")
            tg.send_message("🔴 <b>Market CLOSED</b> - Bot paused until Sunday 22:00 UTC")
        return False

# ─── Logging Setup ────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE, mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("kingade_bot")

# ─── Graceful Shutdown ────────────────────────────────────────────
_running = True


def _shutdown_handler(signum, frame):
    global _running
    logger.info("Shutdown signal received, stopping...")
    _running = False


signal.signal(signal.SIGINT, _shutdown_handler)
signal.signal(signal.SIGTERM, _shutdown_handler)


# ─── Candle Close Tracking ────────────────────────────────────────
_last_candle_time = {}
_last_report_date = None
_last_weekly_report = None
_last_trade_time = {}  # cooldown tracking
TRADE_COOLDOWN_SECONDS = config.TRADE_COOLDOWN_SECONDS  # 0 = off, only open position blocks


def _is_new_candle(symbol, timeframe):
    """Check if a new candle has just closed for a symbol+timeframe."""
    rates = mt5c.get_ohlc(symbol, timeframe, 1)
    if rates is None or rates.empty:
        return False

    candle_time = rates.iloc[-1]["time"]
    key = f"{symbol}_{timeframe}"

    if key not in _last_candle_time:
        _last_candle_time[key] = candle_time
        return False

    if candle_time > _last_candle_time[key]:
        _last_candle_time[key] = candle_time
        return True

    return False


def _print_banner():
    rr = config.get_symbol_param("XAUUSD", "RR_RATIO", 2.5)
    print("=" * 60)
    print("  KINGADE SCALPER BOT")
    print("  EMA10/EMA100 Trend | Pattern+Fib Entry | Wick SL")
    print(f"  RR Ratio: 1:{rr} | Risk: {config.RISK_PERCENT}% of balance")
    print(f"  Max Positions: {config.MAX_POSITIONS}")
    print(f"  Trailing Stop: {config.USE_TRAILING_STOP} | Max Bars: {config.MAX_BARS_IN_TRADE}")
    print(f"  Scan Interval: {config.SCAN_INTERVAL_SECONDS}s")
    print("=" * 60)


def _tf_name(timeframe):
    tf_map = {
        1: "M1", 5: "M5", 15: "M15", 30: "M30",
        16385: "H1", 16388: "H4", 32769: "D1",
    }
    return tf_map.get(timeframe, f"TF{timeframe}")


def _check_daily_report():
    """Send daily report after market close (22:00 UTC on weekdays)."""
    global _last_report_date
    now = datetime.now(UTC)
    today = now.date()

    if _last_report_date == today:
        return

    # Send at 22:00 UTC (market close for XAUUSD) on weekdays
    if now.weekday() < 5 and now.hour == 22:
        try:
            daily_report.generate_and_send_daily_report()
            _last_report_date = today
            logger.info("Daily report sent successfully")
        except Exception as e:
            logger.error(f"Daily report error: {e}")
            tg.notify_error(f"Daily report error: {e}")


def _check_weekly_report():
    """Send weekly report on Friday after market close (22:00 UTC)."""
    global _last_weekly_report
    now = datetime.now(UTC)
    today = now.date()

    if _last_weekly_report == today:
        return

    # Send on Friday at 22:00 UTC (market close)
    if now.weekday() == 4 and now.hour == 22:
        try:
            daily_report.generate_and_send_weekly_report()
            _last_weekly_report = today
            logger.info("Weekly report sent successfully")
        except Exception as e:
            logger.error(f"Weekly report error: {e}")
            tg.notify_error(f"Weekly report error: {e}")


# ─── Main Loop ────────────────────────────────────────────────────
def main():
    _print_banner()

    # Ensure only one instance runs
    if not _acquire_lock():
        sys.exit(1)

    # Prompt for login if not configured
    login_setup.setup_login()

    # Initialize MT5
    if not mt5c.initialize():
        logger.error("Failed to initialize MT5. Is MetaTrader 5 running?")
        sys.exit(1)

    # Validate license
    if not license_manager.validate():
        logger.error("License validation failed. Bot will exit.")
        sys.exit(1)

    # Notify bot started
    tg.notify_bot_started()

    try:
        logger.info("Bot started. Scanning for Kingade setups...")
        scan_count = 0

        while _running:
            scan_count += 1

            # Poll Telegram command channel (e.g. /pause /resume /status).
            # Throttled internally; must run even while paused so /resume works.
            try:
                telegram_commands.poll()
            except Exception as e:
                logger.error(f"Telegram command poll error: {e}")

            # Check market hours (auto-pause at close, auto-resume at open)
            if not _check_market_hours():
                time.sleep(60)
                continue

            # Check pause state
            if _is_paused():
                time.sleep(5)
                continue

            logger.debug(f"--- Scan #{scan_count} ---")

            # Daily drawdown limit: compute the tracker state each scan. When
            # triggered, new entries are blocked (existing positions still
            # get managed/trailed below).
            dd_paused = _daily_drawdown_triggered()

            # Get all available symbols
            if config.AUTO_DISCOVER_SYMBOLS:
                symbols = mt5c.get_available_symbols()
            else:
                symbols = config.SYMBOL_LIST

            logger.debug(f"Scanning {len(symbols)} symbols")

            for symbol in symbols:
                for tf in config.get_symbol_timeframes(symbol):
                    try:
                        # Only process on new candle close
                        if not _is_new_candle(symbol, tf):
                            continue

                        tf_name = _tf_name(tf)
                        logger.info(f"New candle on {symbol} {tf_name}")

                        # Analyze for signals
                        signal_data = signal_engine.analyze_symbol(symbol, tf)
                        if signal_data is None:
                            continue

                        # Check if we already have a position
                        if trade_manager.has_existing_signal(symbol, tf):
                            logger.info(
                                f"Already have position on {symbol} {tf_name}, skipping"
                            )
                            continue

                        # Double-check position limits
                        if not trade_manager.can_open_trade(symbol):
                            logger.info(
                                f"Position limit reached for {symbol}, skipping"
                            )
                            continue

                        # Check cooldown between trades on same symbol
                        now = time.time()
                        if symbol in _last_trade_time:
                            elapsed = now - _last_trade_time[symbol]
                            if elapsed < TRADE_COOLDOWN_SECONDS:
                                remaining = int((TRADE_COOLDOWN_SECONDS - elapsed) / 60)
                                logger.debug(
                                    f"{symbol} {tf_name}: cooldown {remaining}min remaining, skipping"
                                )
                                continue

                        # ─── Signal Confirmation Dashboard ───────────
                        direction = signal_data["direction"].upper()
                        emoji = "\U0001F7E2" if direction == "BUY" else "\U0001F534"
                        sl_dist = abs(signal_data["entry_price"] - signal_data["sl"])
                        tp_txt, rr_txt = "OPEN", "1:inf"
                        if not config.get_symbol_param(
                                symbol, "USE_OPEN_RR", config.USE_OPEN_RR):
                            tp_dist = abs(signal_data["tp1"] - signal_data["entry_price"])
                            tp_txt = f"{tp_dist:.2f} pts"
                            rr_txt = f"1:{tp_dist / sl_dist:.2f}" if sl_dist > 0 else "1:0"

                        logger.info(
                            f"\n{'='*50}\n"
                            f"  {emoji} SIGNAL CONFIRMED: {symbol} {tf_name}\n"
                            f"{'='*50}\n"
                            f"  Direction:  {direction}\n"
                            f"  Entry:      {signal_data['entry_price']:.2f}\n"
                            f"  Stop Loss:  {signal_data['sl']:.2f} ({sl_dist:.2f} pts)\n"
                            f"  Take Profit:{tp_txt}\n"
                            f"  Risk:Reward: {rr_txt}\n"
                            f"  ATR(14):    {signal_data.get('atr', 0):.2f}\n"
                            f"  Swing High: {signal_data.get('swing_high', 0):.2f}\n"
                            f"  Swing Low:  {signal_data.get('swing_low', 0):.2f}\n"
                            f"{'='*50}"
                        )

                        # Execute (blocked when the daily drawdown limit was hit)
                        if dd_paused:
                            logger.info(
                                f"{symbol} {tf_name}: skipped entry "
                                f"(daily drawdown limit reached)"
                            )
                            continue
                        order_result = trade_manager.execute_signal(signal_data)

                        if order_result:
                            _last_trade_time[symbol] = time.time()
                            # Notify Telegram only after successful order
                            tg.notify_signal(signal_data)
                            tg.notify_trade_opened(signal_data, order_result)

                    except Exception as e:
                        logger.error(f"Error on {symbol}: {e}")

            # Manage open positions
            trade_manager.manage_open_positions()

            # Check for daily report
            _check_daily_report()

            # Check for weekly report
            _check_weekly_report()

            # Wait before next scan
            time.sleep(config.SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        _release_lock()
        mt5c.shutdown()
        logger.info("Bot shut down cleanly")


if __name__ == "__main__":
    main()
