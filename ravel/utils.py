from typing import List, Optional, Set

import shutil, os
from rich.console import Console

console = Console()

def get_free_gpus(requested: int = 1, reserved: Optional[Set[int]] = None) -> list[int]:
    reserved = reserved or set()
    if os.getenv("RAVEL_NO_GPU") == "1":
        free = []
        candidate = 0
        while len(free) < requested:
            if candidate not in reserved:
                free.append(candidate)
            candidate += 1
        return free

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
                    idx_int = int(idx)
                    if idx_int in reserved:
                        continue
                    free.append(idx_int)
                    if len(free) >= requested:
                        return free
            if free:
                return free[:requested]
        except Exception:
            pass

    console.print("[dim]No NVIDIA → pretending GPUs are available[/]")
    return list(range(requested))
