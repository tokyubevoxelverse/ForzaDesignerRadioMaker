"""YouTube playlist / video source via the standalone yt-dlp.exe.

Uses the cached yt-dlp binary installed by ``ytdlp_runtime`` rather than the
Python module, so the bundled EXE stays small and yt-dlp can be updated
independently of the app.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable, Iterable, Optional

from ..audio import convert_to_wav
from ..station import Song
from ..ytdlp_runtime import (
    ensure_ytdlp, ffmpeg_location, subprocess_kwargs,
)

ProgressCb = Callable[[int, int, str], None]


def _safe_filename(s: str) -> str:
    keep = "".join(c if c.isalnum() or c in " -_." else "_" for c in s).strip()
    return keep[:120] or "track"


def fetch_playlist_entries(url: str, progress: Optional[ProgressCb] = None) -> list[dict]:
    """Return [{id, title, webpage_url}, ...] for a playlist or a single video."""
    ytdlp = ensure_ytdlp(progress)
    cmd = [
        str(ytdlp),
        "--flat-playlist",
        "-J",                 # single JSON object
        "--no-warnings",
        "--ignore-config",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, **subprocess_kwargs())
    if proc.returncode != 0:
        raise RuntimeError(
            f"yt-dlp metadata fetch failed:\n{(proc.stderr or '').strip()[-2000:]}"
        )
    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"yt-dlp returned invalid JSON: {exc}") from exc

    entries = info.get("entries") if isinstance(info, dict) else None
    if entries:
        return [e for e in entries if e]
    # Single video
    if isinstance(info, dict) and info.get("id"):
        return [info]
    return []


def _download_one(
    ytdlp: Path,
    watch_url: str,
    out_path: Path,
    progress_line_cb: Optional[Callable[[str], None]] = None,
) -> Path:
    """Download bestaudio for a single URL to a deterministic path.

    yt-dlp picks the container extension itself; we use the `--print
    after_move:filepath` trick to learn the final path it wrote to.
    """
    out_template = str(out_path.with_suffix(".%(ext)s"))
    ff = ffmpeg_location()
    cmd = [
        str(ytdlp),
        "-f", "bestaudio/best",
        "-o", out_template,
        "--no-playlist",
        "--no-warnings",
        "--ignore-config",
        "--print", "after_move:filepath",
        "--no-simulate",
        watch_url,
    ]
    if ff:
        cmd[-1:-1] = ["--ffmpeg-location", ff]

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, **subprocess_kwargs(),
    )
    final_path: Optional[str] = None
    assert proc.stdout is not None
    for raw_line in proc.stdout:
        line = raw_line.rstrip()
        if not line:
            continue
        # The --print line is just the path; any line that exists on disk wins.
        if Path(line).exists():
            final_path = line
        elif progress_line_cb:
            progress_line_cb(line)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp exit {proc.returncode} for {watch_url}")
    if not final_path:
        # Fallback: glob for files matching the template stem.
        cands = list(out_path.parent.glob(out_path.stem + ".*"))
        if not cands:
            raise FileNotFoundError(f"yt-dlp produced no file for {watch_url}")
        final_path = str(cands[0])
    return Path(final_path)


def download_entries(
    entries: Iterable[dict],
    music_dir: Path,
    *,
    progress: Optional[ProgressCb] = None,
    sample_rate: int = 48000,
) -> list[Song]:
    """Download each entry, convert to WAV, return Song records.

    Individual failures are reported via progress but don't abort the batch.
    """
    ytdlp = ensure_ytdlp(progress)
    entries = list(entries)
    total = len(entries)
    music_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = music_dir / "_dl_tmp"
    tmp_dir.mkdir(exist_ok=True)

    songs: list[Song] = []
    for i, entry in enumerate(entries, 1):
        video_id = entry.get("id") or entry.get("url")
        if not video_id:
            continue
        watch_url = entry.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"
        title = entry.get("title") or str(video_id)

        if progress:
            progress(i - 1, total, f"Downloading {i}/{total}: {title}")

        try:
            downloaded = _download_one(
                ytdlp, watch_url, tmp_dir / f"track_{i:03d}",
            )
            wav_name = f"{i:02d}_{_safe_filename(title)}.wav"
            wav_path = music_dir / wav_name
            convert_to_wav(downloaded, wav_path, sample_rate=sample_rate)
            try:
                downloaded.unlink()
            except OSError:
                pass
            songs.append(Song(
                title=title,
                artist=str(entry.get("uploader") or entry.get("channel") or ""),
                source_url=watch_url,
                wav_path=f"music/{wav_name}",
            ))
        except Exception as exc:
            if progress:
                progress(i, total, f"FAILED {title}: {exc}")
            continue

    try:
        # Best-effort tmp cleanup; ignore leftovers from failed downloads.
        for p in tmp_dir.glob("*"):
            try: p.unlink()
            except OSError: pass
        tmp_dir.rmdir()
    except OSError:
        pass

    if progress:
        progress(total, total, f"Done. {len(songs)}/{total} tracks ready.")
    return songs
