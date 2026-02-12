#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ -d ".venv" ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  else
    python3 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
fi

python -m pip install --upgrade pip

if [[ "${RAVEL_BUILD_DEPS:-0}" == "1" ]]; then
  python -m pip install -e .
else
  python -m pip install -e . --no-deps
fi

python -m build
