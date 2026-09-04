"""Resolve where CustomMacro keeps its state.

Historically every path in this project was relative ("data/macros.json"),
which resolves against the *current working directory*. Launched from a
shortcut, the Start Menu, or a PyInstaller bundle, CWD is not the repo root,
so the app silently started empty and wrote new state somewhere unexpected.

User data belongs in the per-user application data directory. This module
resolves it with no third-party dependency (the app ships as a frozen exe,
so every avoided dependency is bytes off the bundle) and migrates any legacy
./data directory on first run.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "CustomMacro"


def _platform_data_dir() -> Path:
    """The OS-conventional per-user data directory for this app."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    # XDG, with the spec-mandated fallback.
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def _bundle_root() -> Path:
    """Directory the application is running from, frozen or not."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Return the app data directory, creating it if needed.

    An override is honoured so the test suite can point at a tmp_path
    instead of polluting the developer's real profile.
    """
    override = os.environ.get("CUSTOMMACRO_DATA_DIR")
    target = Path(override) if override else _platform_data_dir()
    target.mkdir(parents=True, exist_ok=True)
    return target


def log_dir() -> Path:
    target = data_dir() / "logs"
    target.mkdir(parents=True, exist_ok=True)
    return target


def migrate_legacy_data() -> list[str]:
    """Copy state from the old ./data directory into the app data dir.

    Returns the names of the files migrated. Copies rather than moves, and
    never overwrites, so a failed migration is always recoverable by hand.
    """
    legacy = _bundle_root() / "data"
    if not legacy.is_dir():
        return []

    destination = data_dir()
    if legacy.resolve() == destination.resolve():
        return []

    migrated: list[str] = []
    for name in ("macros.json", "vault.json"):
        source = legacy / name
        target = destination / name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)
            migrated.append(name)
    return migrated
