# Copyright (c) 2026 Kingade Forex. All rights reserved.
# Auto-updater module - checks GitHub for new versions and updates files.
import os
import sys
import json
import hashlib
import logging
import shutil
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

VERSION_URL = "https://raw.githubusercontent.com/kingade-code/m1m5-scalper-bot/main/version.json"
LOCAL_VERSION_FILE = "version.json"
BACKUP_DIR = "_backup"
PROTECTED_FILES = ["config.py", "license.json", "valid_keys.json"]


def get_local_version():
    try:
        with open(LOCAL_VERSION_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": "0.0.0", "files": {}}


def get_remote_version():
    try:
        resp = requests.get(VERSION_URL, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug(f"Update check failed: {e}")
    return None


def file_hash(filepath):
    try:
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except (FileNotFoundError, PermissionError):
        return None


def download_file(url, dest):
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            with open(dest, "w", encoding="utf-8", newline="\n") as f:
                f.write(resp.text)
            return True
    except Exception as e:
        logger.warning(f"Failed to download {url}: {e}")
    return False


def backup_file(filepath):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if os.path.exists(filepath):
        dest = os.path.join(BACKUP_DIR, os.path.basename(filepath))
        shutil.copy2(filepath, dest)


def check_and_update():
    local = get_local_version()
    local_ver = local.get("version", "0.0.0")
    local_files = local.get("files", {})

    remote = get_remote_version()
    if remote is None:
        return False

    remote_ver = remote.get("version", "0.0.0")
    remote_files = remote.get("files", {})
    changelog = remote.get("changelog", "")

    if remote_ver <= local_ver:
        logger.info(f"Already up to date (v{local_ver})")
        return False

    logger.info(f"Update available: v{local_ver} -> v{remote_ver}")
    logger.info(f"Changelog: {changelog}")

    updated = 0
    failed = 0

    for filename, url in remote_files.items():
        if filename in PROTECTED_FILES:
            continue

        local_md5 = file_hash(filename)
        remote_md5 = local_files.get(filename, {}).get("md5", "")

        if local_md5 == remote_md5 and os.path.exists(filename):
            continue

        backup_file(filename)
        logger.info(f"Updating {filename}...")

        if download_file(url, filename):
            new_md5 = file_hash(filename)
            if filename not in local_files:
                local_files[filename] = {}
            local_files[filename]["md5"] = new_md5
            updated += 1
            logger.info(f"Updated {filename}")
        else:
            failed += 1
            logger.warning(f"Failed to update {filename}")

    if updated > 0:
        local["version"] = remote_ver
        local["files"] = local_files
        local["changelog"] = changelog
        with open(LOCAL_VERSION_FILE, "w") as f:
            json.dump(local, f, indent=2)
        logger.info(f"Update complete: {updated} files updated, {failed} failed")
        return True
    else:
        logger.info("No files needed updating")
        return False


def run_update_check():
    try:
        updated = check_and_update()
        if updated:
            logger.info("Restarting bot with new files...")
            python = sys.executable
            os.execl(python, python, *sys.argv)
    except Exception as e:
        logger.warning(f"Auto-update error (non-fatal): {e}")
