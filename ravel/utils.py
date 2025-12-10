from typing import List

import shutil, os
from rich.console import Console

console = Console()

def get_free_gpus(requested: int = 1) -> list[int]:
    if os.getenv("RAVEL_NO_GPU") == "1":
        return list(range(requested))

    if shutil.which("nvidia-smi"):
        try:
            import subprocess
            result = subprocess.check_output([
                "nvidia-smi",
                "--query-gpu=index,utilization.gpu",
                "--format=csv,noheader,nounits"
            ], stderr=subprocess.DEVNULL)

            lines = result.decode().strip().splitlines()
            free = []
            for line in lines:
                if not line.strip():
                    continue
                idx, util = line.strip().split(",", 1)
                if int(util.strip()) < 20:
                    free.append(int(idx))
                    if len(free) >= requested:
                        return free
            if free:
                return free[:requested]
        except Exception:
            pass

    console.print("[dim]No NVIDIA → pretending GPUs are available[/]")
    return list(range(requested))