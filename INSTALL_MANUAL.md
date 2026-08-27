# Kingade Scalper Bot
## Installation & User Manual v2.1.0

**XAUUSD Gold M1/M5 Scalping Bot** — fully automated with Telegram monitoring.

---

## 1. System Requirements

| Item | Requirement |
|------|-------------|
| Operating System | Windows 10 / 11 (64-bit) |
| Python | 3.10 – 3.12 (64-bit) |
| MetaTrader 5 | Latest version from your broker (Exness) |
| Account | Exness live or demo account with XAUUSD |
| Internet | Required for MT5 + Telegram |

> **IMPORTANT:** Python must be installed BEFORE MetaTrader 5, and both must be the same bitness (64-bit). Always check **"Add Python to PATH"** during Python installation.

---

## 2. Step-by-Step Installation

### Step 1 — Install Python
1. Download Python 3.11 from https://www.python.org/downloads/
2. Run the installer
3. **CHECK** the box: `Add Python to PATH`
4. Click **Install Now**

### Step 2 — Install MetaTrader 5
1. Download MT5 from your broker (https://www.exness.com)
2. Install and log in with your trading account
3. If you don't have an Exness account yet, register at:
   `https://one.exnesstrack.net/a/0fpwztsr9d`

### Step 3 — Prepare MT5
1. Open **MetaTrader 5** and log in
2. Enable **Algo Trading**:
   - Tools → Options → **Expert Advisors** tab
   - Check ✅ `Allow algorithmic trading`
3. Make sure **XAUUSD** is in your Market Watch:
   - Right-click Market Watch → Symbols → find **XAUUSD**
   - If hidden, enable it (it's sometimes under a "metals" filter)
4. Leave MT5 **running** in the background (do not close it)

### Step 4 — Install the Bot
1. Download `KingadeBot_Download.zip` and **unzip** to any folder (e.g. `C:\KingadeBot\`)
2. Double-click **`INSTALL.bat`**
   - This installs all required packages automatically
   - It also creates the `reports` folder and adds **auto-start on login**
3. Alternatively, manually install packages:
   ```
   pip install MetaTrader5 pandas numpy reportlab python-pptx requests
   ```

### Step 5 — Run the Bot
1. With MT5 still open, double-click **`start_bot.bat`**
2. A console window opens — this is the bot, **do not close it**
3. The bot will:
   - Auto-detect your MT5 account, OR ask for
     **Login (account number)**, **Password**, **Server**
     (You get these from your broker — e.g. broker server `Exness-MT5Trial9`)
   - Start a **free 3-day trial**, OR ask for your **license key**
   - Begin scanning XAUUSD automatically

---

## 3. How the Bot Works

| Setting | Value |
|---------|-------|
| Symbol | XAUUSD (Gold) |
| Timeframes | M1 + M5 |
| Entry | Hammer / Engulfing candlestick patterns |
| Trend filter | EMA 10 vs EMA 100 |
| Stop Loss | 5 pips beyond previous bar wick |
| Take Profit | 1:4.0 risk:reward |
| Trailing stop | ATR-based (0.3x start, 0.1x step) |
| Risk per trade | 4% (max $20) |
| Max lot | 0.10 |
| Max positions | 1 |
| Cooldown | 10 min between trades |
| Force close | After 15 bars |

---

## 4. Telegram Notifications

The bot sends real-time alerts to **@kingadefx_bot**:
- 🟢/🔴 Signal detected
- ✅ Trade opened (with entry/SL/TP)
- 💰/💸 Trade closed (win/loss)
- 📊 Daily report (PDF + PPTX)
- 🚀 Bot start / pause notifications

No setup needed — it works automatically.

---

## 5. Daily Reports

Every trading day after market close at 22:00 UTC, the bot sends:
- Summary message (trades, wins/losses, daily P/L, balance)
- **PDF report** with full trade log
- **PPTX report** with charts

Weekly reports are sent **every Friday**.
Reports also save to the `reports\` folder locally.

---

## 6. Pausing / Stopping the Bot

**Temporarily pause** — create an empty file named `PAUSED` in the bot folder.
The bot stops trading but keeps running. Delete the file to resume.

**Full stop** — close the bot console window.

**Disable auto-start** — delete `KingadeScalperBot.bat` from:
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`

---

## 7. License

| Tier | Price | Duration |
|------|-------|----------|
| Monthly | $99/month | 30 days |
| Annual | $499/year | 365 days |
| Lifetime | $999 | Unlimited |

- First **3 days are free** (trial) — no key required
- Keys look like: `KNG-M-XXXX-XXXX-XXXX`
- Purchase / activate: contact **@KingAdeFx** on Telegram
- One key works on one MT5 account

---

## 8. Troubleshooting

| Problem | Fix |
|---------|-----|
| `MetaTrader5 not found` on install | Install Python 3.10–3.12 (not 3.13+), 64-bit only |
| Bot says "MT5 not running" | Open MT5 and log in first |
| "Algo trading disabled" | Tools → Options → Expert Advisors → allow algorithmic trading |
| No XAUUSD signals | Make sure XAUUSD is visible in Market Watch |
| Order rejected on Exness | Nothing to do — bot auto-uses FOK filling mode |
| Bot closes instantly | Run `start_bot.bat` as **right-click → Run as administrator** |
| Bad gateway / API errors | Check internet connection |

---

## 9. Support

- **Email:** kingade.fx@gmail.com
- **Telegram:** @KingAdeFx
- **Brand:** Kingade Forex

&copy; 2026 Kingade Forex. All rights reserved.
This software is licensed intellectual property. Unauthorized copying, modification, distribution, or use is strictly prohibited.