import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from .utils import console


def _state_dir() -> str:
    return os.environ.get(
        "RAVEL_STATE_DIR",
        os.path.join(os.path.expanduser("~"), ".ravel"),
    )


def db_path() -> str:
    return os.environ.get("RAVEL_DB_PATH", os.path.join(_state_dir(), "ravel.db"))


def _ensure_state_dir() -> None:
    os.makedirs(_state_dir(), exist_ok=True)


def _connect() -> sqlite3.Connection:
    _ensure_state_dir()
    conn = sqlite3.connect(db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    _init_db(conn)
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except sqlite3.OperationalError:
        pass


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            command TEXT NOT NULL,
            gpus INTEGER NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            memory_tag TEXT,
            cwd TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            gpus_assigned TEXT,
            returncode INTEGER,
            stdout TEXT,
            stderr TEXT
        );
        CREATE TABLE IF NOT EXISTS job_deps (
            job_id TEXT NOT NULL,
            depends_on TEXT NOT NULL
        );
        """
    )
    _ensure_column(conn, "jobs", "priority", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "jobs", "memory_tag", "TEXT")
    _ensure_column(conn, "jobs", "cwd", "TEXT")
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_jobs_status_created
            ON jobs(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_priority_created
            ON jobs(priority, created_at);
        CREATE INDEX IF NOT EXISTS idx_job_deps_job
            ON job_deps(job_id);
        CREATE INDEX IF NOT EXISTS idx_job_deps_depends
            ON job_deps(depends_on);
        """
    )

def add_job(
    command: List[str],
    gpus: int = 1,
    priority: int = 0,
    depends_on: Optional[List[str]] = None,
    memory_tag: Optional[str] = None,
    cwd: Optional[str] = None,
) -> str:
    job_id = str(uuid.uuid4())[:8]
    created_at = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, command, gpus, priority, memory_tag, cwd, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                json.dumps(command),
                gpus,
                priority,
                memory_tag,
                cwd,
                "queued",
                created_at,
            ),
        )
        if depends_on:
            conn.executemany(
                "INSERT INTO job_deps (job_id, depends_on) VALUES (?, ?)",
                [(job_id, dep) for dep in depends_on],
            )
    return job_id


def get_job(job_id: str) -> Optional[Dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def list_jobs(statuses: Optional[Iterable[str]] = None) -> List[Dict]:
    with _connect() as conn:
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            rows = conn.execute(
                f"""
                SELECT * FROM jobs
                WHERE status IN ({placeholders})
                ORDER BY created_at
                """,
                list(statuses),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at"
            ).fetchall()
    return [_row_to_job(row) for row in rows]

def list_ready_jobs(limit: Optional[int] = None) -> List[Dict]:
    with _connect() as conn:
        limit_sql = f"LIMIT {int(limit)}" if limit else ""
        rows = conn.execute(
            """
            SELECT j.*
            FROM jobs j
            WHERE j.status = 'queued'
              AND NOT EXISTS (
                SELECT 1
                FROM job_deps d
                JOIN jobs dep ON dep.id = d.depends_on
                WHERE d.job_id = j.id
                  AND dep.status != 'done'
              )
            ORDER BY j.priority DESC, j.created_at ASC, j.rowid ASC
            """
            + limit_sql
        ).fetchall()
    return [_row_to_job(row) for row in rows]


def mark_blocked_jobs_due_to_failed_deps() -> int:
    with _connect() as conn:
        result = conn.execute(
            """
            UPDATE jobs
            SET status = 'blocked'
            WHERE status = 'queued'
              AND EXISTS (
                SELECT 1
                FROM job_deps d
                JOIN jobs dep ON dep.id = d.depends_on
                WHERE d.job_id = jobs.id
                  AND dep.status IN ('failed', 'blocked')
              )
            """
        )
    return result.rowcount


def try_claim_job(job_id: str, gpus_assigned: List[int]) -> bool:
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        result = conn.execute(
            """
            UPDATE jobs
            SET status = 'running',
                started_at = ?,
                gpus_assigned = ?
            WHERE id = ? AND status = 'queued'
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                json.dumps(gpus_assigned),
                job_id,
            ),
        )
        conn.execute("COMMIT")
    return result.rowcount == 1


def set_job_assigned_gpus(job_id: str, gpus_assigned: List[int]) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE jobs SET gpus_assigned = ? WHERE id = ?",
            (json.dumps(gpus_assigned), job_id),
        )


def set_job_finished(
    job_id: str,
    status: str,
    returncode: Optional[int],
    stdout: str,
    stderr: str,
) -> None:
    finished_at = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                finished_at = ?,
                returncode = ?,
                stdout = ?,
                stderr = ?
            WHERE id = ?
            """,
            (status, finished_at, returncode, stdout, stderr, job_id),
        )


def clear_jobs_for_tests() -> None:
    if os.getenv("RAVEL_TEST_MODE") != "1":
        console.print("[red]Refusing to clear jobs outside test mode[/]")
        return
    with _connect() as conn:
        conn.execute("DELETE FROM job_deps")
        conn.execute("DELETE FROM jobs")


def _row_to_job(row: sqlite3.Row) -> Dict:
    job = dict(row)
    job["command"] = json.loads(job["command"])
    job["gpus_assigned"] = (
        json.loads(job["gpus_assigned"]) if job["gpus_assigned"] else []
    )
    return job
