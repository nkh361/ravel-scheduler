import subprocess

from ravel.cli import _collect_submit_jobs, _parse_submit_line
from ravel.daemon import run_once
from ravel.store import (
    add_job,
    clear_jobs_for_tests,
    get_job,
    list_jobs,
    list_recent_jobs,
    mark_blocked_jobs_due_to_failed_deps,
    set_job_finished,
)

def test_job_gets_executed(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_NO_GPU", "1")
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))

    clear_jobs_for_tests()

    calls = []
    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return type(
            "Obj",
            (),
            {"returncode": 0, "stdout": "", "stderr": ""},
        )()

    monkeypatch.setattr(subprocess, "run", fake_run)

    job_id = add_job(["echo", "hello", "ravel"], gpus=1)
    run_once(inline=True)

    assert len(calls) == 1
    assert "echo" in calls[0]
    job = get_job(job_id)
    assert job["status"] == "done"


def test_priority_fifo_order(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_NO_GPU", "1")
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))
    monkeypatch.setenv("RAVEL_MAX_WORKERS", "1")

    clear_jobs_for_tests()

    calls = []
    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return type(
            "Obj",
            (),
            {"returncode": 0, "stdout": "", "stderr": ""},
        )()

    monkeypatch.setattr(subprocess, "run", fake_run)

    job_low = add_job(["echo", "low"], gpus=1, priority=0)
    job_high_a = add_job(["echo", "high-a"], gpus=1, priority=10)
    job_high_b = add_job(["echo", "high-b"], gpus=1, priority=10)

    run_once(inline=True)
    run_once(inline=True)
    run_once(inline=True)

    assert calls[0] == ["echo", "high-a"]
    assert calls[1] == ["echo", "high-b"]
    assert calls[2] == ["echo", "low"]

    assert get_job(job_low)["status"] == "done"
    assert get_job(job_high_a)["status"] == "done"
    assert get_job(job_high_b)["status"] == "done"


def test_dag_dependency(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_NO_GPU", "1")
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))
    monkeypatch.setenv("RAVEL_MAX_WORKERS", "1")

    clear_jobs_for_tests()

    calls = []
    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return type(
            "Obj",
            (),
            {"returncode": 0, "stdout": "", "stderr": ""},
        )()

    monkeypatch.setattr(subprocess, "run", fake_run)

    job_a = add_job(["echo", "a"], gpus=1)
    job_b = add_job(["echo", "b"], gpus=1, depends_on=[job_a])

    run_once(inline=True)
    run_once(inline=True)

    assert calls[0] == ["echo", "a"]
    assert calls[1] == ["echo", "b"]
    assert get_job(job_b)["status"] == "done"


def test_memory_tag_limits(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_NO_GPU", "1")
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))
    monkeypatch.setenv("RAVEL_MAX_WORKERS", "2")
    monkeypatch.setenv("RAVEL_MEMORY_LIMITS", "large=1")

    clear_jobs_for_tests()

    calls = []
    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return type(
            "Obj",
            (),
            {"returncode": 0, "stdout": "", "stderr": ""},
        )()

    monkeypatch.setattr(subprocess, "run", fake_run)

    job_a = add_job(["echo", "large-a"], gpus=1, memory_tag="large")
    job_b = add_job(["echo", "large-b"], gpus=1, memory_tag="large")

    run_once(inline=True)
    running = list_jobs(["running"])
    assert len(running) == 0

    run_once(inline=True)
    assert get_job(job_a)["status"] == "done"
    assert get_job(job_b)["status"] == "done"


def test_blocked_dependency(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_NO_GPU", "1")
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))

    clear_jobs_for_tests()

    job_a = add_job(["echo", "a"], gpus=1)
    job_b = add_job(["echo", "b"], gpus=1, depends_on=[job_a])

    set_job_finished(job_a, "failed", 1, "", "boom")
    mark_blocked_jobs_due_to_failed_deps()

    assert get_job(job_b)["status"] == "blocked"


def test_recent_jobs_filter(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_NO_GPU", "1")
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))

    clear_jobs_for_tests()

    job_a = add_job(["echo", "a"], gpus=1)
    job_b = add_job(["echo", "b"], gpus=1)
    set_job_finished(job_a, "done", 0, "", "")
    set_job_finished(job_b, "failed", 2, "", "fail")

    failed_jobs = list_recent_jobs(10, statuses=["failed"])
    done_jobs = list_recent_jobs(10, statuses=["done"])

    assert len(failed_jobs) == 1
    assert failed_jobs[0]["id"] == job_b
    assert len(done_jobs) == 1
    assert done_jobs[0]["id"] == job_a


def test_ravelfile_parsing_defaults_and_heredoc():
    defaults = {"gpus": 1, "priority": 0, "memory_tag": None}
    lines = [
        "SET GPUS 2",
        "SET PRIORITY 7",
        "JOB name=prep after=seed -- echo prep",
        "JOB python3 - <<'PY'",
        "print('hello')",
        "PY",
    ]
    jobs = _collect_submit_jobs(lines, defaults)
    assert defaults["gpus"] == 2
    assert defaults["priority"] == 7
    assert len(jobs) == 2

    parsed = _parse_submit_line(jobs[0], defaults["gpus"], defaults["priority"], None)
    assert parsed["name"] == "prep"
    assert parsed["after"] == ["seed"]
