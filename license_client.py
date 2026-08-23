"""Kingade Scalper Bot - License Client
Validates license key on bot startup.

Usage in main.py:
    import license_client
    if not license_client.validate():
        sys.exit(1)
"""

import os
import json
import time
import requests
import MetaTrader5 as mt5
from datetime import datetime, timedelta

# License server URL
LICENSE_SERVER = os.getenv("LICENSE_SERVER", "https://kingade-license.onrender.com")

# Cache file for offline grace period
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".license_cache")
LICENSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "license.json")

# Offline grace period (24 hours)
GRACE_PERIOD_HOURS = 24


def get_mt5_account():
    """Get current MT5 account number and server."""
    info = mt5.account_info()
    if info:
        return info.login, info.server
    return None, None


def load_license():
    """Load license key from file."""
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_license(data):
    """Save license data to file."""
    with open(LICENSE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def save_cache(data):
    """Save validation result for offline grace period."""
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)


def load_cache():
    """Load cached validation result."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def validate_online(license_key, mt5_account):
    """Validate license with server."""
    try:
        response = requests.post(
            f"{LICENSE_SERVER}/validate",
            json={
                "license_key": license_key,
                "mt5_account": mt5_account
            },
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return {"valid": False, "message": f"Server error: {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"valid": False, "message": f"Connection error: {str(e)}"}


def activate_online(license_key, mt5_account, mt5_server, email=None):
    """Activate license with server."""
    try:
        response = requests.post(
            f"{LICENSE_SERVER}/activate",
            json={
                "license_key": license_key,
                "mt5_account": mt5_account,
                "mt5_server": mt5_server,
                "email": email
            },
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return {"valid": False, "message": f"Server error: {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"valid": False, "message": f"Connection error: {str(e)}"}


def validate():
    """Main validation function. Returns True if license is valid."""
    print("\n" + "=" * 60)
    print("  LICENSE VALIDATION")
    print("=" * 60)
    
    # Load license
    lic_data = load_license()
    license_key = lic_data.get("license_key")
    
    if not license_key:
        print("  No license key found.")
        print("  Enter your license key below:")
        print("  (Contact @kingadefx on Telegram to purchase)\n")
        license_key = input("  License Key: ").strip()
        
        if not license_key:
            print("\n  ERROR: License key required!")
            print("  Purchase at: https://sellix.io/kingadebot")
            print("=" * 60 + "\n")
            return False
        
        # Save license key
        lic_data["license_key"] = license_key
        save_license(lic_data)
    
    # Get MT5 account
    mt5_account, mt5_server = get_mt5_account()
    if not mt5_account:
        print("  WARNING: MT5 not connected. Will validate when connected.")
        # Try offline validation
        cache = load_cache()
        if cache.get("license_key") == license_key:
            cached_time = datetime.fromisoformat(cache.get("validated_at", "2000-01-01"))
            if datetime.now() - cached_time < timedelta(hours=GRACE_PERIOD_HOURS):
                print(f"  Using cached validation (expires in {GRACE_PERIOD_HOURS}h)")
                print("=" * 60 + "\n")
                return True
        print("  Please connect to MT5 first.")
        print("=" * 60 + "\n")
        return False
    
    # Try online validation
    print(f"  Validating license for MT5 account {mt5_account}...")
    result = validate_online(license_key, mt5_account)
    
    if result.get("valid"):
        print(f"  License valid! Package: {result.get('package', 'pro')}")
        
        # Try activation if not yet activated
        if not lic_data.get("activated"):
            print("  Activating license...")
            activation = activate_online(license_key, mt5_account, mt5_server)
            if activation.get("valid"):
                lic_data["activated"] = True
                lic_data["package"] = result.get("package", "pro")
                lic_data["activated_at"] = datetime.now().isoformat()
                save_license(lic_data)
                print("  License activated!")
        
        # Cache for offline use
        save_cache({
            "license_key": license_key,
            "mt5_account": mt5_account,
            "validated_at": datetime.now().isoformat(),
            "valid": True
        })
        
        print("=" * 60 + "\n")
        return True
    else:
        message = result.get("message", "Unknown error")
        print(f"  License invalid: {message}")
        
        # Check offline grace period
        cache = load_cache()
        if cache.get("license_key") == license_key and cache.get("valid"):
            cached_time = datetime.fromisoformat(cache.get("validated_at", "2000-01-01"))
            remaining = timedelta(hours=GRACE_PERIOD_HOURS) - (datetime.now() - cached_time)
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                print(f"  Offline grace period: {hours}h {minutes}m remaining")
                print("=" * 60 + "\n")
                return True
        
        print("\n  To purchase a license:")
        print("  Telegram: @kingadefx")
        print("  Website: https://sellix.io/kingadebot")
        print("=" * 60 + "\n")
        return False


if __name__ == "__main__":
    # Test validation
    if validate():
        print("License validation passed!")
    else:
        print("License validation failed!")
