# Sample Workflows (Data + AI Engineers)

This doc focuses on practical workflows that match day-to-day data engineering and AI engineering needs.

## Workflow 1: Data Pipeline ETL Backfill
Goal: Run multiple backfill jobs that each need a GPU or CPU slot, while tracking them from another terminal.

1. Start the daemon (once per machine):
   - `ravel daemon start`
2. Enqueue a set of backfill jobs:
   - `ravel run --no-wait "python3 scripts/backfill_users.py --date 2024-10-01"`
   - `ravel run --no-wait "python3 scripts/backfill_orders.py --date 2024-10-01"`
   - `ravel run --no-wait "python3 scripts/backfill_sessions.py --date 2024-10-01"`
3. Watch progress from another terminal:
   - `ravel dash`
4. Check queue state at any time:
   - `ravel queue`

Tips:
1. Use `--no-wait` to enqueue quickly from a deploy or tmux session.
2. Run the dashboard in a dedicated monitoring window.

## Workflow 2: Model Training + Evaluation
Goal: Kick off a long training job, then enqueue evaluation or ablation runs.

1. Train a model:
   - `ravel run --no-wait "python3 train.py --config configs/base.yaml"`
2. Enqueue eval jobs once training starts:
   - `ravel run --no-wait "python3 eval.py --checkpoint runs/base/checkpoint.pt"`
   - `ravel run --no-wait "python3 eval.py --checkpoint runs/base/checkpoint.pt --subset validation"`
3. Watch running jobs:
   - `ravel dash`

Tips:
1. Run `ravel queue` to see if eval jobs are queued while the training job is running.
2. Use separate terminals for run, monitor, and log tailing.

## Workflow 3: Feature Generation + GPU Inference
Goal: Batch-generate embeddings and feed them into downstream jobs.

1. Run GPU embedding generation:
   - `ravel run --no-wait "python3 jobs/gen_embeddings.py --input s3://bucket/dataset"`
2. While that runs, enqueue post-processing:
   - `ravel run --no-wait "python3 jobs/postprocess_embeddings.py --input s3://bucket/output"`
3. Monitor in another terminal:
   - `ravel dash`

Tips:
1. Ensure your downstream job checks for inputs and waits if needed.
2. Use `ravel queue` for a quick sanity check during long runs.

## Workflow 4: Multi-Experiment Sweep
Goal: Run a sweep without saturating GPUs.

1. Enqueue a sweep (one job per run):
   - `ravel run --no-wait "python3 sweep.py --lr 3e-4 --seed 1"`
   - `ravel run --no-wait "python3 sweep.py --lr 3e-4 --seed 2"`
   - `ravel run --no-wait "python3 sweep.py --lr 1e-4 --seed 1"`
2. Monitor the pipeline:
   - `ravel dash`

Tips:
1. Ravel will only start a job when enough GPUs are available.
2. Keep `ravel queue` open when tuning sweep size.
