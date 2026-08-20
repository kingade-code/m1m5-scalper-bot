import MetaTrader5 as mt5

# ─── MT5 Connection ───────────────────────────────────────────────
MT5_PATH = None
MT5_LOGIN = None
MT5_PASSWORD = None
MT5_SERVER = None
MT5_TIMEOUT = 10_000

# ─── Timeframes ───────────────────────────────────────────────────
TIMEFRAMES = [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5]

# ─── Swing Detection ──────────────────────────────────────────────
SWING_LOOKBACK = 80  # Shorter lookback for scalping
SWING_STRENGTH = 2  # Lower = more swing points = more signals

# ─── Fibonacci Settings ───────────────────────────────────────────
FIB_ENTRY_LOW = 0.5
FIB_ENTRY_HIGH = 0.786

# ─── Risk Management ─────────────────────────────────────────────
RISK_PERCENT = 4.0  # Conservative — 50% less risk, same 77.3% WR
MAX_POSITIONS = 10
MAX_POSITIONS_PER_SYMBOL = 1
MAGIC_NUMBER = 777777
SLIPPAGE = 3

# ─── Symbol Filter ────────────────────────────────────────────────
AUTO_DISCOVER_SYMBOLS = False
SYMBOL_LIST = ["XAUUSD", "GBPUSD", "AUDUSD"]

# ─── Confirmation ─────────────────────────────────────────────────
REQUIRE_CONFIRMATION = True
CONFIRMATION_CANDLES = 1

# ─── Trend Filter ─────────────────────────────────────────────────
USE_TREND_FILTER = True
TREND_EMA_PERIOD = 30

# ─── Momentum Filter ──────────────────────────────────────────────
USE_MOMENTUM_FILTER = True
RSI_PERIOD = 14
RSI_OVERSOLD = 55  # Relaxed RSI filter
RSI_OVERBOUGHT = 45  # Relaxed RSI filter
MIN_BODY_RATIO = 0.10  # Lower bar for more entries

# ─── ATR Stop Loss ───────────────────────────────────────────────
USE_ATR_SL = True
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.0  # Tight SL for scalping
MIN_STOP_DISTANCE = 5.0  # Lower for EURUSD/GBPUSD, XAUUSD will skip tight signals

# ─── Scalper TP ───────────────────────────────────────────────────
ATR_TP_MULTIPLIER = 1.5  # TP = entry +/- ATR * multiplier (tighter than fib ext)

# ─── Trailing Stop ────────────────────────────────────────────────
USE_TRAILING_STOP = True
TRAILING_START_ATR = 0.75  # Start trailing after 0.75*ATR profit (+19% avg win, 71.9% WR)
TRAILING_STEP_ATR = 0.2  # Trail by 0.2*ATR behind price (+4% WR, +12% PF vs 0.3)

# ─── Max Bars in Trade ────────────────────────────────────────────
MAX_BARS_IN_TRADE = 15  # Very fast exits for scalping

# ─── Logging ──────────────────────────────────────────────────────
LOG_LEVEL = "DEBUG"
LOG_FILE = "m1m5_scalper.log"

# ─── Telegram ─────────────────────────────────────────────────────
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = "8803542513:AAF4TtMmcWIHAj88xNxsjHH8NYxqHMUfwag"
TELEGRAM_CHAT_IDS = [6412335897, -1002127450559]  # Private chat + KINGADE FOREX group

# ─── Scan Interval ────────────────────────────────────────────────
SCAN_INTERVAL_SECONDS = 10
