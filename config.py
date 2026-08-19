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
RISK_PERCENT = 8.0  # Aggressive for $1000/mo target on $1k
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
TREND_EMA_PERIOD = 50

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
TRAILING_START_ATR = 0.5  # Start trailing after price moves 0.5*ATR in profit
TRAILING_STEP_ATR = 0.3  # Trail by 0.3*ATR behind price

# ─── Max Bars in Trade ────────────────────────────────────────────
MAX_BARS_IN_TRADE = 15  # Very fast exits for scalping

# ─── Logging ──────────────────────────────────────────────────────
LOG_LEVEL = "DEBUG"
LOG_FILE = "m1m5_scalper.log"

# ─── Telegram ─────────────────────────────────────────────────────
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = "8803542513:AAF4TtMmcWIHAj88xNxsjHH8NYxqHMUfwag"
TELEGRAM_CHAT_IDS = [6412335897]  # Private chat + add group ID here

# ─── Scan Interval ────────────────────────────────────────────────
SCAN_INTERVAL_SECONDS = 10
