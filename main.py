import os
import sys
import time
import signal
import logging
from datetime import datetime

import config
import mt5_connector as mt5c
import signal_engine
import trade_manager
import telegram_notifier as tg
import daily_report
import login_setup

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

# ─── Market Hours ─────────────────────────────────────────────────
_market_paused = False

def _is_market_open():
    """Check if forex market is open.
    Market opens Sunday 22:00 UTC, closes Friday 22:00 UTC."""
    now = datetime.utcnow()
    weekday = now.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
    
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
        logging.FileHandler(config.LOG_FILE, mode="a"),
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
    print("=" * 60)
    print("  KINGADE SCALPER BOT")
    print("  Entry Zone: 0.5 - 0.786 | ATR-based SL/TP")
    print(f"  Timeframes: {' | '.join(_tf_name(tf) for tf in config.TIMEFRAMES)}")
    print(f"  Risk Per Trade: {config.RISK_PERCENT}%")
    print(f"  Max Positions: {config.MAX_POSITIONS}")
    print(f"  Trailing Stop: {config.USE_TRAILING_STOP}")
    print(f"  Max Bars: {config.MAX_BARS_IN_TRADE}")
    print(f"  Magic Number: {config.MAGIC_NUMBER}")
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
    now = datetime.now()
    today = now.date()

    if _last_report_date == today:
        return

    # Send at 22:00 UTC (market close for XAUUSD) on weekdays
    if now.weekday() < 5 and now.hour == 22 and now.minute >= 0:
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
    now = datetime.now()
    today = now.date()

    if _last_weekly_report == today:
        return

    # Send on Friday at 22:00 UTC (market close)
    if now.weekday() == 4 and now.hour == 22 and now.minute >= 0:
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

    # Prompt for login if not configured
    login_setup.setup_login()

    # Initialize MT5
    if not mt5c.initialize():
        logger.error("Failed to initialize MT5. Is MetaTrader 5 running?")
        sys.exit(1)

    # Notify bot started
    # tg.notify_bot_started()

    try:
        logger.info("Bot started. Scanning for Kingade setups...")
        scan_count = 0

        while _running:
            scan_count += 1

            # Check market hours (auto-pause at close, auto-resume at open)
            if not _check_market_hours():
                time.sleep(60)
                continue

            # Check pause state
            if _is_paused():
                time.sleep(5)
                continue

            logger.debug(f"--- Scan #{scan_count} ---")

            # Get all available symbols
            if config.AUTO_DISCOVER_SYMBOLS:
                symbols = mt5c.get_available_symbols()
            else:
                symbols = config.SYMBOL_LIST

            logger.debug(f"Scanning {len(symbols)} symbols")

            for symbol in symbols:
                for tf in config.TIMEFRAMES:
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

                        # ─── Signal Confirmation Dashboard ───────────
                        direction = signal_data["direction"].upper()
                        emoji = "\U0001F7E2" if direction == "BUY" else "\U0001F534"
                        sl_dist = abs(signal_data["entry_price"] - signal_data["sl"])
                        tp_dist = abs(signal_data["tp1"] - signal_data["entry_price"])
                        rr_ratio = tp_dist / sl_dist if sl_dist > 0 else 0

                        logger.info(
                            f"\n{'='*50}\n"
                            f"  {emoji} SIGNAL CONFIRMED: {symbol} {tf_name}\n"
                            f"{'='*50}\n"
                            f"  Direction:  {direction}\n"
                            f"  Entry:      {signal_data['entry_price']:.2f}\n"
                            f"  Stop Loss:  {signal_data['sl']:.2f} ({sl_dist:.2f} pts)\n"
                            f"  Take Profit:{signal_data['tp1']:.2f} ({tp_dist:.2f} pts)\n"
                            f"  Risk:Reward: 1:{rr_ratio:.2f}\n"
                            f"  ATR(14):    {signal_data.get('atr', 0):.2f}\n"
                            f"  Swing High: {signal_data.get('swing_high', 0):.2f}\n"
                            f"  Swing Low:  {signal_data.get('swing_low', 0):.2f}\n"
                            f"{'='*50}"
                        )

                        # Notify Telegram
                        tg.notify_signal(signal_data)

                        # Execute
                        order_result = trade_manager.execute_signal(signal_data)

                        if order_result:
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
        mt5c.shutdown()
        logger.info("Bot shut down cleanly")


if __name__ == "__main__":
    main()
