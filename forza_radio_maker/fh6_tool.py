"""Locate and launch the external FH6 Radio Tool.

The FH6 Radio Tool is a separate program. We try to find it automatically in
common install locations (Downloads, Documents, Desktop, %ProgramFiles%) and
remember the path in settings so the user only confirms it once.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional

from . import settings
from .paths import resource_dir
from .ytdlp_runtime import app_data_dir

LAUNCHER_NAMES = (
    "run_tool.bat",
    "FH6RadioTool.exe",
)

# Top-level folder names we look for the tool inside. Match anything that
# starts with "FH6" so versioned/renamed copies still get picked up.
FOLDER_HINTS = ("FH6_Radio_tool", "FH6RadioTool", "FH6_Radio")

SETTING_KEY = "fh6_tool_path"


def _candidate_roots() -> list[Path]:
    home = Path.home()
    roots = [
        home / "Downloads",
        home / "Documents",
        home / "Desktop",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    ]
    return [r for r in roots if r.exists()]


def _find_launcher_in(folder: Path) -> Optional[Path]:
    # Direct hit
    for name in LAUNCHER_NAMES:
        p = folder / name
        if p.exists():
            return p
    # One level deeper (FH6_Radio_tool-master\FH6_Radio_tool-master\run_tool.bat)
    for name in LAUNCHER_NAMES:
        for hit in folder.glob(f"*/{name}"):
            return hit
        for hit in folder.glob(f"*/*/{name}"):
            return hit
    return None


def autodetect() -> Optional[Path]:
    """Search common locations for the FH6 Radio Tool launcher."""
    for root in _candidate_roots():
        try:
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                low = child.name.lower()
                if not any(h.lower() in low for h in FOLDER_HINTS):
                    continue
                hit = _find_launcher_in(child)
                if hit:
                    return hit
        except (PermissionError, OSError):
            continue
    return None


def resolve() -> Optional[Path]:
    """Saved path first, then autodetect. Returns None if not found."""
    saved = settings.get(SETTING_KEY)
    if saved:
        p = Path(saved)
        if p.exists():
            return p
    found = autodetect()
    if found:
        remember(found)
    return found


def remember(path: Path) -> None:
    settings.set_(SETTING_KEY, str(path))


def state_db_path(launcher: Path) -> Path:
    """Where the FH6 Radio Tool keeps its SQLite settings."""
    return launcher.parent / "work" / "fh6_radio_tool_v2.sqlite3"


def _ensure_state_db_schema(db_path: Path) -> None:
    """Create just the app_settings table if the DB doesn't exist yet.

    The full FH6 Radio Tool schema has many tables, but for setting a single
    pre-launch value we only need app_settings. The tool creates all other
    tables on its own first launch.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)


def set_state_setting(launcher: Path, key: str, value: object) -> None:
    """Write a setting into the FH6 Radio Tool's SQLite before it launches.

    Their StateStore stores values as JSON, so we match that encoding.
    Safe to call when the tool is not running; if it's already running this
    write will not affect the in-memory copy.
    """
    db = state_db_path(launcher)
    _ensure_state_db_schema(db)
    from datetime import datetime
    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings(key,value,updated_at) VALUES(?,?,?)",
            (key, json.dumps(value, ensure_ascii=False),
             datetime.utcnow().isoformat()),
        )


def get_state_setting(launcher: Path, key: str, default: object = None) -> object:
    db = state_db_path(launcher)
    if not db.exists():
        return default
    try:
        with sqlite3.connect(str(db)) as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key=?", (key,)
            ).fetchone()
    except sqlite3.DatabaseError:
        return default
    if not row:
        return default
    try:
        return json.loads(row[0])
    except Exception:
        return default


def fmod_tool_configured(launcher: Path) -> bool:
    """True if the FH6 Radio Tool already knows where Fmod Bank Tools lives."""
    val = get_state_setting(launcher, "fmod_tool", "")
    return bool(val) and Path(str(val)).exists()


FMOD_BANK_TOOLS_ZIP_NAME = "Fmod_Bank_Tools.zip"
FMOD_BANK_TOOLS_EXE_NAME = "Fmod_Bank_Tools.exe"


def fmod_bank_tools_dir() -> Path:
    """Where the bundled Fmod Bank Tools gets extracted to on first use."""
    return app_data_dir() / "fmod_bank_tools"


def fmod_bank_tools_exe() -> Path:
    return fmod_bank_tools_dir() / FMOD_BANK_TOOLS_EXE_NAME


def ensure_fmod_bank_tools() -> Optional[Path]:
    """Extract the bundled Fmod Bank Tools zip on first use, return the exe.

    The zip ships inside our app resources so users do not have to download
    a separate dependency. Returns None if the bundle is missing (e.g. when
    running from a dev checkout where the zip wasn't placed in resources/).
    """
    exe = fmod_bank_tools_exe()
    if exe.exists():
        return exe

    zip_path = resource_dir() / FMOD_BANK_TOOLS_ZIP_NAME
    if not zip_path.exists():
        return None

    target = fmod_bank_tools_dir()
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target)
    return exe if exe.exists() else None


def launch(path: Path) -> None:
    """Start the FH6 Radio Tool in its own working directory.

    For .bat we use cmd /c start so the batch detaches from us cleanly; for
    .exe we Popen directly so children don't inherit our console (if any).
    """
    cwd = str(path.parent)
    if path.suffix.lower() == ".bat":
        # `start "" "<bat>"` gives the batch its own window and lets us return.
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", str(path)],
            cwd=cwd,
            creationflags=0x00000010 if sys.platform == "win32" else 0,  # CREATE_NEW_CONSOLE
        )
    else:
        subprocess.Popen([str(path)], cwd=cwd)
