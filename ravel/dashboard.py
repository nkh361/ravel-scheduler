import select
import sys
import time
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from .store import list_jobs

def dashboard(refresh=0.5):
    """Display the dashboard"""
    console = Console()
    try:
        with Live(
            _render_dashboard([], [], [], []),
            console=console,
            refresh_per_second=max(1, int(1 / refresh)),
            screen=True,
        ) as live:
            while True:
                if _stdin_closed():
                    break
                running = list_jobs(["running"])
                queued = list_jobs(["queued"])
                blocked = list_jobs(["blocked"])
                failed = list_jobs(["failed"])
                live.update(_render_dashboard(running, queued, blocked, failed))
                time.sleep(refresh)
    except KeyboardInterrupt:
        pass

def _stdin_closed() -> bool:
    if not sys.stdin or sys.stdin.closed:
        return True
    if not sys.stdin.isatty():
        return False
    try:
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if ready:
            data = sys.stdin.read(1)
            return data == ""
    except Exception:
        return False
    return False


def _render_dashboard(
    running: list[dict],
    queued: list[dict],
    blocked: list[dict],
    failed: list[dict],
) -> Layout:
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body"),
    )

    header_text = (
        f"running={len(running)}  "
        f"queued={len(queued)}  "
        f"blocked={len(blocked)}  "
        f"failed={len(failed)}"
    )
    layout["header"].update(Panel(header_text, title="Ravel", padding=(0, 2)))

    if not running and not queued:
        layout["body"].update(Panel("No active jobs. Waiting for new jobs..."))
        return layout

    table = Table(title="Jobs", show_lines=False)
    table.add_column("Status", no_wrap=True)
    table.add_column("ID", no_wrap=True)
    table.add_column("GPUs", no_wrap=True)
    table.add_column("Priority", no_wrap=True)
    table.add_column("Created", no_wrap=True)
    table.add_column("Command", overflow="fold")

    for job in running:
        table.add_row(
            "running",
            job["id"],
            str(job.get("gpus", "-")),
            str(job.get("priority", 0)),
            job.get("created_at", "-"),
            _truncate_command(job.get("command", [])),
        )
    for job in queued:
        table.add_row(
            "queued",
            job["id"],
            str(job.get("gpus", "-")),
            str(job.get("priority", 0)),
            job.get("created_at", "-"),
            _truncate_command(job.get("command", [])),
        )

    layout["body"].update(Panel(table))
    return layout


def _truncate_command(command: list[str], max_len: int = 80) -> str:
    text = " ".join(command)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
