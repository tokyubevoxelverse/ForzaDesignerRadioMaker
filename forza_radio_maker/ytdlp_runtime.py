"""Manage a user-side yt-dlp.exe install.

The app does NOT bundle yt-dlp. Instead, on the first Spotify/YouTube build,
we download the official standalone `yt-dlp.exe` from the GitHub release
"latest" tag and cache it at:

    %LOCALAPPDATA%\\ForzaHorizonRadioMaker\\bin\\yt-dlp.exe

This keeps the bundled EXE small and lets yt-dlp stay current without
requiring users to reinstall the whole app every time YouTube changes.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Callable, Optional

import requests

ProgressCb = Callable[[int, int, str], None]  # done, total, message

YTDLP_LATEST_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

# Stale-after duration for the auto-update check. We don't want to hit GitHub
# on every launch, but a yt-dlp from a month ago is asking for trouble.
UPDATE_CHECK_AFTER_SECONDS = 7 * 24 * 3600  # 7 days


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    p = Path(base) / "ForzaHorizonRadioMaker"
    p.mkdir(parents=True, exist_ok=True)
    return p


def bin_dir() -> Path:
    p = app_data_dir() / "bin"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ytdlp_path() -> Path:
    return bin_dir() / "yt-dlp.exe"


def is_installed() -> bool:
    p = ytdlp_path()
    return p.exists() and p.stat().st_size > 1_000_000  # sanity: >1MB


def _download(url: str, dest: Path, progress: Optional[ProgressCb]) -> None:
    """Stream a download with optional progress callback."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=60, allow_redirects=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        last_pct = -1
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                if progress and total > 0:
                    # Throttle progress signals to whole-percent changes so we
                    # don't flood the UI thread with thousands of updates.
                    pct = done * 100 // total
                    if pct != last_pct:
                        last_pct = pct
                        progress(done, total, f"Downloading yt-dlp.exe… {pct}%")
                elif progress:
                    progress(done, 0, f"Downloading yt-dlp.exe… {done // 1024} KB")
    tmp.replace(dest)


def ensure_ytdlp(progress: Optional[ProgressCb] = None) -> Path:
    """Return path to yt-dlp.exe, downloading if missing.

    Does NOT auto-update if already present; call ``update_if_stale`` for that.
    """
    path = ytdlp_path()
    if is_installed():
        return path
    if progress:
        progress(0, 0, "yt-dlp not found on this device — downloading the latest release…")
    _download(YTDLP_LATEST_URL, path, progress)
    # Record install time so update_if_stale can decide whether to re-check.
    (bin_dir() / "ytdlp.stamp").write_text(str(int(time.time())))
    if progress:
        progress(1, 1, f"yt-dlp installed at {path}")
    return path


def update_if_stale(progress: Optional[ProgressCb] = None) -> Path:
    """Re-download yt-dlp if the local copy is older than the staleness window.

    Failures are non-fatal — we fall back to the existing copy.
    """
    path = ensure_ytdlp(progress)
    stamp_file = bin_dir() / "ytdlp.stamp"
    try:
        last = int(stamp_file.read_text()) if stamp_file.exists() else 0
    except ValueError:
        last = 0
    if time.time() - last < UPDATE_CHECK_AFTER_SECONDS:
        return path
    try:
        if progress:
            progress(0, 0, "Checking for a newer yt-dlp…")
        _download(YTDLP_LATEST_URL, path, progress)
        stamp_file.write_text(str(int(time.time())))
    except Exception as exc:
        if progress:
            progress(0, 0, f"Update check failed ({exc}); keeping existing yt-dlp.")
    return path


def ffmpeg_location() -> str:
    """Path to the ffmpeg binary bundled by imageio-ffmpeg."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""


def subprocess_kwargs() -> dict:
    """Common kwargs for subprocess calls — hides the console window on Windows."""
    kw: dict = {}
    if sys.platform == "win32":
        # CREATE_NO_WINDOW so the yt-dlp child doesn't pop a console flash
        # when the parent is a --windowed PyInstaller build.
        kw["creationflags"] = 0x08000000
    return kw
