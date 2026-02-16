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
@click.option("--queued", "only_queued", is_flag=True, help="Clear only queued jobs")
@click.option("--all", "all_jobs", is_flag=True, help="Clear all jobs (dangerous)")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
def clear(only_queued: bool, all_jobs: bool, yes: bool):
    """Clear queued jobs or all jobs"""
    from .store import clear_jobs

    if all_jobs and only_queued:
        console.print("[red]Choose only one of --all or --queued[/]")
        return

    if all_jobs:
        if not yes and not click.confirm("Clear ALL jobs? This cannot be undone."):
            return
        deleted = clear_jobs()
        console.print(f"[yellow]Cleared {deleted} jobs.[/]")
        return

    deleted = clear_jobs(["queued"])
    console.print(f"[green]Cleared {deleted} queued jobs.[/]")

@main.command()
@click.argument("job_id")
def stop(job_id: str):
    """Stop a running job by ID"""
    from .store import get_job, set_job_finished
    import psutil

    job = get_job(job_id)
    if not job:
        console.print("[red]Job not found.[/]")
        return
    if job["status"] != "running":
        console.print(f"[yellow]Job {job_id} is not running (status={job['status']}).[/]")
        return
    pid = job.get("pid")
    if not pid:
        console.print(f"[red]Job {job_id} has no PID recorded.[/]")
        return
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=10)
        set_job_finished(job_id, "stopped", -1, "", "terminated by user")
        console.print(f"[yellow]Stopped {job_id}.[/]")
    except psutil.NoSuchProcess:
        set_job_finished(job_id, "stopped", -1, "", "process not found")
        console.print(f"[yellow]Process for {job_id} not found. Marked stopped.[/]")
    except psutil.TimeoutExpired:
        proc.kill()
        set_job_finished(job_id, "stopped", -1, "", "killed by user")
        console.print(f"[yellow]Killed {job_id}.[/]")
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

    defaults = {
        "gpus": gpus,
        "priority": priority,
        "memory_tag": memory_tag,
    }

    jobs = _collect_submit_jobs(lines, defaults)

    if not jobs:
        console.print("[yellow]No jobs found in file.[/]")
        return

    if not daemon_running():
        start_daemon()

    parsed_jobs = [
        _parse_submit_line(raw, defaults["gpus"], defaults["priority"], defaults["memory_tag"])
        for raw in jobs
    ]

    job_ids = []
    name_to_id: dict[str, str] = {}
    submit_cwd = os.path.abspath(os.path.dirname(file))
    for entry in parsed_jobs:
        cmd_list = _shell_command(entry["command"])
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

@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
def validate(file: str):
    """Validate a Ravelfile or jobs file"""
    with open(file, "r") as handle:
        lines = handle.read().splitlines()

    defaults = {"gpus": 1, "priority": 0, "memory_tag": None}
    errors = []
    jobs = _collect_submit_jobs(lines, defaults, errors=errors)

    parsed = []
    for idx, raw in enumerate(jobs, start=1):
        try:
            entry = _parse_submit_line(raw, defaults["gpus"], defaults["priority"], defaults["memory_tag"])
        except Exception as exc:
            errors.append(f"job {idx}: failed to parse metadata ({exc})")
            continue
        parsed.append(entry)

    names = {p["name"] for p in parsed if p["name"]}
    for idx, entry in enumerate(parsed, start=1):
        for dep in entry["after"]:
            if dep in names:
                continue
            if len(dep) == 8 and dep.isalnum():
                continue
            errors.append(f"job {idx}: unknown dependency '{dep}'")

    if errors:
        console.print("[red]Invalid Ravelfile/jobs file:[/]")
        for err in errors:
            console.print(f"- {err}")
        raise SystemExit(1)

    console.print("[green]Ravelfile/jobs file is valid.[/]")


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


def _shell_command(command: str) -> list[str]:
    if os.name == "nt":
        return ["powershell", "-NoProfile", "-Command", command]
    return ["/bin/bash", "-lc", command]

def _apply_ravelfile_set(line: str, defaults: dict) -> bool:
    parts = line.split(None, 2)
    if len(parts) < 3:
        return False
    key = parts[1].strip().lower()
    value = parts[2].strip()
    if key == "gpus":
        try:
            defaults["gpus"] = int(value)
        except ValueError:
            return False
    elif key == "priority":
        try:
            defaults["priority"] = int(value)
        except ValueError:
            return False
    elif key in {"memory", "mem", "memory_tag"}:
        defaults["memory_tag"] = value or None
    else:
        return False
    return True


def _collect_submit_jobs(
    lines: list[str],
    defaults: dict,
    errors: Optional[list[str]] = None,
) -> list[str]:
    jobs: list[str] = []
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

        if line.upper().startswith("SET "):
            if not _apply_ravelfile_set(line, defaults):
                if errors is not None:
                    errors.append(f"line {idx + 1}: invalid SET directive")
            idx += 1
            continue

        if line.upper().startswith("JOB "):
            line = raw[raw.upper().find("JOB") + 3 :].lstrip()

        command_lines = [line]
        heredoc_tag = _detect_heredoc_tag(line)
        if heredoc_tag:
            idx += 1
            while idx < len(lines):
                command_lines.append(lines[idx])
                if lines[idx].strip() == heredoc_tag:
                    break
                idx += 1
            if idx >= len(lines) or (lines[idx].strip() != heredoc_tag):
                if errors is not None:
                    errors.append(f"line {idx + 1}: unterminated heredoc '{heredoc_tag}'")
        jobs.append("\n".join(command_lines))
        idx += 1
    return jobs

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
@click.option("--host", default="127.0.0.1", help="Host interface")
@click.option("--port", default=8000, type=int, help="Port to serve")
def web(host: str, port: int):
    """Start the web UI"""
    from ravel_web.app import create_app
    app = create_app()
    app.run(host=host, port=port, threaded=True)

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
        cwd = job.get("cwd") or "-"
        extra = f" cwd={cwd}" if raw_status == "failed" else ""
        console.print(
            f"{job['id']} {status} rc={rc_text} "
            f"created={created} finished={finished}{extra} :: {cmd}"
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
@click.option("--verbose", "-v", is_flag=True, help="Show detailed status")
def daemon_show_status(verbose: bool):
    """Show daemon status"""
    status = daemon_status()
    console.print(f"[bold]Daemon:[/] {status}")
    if not verbose:
        return
    from .store import list_recent_jobs
    from .daemon import _read_pid
    pid = _read_pid()
    console.print(f"pid={pid if pid else '-'}")
    console.print(f"db={os.environ.get('RAVEL_DB_PATH', '') or 'default'}")
    recent = list_recent_jobs(1)
    if recent:
        job = recent[0]
        console.print(
            f"last_job={job['id']} status={job['status']} created={job.get('created_at','-')}"
        )


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
