"""Station metadata + logo handling.

A "station" is a directory under stations/<slug>/ that holds:
  - station.json   : name, source type, logo path, song list
  - logo.png       : square cover art used by the FH6 Radio Tool UI
  - music/*.wav    : the playable songs in playback order

The FH6 Radio Tool consumes the music/ folder as its "music folder"; the
logo/name are surfaced in this app and copied to the project for any
downstream tooling that wants them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal, Optional

from PIL import Image

SourceType = Literal["spotify", "youtube", "custom"]

LOGO_SIZE = 512  # square, big enough for any in-game / UI display

DEFAULT_LOGOS = {
    "spotify": "default_spotify.png",
    "youtube": "default_youtube.png",
    "custom":  "default_custom.png",
}


@dataclass
class Song:
    title: str
    artist: str = ""
    source_url: str = ""
    wav_path: str = ""   # relative to project dir

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StationMeta:
    name: str
    source: SourceType
    slug: str
    logo_path: str = ""   # relative to project dir, e.g. "logo.png"
    songs: list[Song] = field(default_factory=list)
    source_url: str = ""  # original playlist URL for spotify/youtube

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source": self.source,
            "slug": self.slug,
            "logo_path": self.logo_path,
            "source_url": self.source_url,
            "songs": [s.to_dict() for s in self.songs],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StationMeta":
        return cls(
            name=d["name"],
            source=d["source"],
            slug=d["slug"],
            logo_path=d.get("logo_path", ""),
            source_url=d.get("source_url", ""),
            songs=[Song(**s) for s in d.get("songs", [])],
        )


def save_meta(project_dir: Path, meta: StationMeta) -> None:
    (project_dir / "station.json").write_text(
        json.dumps(meta.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_meta(project_dir: Path) -> Optional[StationMeta]:
    f = project_dir / "station.json"
    if not f.exists():
        return None
    return StationMeta.from_dict(json.loads(f.read_text(encoding="utf-8")))


def install_logo(project_dir: Path, source_image: Path) -> Path:
    """Copy + normalize a user-picked image into the project as logo.png.

    Resizes to LOGO_SIZE x LOGO_SIZE, centered on a transparent canvas so
    non-square sources don't get stretched.
    """
    out = project_dir / "logo.png"
    img = Image.open(source_image).convert("RGBA")
    img.thumbnail((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
    canvas = Image.new("RGBA", (LOGO_SIZE, LOGO_SIZE), (0, 0, 0, 0))
    x = (LOGO_SIZE - img.width) // 2
    y = (LOGO_SIZE - img.height) // 2
    canvas.paste(img, (x, y), img)
    canvas.save(out, format="PNG")
    return out


def make_placeholder_logo(project_dir: Path, name: str, source: SourceType) -> Path:
    """Generate a simple branded placeholder if the user did not pick one."""
    from PIL import ImageDraw, ImageFont
    bg = {
        "spotify": (29, 185, 84),    # Spotify green
        "youtube": (255, 0, 0),      # YouTube red
        "custom":  (45, 55, 72),     # neutral slate
    }[source]
    img = Image.new("RGBA", (LOGO_SIZE, LOGO_SIZE), bg + (255,))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 64)
    except OSError:
        font = ImageFont.load_default()
    text = (name or source.title())[:18]
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((LOGO_SIZE - w) / 2, (LOGO_SIZE - h) / 2 - bbox[1]),
              text, font=font, fill=(255, 255, 255, 255))
    out = project_dir / "logo.png"
    img.save(out, format="PNG")
    return out
