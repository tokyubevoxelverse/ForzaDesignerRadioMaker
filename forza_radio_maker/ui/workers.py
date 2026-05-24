"""Qt worker threads so long-running downloads don't freeze the UI."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal


class BuildWorker(QObject):
    """Runs a build_fn(progress_callback) -> result in a worker thread."""
    progress = Signal(int, int, str)  # done, total, message
    finished = Signal(object)         # result on success
    failed = Signal(str)              # error message

    def __init__(self, build_fn: Callable[[Callable[[int, int, str], None]], object]):
        super().__init__()
        self._build_fn = build_fn

    def run(self):
        def cb(done: int, total: int, msg: str):
            self.progress.emit(int(done), int(total), str(msg))
        try:
            result = self._build_fn(cb)
        except Exception as exc:  # surface to UI
            import traceback
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")
            return
        self.finished.emit(result)
