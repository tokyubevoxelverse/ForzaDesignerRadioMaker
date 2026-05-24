"""Audio conversion helpers.

FH6 Radio Tool consumes 16-bit PCM WAVs. We use the ffmpeg binary that
ships with imageio-ffmpeg so the EXE has no external dependency.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        # Fall back to system ffmpeg if available; otherwise error at call time.
        return shutil.which("ffmpeg") or "ffmpeg"


def convert_to_wav(src: Path, dst: Path, *, sample_rate: int = 48000) -> Path:
    """Convert any audio file (mp3/m4a/opus/wav/etc.) to 16-bit stereo PCM WAV.

    FH6 expects 48 kHz stereo PCM16 for radio tracks, matching the original
    extracted assets.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _ffmpeg_exe(),
        "-y",
        "-i", str(src),
        "-vn",
        "-ac", "2",
        "-ar", str(sample_rate),
        "-sample_fmt", "s16",
        "-f", "wav",
        str(dst),
    ]
    # capture stderr so a failed convert surfaces in the UI log instead of a
    # silent missing-file later on.
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed for {src.name} (exit {proc.returncode}):\n"
            + (proc.stderr or "").strip()[-2000:]
        )
    return dst


def probe_duration(path: Path) -> Optional[float]:
    """Return audio duration in seconds, or None if probe fails."""
    try:
        from mutagen import File as MFile
        m = MFile(str(path))
        if m is not None and m.info is not None:
            return float(m.info.length)
    except Exception:
        return None
    return None
