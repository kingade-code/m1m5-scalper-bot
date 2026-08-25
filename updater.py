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

GITHUB_REPO = "kingade-code/m1m5-scalper-bot"
GITHUB_TOKEN = "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"
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
        headers = {}
        if GITHUB_TOKEN and GITHUB_TOKEN != "ghp_":
            headers["Authorization"] = f"token {GITHUB_TOKEN}"
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/version.json"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            import base64
            data = resp.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return json.loads(content)
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
        headers = {}
        if GITHUB_TOKEN and GITHUB_TOKEN != "ghp_":
            headers["Authorization"] = f"token {GITHUB_TOKEN}"
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            import base64
            data = resp.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            with open(dest, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
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

        local_entry = local_files.get(filename, {})
        if isinstance(local_entry, str):
            local_entry = {}
        local_md5 = file_hash(filename)
        remote_md5 = local_entry.get("md5", "")

        if local_md5 == remote_md5 and os.path.exists(filename):
            continue

        backup_file(filename)
        logger.info(f"Updating {filename}...")

        if download_file(url, filename):
            new_md5 = file_hash(filename)
            if filename not in local_files or isinstance(local_files[filename], str):
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
