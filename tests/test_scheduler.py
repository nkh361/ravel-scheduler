import subprocess
import ravel.scheduler as sched
from ravel.scheduler import queue, running, add_job, _worker_once

def test_job_gets_executed(monkeypatch):
    monkeypatch.setenv("RAVEL_NO_GPU", "1")
    monkeypatch.setenv("RAVEL_TEST_MODE", "1")

    queue.clear()
    running.clear()

    calls = []
    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return type("Obj", (), {"returncode": 0})()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("ravel.scheduler.time.sleep", lambda x: None)

    add_job("echo hello ravel", gpus=1)
    _worker_once()

    assert len(calls) == 1
    assert "echo hello ravel" in calls[0]
    assert len(queue) == 0
    assert len(running) == 0
