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
3. Priority scheduling (higher runs first):
   - `ravel run --priority 10 "python3 path/to/script.py"`
4. DAG dependencies:
   - `ravel run --after <job_id> "python3 path/to/script.py"`
5. Memory tags for resource limits:
   - `ravel run --memory-tag large "python3 path/to/script.py"`
6. List queued and running jobs:
   - `ravel queue`
7. Live dashboard (watch running jobs):
   - `ravel dash`
   - Stays open until you exit (Ctrl+D or Ctrl+C)
   - Uses a full-screen terminal view (like vim)
8. Start the web UI:
   - `ravel web --host 127.0.0.1 --port 8000`
9. View recent jobs:
   - `ravel logs --limit 10`
   - `ravel logs --failed`
   - `ravel logs --passed`
   - `ravel logs --status queued,running,blocked`
10. Clear jobs:
   - `ravel clear` (clears queued jobs)
   - `ravel clear --all` (clears all jobs)
11. Stop a running job:
   - `ravel stop <job_id>`
12. Retry a job:
   - `ravel retry <job_id>`
13. Submit a batch file (Ravelfile or jobs.txt):
   - `ravel submit Ravelfile --no-wait`
   - `ravel submit jobs.txt --no-wait`
   - Each line is executed as-is via `/bin/bash -lc` (no re-quoting).
   - Ravelfile format:
     - `JOB <command>`
     - `SET PRIORITY <value>`, `SET GPUS <value>`, `SET MEMORY <value>`
     - Inline metadata: `JOB name=... priority=... gpus=... memory=... after=... -- <command>`
   - `after=` can reference `name=` entries or existing job IDs.
   - Relative paths resolve from the directory containing the batch file.
   - Heredocs are supported (lines are grouped until the heredoc terminator).
   - On Windows (PowerShell), commands run via `powershell -NoProfile -Command`.
14. Validate a Ravelfile/jobs file:
   - `ravel validate Ravelfile`

## Daemon Controls
1. Start the daemon:
   - `ravel daemon start`
2. Check daemon status:
   - `ravel daemon status`
   - `ravel daemon status --verbose`
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
4. `RAVEL_MAX_WORKERS`
   - Max concurrent jobs.
5. `RAVEL_MEMORY_LIMITS`
   - Comma-delimited limits for `--memory-tag` (example: `large=1,medium=2`).

## Troubleshooting
1. Daemon says running but jobs do not start:
   - Check GPU availability or set `RAVEL_NO_GPU=1` to test.
2. Nothing appears in `ravel dash`:
   - Verify the daemon is running and that the same `RAVEL_DB_PATH` is used.
3. Stuck jobs:
   - Stop and restart the daemon, then re-run the job.
