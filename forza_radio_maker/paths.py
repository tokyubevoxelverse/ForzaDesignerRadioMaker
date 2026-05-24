"""Filesystem helpers for projects and bundled resources."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def app_dir() -> Path:
    """Directory containing the running app (next to the EXE when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """Bundled read-only resources (PyInstaller unpacks these into _MEIPASS)."""
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / "forza_radio_maker" / "resources"
    return Path(__file__).resolve().parent / "resources"


def projects_root() -> Path:
    """Where generated radio-station projects live."""
    root = app_dir() / "stations"
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_dir(slug: str) -> Path:
    p = projects_root() / slug
    (p / "music").mkdir(parents=True, exist_ok=True)
    return p


def safe_slug(name: str) -> str:
    keep = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
    keep = keep.replace(" ", "_")
    return keep or "station"
