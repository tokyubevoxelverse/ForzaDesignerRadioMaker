from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .theme import FULL_QSS
from .ui.main_window import MainWindow


def run(argv: list[str]) -> int:
    app = QApplication(argv)
    app.setStyleSheet(FULL_QSS)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run(sys.argv))
