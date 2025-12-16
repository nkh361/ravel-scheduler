import shlex

import click
import time
import os
from .scheduler import add_job, list_jobs, running, queue as job_queue
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

    add_job(cmd_list, gpus=gpus)

    if dash:
        from .dashboard import dashboard
        dashboard()

    my_job_id = job_queue[-1]["id"] if job_queue else None

    while my_job_id:
        if any(j["id"] == my_job_id for j in job_queue):
            time.sleep(0.3)
        elif my_job_id in running:
            time.sleep(0.3)
        else:
            break

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

if __name__ == "__main__":
    main()