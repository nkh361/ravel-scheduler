import subprocess
from ravel.daemon import run_once
from ravel.store import add_job, clear_jobs_for_tests, get_job

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
    run_once()

    assert len(calls) == 1
    assert "echo" in calls[0]
    job = get_job(job_id)
    assert job["status"] == "done"
