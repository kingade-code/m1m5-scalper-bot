# Copyright (c) 2026 Kingade Forex. All rights reserved.
# Standalone zip-swap updater for the KingadeBot.
#
# Runs on your OTHER PC to bring a copy of the bot up to date WITHOUT a full
# reinstall. It downloads (or uses) the latest KingadeBot_Download.zip, swaps
# the changed runtime files in place, and PRESERVES your personal files
# (config.py, license.json, valid_keys.json) so your settings and license
# are never overwritten.
#
# Stdlib ONLY - no pip installs, no GitHub token required.
#
# Usage:
#   python update_kingade.py                 # prompt for zip path/URL
#   python update_kingade.py "path\to.zip"   # use a local zip
#   python update_kingade.py "https://..."   # download from a URL

import os
import sys
import json
import shutil
import hashlib
import tempfile
import zipfile
import urllib.request
from pathlib import Path

# Files that carry the user's personal state - NEVER overwrite them.
PROTECTED_FILES = ["config.py", "license.json", "valid_keys.json"]

# Files that may exist in the bot folder but are runtime/analysis artifacts
# and should NOT be copied from the zip (keep the current/local ones).
# Effectively anything not in the zip's runtime set is left alone.
ZIP_SOURCE = "KingadeBot_Download.zip"
BACKUP_DIR = "_backup"
INSTALL_DIR = Path(__file__).resolve().parent


def log(msg):
    print("[update] " + msg)


def md5(path):
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (FileNotFoundError, PermissionError):
        return None


def read_version():
    try:
        with open(INSTALL_DIR / "version.json", "r") as f:
            return json.load(f).get("version", "0.0.0")
    except (FileNotFoundError, json.JSONDecodeError):
        return "0.0.0"


def resolve_payload(arg=None):
    """Return a local zip path. If `arg` looks like a URL, download it."""
    if not arg:
        arg = input("Path or URL to the KingadeBot zip (or Enter for default): ").strip()
    if arg.lower().startswith("http://") or arg.lower().startswith("https://"):
        log(f"Downloading {arg} ...")
        tmp = tempfile.mktemp(suffix=".zip")
        urllib.request.urlretrieve(arg, tmp)
        return tmp
    if arg:
        return arg
    default = INSTALL_DIR / ZIP_SOURCE
    if default.exists():
        return str(default)
    return None


def extract_zip(zip_path):
    tmp = tempfile.mkdtemp(prefix="kingade_update_")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(tmp)
    return tmp, zip_path


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    current_ver = read_version()
    log(f"Existing bot version: {current_ver}")

    zip_path = resolve_payload(arg)
    if not zip_path or not os.path.isfile(zip_path):
        log("ERROR: No update zip available. Put KingadeBot_Download.zip next to "
            "this script, or pass a path / URL.")
        return 1

    staging, _ = extract_zip(zip_path)
    log(f"Extracted update to {staging}")

    os.makedirs(INSTALL_DIR / BACKUP_DIR, exist_ok=True)

    changed = []
    added = []
    skipped = []

    for item in sorted(os.listdir(staging)):
        src = os.path.join(staging, item)
        if not os.path.isfile(src):
            continue
        if item in PROTECTED_FILES:
            skipped.append(item)
            log(f"Preserved (not overwritten): {item}")
            continue
        dest = INSTALL_DIR / item
        src_md5 = md5(src)
        if dest.exists() and md5(dest) == src_md5:
            log(f"Unchanged, skipping: {item}")
            continue
        # back up the current local copy before overwriting
        existed_before = dest.exists()
        if existed_before:
            shutil.copy2(dest, INSTALL_DIR / BACKUP_DIR / item)
        shutil.copy2(src, dest)
        if not dest.exists() or md5(dest) != src_md5:
            log(f"COPY FAILED: {item}")
            skipped.append(item)
            continue
        if existed_before:
            changed.append(item)
        else:
            added.append(item)
        log(f"Updated: {item}")

    log("---- Summary ----")
    log(f"Changed: {len(changed)}   Added: {len(added)}   Preserved/Skipped: {len(skipped)}")
    if changed:
        log("Changed files: " + ", ".join(changed))
    if added:
        log("New files: " + ", ".join(added))

    shutil.rmtree(staging, ignore_errors=True)
    log("Done. If the bot was running, restart it to load the new files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())