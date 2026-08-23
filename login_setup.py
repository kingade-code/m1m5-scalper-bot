"""Login setup helper for Kingade Scalper Bot.
Auto-detects existing MT5 account. No prompts needed.
"""
import os
import config


def setup_login():
    """Auto-detect MT5 account. Returns True always — MT5 handles connection."""
    if config.MT5_LOGIN and config.MT5_PASSWORD and config.MT5_SERVER:
        print(f"  Using saved credentials: {config.MT5_LOGIN} @ {config.MT5_SERVER}")
    else:
        print("  No credentials in config.py — using existing MT5 login")
    return True
