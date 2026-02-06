# Ravel Usage Guide

This guide explains how to install and use Ravel from the CLI, including common flags and daemon controls.

## Install
1. Create and activate a virtual environment (recommended):
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install in editable mode:
   - `pip install -e .`

## Core Commands
1. Run a job:
   - `ravel run "python3 path/to/script.py"`
2. Enqueue without waiting for completion:
   - `ravel run --no-wait "python3 path/to/script.py"`
3. List queued and running jobs:
   - `ravel queue`
4. Live dashboard (watch running jobs):
   - `ravel dash`

## Daemon Controls
1. Start the daemon:
   - `ravel daemon start`
2. Check daemon status:
   - `ravel daemon status`
3. Stop the daemon:
   - `ravel daemon stop`

## Job Execution Model
1. Jobs are queued in a shared SQLite database so any terminal can observe them.
2. A daemon process picks jobs from the queue, assigns GPUs, and runs them.
3. Output is stored in the database and printed when you run without `--no-wait`.

## Configuration
Ravel is configured by environment variables.

1. `RAVEL_STATE_DIR`
   - Directory for state files (defaults to `~/.ravel`).
2. `RAVEL_DB_PATH`
   - SQLite database path (defaults to `~/.ravel/ravel.db`).
3. `RAVEL_NO_GPU`
   - If `1`, bypass GPU checks (useful on CPU-only machines).

## Troubleshooting
1. Daemon says running but jobs do not start:
   - Check GPU availability or set `RAVEL_NO_GPU=1` to test.
2. Nothing appears in `ravel dash`:
   - Verify the daemon is running and that the same `RAVEL_DB_PATH` is used.
3. Stuck jobs:
   - Stop and restart the daemon, then re-run the job.
