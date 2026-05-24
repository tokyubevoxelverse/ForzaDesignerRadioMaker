"""Spotify playlist source via the standalone yt-dlp.exe.

Spotify itself does not let third-party apps download playable audio, so
we do this in two steps:
  1. Read the playlist's track list (title + artist) without auth, via
     the open.spotify.com embed JSON. No API key needed.
  2. For each track, search YouTube via yt-dlp's `ytsearch1:` extractor
     for "<title> <artist>" and download the top match as audio.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

import requests

from ..audio import convert_to_wav
from ..station import Song
from ..ytdlp_runtime import (
    ensure_ytdlp, ffmpeg_location, subprocess_kwargs,
)

ProgressCb = Callable[[int, int, str], None]


def _safe_filename(s: str) -> str:
    keep = "".join(c if c.isalnum() or c in " -_." else "_" for c in s).strip()
    return keep[:120] or "track"


def _extract_playlist_id(url: str) -> Optional[str]:
    m = re.search(r"playlist[/:]([a-zA-Z0-9]+)", url)
    return m.group(1) if m else None


def fetch_playlist_tracks(url: str) -> list[dict]:
    """Return [{title, artist}, ...] for a public Spotify playlist URL.

    Uses the open.spotify.com embed page which exposes the playlist's track
    list as JSON in a __NEXT_DATA__ script tag. No API auth required.
    """
    pid = _extract_playlist_id(url)
    if not pid:
        raise ValueError("Could not find a Spotify playlist ID in that URL.")

    embed_url = f"https://open.spotify.com/embed/playlist/{pid}"
    resp = requests.get(embed_url, headers={
        "User-Agent": "Mozilla/5.0 (ForzaHorizonRadioMaker)",
    }, timeout=20)
    resp.raise_for_status()
    html = resp.text

    m = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html, re.DOTALL,
    )
    if not m:
        raise RuntimeError(
            "Spotify embed page did not contain track data. "
            "Make sure the playlist is public."
        )
    data = json.loads(m.group(1))

    candidates: list[dict] = []

    def walk(obj):
        if isinstance(obj, dict):
            tracks = obj.get("trackList") or obj.get("tracks")
            if isinstance(tracks, list) and tracks and isinstance(tracks[0], dict) \
                    and ("title" in tracks[0] or "name" in tracks[0]):
                candidates.extend(tracks)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)

    out: list[dict] = []
    for t in candidates:
        title = t.get("title") or t.get("name") or ""
        artists_field = t.get("subtitle") or t.get("artists") or t.get("artist") or ""
        if isinstance(artists_field, list):
            artist = ", ".join(
                a.get("name", "") if isinstance(a, dict) else str(a)
                for a in artists_field
            )
        else:
            artist = str(artists_field)
        if title:
            out.append({"title": title.strip(), "artist": artist.strip()})

    seen = set()
    dedup = []
    for t in out:
        key = (t["title"], t["artist"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(t)
    return dedup


def _ytsearch_download(
    ytdlp: Path,
    query: str,
    out_path: Path,
) -> Path:
    out_template = str(out_path.with_suffix(".%(ext)s"))
    ff = ffmpeg_location()
    cmd = [
        str(ytdlp),
        "-f", "bestaudio/best",
        "-o", out_template,
        "--no-playlist",
        "--no-warnings",
        "--ignore-config",
        "--default-search", "ytsearch1",
        "--print", "after_move:filepath",
        f"ytsearch1:{query}",
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
        if line and Path(line).exists():
            final_path = line
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp exit {proc.returncode} for: {query}")
    if not final_path:
        cands = list(out_path.parent.glob(out_path.stem + ".*"))
        if not cands:
            raise FileNotFoundError(f"yt-dlp produced no file for: {query}")
        final_path = str(cands[0])
    return Path(final_path)


def download_tracks(
    tracks: list[dict],
    music_dir: Path,
    *,
    progress: Optional[ProgressCb] = None,
    sample_rate: int = 48000,
) -> list[Song]:
    """For each {title, artist} pair, ytsearch the top match and convert to WAV."""
    ytdlp = ensure_ytdlp(progress)
    music_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = music_dir / "_dl_tmp"
    tmp_dir.mkdir(exist_ok=True)

    total = len(tracks)
    songs: list[Song] = []
    for i, t in enumerate(tracks, 1):
        query = f"{t['title']} {t['artist']}".strip()
        if progress:
            progress(i - 1, total, f"Searching {i}/{total}: {query}")
        try:
            downloaded = _ytsearch_download(
                ytdlp, query, tmp_dir / f"track_{i:03d}",
            )
            wav_name = f"{i:02d}_{_safe_filename(t['title'])}.wav"
            wav_path = music_dir / wav_name
            convert_to_wav(downloaded, wav_path, sample_rate=sample_rate)
            try:
                downloaded.unlink()
            except OSError:
                pass
            songs.append(Song(
                title=t["title"],
                artist=t["artist"],
                source_url="",
                wav_path=f"music/{wav_name}",
            ))
        except Exception as exc:
            if progress:
                progress(i, total, f"FAILED {query}: {exc}")
            continue

    try:
        for p in tmp_dir.glob("*"):
            try: p.unlink()
            except OSError: pass
        tmp_dir.rmdir()
    except OSError:
        pass
    if progress:
        progress(total, total, f"Done. {len(songs)}/{total} tracks ready.")
    return songs
