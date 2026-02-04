import os
import shlex
import time

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
@click.option("--dash", is_flag=True, help="Display the dashboard")
def run(command: tuple[str], gpus: int, dash: bool):
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

    job_id = add_job(cmd_list, gpus=gpus)

    if not daemon_running():
        start_daemon()

    if dash:
        from .dashboard import dashboard
        dashboard()

    _wait_for_job(job_id)

    console.print("[bold cyan]All done! Exiting.[/]")


@main.command()
def queue():
    """List the queued jobs"""
    list_jobs()

@main.command()
def version():
    from . import __version__
    click.echo(f"ravel-scheduler {__version__}")

@main.command()
def dash():
    """Display the dashboard"""
    from .dashboard import dashboard
    dashboard()


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
