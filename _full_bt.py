import sys, os
sys.path.insert(0, os.getcwd())
import MetaTrader5 as mt5
import backtest as bt
from report import build_pdf

bt.BACKTEST_SYMBOLS = ["XAUUSD", "GBPUSD", "AUDUSD"]
bt.BACKTEST_TIMEFRAMES = [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5]
bt.BACKTEST_MONTHS = 6

result = bt.run_backtest()
pdf_path = "M1M5_Full_Backtest_Report.pdf"
build_pdf(result, pdf_path)
print(f"PDF saved: {pdf_path}")
