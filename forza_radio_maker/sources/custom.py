"""Custom local-files source.

User picks any number of local audio files; we copy/convert each into
the project's music/ folder as 16-bit PCM WAV. mp3/m4a/flac/opus all get
normalized to a single FH6-compatible format.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Optional

from ..audio import convert_to_wav
from ..station import Song

ProgressCb = Callable[[int, int, str], None]

SUPPORTED_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}


def _safe_filename(s: str) -> str:
    keep = "".join(c if c.isalnum() or c in " -_." else "_" for c in s).strip()
    return keep[:120] or "track"


def _read_tags(path: Path) -> tuple[str, str]:
    """Best-effort title/artist extraction from file tags, else stem fallback."""
    try:
        from mutagen import File as MFile
        m = MFile(str(path), easy=True)
        if m is not None:
            title = (m.get("title") or [path.stem])[0]
            artist = (m.get("artist") or [""])[0]
            return title, artist
    except Exception:
        pass
    return path.stem, ""


def import_files(
    files: Iterable[Path],
    music_dir: Path,
    *,
    progress: Optional[ProgressCb] = None,
    sample_rate: int = 48000,
) -> list[Song]:
    files = [Path(f) for f in files]
    total = len(files)
    music_dir.mkdir(parents=True, exist_ok=True)

    songs: list[Song] = []
    for i, src in enumerate(files, 1):
        if progress:
            progress(i - 1, total, f"Converting {i}/{total}: {src.name}")
        try:
            title, artist = _read_tags(src)
            wav_name = f"{i:02d}_{_safe_filename(title)}.wav"
            wav_path = music_dir / wav_name
            convert_to_wav(src, wav_path, sample_rate=sample_rate)
            songs.append(Song(
                title=title,
                artist=artist,
                source_url=str(src),
                wav_path=f"music/{wav_name}",
            ))
        except Exception as exc:
            if progress:
                progress(i, total, f"FAILED {src.name}: {exc}")
            continue
    if progress:
        progress(total, total, f"Done. {len(songs)}/{total} tracks ready.")
    return songs
