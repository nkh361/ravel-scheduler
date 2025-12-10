from typing import List

import psutil
from rich.console import Console

console = Console()

def get_free_gpus(requested: int=1) -> list[int]:
    """
    return list of GPU indices
    :param requested: number of GPUs to request
    :return: list of GPU indices
    """
    try:
        import subprocess
        result = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index,utilization.gpu", "--format=csv,noheader,nounits"])
        free = []
        for line in result.decode().splitlines():
            idx, util = line.strip().split(",")
            if int(util) < 10:
                free.append(int(idx))
                if len(free) >= requested:
                    break
        return free[:requested]
    except:
        # no NVIDIA
        return list(range(requested))