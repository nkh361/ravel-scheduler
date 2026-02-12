"""Cross-platform build helper for Ravel.

Usage:
  python build.py
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmds = [
        [sys.executable, "-m", "pip", "install", "-e", "."],
        [sys.executable, "-m", "build"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
