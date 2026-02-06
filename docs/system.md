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
   - Executes the command and stores results.
3. The job finishes with `done` or `failed` and includes stdout/stderr.

## Data Model (SQLite)
Table: `jobs`

Key fields:
1. `id` (string): Job ID.
2. `command` (json): Command array, stored as JSON.
3. `gpus` (int): Number of GPUs requested.
4. `priority` (int): Higher runs first.
5. `memory_tag` (string): Used with `RAVEL_MEMORY_LIMITS`.
6. `status` (string): `queued`, `running`, `done`, `failed`, `blocked`.
7. `created_at`, `started_at`, `finished_at` (timestamps).
8. `gpus_assigned` (json): List of GPU indices assigned.
9. `returncode`, `stdout`, `stderr`.

Table: `job_deps`
1. `job_id` (string): The dependent job.
2. `depends_on` (string): A prerequisite job ID.

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
