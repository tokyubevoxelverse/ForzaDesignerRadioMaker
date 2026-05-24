"""PyInstaller entry point.

PyInstaller runs the target script as ``__main__`` standalone (not as a
package member), so the package-relative imports in ``forza_radio_maker/
__main__.py`` fail when frozen. This launcher uses absolute imports so
it works both as a script and when bundled into the EXE. The package
``__main__.py`` is still used for ``python -m forza_radio_maker``.
"""
from __future__ import annotations

import sys


def main() -> int:
    from forza_radio_maker.app import run
    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
