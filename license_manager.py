"""Offline license key manager with tier support.

Key formats:
  KNG-M-XXXX-XXXX-XXXX (Monthly - $99/month)
  KNG-A-XXXX-XXXX-XXXX (Annual - $499/year)
  KNG-L-XXXX-XXXX-XXXX (Lifetime - $999)

Validates: format + tier + whitelist from valid_keys.json
Saves to: license.json (local file)
"""
import os
import json
import re
import time
from datetime import datetime, timedelta

LICENSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "license.json")
KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "valid_keys.json")

# Key patterns for each tier
KEY_PATTERNS = {
    "monthly": re.compile(r"^KNG-M-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"),
    "annual": re.compile(r"^KNG-A-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"),
    "lifetime": re.compile(r"^KNG-L-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"),
}

# Tier durations (for monthly and annual)
TIER_DURATIONS = {
    "monthly": timedelta(days=30),
    "annual": timedelta(days=365),
    "lifetime": None,  # No expiration
}

TIER_NAMES = {
    "monthly": "Monthly ($99/month)",
    "annual": "Annual ($499/year)",
    "lifetime": "Lifetime ($999)",
}


def detect_tier(key):
    """Detect tier from key prefix."""
    if key.startswith("KNG-M-"):
        return "monthly"
    elif key.startswith("KNG-A-"):
        return "annual"
    elif key.startswith("KNG-L-"):
        return "lifetime"
    return None


def _load_valid_keys():
    """Load valid keys from whitelist file with tier info."""
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r") as f:
                data = json.load(f)
            # New format: dict with tier info
            if isinstance(data, dict) and not data.get("keys"):
                return data
            # Old format: {"keys": [...]}
            return {k: {"tier": detect_tier(k) or "lifetime", "active": True} 
                    for k in data.get("keys", [])}
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def load_license():
    """Load license data from file."""
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_license(key, mt5_account, tier):
    """Save license data to file with tier and expiration."""
    now = datetime.now()
    duration = TIER_DURATIONS.get(tier)
    
    data = {
        "license_key": key,
        "mt5_account": mt5_account,
        "tier": tier,
        "tier_name": TIER_NAMES.get(tier, "Unknown"),
        "activated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    if duration:
        expires_at = now + duration
        data["expires_at"] = expires_at.strftime("%Y-%m-%d %H:%M:%S")
        data["days_remaining"] = duration.days
    else:
        data["expires_at"] = None
        data["days_remaining"] = None
    
    with open(LICENSE_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


def check_expiration(lic_data):
    """Check if license has expired."""
    expires_at = lic_data.get("expires_at")
    if not expires_at:
        return True, "Lifetime license - no expiration."
    
    exp_date = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    
    if now > exp_date:
        days_expired = (now - exp_date).days
        return False, f"License expired {days_expired} day(s) ago. Please renew."
    
    days_remaining = (exp_date - now).days
    return True, f"{days_remaining} day(s) remaining."


def validate_key_format(key):
    """Validate license key format for any tier."""
    if not key:
        return False, "License key is empty.", None
    
    key = key.strip().upper()
    tier = detect_tier(key)
    
    if not tier:
        return False, f"Invalid format. Expected: KNG-M/A/L-XXXX-XXXX-XXXX, Got: {key}", None
    
    pattern = KEY_PATTERNS[tier]
    if not pattern.match(key):
        return False, f"Invalid {tier} key format.", None
    
    return True, key, tier


def validate_key_whitelist(key, tier):
    """Check if key exists in valid_keys.json whitelist with correct tier."""
    valid_keys = _load_valid_keys()
    if not valid_keys:
        return False, "No valid keys found. Contact support."
    
    key_data = valid_keys.get(key)
    if not key_data:
        return False, "Invalid license key. Contact support."
    
    # Check if key is active
    if not key_data.get("active", True):
        return False, "License key has been deactivated. Contact support."
    
    # Check tier match
    key_tier = key_data.get("tier")
    if key_tier and key_tier != tier:
        return False, f"Key is for {key_tier} tier, not {tier}. Contact support."
    
    return True, "Key valid."


def validate():
    """Main validation function. Returns True if license is valid."""
    print("\n" + "=" * 50)
    print("  KINGADE FOREX - LICENSE VALIDATION")
    print("=" * 50)

    # Load existing license
    lic_data = load_license()
    key = lic_data.get("license_key")
    account = lic_data.get("mt5_account")

    # Existing valid license
    if key and account:
        tier = detect_tier(key)
        
        # Check expiration
        valid_exp, exp_msg = check_expiration(lic_data)
        if not valid_exp:
            print(f"  {exp_msg}")
            print("  Please enter a new license key.\n")
        else:
            # Check whitelist
            valid, msg = validate_key_whitelist(key, tier)
            if valid:
                print(f"  License valid for account {account}.")
                print(f"  Tier: {TIER_NAMES.get(tier, 'Unknown')}")
                if lic_data.get("expires_at"):
                    print(f"  Expires: {lic_data['expires_at']}")
                    print(f"  {exp_msg}")
                else:
                    print(f"  {exp_msg}")
                return True
            else:
                print(f"  {msg}")
                print("  Please enter a valid license key.\n")

    # Prompt for new key
    print("  No valid license found.")
    print("  Enter your license key below.")
    print("  Formats:")
    print("    KNG-M-XXXX-XXXX-XXXX (Monthly - $99/month)")
    print("    KNG-A-XXXX-XXXX-XXXX (Annual - $499/year)")
    print("    KNG-L-XXXX-XXXX-XXXX (Lifetime - $999)\n")

    key = input("  License Key: ").strip().upper()

    # Validate format
    valid, result, tier = validate_key_format(key)
    if not valid:
        print(f"  ERROR: {result}")
        return False
    key = result

    # Validate whitelist
    valid, msg = validate_key_whitelist(key, tier)
    if not valid:
        print(f"  ERROR: {msg}")
        return False

    # Get MT5 account
    account = input("  MT5 Account Number: ").strip()
    if not account or not account.isdigit():
        print("  ERROR: Invalid MT5 account number.")
        return False

    # Save with tier info
    lic_data = save_license(key, account, tier)
    print(f"\n  License activated for account {account}.")
    print(f"  Key: {key}")
    print(f"  Tier: {TIER_NAMES.get(tier, 'Unknown')}")
    if lic_data.get("expires_at"):
        print(f"  Expires: {lic_data['expires_at']}")
    else:
        print(f"  Status: Lifetime (no expiration)")
    return True


def get_tier_info(key):
    """Get tier information for a key."""
    tier = detect_tier(key)
    if not tier:
        return None
    return {
        "tier": tier,
        "name": TIER_NAMES.get(tier),
        "duration": TIER_DURATIONS.get(tier),
    }


if __name__ == "__main__":
    validate()
