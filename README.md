# ravel
Fast, local GPU scheduler with a shared, cross-terminal job queue and daemon.

## Install
1. Create and activate a virtual environment (recommended):
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install in editable mode:
   - `pip install -e .`

## Build
1. macOS / Linux:
   - `./build.sh`
2. Windows (PowerShell):
   - `powershell -ExecutionPolicy Bypass -File build.ps1`
3. Cross-platform (Python):
   - `python build_helper.py`
4. To install dependencies during build:
   - `RAVEL_BUILD_DEPS=1 ./build.sh`

## Web UI Tutorial (Flask)
1. Start the daemon (if it is not running):
   - `ravel daemon start`
2. Launch the web UI:
   - `ravel web --host 127.0.0.1 --port 8000`
3. Open your browser:
   - `http://127.0.0.1:8000`

## Ravelfile Tutorial
1. Create a `Ravelfile` in your project root:
   ```text
   # Example Ravelfile
   # JOB <command>
   # SET PRIORITY <value>
   # SET GPUS <value>
   # SET MEMORY <value>

   SET GPUS 1
   SET PRIORITY 5

   JOB name=extract -- python3 examples/feature_pipeline.py --rows 5000 --dim 64 --sleep 0.1
   JOB name=features after=extract -- python3 examples/feature_pipeline.py --rows 12000 --dim 128 --sleep 0.05

   SET PRIORITY 10
   SET MEMORY large
   JOB name=train after=features -- python3 examples/feature_pipeline.py --rows 20000 --dim 256 --sleep 0.0
   ```
2. Validate it:
   - `ravel validate Ravelfile`
3. Submit it:
   - `ravel submit Ravelfile --no-wait`

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
   - Stays open until you exit (Ctrl+D or Ctrl+C)
   - Uses a full-screen terminal view (like vim)
4. Start the web UI:
   - `ravel web --host 127.0.0.1 --port 8000`
5. Show recent job summaries:
   - `ravel logs --limit 10`
   - `ravel logs --failed`
   - `ravel logs --passed`
   - `ravel logs --status queued,running,blocked`
6. Clear jobs:
   - `ravel clear` (clears queued jobs)
   - `ravel clear --all` (clears all jobs)
7. Stop a running job:
   - `ravel stop <job_id>`
8. Retry a job:
   - `ravel retry <job_id>`
9. Manage the daemon:
   - `ravel daemon status`
   - `ravel daemon status --verbose`
   - `ravel daemon stop`
10. Submit a batch file:
   - `ravel submit Ravelfile --no-wait`
   - `ravel submit jobs.txt --no-wait`
   - Optional metadata: `JOB name=... priority=... gpus=... memory=... after=... -- <command>`
   - Relative paths resolve from the directory containing the batch file.
   - Heredocs are supported.
   - On Windows (PowerShell), commands run via `powershell -NoProfile -Command`.
11. Validate a Ravelfile/jobs file:
   - `ravel validate Ravelfile`

## Example
1. Start a long-running job from one terminal:
   - `ravel run "python3 examples/train.py"`
2. Watch it from another terminal:
   - `ravel dash`
3. Check the queue:
   - `ravel queue`
4. Submit a batch file:
   - `ravel submit examples/jobs.txt --no-wait`

## Notes
- State and logs live in `~/.ravel` by default.
- Override with `RAVEL_STATE_DIR` or `RAVEL_DB_PATH` if needed.
- Set `RAVEL_MAX_WORKERS` to control concurrency.
- Set `RAVEL_MEMORY_LIMITS` like `large=1,medium=2` to limit tags.
