import subprocess

from ravel.daemon import run_once
from ravel.store import add_job, clear_jobs_for_tests, get_job, list_jobs

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
