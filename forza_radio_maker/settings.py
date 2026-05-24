"""Tiny JSON-backed settings store kept in %LOCALAPPDATA%.

Currently just remembers the FH6 Radio Tool launcher path so the user only
has to point at it once.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ytdlp_runtime import app_data_dir


def _settings_file() -> Path:
    return app_data_dir() / "settings.json"


def load() -> dict:
    f = _settings_file()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(data: dict) -> None:
    _settings_file().write_text(
        json.dumps(data, indent=2), encoding="utf-8",
    )


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def set_(key: str, value: Any) -> None:
    data = load()
    data[key] = value
    save(data)
