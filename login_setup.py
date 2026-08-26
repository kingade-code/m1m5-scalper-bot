# Copyright (c) 2026 Kingade Forex. All rights reserved.
# This software is licensed intellectual property.
# Unauthorized copying, modification, distribution, or use is strictly prohibited.
# A valid license key (KNG-XXXX-XXXX-XXXX) is required to run this bot.
# Purchase at: https://sellix.io/kingadebot
"""Login setup helper for Kingade Scalper Bot.
Auto-detects existing MT5 account or prompts for credentials on first run.
"""
import os
import json
import MetaTrader5 as mt5
import config

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mt5_credentials.json")


def _load_credentials():
    """Load saved credentials from file."""
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    try:
        with open(CREDENTIALS_FILE, "r") as f:
            data = json.load(f)
        if data.get("login") and data.get("password") and data.get("server"):
            return data
    except Exception:
        pass
    return None


def _save_credentials(login, password, server):
    """Save credentials to file."""
    data = {"login": int(login), "password": password, "server": server}
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Credentials saved to {CREDENTIALS_FILE}")


def setup_login():
    """Setup MT5 login. Flow:
    1. Try config.py values (if set)
    2. Try saved credentials file
    3. Try auto-detect (connect to running MT5)
    4. Prompt user for credentials
    """
    # Step 1: Check config.py
    if config.MT5_LOGIN and config.MT5_PASSWORD and config.MT5_SERVER:
        print(f"  Using config.py credentials: {config.MT5_LOGIN} @ {config.MT5_SERVER}")
        return True

    # Step 2: Check saved credentials
    saved = _load_credentials()
    if saved:
        print(f"  Using saved credentials: {saved['login']} @ {saved['server']}")
        config.MT5_LOGIN = saved["login"]
        config.MT5_PASSWORD = saved["password"]
        config.MT5_SERVER = saved["server"]
        return True

    # Step 3: Try auto-detect (MT5 already running with a logged-in account)
    print("  No saved credentials. Trying to connect to running MT5...")
    if mt5.initialize():
        info = mt5.account_info()
        if info:
            print(f"  Auto-detected: {info.login} @ {info.server}")
            config.MT5_LOGIN = info.login
            config.MT5_PASSWORD = ""  # Already connected, no password needed
            config.MT5_SERVER = info.server
            # Save for next time (skip password since we're already connected)
            _save_credentials(info.login, "", info.server)
            return True
        mt5.shutdown()

    # Step 4: Prompt user
    print("\n" + "=" * 50)
    print("  MT5 LOGIN REQUIRED")
    print("=" * 50)
    print("  Enter your MT5 credentials to connect.")
    print("  These will be saved locally for future runs.\n")

    login = input("  Login (account number): ").strip()
    if not login:
        print("  Error: Login is required")
        return False

    password = input("  Password: ").strip()
    if not password:
        print("  Error: Password is required")
        return False

    server = input("  Server (e.g., Exness-MT5Trial9): ").strip()
    if not server:
        print("  Error: Server is required")
        return False

    # Save credentials
    _save_credentials(login, password, server)

    # Set config
    config.MT5_LOGIN = int(login)
    config.MT5_PASSWORD = password
    config.MT5_SERVER = server

    print(f"\n  Credentials saved. Connecting to {server}...")
    return True
