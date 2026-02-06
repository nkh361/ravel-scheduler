# ravel
GPU scheduler with a shared, cross-terminal job queue and daemon.

## Install
1. Create and activate a virtual environment (recommended):
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install in editable mode:
   - `pip install -e .`

## Usage
1. Run a job (auto-starts the daemon if needed):
   - `ravel run "python3 path/to/script.py"`
   - `ravel run --no-wait "python3 path/to/script.py"` (enqueue and exit immediately)
   - `ravel run --priority 10 "python3 path/to/script.py"` (higher runs first)
   - `ravel run --after <job_id> "python3 path/to/script.py"` (DAG dependency)
   - `ravel run --memory-tag large "python3 path/to/script.py"` (resource tag)
2. List queued/running jobs:
   - `ravel queue`
3. Watch jobs live from any terminal:
   - `ravel dash`
4. Manage the daemon:
   - `ravel daemon status`
   - `ravel daemon stop`

## Example
1. Start a long-running job from one terminal:
   - `ravel run "python3 examples/train.py"`
2. Watch it from another terminal:
   - `ravel dash`
3. Check the queue:
   - `ravel queue`

## Notes
- State and logs live in `~/.ravel` by default.
- Override with `RAVEL_STATE_DIR` or `RAVEL_DB_PATH` if needed.
- Set `RAVEL_MAX_WORKERS` to control concurrency.
- Set `RAVEL_MEMORY_LIMITS` like `large=1,medium=2` to limit tags.
