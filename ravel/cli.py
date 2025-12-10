import click
from .scheduler import add_job, list_jobs

@click.group()
def main():
    pass

@main.command()
@click.argument("command", nargs=1, required=True)
@click.option("--gpus", "-g", default=1, help="Number of GPUs")
def run(command: tuple[str], gpus: int):
    """Run a command"""
    cmd_str = " ".join(command)
    add_job(cmd_str, gpus=gpus)

@main.command()
def queue():
    """List the queued jobs"""
    list_jobs()

@main.command()
def version():
    from . import __version__
    click.echo(f"ravel-scheduler {__version__}")

if __name__ == "__main__":
    main()