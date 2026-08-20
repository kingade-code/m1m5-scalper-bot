import MetaTrader5 as mt5
import backtest as bt
from report import build_pdf

bt.BACKTEST_SYMBOLS = ["XAUUSD", "GBPUSD", "AUDUSD"]
bt.BACKTEST_TIMEFRAMES = [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5]
bt.BACKTEST_MONTHS = 6

result = bt.run_backtest()
build_pdf(result, "M1M5_Scalper_Report.pdf")
print(f"M1-M5 PDF saved")
