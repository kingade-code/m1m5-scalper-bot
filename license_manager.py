"""Offline license key manager.

Key format: KNG-XXXX-XXXX-XXXX (alphanumeric, 3 groups of 4)
Validates: format + whitelist from valid_keys.json
Saves to: license.json (local file)
"""
import os
import json
import re
import time

LICENSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "license.json")
KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "valid_keys.json")
KEY_PATTERN = re.compile(r"^KNG-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


def _load_valid_keys():
    """Load valid keys from whitelist file."""
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r") as f:
                data = json.load(f)
            return set(data.get("keys", []))
        except (json.JSONDecodeError, IOError):
            pass
    return set()


def load_license():
    """Load license data from file."""
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_license(key, mt5_account):
    """Save license data to file."""
    data = {
        "license_key": key,
        "mt5_account": mt5_account,
        "activated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(LICENSE_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


def validate_key_format(key):
    """Validate license key format: KNG-XXXX-XXXX-XXXX"""
    if not key:
        return False, "License key is empty."
    key = key.strip().upper()
    if not KEY_PATTERN.match(key):
        return False, f"Invalid format. Expected: KNG-XXXX-XXXX-XXXX, Got: {key}"
    return True, key


def validate_key_whitelist(key):
    """Check if key exists in valid_keys.json whitelist."""
    valid_keys = _load_valid_keys()
    if not valid_keys:
        return False, "No valid keys found. Contact support."
    if key not in valid_keys:
        return False, "Invalid license key. Contact support."
    return True, "Key valid."


def validate():
    """Main validation function. Returns True if license is valid."""
    print("\n  LICENSE VALIDATION")

    # Load existing license
    lic_data = load_license()
    key = lic_data.get("license_key")
    account = lic_data.get("mt5_account")

    # Existing valid license
    if key and account:
        valid, msg = validate_key_whitelist(key)
        if valid:
            print(f"  License valid for account {account}.")
            return True
        else:
            print(f"  {msg}")
            print("  Please enter a valid license key.\n")

    # Prompt for new key
    print("  No valid license found.")
    print("  Enter your license key below.")
    print("  Format: KNG-XXXX-XXXX-XXXX\n")

    key = input("  License Key: ").strip().upper()

    # Validate format
    valid, result = validate_key_format(key)
    if not valid:
        print(f"  ERROR: {result}")
        return False
    key = result

    # Validate whitelist
    valid, msg = validate_key_whitelist(key)
    if not valid:
        print(f"  ERROR: {msg}")
        return False

    # Get MT5 account
    account = input("  MT5 Account Number: ").strip()
    if not account or not account.isdigit():
        print("  ERROR: Invalid MT5 account number.")
        return False

    # Save
    save_license(key, account)
    print(f"\n  License activated for account {account}.")
    print(f"  Key: {key}")
    return True


if __name__ == "__main__":
    validate()
