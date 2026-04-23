# System Documentation

This document describes how Ravel works internally and how to contribute safely.

## Architecture Overview
Ravel is a lightweight local scheduler with three main components:

1. CLI (`ravel/cli.py`)
   - Entry point for commands like `ravel run`, `ravel queue`, `ravel dash`, and daemon controls.
2. Daemon (`ravel/daemon.py`)
   - Detached background process that pulls jobs from the queue and runs them.
3. Store (`ravel/store.py`)
   - SQLite-backed job store that enables cross-terminal visibility.

## Job Lifecycle
1. `ravel run` enqueues a job in SQLite.
2. The daemon periodically:
   - Selects the next queued job.
   - Checks GPU availability.
   - Atomically claims the job (marks it as running).
   - Executes the command, writing stdout and stderr live to `~/.ravel/logs/<job_id>.log`.
   - Stores the full output in the database when the process exits.
3. The job finishes with `done` or `failed` and includes stdout/stderr.
4. If `timeout` is set, `proc.wait(timeout=N)` raises `subprocess.TimeoutExpired`; the process is killed and the job is marked `failed` with a timeout message in `stderr`.
5. If `retry_count < max_retries` after a failure (or timeout), the daemon automatically queues a new job with `retry_count + 1`.
6. Failed or stopped jobs can also be re-queued manually with `ravel retry <job_id>`; the new job records the original ID in `retried_from`.

## Data Model (SQLite)
Table: `jobs`

Key fields:
1. `id` (string): Job ID.
2. `command` (json): Command array, stored as JSON.
3. `gpus` (int): Number of GPUs requested.
4. `priority` (int): Higher runs first.
5. `memory_tag` (string): Used with `RAVEL_MEMORY_LIMITS`.
6. `status` (string): `queued`, `running`, `done`, `failed`, `blocked`, `stopped`.
7. `created_at`, `started_at`, `finished_at` (timestamps).
8. `gpus_assigned` (json): List of GPU indices assigned.
9. `returncode`, `stdout`, `stderr`.
10. `retried_from` (string): ID of the preceding job if created by `ravel retry` or auto-retry.
11. `timeout` (int, nullable): Seconds before the daemon kills the process; `NULL` means no limit.
12. `max_retries` (int, default 0): How many times the daemon will auto-requeue on failure.
13. `retry_count` (int, default 0): How many auto-retries have been attempted so far.

Table: `job_deps`
1. `job_id` (string): The dependent job.
2. `depends_on` (string): A prerequisite job ID.

## Live Log Files
While a job is running, its stdout and stderr are written in real time to `~/.ravel/logs/<job_id>.log` (both streams are merged into one file). This powers `ravel tail --follow`. After the job finishes, the full log is also stored in the `stdout` column of the `jobs` table so it is accessible even if the log file is deleted.

## GPU Scheduling
`ravel/utils.py` contains `get_free_gpus()` which uses `nvidia-smi` to find GPUs with < 20% utilization. If `RAVEL_NO_GPU=1`, it returns mock GPU availability.

## Daemon Behavior
The daemon is started with `start_new_session=True` so it is detached from the terminal. It persists until stopped with `ravel daemon stop`.

## Testing
1. Tests use a temporary SQLite database via `RAVEL_DB_PATH`.
2. `RAVEL_TEST_MODE=1` enables safe cleanup methods like `clear_jobs_for_tests()`.

## Contributing
1. Prefer small, focused changes.
2. Keep CLI output stable and human-friendly.
3. Update `README.md` and `docs/` whenever you add new features or flags.
4. Add tests for new behavior when feasible.

## Design Principles
1. Simple CLI-first UX.
2. Cross-terminal visibility with minimal dependencies.
3. Safe defaults and clear logging.
