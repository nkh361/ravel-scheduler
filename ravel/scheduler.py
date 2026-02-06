from typing import List, Optional

from .store import add_job as _add_job, list_jobs as _list_jobs
from .utils import console

DASHBOARD_MODE = False

def _format_command(command: List[str]) -> str:
    return " ".join(command)


def add_job(
    command: List[str],
    gpus: int = 1,
    priority: int = 0,
    depends_on: Optional[List[str]] = None,
    memory_tag: Optional[str] = None,
    cwd: Optional[str] = None,
) -> str:
    job_id = _add_job(
        command,
        gpus=gpus,
        priority=priority,
        depends_on=depends_on,
        memory_tag=memory_tag,
        cwd=cwd,
    )
    if not DASHBOARD_MODE:
        console.print(
            f"[green]Job {job_id} queued:[/] {_format_command(command)} (GPUs: {gpus})"
        )
    return job_id

def list_jobs():
    queued = _list_jobs(["queued"])
    running = _list_jobs(["running"])
    if not queued and not running:
        console.print("[yellow]No jobs queued![/]")
        return
    for job in queued:
        console.print(
            f"[blue]QUEUED[/] {job['id']} :: {_format_command(job['command'])}"
        )
    for job in running:
        console.print(
            f"[bold green]RUNNING[/] {job['id']} :: {_format_command(job['command'])}"
        )
