import os
import signal
import subprocess
import sys
import time
from typing import Optional

from .store import db_path, get_job, peek_next_queued_job, set_job_finished, try_claim_job
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
    console.print(f"[dim]ravel daemon using db at {db_path()}[/]")
    while True:
        did_work = run_once()
        if not did_work:
            time.sleep(poll_interval)

def run_once() -> bool:
    job = peek_next_queued_job()
    if not job:
        return False

    free = get_free_gpus(job["gpus"])
    if len(free) < job["gpus"]:
        return False

    if not try_claim_job(job["id"], free):
        return False

    _run_job(job_id=job["id"], gpus_assigned=free)
    return True

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
            capture_output=True,
            text=True,
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
