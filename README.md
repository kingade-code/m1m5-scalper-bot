# Kingade Scalper Bot

Automated XAUUSD scalping bot using Fibonacci retracement (0.618–0.786) on M30 timeframe.

## Features

- Fibonacci entry zone detection with ATR-based SL/TP
- Trailing stop management
- H1 trend filter (EMA 50)
- RSI + body ratio momentum filter
- Telegram notifications (signals, trades, daily reports)
- Auto-start on Windows login
- Daily PDF + PPTX reports at market close

## Backtest Results (2018–2026)

| Metric | Value |
|--------|-------|
| Trades | 563 |
| Win Rate | 78.2% |
| Profit Factor | 3.63 |
| Sharpe Ratio | 8.05 |
| Max Drawdown | 11.6% |

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Configure `config.py` with your MT5 account and Telegram bot token
3. Run: `python main.py`

## Auto-Start

A startup script is installed at `shell:startup` that launches MT5 and the bot on login.

## License

Private - Kingade FX
