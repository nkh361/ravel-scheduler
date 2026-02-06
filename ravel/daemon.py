import os
import signal
import subprocess
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Optional

from .store import (
    db_path,
    get_job,
    list_jobs,
    list_ready_jobs,
    mark_blocked_jobs_due_to_failed_deps,
    set_job_finished,
    try_claim_job,
)
from .utils import console, get_free_gpus


def _state_dir() -> str:
    return os.environ.get(
        "RAVEL_STATE_DIR",
        os.path.join(os.path.expanduser("~"), ".ravel"),
    )

def _pid_path() -> str:
    return os.path.join(_state_dir(), "daemon.pid")

def _log_path() -> str:
    return os.path.join(_state_dir(), "daemon.log")

def daemon_running() -> bool:
    pid = _read_pid()
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        _clear_pid()
        return False

def start_daemon() -> None:
    os.makedirs(_state_dir(), exist_ok=True)
    if daemon_running():
        console.print("[yellow]Daemon already running[/]")
        return
    log = open(_log_path(), "a", buffering=1)
    proc = subprocess.Popen(
        [sys.executable, "-m", "ravel.daemon"],
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    _write_pid(proc.pid)
    console.print(f"[green]Daemon started[/] (pid {proc.pid})")

def stop_daemon() -> None:
    pid = _read_pid()
    if not pid:
        console.print("[yellow]Daemon not running[/]")
        return
    try:
        os.kill(pid, signal.SIGTERM)
        console.print("[green]Daemon stopped[/]")
    except OSError:
        console.print("[yellow]Daemon already stopped[/]")
    _clear_pid()

def daemon_status() -> str:
    if daemon_running():
        return "running"
    return "stopped"

def run_daemon_forever(poll_interval: float = 1.0) -> None:
    _ensure_stdio()
    console.print(f"[dim]ravel daemon using db at {db_path()}[/]")
    max_workers = _get_max_workers()
    executor = ThreadPoolExecutor(max_workers=max_workers)
    active: set[Future] = set()
    while True:
        active = {f for f in active if not f.done()}
        did_work = run_once(executor=executor, active_futures=active)
        if not did_work:
            time.sleep(poll_interval)

def run_once(
    executor: Optional[ThreadPoolExecutor] = None,
    active_futures: Optional[set[Future]] = None,
    inline: bool = False,
) -> bool:
    max_workers = _get_max_workers()
    active_futures = active_futures or set()
    if executor is None and not inline:
        executor = ThreadPoolExecutor(max_workers=max_workers)

    mark_blocked_jobs_due_to_failed_deps()

    did_work = False
    running = list_jobs(["running"])
    running_count = len(running)
    slots = max(0, max_workers - running_count - len(active_futures))
    if slots <= 0:
        return False

    memory_limits = _parse_memory_limits(os.getenv("RAVEL_MEMORY_LIMITS", ""))
    running_by_tag = _count_running_by_memory_tag(running)
    reserved_gpus = _reserved_gpus(running)

    for job in list_ready_jobs(limit=slots * 2 or 1):
        if slots <= 0:
            break
        if not _memory_tag_available(job.get("memory_tag"), memory_limits, running_by_tag):
            continue
        free = get_free_gpus(job["gpus"], reserved=reserved_gpus)
        if len(free) < job["gpus"]:
            continue
        if not try_claim_job(job["id"], free):
            continue

        reserved_gpus.update(free)
        if job.get("memory_tag"):
            running_by_tag[job["memory_tag"]] = running_by_tag.get(job["memory_tag"], 0) + 1

        if executor and not inline:
            future = executor.submit(_run_job, job_id=job["id"], gpus_assigned=free)
            active_futures.add(future)
        else:
            _run_job(job_id=job["id"], gpus_assigned=free)
        did_work = True
        slots -= 1

    return did_work

def _run_job(job_id: str, gpus_assigned: list[int]) -> None:
    job = get_job(job_id)
    if not job:
        return

    env = os.environ.copy()
    env["NVIDIA_VISIBLE_DEVICES"] = ",".join(map(str, gpus_assigned))

    try:
        result = subprocess.run(
            job["command"],
            shell=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            cwd=job.get("cwd") or None,
            env=env,
        )
        status = "done" if result.returncode == 0 else "failed"
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        returncode: Optional[int] = result.returncode
    except Exception as exc:
        status = "failed"
        stdout = ""
        stderr = str(exc)
        returncode = None

    set_job_finished(
        job_id=job_id,
        status=status,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )

def _ensure_stdio() -> None:
    for fd, mode in ((0, os.O_RDONLY), (1, os.O_WRONLY), (2, os.O_WRONLY)):
        try:
            os.fstat(fd)
        except OSError:
            devnull = os.open(os.devnull, mode)
            os.dup2(devnull, fd)
            os.close(devnull)

def _get_max_workers() -> int:
    try:
        value = int(os.getenv("RAVEL_MAX_WORKERS", "1"))
        return max(1, value)
    except ValueError:
        return 1

def _parse_memory_limits(value: str) -> dict[str, int]:
    limits: dict[str, int] = {}
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            continue
        key, raw = part.split("=", 1)
        key = key.strip()
        try:
            limits[key] = int(raw.strip())
        except ValueError:
            continue
    return limits

def _count_running_by_memory_tag(running: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for job in running:
        tag = job.get("memory_tag")
        if not tag:
            continue
        counts[tag] = counts.get(tag, 0) + 1
    return counts

def _memory_tag_available(
    tag: Optional[str],
    limits: dict[str, int],
    counts: dict[str, int],
) -> bool:
    if not tag:
        return True
    if tag not in limits:
        return True
    return counts.get(tag, 0) < limits[tag]

def _reserved_gpus(running: list[dict]) -> set[int]:
    reserved: set[int] = set()
    for job in running:
        for gpu in job.get("gpus_assigned", []):
            reserved.add(gpu)
    return reserved

def _write_pid(pid: int) -> None:
    with open(_pid_path(), "w") as handle:
        handle.write(str(pid))

def _read_pid() -> Optional[int]:
    try:
        with open(_pid_path(), "r") as handle:
            data = handle.read().strip()
            return int(data) if data else None
    except FileNotFoundError:
        return None
    except ValueError:
        return None

def _clear_pid() -> None:
    try:
        os.remove(_pid_path())
    except FileNotFoundError:
        pass

def main() -> None:
    run_daemon_forever()

if __name__ == "__main__":
    main()
