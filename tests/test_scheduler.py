import subprocess

from click.testing import CliRunner

from ravel.cli import _collect_submit_jobs, _parse_submit_line
from ravel.cli import main as cli_main
from ravel.daemon import run_once
from ravel.store import (
    add_job,
    clear_jobs_for_tests,
    get_job,
    get_job_deps,
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

    class FakeProc:
        def __init__(self, cmd):
            self.pid = 12345
            self._cmd = cmd
            self.returncode = 0

        def communicate(self):
            calls.append(self._cmd)
            return "", ""

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: FakeProc(cmd))

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

    class FakeProc:
        def __init__(self, cmd):
            self.pid = 12345
            self._cmd = cmd
            self.returncode = 0

        def communicate(self):
            calls.append(self._cmd)
            return "", ""

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: FakeProc(cmd))

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

    class FakeProc:
        def __init__(self, cmd):
            self.pid = 12345
            self._cmd = cmd
            self.returncode = 0

        def communicate(self):
            calls.append(self._cmd)
            return "", ""

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: FakeProc(cmd))

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

    class FakeProc:
        def __init__(self, cmd):
            self.pid = 12345
            self._cmd = cmd
            self.returncode = 0

        def communicate(self):
            calls.append(self._cmd)
            return "", ""

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: FakeProc(cmd))

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


def _make_fake_proc_factory(calls):
    class FakeProc:
        def __init__(self, cmd):
            self.pid = 12345
            self._cmd = cmd
            self.returncode = 0

        def communicate(self):
            calls.append(self._cmd)
            return "", ""

    return lambda cmd, **kwargs: FakeProc(cmd)


def test_retry_failed_job_queues_new_job(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))
    monkeypatch.setattr("ravel.cli.daemon_running", lambda: True)

    clear_jobs_for_tests()

    job_id = add_job(["echo", "hello"], gpus=2, priority=5, memory_tag="large")
    set_job_finished(job_id, "failed", 1, "", "error")

    result = CliRunner().invoke(cli_main, ["retry", job_id, "--no-wait"])

    assert result.exit_code == 0
    new_jobs = [j for j in list_jobs() if j["id"] != job_id]
    assert len(new_jobs) == 1
    new = new_jobs[0]
    assert new["status"] == "queued"
    assert new["command"] == ["echo", "hello"]
    assert new["gpus"] == 2
    assert new["priority"] == 5
    assert new["memory_tag"] == "large"
    assert new["retried_from"] == job_id


def test_retry_stopped_job_queues_new_job(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))
    monkeypatch.setattr("ravel.cli.daemon_running", lambda: True)

    clear_jobs_for_tests()

    job_id = add_job(["echo", "stopped"], gpus=1)
    set_job_finished(job_id, "stopped", -1, "", "terminated")

    result = CliRunner().invoke(cli_main, ["retry", job_id, "--no-wait"])

    assert result.exit_code == 0
    new_jobs = [j for j in list_jobs() if j["id"] != job_id]
    assert len(new_jobs) == 1
    assert new_jobs[0]["status"] == "queued"
    assert new_jobs[0]["retried_from"] == job_id


def test_retry_non_retryable_status_does_not_create_job(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))
    monkeypatch.setattr("ravel.cli.daemon_running", lambda: True)

    clear_jobs_for_tests()

    for status, finish_args in [
        ("queued", None),
        ("done", (0, "ok", "")),
    ]:
        clear_jobs_for_tests()
        job_id = add_job(["echo", "x"], gpus=1)
        if finish_args is not None:
            rc, stdout, stderr = finish_args
            set_job_finished(job_id, status, rc, stdout, stderr)

        result = CliRunner().invoke(cli_main, ["retry", job_id, "--no-wait"])

        assert result.exit_code == 0
        assert len(list_jobs()) == 1, f"Expected no new job for status={status}"


def test_retry_nonexistent_job(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))

    clear_jobs_for_tests()

    result = CliRunner().invoke(cli_main, ["retry", "deadbeef", "--no-wait"])

    assert result.exit_code == 0
    assert list_jobs() == []


def test_retry_preserves_dependencies(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))
    monkeypatch.setattr("ravel.cli.daemon_running", lambda: True)

    clear_jobs_for_tests()

    dep_id = add_job(["echo", "dep"], gpus=1)
    job_id = add_job(["echo", "main"], gpus=1, depends_on=[dep_id])
    set_job_finished(job_id, "failed", 1, "", "error")

    result = CliRunner().invoke(cli_main, ["retry", job_id, "--no-wait"])

    assert result.exit_code == 0
    new_jobs = [j for j in list_jobs() if j["id"] not in {job_id, dep_id}]
    assert len(new_jobs) == 1
    assert dep_id in get_job_deps(new_jobs[0]["id"])


def test_retry_job_executes_and_succeeds(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVEL_NO_GPU", "1")
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")
    monkeypatch.setenv("RAVEL_DB_PATH", str(tmp_path / "ravel.db"))
    monkeypatch.setattr("ravel.cli.daemon_running", lambda: True)

    clear_jobs_for_tests()

    calls = []
    monkeypatch.setattr(subprocess, "Popen", _make_fake_proc_factory(calls))

    job_id = add_job(["echo", "retry-me"], gpus=1)
    set_job_finished(job_id, "failed", 1, "", "simulated failure")

    result = CliRunner().invoke(cli_main, ["retry", job_id, "--no-wait"])
    assert result.exit_code == 0

    run_once(inline=True)

    new_jobs = [j for j in list_jobs() if j["id"] != job_id]
    assert len(new_jobs) == 1
    new = new_jobs[0]
    assert new["status"] == "done"
    assert new["retried_from"] == job_id
    assert calls == [["echo", "retry-me"]]
