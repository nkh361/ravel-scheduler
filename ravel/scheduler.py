import os
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, List

from .utils import console, get_free_gpus

DASHBOARD_MODE = False
_worker_started = False

queue: List[Dict] = []
running: Dict[str, Dict] = {}

def add_job(command: str, gpus: int = 1):
    global _worker_started

    job = {
        "id": str(uuid.uuid4())[:8],
        "command": command,
        "gpus": gpus,
        "status": "queued",
        "created": datetime.now().isoformat(timespec="minutes")
    }
    queue.append(job)
    if not DASHBOARD_MODE:
        console.print(f"[green]Job {job['id']} queued:[/] {command} (GPUs: {gpus})")

    if os.getenv("RAVEL_TEST_MODE") != "1" and not _worker_started:
        _worker_started = True
        threading.Thread(target=_worker, daemon=True).start()

def list_jobs():
    if not queue and not running:
        console.print("[yellow]No jobs queued![/]")
        return
    for job in queue:
        console.print(f"[blue]QUEUED[/] {job['id']} :: {job['command']}")
    for job in running.values():
        console.print(f"[bold green]RUNNING[/] {job['id']} :: {job['command']}")

# def _run_one_job(job: Dict):
#     """Shared logic for real worker and test worker"""
#     free = job["gpus_assigned"]
#     env = os.environ.copy()
#     env["NVIDIA_VISIBLE_DEVICES"] = ",".join(map(str, job.get("gpus_assigned", [])))
#
#     console.print(f"[bold magenta]Starting[/] {job['id']} → GPUs {free}")
#
#     import subprocess
#     try:
#         result = subprocess.run(
#             job["command"],
#             shell=False,
#             capture_output=True,
#             text=True,
#             env=env
#         )
#
#         if result.stdout:
#             console.print(result.stdout.strip())
#         if result.stderr:
#             console.print(f"[red]{result.stderr.strip()}[/]")
#
#         status = "done" if result.returncode == 0 else "failed"
#
#     except Exception as e:
#         console.print(f"[red]Crash:[/] {e}")
#         status = "failed"
#
#     console.print(f"[bold green]Finished[/] {job['id']} — {status}")
#     running.pop(job["id"], None)

def _run_one_job(job: Dict):
    free = job["gpus_assigned"]
    env = os.environ.copy()
    env["NVIDIA_VISIBLE_DEVICES"] = ",".join(map(str, free))

    if not DASHBOARD_MODE:
        console.print(f"[bold magenta]Starting[/] {job['id']} → GPUs {free}")

    import subprocess
    try:
        result = subprocess.run(
            job["command"],
            shell=False,
            capture_output=True,
            text=True,
            env=env
        )

        status = "done" if result.returncode == 0 else "failed"

    except Exception as e:
        result = None
        status = "failed"
        if not DASHBOARD_MODE:
            console.print(f"[red]Crash:[/] {e}")

    if not DASHBOARD_MODE:
        if result:
            if result.stdout:
                console.print(result.stdout.strip())
            if result.stderr:
                console.print(f"[red]{result.stderr.strip()}[/]")
        console.print(f"[bold green]Finished[/] {job['id']} — {status}")

    running.pop(job["id"], None)


def _worker():
    while True:
        if not queue:
            time.sleep(2)
            continue
        job = queue[0]
        free = get_free_gpus(job["gpus"])
        if len(free) < job["gpus"]:
            time.sleep(5)
            continue

        job = queue.pop(0)
        job["status"] = "running"
        job["gpus_assigned"] = free
        running[job["id"]] = job
        _run_one_job(job)

def _worker_once():
    """Run exactly one iteration — only used in tests"""
    if not queue:
        return
    job = queue[0]
    free = get_free_gpus(job["gpus"])
    if len(free) < job["gpus"]:
        return

    job = queue.pop(0)
    job["status"] = "running"
    job["gpus_assigned"] = free
    running[job["id"]] = job
    _run_one_job(job)