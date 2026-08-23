# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
import MetaTrader5 as mt5
import backtest as bt
from report import build_pdf

bt.BACKTEST_SYMBOLS = ["XAUUSD", "GBPUSD", "AUDUSD"]
bt.BACKTEST_TIMEFRAMES = [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5]
bt.BACKTEST_MONTHS = 6

result = bt.run_backtest()
build_pdf(result, "M1M5_Scalper_Report.pdf")
print(f"M1-M5 PDF saved")
