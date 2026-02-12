$ErrorActionPreference = 'Stop'

if (-not $env:VIRTUAL_ENV) {
  if (Test-Path ".venv") {
    . .venv\\Scripts\\Activate.ps1
  } else {
    python -m venv .venv
    . .venv\\Scripts\\Activate.ps1
  }
}

python -m pip install --upgrade pip

if ($env:RAVEL_BUILD_DEPS -eq "1") {
  python -m pip install -e .
} else {
  python -m pip install -e . --no-deps
}

python -m build
