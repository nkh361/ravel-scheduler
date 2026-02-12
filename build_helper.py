"""Cross-platform build helper for Ravel.

Usage:
  python build_helper.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if not os.environ.get("VIRTUAL_ENV"):
        venv_path = Path(".venv")
        if not venv_path.exists():
            result = subprocess.run([sys.executable, "-m", "venv", ".venv"])
            if result.returncode != 0:
                return result.returncode
        python = str(venv_path / ("Scripts" if os.name == "nt" else "bin") / "python")
    else:
        python = sys.executable

    cmds = [
        [python, "-m", "pip", "install", "--upgrade", "pip"],
    ]

    if os.environ.get("RAVEL_BUILD_DEPS") == "1":
        cmds.append([python, "-m", "pip", "install", "-e", "."])
    else:
        cmds.append([python, "-m", "pip", "install", "-e", ".", "--no-deps"])

    cmds.append([python, "-m", "build"])

    for cmd in cmds:
        result = subprocess.run(cmd)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
