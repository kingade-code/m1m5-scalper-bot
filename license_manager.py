"""Offline license key manager.

Key format: KNG-XXXX-XXXX-XXXX (alphanumeric, 3 groups of 4)
Validates: format + MT5 account number
Saves to: license.json (local file)
"""
import os
import json
import re
import hashlib
import time

LICENSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "license.json")
KEY_PATTERN = re.compile(r"^KNG-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


def _hash_key(key, account):
    """Generate validation hash from key + MT5 account."""
    raw = f"{key}-{account}-kingade-2026"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


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
        "hash": _hash_key(key, mt5_account),
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


def validate():
    """Main validation function. Returns True if license is valid."""
    print("\n  LICENSE VALIDATION")

    # Load existing license
    lic_data = load_license()
    key = lic_data.get("license_key")
    account = lic_data.get("mt5_account")

    # Existing valid license
    if key and lic_data.get("hash"):
        expected_hash = _hash_key(key, account)
        if lic_data["hash"] == expected_hash:
            print(f"  License valid for account {account}.")
            return True
        else:
            print("  License file corrupted. Please re-enter your key.")

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
