import os
import shlex
import time
from typing import Optional

import click

from .daemon import daemon_running, daemon_status, start_daemon, stop_daemon
from .scheduler import add_job, list_jobs
from .store import get_job
from .utils import console

@click.group()
def main():
    pass

@main.command()
@click.argument("command", nargs=-1, required=True)
@click.option("--gpus", "-g", default=1, help="Number of GPUs")
@click.option("--priority", "-p", default=0, help="Higher runs first")
@click.option(
    "--after",
    multiple=True,
    help="Job ID(s) that must finish before this runs (repeatable)",
)
@click.option("--memory-tag", "--mem", default=None, help="Memory tag for limits")
@click.option("--dash", is_flag=True, help="Display the dashboard")
@click.option(
    "--no-wait",
    is_flag=True,
    help="Enqueue the job and exit without waiting",
)
def run(
    command: tuple[str],
    gpus: int,
    priority: int,
    after: tuple[str],
    memory_tag: Optional[str],
    dash: bool,
    no_wait: bool,
):
    """Run a command or .py file"""
    cmd_str = command[0]
    if dash:
        import ravel.scheduler as sched
        sched.DASHBOARD_MODE = True

    if cmd_str.endswith(".py"):
        full_path = os.path.abspath(cmd_str)
        cmd_list = ["python3", full_path]
    else:
        cmd_list = shlex.split(cmd_str)
        if len(cmd_list) >= 2 and cmd_list[1].endswith(".py"):
            if not os.path.isabs(cmd_list[1]):
                cmd_list[1] = os.path.abspath(cmd_list[1])

    depends_on = list(after) if after else None
    job_id = add_job(
        cmd_list,
        gpus=gpus,
        priority=priority,
        depends_on=depends_on,
        memory_tag=memory_tag,
        cwd=os.getcwd(),
    )

    if not daemon_running():
        start_daemon()

    if dash:
        from .dashboard import dashboard
        dashboard()

    if no_wait:
        console.print(f"[dim]Enqueued {job_id}. Exiting (no-wait).[/]")
        return

    _wait_for_job(job_id)

    console.print("[bold cyan]All done! Exiting.[/]")


@main.command()
def queue():
    """List the queued jobs"""
    list_jobs()

@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--gpus", "-g", default=1, help="Number of GPUs")
@click.option("--priority", "-p", default=0, help="Higher runs first")
@click.option("--memory-tag", "--mem", default=None, help="Memory tag for limits")
@click.option("--no-wait", is_flag=True, help="Enqueue jobs and exit immediately")
def submit(file: str, gpus: int, priority: int, memory_tag: Optional[str], no_wait: bool):
    """Submit a batch of jobs from a text file"""
    from .store import add_dependencies

    with open(file, "r") as handle:
        lines = handle.read().splitlines()

    jobs = []
    idx = 0
    while idx < len(lines):
        raw = lines[idx]
        line = raw.strip()
        if not line:
            idx += 1
            continue
        if line.startswith("#"):
            idx += 1
            continue

        command_lines = [raw]
        heredoc_tag = _detect_heredoc_tag(raw)
        if heredoc_tag:
            idx += 1
            while idx < len(lines):
                command_lines.append(lines[idx])
                if lines[idx].strip() == heredoc_tag:
                    break
                idx += 1
        jobs.append("\n".join(command_lines))
        idx += 1

    if not jobs:
        console.print("[yellow]No jobs found in file.[/]")
        return

    if not daemon_running():
        start_daemon()

    parsed_jobs = [_parse_submit_line(raw, gpus, priority, memory_tag) for raw in jobs]

    job_ids = []
    name_to_id: dict[str, str] = {}
    submit_cwd = os.path.abspath(os.path.dirname(file))
    for entry in parsed_jobs:
        cmd_list = ["/bin/bash", "-lc", entry["command"]]
        job_id = add_job(
            cmd_list,
            gpus=entry["gpus"],
            priority=entry["priority"],
            memory_tag=entry["memory_tag"],
            cwd=submit_cwd,
        )
        job_ids.append(job_id)
        if entry["name"]:
            name_to_id[entry["name"]] = job_id

    for entry, job_id in zip(parsed_jobs, job_ids):
        depends_on = []
        for dep in entry["after"]:
            depends_on.append(name_to_id.get(dep, dep))
        add_dependencies(job_id, depends_on)

    console.print(f"[green]Queued {len(job_ids)} jobs.[/]")
    if no_wait:
        return

    for job_id in job_ids:
        _wait_for_job(job_id)


def _parse_submit_line(
    raw: str,
    default_gpus: int,
    default_priority: int,
    default_memory_tag: Optional[str],
) -> dict:
    if " -- " in raw:
        meta, command = raw.split(" -- ", 1)
        meta = meta.strip()
    else:
        meta = ""
        command = raw

    gpus = default_gpus
    priority = default_priority
    memory_tag = default_memory_tag
    name = None
    after: list[str] = []

    if meta:
        parts = [p for p in meta.split() if p]
        for part in parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "gpus":
                try:
                    gpus = int(value)
                except ValueError:
                    pass
            elif key == "priority":
                try:
                    priority = int(value)
                except ValueError:
                    pass
            elif key in {"memory", "mem", "memory_tag"}:
                memory_tag = value or None
            elif key == "name":
                name = value or None
            elif key in {"after", "depends"}:
                after = [v.strip() for v in value.split(",") if v.strip()]

    return {
        "command": command,
        "gpus": gpus,
        "priority": priority,
        "memory_tag": memory_tag,
        "name": name,
        "after": after,
    }


def _detect_heredoc_tag(line: str) -> Optional[str]:
    if "<<'" in line:
        start = line.split("<<'", 1)[1]
        if "'" in start:
            return start.split("'", 1)[0]
    if "<<\"" in line:
        start = line.split("<<\"", 1)[1]
        if "\"" in start:
            return start.split("\"", 1)[0]
    if "<<" in line:
        start = line.split("<<", 1)[1].strip()
        if start:
            return start.split()[0]
    return None

@main.command()
def version():
    from . import __version__
    click.echo(f"ravel-scheduler {__version__}")

@main.command()
def dash():
    """Display the dashboard"""
    from .dashboard import dashboard
    dashboard()

@main.command()
@click.option("--limit", "-l", default=10, help="Number of recent jobs to show")
@click.option("--failed", "only_failed", is_flag=True, help="Show only failed jobs")
@click.option("--passed", "only_passed", is_flag=True, help="Show only passed jobs")
@click.option("--blocked", "only_blocked", is_flag=True, help="Show only blocked jobs")
@click.option(
    "--status",
    "status_filter",
    default=None,
    help="Filter by status: queued,running,done,failed,blocked",
)
def logs(limit: int, only_failed: bool, only_passed: bool, only_blocked:bool, status_filter: Optional[str]):
    """Show recent jobs with summaries"""
    from .store import list_recent_jobs

    if only_failed and only_passed:
        console.print("[red]Choose only one of --failed, --passed, or --blocked[/]")
        return

    if status_filter and (only_failed or only_passed):
        console.print("[red]Choose either --status or --failed/--passed/--blocked[/]")
        return

    statuses = None
    if only_failed:
        statuses = ["failed"]
    elif only_passed:
        statuses = ["done"]
    elif only_blocked:
        statuses = ["blocked"]
    elif status_filter:
        statuses = [s.strip() for s in status_filter.split(",") if s.strip()]

    limit = max(1, limit)
    jobs = list_recent_jobs(limit, statuses=statuses)
    if not jobs:
        console.print("[yellow]No jobs found.[/]")
        return

    console.print(f"[bold]Last {len(jobs)} jobs:[/]")
    for job in jobs:
        raw_status = job["status"]
        if raw_status == "done":
            status = "[bold green]done[/]"
        elif raw_status == "failed":
            status = "[bold red]failed[/]"
        elif raw_status == "blocked":
            status = "[bold yellow]blocked[/]"
        else:
            status = raw_status
        cmd = " ".join(job["command"])
        created = job.get("created_at") or "-"
        finished = job.get("finished_at") or "-"
        rc = job.get("returncode")
        rc_text = "-" if rc is None else str(rc)
        console.print(
            f"{job['id']} {status} rc={rc_text} "
            f"created={created} finished={finished} :: {cmd}"
        )


@main.group()
def daemon():
    """Manage the ravel daemon"""
    pass


@daemon.command("start")
def daemon_start():
    """Start the daemon"""
    start_daemon()


@daemon.command("stop")
def daemon_stop():
    """Stop the daemon"""
    stop_daemon()


@daemon.command("status")
def daemon_show_status():
    """Show daemon status"""
    console.print(f"[bold]Daemon:[/] {daemon_status()}")


def _wait_for_job(job_id: str) -> None:
    while True:
        job = get_job(job_id)
        if not job:
            time.sleep(0.3)
            continue
        if job["status"] in {"done", "failed"}:
            if job["stdout"]:
                console.print(job["stdout"].strip())
            if job["stderr"]:
                console.print(f"[red]{job['stderr'].strip()}[/]")
            status = job["status"]
            console.print(f"[bold green]Finished[/] {job_id} — {status}")
            return
        time.sleep(0.3)

if __name__ == "__main__":
    main()
