import os
from typing import Optional

from flask import Flask, jsonify, render_template, request
import psutil

from ravel.daemon import daemon_running
from ravel.store import list_jobs


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/summary")
    def summary():
        statuses = ["queued", "running", "blocked", "failed", "done"]
        counts = {status: len(list_jobs([status])) for status in statuses}
        return jsonify(
            {
                "daemon": "running" if daemon_running() else "stopped",
                "counts": counts,
                "db": os.environ.get("RAVEL_DB_PATH", "") or "default",
            }
        )

    @app.get("/api/resources")
    def resources():
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=None)
        return jsonify(
            {
                "cpu_percent": cpu,
                "memory_total": mem.total,
                "memory_used": mem.used,
                "memory_percent": mem.percent,
                "gpus": _gpu_stats(),
            }
        )

    @app.get("/api/jobs")
    def jobs():
        statuses = _parse_statuses(request.args.get("status"))
        limit = int(request.args.get("limit", "50"))
        jobs = list_jobs(statuses)[:limit]
        return jsonify({"jobs": [_serialize_job(j) for j in jobs]})

    return app


def _serialize_job(job: dict) -> dict:
    return {
        "id": job["id"],
        "status": job["status"],
        "gpus": job.get("gpus"),
        "priority": job.get("priority", 0),
        "created_at": job.get("created_at"),
        "finished_at": job.get("finished_at"),
        "command": " ".join(job.get("command", [])),
    }


def _parse_statuses(value: Optional[str]) -> Optional[list[str]]:
    if not value:
        return None
    return [s for s in value.split(",") if s]


def _gpu_stats() -> list[dict]:
    if not _has_nvidia_smi():
        return []
    try:
        import subprocess

        result = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,utilization.gpu,utilization.memory,memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
        )
        lines = result.decode().strip().splitlines()
        gpus = []
        for line in lines:
            if not line.strip():
                continue
            idx, util, mem_util, mem_total, mem_used = [v.strip() for v in line.split(",")]
            gpus.append(
                {
                    "index": int(idx),
                    "util_gpu": float(util),
                    "util_mem": float(mem_util),
                    "memory_total": float(mem_total),
                    "memory_used": float(mem_used),
                }
            )
        return gpus
    except Exception:
        return []


def _has_nvidia_smi() -> bool:
    import shutil

    return shutil.which("nvidia-smi") is not None
